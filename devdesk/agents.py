"""Independent LangChain agent definitions.

The A2A SDK handles inter-agent communication; LangChain handles reasoning.
"""

import os

from langchain.agents import create_agent


def build_agent(role: str):
    model = os.getenv("MODEL", "openai:gpt-5-nano")
    if role == "triage":
        prompt = (
            "You are a backend bug triage engineer. Analyze the given bug report. "
            "Output a concise CATEGORY, SEVERITY (low/medium/high), and LIKELY CAUSE. "
            "Be explicit when the root cause is uncertain. Do not claim you ran code."
        )
    elif role == "solution":
        prompt = (
            "You are a senior Python backend engineer. Given a bug report and a "
            "triage assessment, propose a concrete fix and a way to test it. "
            "Show a small code snippet when useful. Never pretend you executed tests."
        )
    else:
        raise ValueError(f"Unknown agent role: {role}")

    # These are ordinary LangChain v1 agents, not Deep Agents.
    return create_agent(model=model, tools=[], system_prompt=prompt)


async def invoke_agent(agent, prompt: str) -> str:
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]}
    )
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    # Content blocks are possible with some model providers.
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
