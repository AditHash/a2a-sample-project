"""CLI -> Triage A2A server -> Solution A2A server."""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from devdesk.remote import ask_remote_agent


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "bug",
        nargs="?",
        default="FastAPI /users returns HTTP 500 when email is missing",
        help="Describe the backend bug to investigate",
    )
    args = parser.parse_args()

    url = os.getenv("TRIAGE_AGENT_URL", "http://127.0.0.1:8001")
    print(f"Sending bug report to {url} using A2A...\n")
    try:
        answer = await ask_remote_agent(url, args.bug)
    except Exception as exc:
        raise SystemExit(
            f"A2A request failed: {exc}\n"
            "Verify both servers are running and .env has a valid API key."
        ) from exc
    print(answer)


def main() -> None:
    load_dotenv()
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
