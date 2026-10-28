"""Start the LangChain Triage A2A server: uv run triage-agent.py."""

from dotenv import load_dotenv
import uvicorn

from devdesk.server import make_app


if __name__ == "__main__":
    load_dotenv()
    host, port = "127.0.0.1", 8001
    uvicorn.run(
        make_app("triage", host, port),
        host=host,
        port=port,
    )
