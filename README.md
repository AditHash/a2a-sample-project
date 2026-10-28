# DevDesk A2A — LangChain Agents + Agent2Agent

A **small practical A2A project**: two independent Python services use ordinary LangChain v1 agents and communicate through the official A2A Python SDK.

No LangGraph orchestration, Deep Agents, Redis, databases, or Docker required.

## Architecture

```text
CLI (A2A client)
       |
       | Discover Agent Card + A2A message
       v
Bug Triage Service  (port 8001)
  ├── LangChain create_agent: classify severity / probable cause
  └── A2A client
          |
          | Discover remote Agent Card + A2A task
          v
Bug Solution Service (port 8002)
  └── LangChain create_agent: propose fix + tests
          |
          +-- A2A artifact --> Triage --> CLI
```

**The inter-agent call is real A2A**, not a custom `POST /solve` API. The triage service makes the remote call deterministically so you can observe it on every request. Later, replace this fixed handoff with a LangChain tool that the model selects.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key (the default model is `openai:gpt-5-nano`)

## Setup

```bash
git clone https://github.com/AditHash/a2a-sample-project.git
cd a2a-sample-project
uv sync
```

Create a local `.env` from the example:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows PowerShell:**
```powershell
Copy-Item .env.example .env
```

Fill in `OPENAI_API_KEY`. Do not commit your `.env`.

### Quick start: three simple commands

Start the **Solution Agent** in the first terminal:

```bash
uv run solution-agent.py
```

Start the **Triage Agent** in a second terminal:

```bash
uv run triage-agent.py
```

Run the **client** in a third terminal:

```bash
uv run main.py "FastAPI returns HTTP 500 when email is missing"
```

Calling `uv run main.py` without arguments uses a default sample bug.

The module-based commands below are also supported.

### Start three terminals in the repository folder

**Terminal 1 — Solution Agent:**

```bash
uv run python -m devdesk.server --role solution
```

**Terminal 2 — Triage Agent:**

```bash
uv run python -m devdesk.server --role triage
```

**Terminal 3 — Client:**

```bash
uv run python -m devdesk.cli "FastAPI returns HTTP 500 when email is missing"
```

The CLI sends an A2A request to the triage service, which calls the solution service over A2A, then prints both agents' answers.

Inspect the agent cards:

- http://127.0.0.1:8001/.well-known/agent-card.json
- http://127.0.0.1:8002/.well-known/agent-card.json

To prove remote A2A is required, stop the Solution Agent and try the CLI again. The triage task should fail. Restart it and retry.

## File guide

| Path | Responsibility |
| --- | --- |
| `devdesk/agents.py` | Two ordinary LangChain `create_agent` definitions |
| `devdesk/executor.py` | Bridges A2A tasks and LangChain; calls remote service |
| `devdesk/remote.py` | A2A Agent Card discovery and message sending |
| `devdesk/server.py` | Exposes each agent as a standalone A2A server |
| `devdesk/cli.py` | CLI A2A client |

## What you'll learn

1. **AgentCard / AgentSkill**: what each remote agent advertises.
2. **A2A client**: how it discovers a remote service.
3. **Message / Task**: how remote work is requested.
4. **TaskUpdater / Artifact**: how server work is completed and returned.
5. **Separation of concerns**: LangChain handles reasoning, A2A handles inter-agent communication.

## Next exercises

- Make the triage agent call the Solution Agent through an LLM-selected LangChain tool.
- Add streaming task updates on both services.
- Add structured JSON data artifacts.
- Deploy the services separately and test remote discovery.

## References

- [Official A2A Python samples](https://github.com/a2aproject/a2a-samples/tree/main/samples/python)
- [Hello World sample (current SDK pattern)](https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/helloworld)
- [LangGraph integration sample](https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/langgraph)

This is a learning starter, not a hardened production service. Don't expose the demo to the internet without authentication, input validation, timeouts, and proper authorization.
