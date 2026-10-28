"""Run either A2A server: solution on 8002, triage on 8001."""

import argparse
import logging

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from dotenv import load_dotenv
from starlette.applications import Starlette

from devdesk.executor import DevDeskExecutor


def make_app(role: str, host: str, port: int) -> Starlette:
    title = "Bug Triage Agent" if role == "triage" else "Bug Solution Agent"
    skill = AgentSkill(
        id=f"{role}_bug",
        name=title,
        description=(
            "Analyze backend bugs and ask a separate solution agent"
            if role == "triage"
            else "Suggest fixes and tests for backend bugs"
        ),
        tags=["python", "backend", "bug"],
        examples=["FastAPI returns HTTP 500 when email is missing"],
        input_modes=["text/plain"],
        output_modes=["text/plain", "text/markdown"],
    )
    card = AgentCard(
        name=title,
        description=f"DevDesk independent {role} A2A service",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "text/markdown"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=f"http://{host}:{port}",
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=DevDeskExecutor(role),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = [
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, "/"),
    ]
    return Starlette(routes=routes)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["triage", "solution"], required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    port = args.port or (8001 if args.role == "triage" else 8002)
    uvicorn.run(make_app(args.role, args.host, port), host=args.host, port=port)


if __name__ == "__main__":
    main()
