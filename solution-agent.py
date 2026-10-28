"""Start the LangChain Solution A2A server: uv run solution-agent.py."""

from dotenv import load_dotenv
import uvicorn

from devdesk.server import make_app


if __name__ == "__main__":
    load_dotenv()
    host, port = "127.0.0.1", 8002
    uvicorn.run(
        make_app("solution", host, port),
        host=host,
        port=port,
    )
