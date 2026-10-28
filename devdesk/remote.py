"""Send a real A2A request to an independently running agent."""

from a2a.client import ClientConfig, create_client
from a2a.helpers import (
    get_artifact_text,
    get_message_text,
    new_text_message,
)
from a2a.types import Role, SendMessageRequest, TaskState


async def ask_remote_agent(base_url: str, prompt: str) -> str:
    # create_client discovers the remote Agent Card automatically.
    client = await create_client(
        agent=base_url,
        client_config=ClientConfig(streaming=False),
    )
    try:
        request = SendMessageRequest(
            message=new_text_message(prompt, role=Role.ROLE_USER)
        )
        async for response in client.send_message(request):
            if response.HasField("message"):
                return get_message_text(response.message)

            if response.HasField("task"):
                task = response.task
                if task.status.state != TaskState.TASK_STATE_COMPLETED:
                    raise RuntimeError(
                        f"Remote A2A task {task.id} did not complete: "
                        f"state={task.status.state}"
                    )
                texts = [get_artifact_text(a) for a in task.artifacts]
                text = "\n".join(t for t in texts if t)
                if not text:
                    raise RuntimeError("Remote agent completed without a text artifact")
                return text

        raise RuntimeError("Remote A2A server returned no response")
    finally:
        await client.close()
