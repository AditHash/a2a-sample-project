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

All three scripts use `python-dotenv` and `load_dotenv()` to read the `.env`
beside the scripts. Existing environment variables take precedence over `.env`.

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

The CLI sends an A2A request to the triage service, which calls the solution service over A2A, then prints both agents' answers. Each A2A call allows up to five minutes waiting for a response, since model generation can take time.

Inspect the agent cards:

- http://127.0.0.1:8001/.well-known/agent-card.json
- http://127.0.0.1:8002/.well-known/agent-card.json

To prove remote A2A is required, stop the Solution Agent and try the CLI again. The triage task should fail. Restart it and retry.

## Following the logs

Restart both agent scripts after code changes. All three terminals show timestamped
logs by default. The CLI shows discovery, sending, and total time. The triage
terminal shows model generation, the A2A handoff, and combining the report. The
solution terminal shows generating the fix and returning it. Task logs show task
IDs, WORKING/COMPLETED/FAILED states, and publishing the final artifact.

Each model call reports its duration; a `waiting for response` message means it is
still generating. Logs include text lengths rather than full prompts or answers.
For additional application debug messages, set `LOG_LEVEL=DEBUG` in `.env` and
restart the scripts. Logs go to stderr; the final report goes to stdout.

## File guide

| Path | Responsibility |
| --- | --- |
| `main.py` | CLI client and shared A2A discovery, server, and task handling |
| `triage-agent.py` | LangChain triage agent and A2A handoff to the solution agent |
| `solution-agent.py` | LangChain solution agent that proposes fixes and tests |

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
