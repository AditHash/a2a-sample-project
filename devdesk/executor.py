"""Bridge the A2A task lifecycle to a LangChain agent."""

import logging
import os

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater

from devdesk.agents import build_agent, invoke_agent
from devdesk.remote import ask_remote_agent

logger = logging.getLogger(__name__)


class DevDeskExecutor(AgentExecutor):
    def __init__(self, role: str) -> None:
        self.role = role
        self.agent = build_agent(role)

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        await updater.start_work(new_text_message("Processing bug report..."))

        try:
            user_text = get_message_text(context.message).strip()
            if not user_text:
                raise ValueError("The request must contain a bug description")

            answer = await invoke_agent(self.agent, user_text)

            if self.role == "triage":
                solution_url = os.getenv(
                    "SOLUTION_AGENT_URL", "http://127.0.0.1:8002"
                )
                logger.info("Calling Solution Agent over A2A: %s", solution_url)
                remote_answer = await ask_remote_agent(
                    solution_url,
                    f"Original bug report:\n{user_text}\n\n"
                    f"Triage findings:\n{answer}",
                )
                answer = (
                    f"## Triage Agent\n{answer}\n\n"
                    f"## Solution Agent (via A2A)\n{remote_answer}"
                )

            await updater.add_artifact(
                parts=[new_text_part(answer, media_type="text/markdown")],
                name="bug_report",
                last_chunk=True,
            )
            await updater.complete()
        except Exception:
            logger.exception("%s agent failed", self.role)
            await updater.failed(
                new_text_message(
                    "Agent execution failed. Check the server logs. "
                    "Make sure the remote agent is running and your API key is valid."
                )
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("Task cancellation is not supported in this demo")
