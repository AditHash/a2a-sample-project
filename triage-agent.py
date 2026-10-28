"""Analyze a bug, then ask the Solution Agent for a fix over A2A."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent

from main import ask_remote_agent, invoke_agent, run_server, setup_logging

load_dotenv(Path(__file__).with_name(".env"))


if __name__ == "__main__":
    setup_logging("triage")
    logger = logging.getLogger("devdesk.triage")
    logger.info("Building triage LangChain agent | model=%s", os.getenv("MODEL", "openai:gpt-5-nano"))
    agent = create_agent(
        model=os.getenv("MODEL", "openai:gpt-5-nano"),
        tools=[],
        system_prompt=(
            "You are a backend bug triage engineer. Analyze the given bug report. "
            "Output a concise CATEGORY, SEVERITY (low/medium/high), and LIKELY CAUSE. "
            "Be explicit when the root cause is uncertain. Do not claim you ran code."
        ),
    )

    async def respond(bug: str) -> str:
        logger.info("Step 1/3: analyze the bug report")
        triage = await invoke_agent(agent, bug, role="triage")
        logger.info("Step 2/3: hand off original bug and triage findings to Solution Agent over A2A")
        solution = await ask_remote_agent(
            os.getenv("SOLUTION_AGENT_URL", "http://127.0.0.1:8002"),
            f"Original bug report:\n{bug}\n\nTriage findings:\n{triage}",
        )
        logger.info("Step 3/3: combine triage findings and solution into final report")
        return f"## Triage Agent\n{triage}\n\n## Solution Agent (via A2A)\n{solution}"

    run_server("triage", 8001, respond)
