"""CLI and shared A2A plumbing for the two agent scripts."""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from time import perf_counter

import httpx
import uvicorn
from a2a.client import ClientConfig, create_client
from a2a.helpers import (
    get_artifact_text, get_message_text, new_task_from_user_message,
    new_text_message, new_text_part,
)
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities, AgentCard, AgentInterface, AgentSkill,
    Role, SendMessageRequest, TaskState,
)
from dotenv import load_dotenv
from starlette.applications import Starlette

load_dotenv(Path(__file__).with_name(".env"))
logger = logging.getLogger("devdesk.a2a")


def setup_logging(component: str) -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Our logs explain the flow without dumping SDK payloads or HTTP headers.
    for name in ("httpx", "httpx2", "httpcore", "a2a"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger(f"devdesk.{component}").info(
        "Starting %s | .env=%s | existing environment variables take precedence",
        component, Path(__file__).with_name(".env"),
    )


async def ask_remote_agent(url: str, prompt: str) -> str:
    """Discover an Agent Card, send a message, and read its answer."""
    started = perf_counter()
    logger.info("Discovering remote Agent Card at %s (connect timeout=5s, response timeout=300s)", url)
    # Model responses can take longer than HTTPX's five-second default.
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as http_client:
        client = await create_client(
            agent=url,
            client_config=ClientConfig(streaming=False, httpx_client=http_client)
        )
        try:
            logger.info("Agent Card discovered at %s; sending A2A message (%d characters)", url, len(prompt))
            request = SendMessageRequest(
                message=new_text_message(prompt, role=Role.ROLE_USER)
            )
            async for response in client.send_message(request):
                if response.HasField("message"):
                    logger.info("Received direct A2A message from %s after %.2fs", url, perf_counter() - started)
                    return get_message_text(response.message)
                if response.HasField("task"):
                    task = response.task
                    logger.info(
                        "Received task=%s from %s | state=%s | artifacts=%d | elapsed=%.2fs",
                        task.id, url, TaskState.Name(task.status.state),
                        len(task.artifacts), perf_counter() - started,
                    )
                    if task.status.state != TaskState.TASK_STATE_COMPLETED:
                        raise RuntimeError(
                            f"Remote A2A task {task.id} did not complete: "
                            f"state={task.status.state}"
                        )
                    text = "\n".join(filter(None, map(get_artifact_text, task.artifacts)))
                    if not text:
                        raise RuntimeError("Remote agent completed without a text artifact")
                    return text
            raise RuntimeError("Remote A2A server returned no response")
        finally:
            await client.close()
            logger.debug("Closed A2A client for %s", url)


async def invoke_agent(agent, prompt: str, role: str = "agent") -> str:
    """Read text from a LangChain response, including text content blocks."""
    model_logger = logging.getLogger(f"devdesk.{role}")
    started = perf_counter()
    model_logger.info("Calling model via LangChain | input=%d characters; waiting for response", len(prompt))
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    model_logger.info("Model response received after %.2fs", perf_counter() - started)
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


class BugExecutor(AgentExecutor):
    """Adapt either script's respond() function to A2A tasks."""

    def __init__(self, respond):
        self.respond = respond

    async def execute(self, context, event_queue):
        started = perf_counter()
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
            logger.info("Created task=%s | context=%s", task.id, task.context_id)
        else:
            logger.info("Continuing task=%s | context=%s", task.id, task.context_id)
        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.start_work(new_text_message("Processing bug report..."))
        logger.info("Task=%s state=WORKING", task.id)
        try:
            prompt = get_message_text(context.message).strip()
            if not prompt:
                raise ValueError("The request must contain a bug description")
            logger.info("Task=%s dispatching bug report to agent (%d characters)", task.id, len(prompt))
            answer = await self.respond(prompt)
            await updater.add_artifact(
                parts=[new_text_part(answer, media_type="text/markdown")],
                name="bug_report", last_chunk=True,
            )
            logger.info("Task=%s published artifact=bug_report (%d characters)", task.id, len(answer))
            await updater.complete()
            logger.info("Task=%s state=COMPLETED | total=%.2fs", task.id, perf_counter() - started)
        except Exception:
            logger.exception("Task=%s execution failed after %.2fs", task.id, perf_counter() - started)
            await updater.failed(new_text_message(
                "Agent execution failed. Check the server logs. "
                "Make sure the remote agent is running and your API key is valid."
            ))
            logger.info("Task=%s state=FAILED", task.id)

    async def cancel(self, context, event_queue):
        raise NotImplementedError("Task cancellation is not supported in this demo")


def run_server(role: str, port: int, respond) -> None:
    """Expose an agent through Agent Card discovery and A2A JSON-RPC."""
    title = f"Bug {role.title()} Agent"
    card = AgentCard(
        name=title,
        description=f"DevDesk independent {role} A2A service",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "text/markdown"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC", url=f"http://127.0.0.1:{port}",
            protocol_version="1.0",
        )],
        skills=[AgentSkill(
            id=f"{role}_bug", name=title,
            description=(
                "Analyze backend bugs and ask a separate solution agent"
                if role == "triage"
                else "Suggest fixes and tests for backend bugs"
            ),
            tags=["python", "backend", "bug"],
            examples=["FastAPI returns HTTP 500 when email is missing"],
            input_modes=["text/plain"],
            output_modes=["text/plain", "text/markdown"],
        )],
    )
    handler = DefaultRequestHandler(
        agent_executor=BugExecutor(respond),
        task_store=InMemoryTaskStore(), agent_card=card,
    )
    app = Starlette(routes=[
        *create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/"),
    ])
    logger.info("Serving %s at http://127.0.0.1:%d | Agent Card: /.well-known/agent-card.json | transport: JSON-RPC", title, port)
    uvicorn.run(app, host="127.0.0.1", port=port)


def main() -> None:
    setup_logging("cli")
    started = perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "bug", nargs="?",
        default="FastAPI /users returns HTTP 500 when email is missing",
        help="Describe the backend bug to investigate",
    )
    args = parser.parse_args()
    url = os.getenv("TRIAGE_AGENT_URL", "http://127.0.0.1:8001")
    print(f"Sending bug report to {url} using A2A...\n")
    try:
        answer = asyncio.run(ask_remote_agent(url, args.bug))
        logger.info("Full workflow finished after %.2fs; printing final report", perf_counter() - started)
        print(answer)
    except Exception as exc:
        logger.error("CLI request failed after %.2fs: %s", perf_counter() - started, exc)
        raise SystemExit(
            f"A2A request failed: {exc}\n"
            "Verify both servers are running and .env has a valid API key."
        ) from exc


if __name__ == "__main__":
    main()
