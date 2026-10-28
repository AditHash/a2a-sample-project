"""Suggest a fix and tests for a bug received over A2A."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent

from main import invoke_agent, run_server, setup_logging

load_dotenv(Path(__file__).with_name(".env"))


if __name__ == "__main__":
    setup_logging("solution")
    logger = logging.getLogger("devdesk.solution")
    logger.info("Building solution LangChain agent | model=%s", os.getenv("MODEL", "openai:gpt-5-nano"))
    agent = create_agent(
        model=os.getenv("MODEL", "openai:gpt-5-nano"),
        tools=[],
        system_prompt=(
            "You are a senior Python backend engineer. Given a bug report and a "
            "triage assessment, propose a concrete fix and a way to test it. "
            "Show a small code snippet when useful. Never pretend you executed tests."
        ),
    )

    async def respond(bug: str) -> str:
        logger.info("Received bug report and context; generating a fix and test plan")
        answer = await invoke_agent(agent, bug, role="solution")
        logger.info("Fix and test plan ready; returning answer to A2A executor")
        return answer

    run_server("solution", 8002, respond)
