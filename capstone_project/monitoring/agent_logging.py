"""
Logging utilities for SEC Cybersecurity Agent.
"""

import json
import secrets
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import pydantic
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage
from pydantic_ai.messages import ModelMessage
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.run import AgentRunResult
from pydantic_ai.result import StreamedRunResult


UsageTypeAdapter = pydantic.TypeAdapter(RunUsage)


def create_log_entry(
    agent: Agent,
    messages: List[ModelMessage],
    usage: RunUsage,
    output: str,
    user_prompt: Optional[str] = None
) -> dict:
    """Create a log entry from an agent run."""
    tools = []
    for ts in agent.toolsets:
        tools.extend(ts.tools.keys())

    dict_messages = ModelMessagesTypeAdapter.dump_python(messages)
    dict_usage = UsageTypeAdapter.dump_python(usage)

    # Extract user prompt if not provided
    if not user_prompt:
        for msg in messages:
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if hasattr(part, 'part_kind') and part.part_kind == 'user-prompt':
                        user_prompt = part.content if hasattr(part, 'content') else None
                        break
                if user_prompt:
                    break

    return {
        "agent_name": agent.name,
        "system_prompt": agent._instructions,
        "provider": agent.model.system,
        "model": agent.model.model_name,
        "tools": tools,
        "messages": dict_messages,
        "usage": dict_usage,
        "output": output,
        "user_prompt": user_prompt,
        "timestamp": datetime.now(),
    }


async def log_streamed_run(
    agent: Agent,
    result: StreamedRunResult,
    user_prompt: Optional[str] = None
) -> dict:
    """Log a streamed agent run."""
    output = await result.get_output()
    usage = result.usage()
    messages = result.all_messages()

    log = create_log_entry(
        agent=agent,
        messages=messages,
        usage=usage,
        output=output,
        user_prompt=user_prompt
    )

    return log


def log_run(
    agent: Agent,
    result: AgentRunResult,
    user_prompt: Optional[str] = None
) -> dict:
    """Log a regular agent run."""
    output = result.output
    usage = result.usage()
    messages = result.all_messages()

    log = create_log_entry(
        agent=agent,
        messages=messages,
        usage=usage,
        output=output,
        user_prompt=user_prompt
    )

    return log


def serializer(obj):
    """JSON serializer for datetime and BaseModel objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, pydantic.BaseModel):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj)} not serializable")


def find_last_timestamp(messages):
    """Find the last timestamp in messages."""
    for msg in reversed(messages):
        if isinstance(msg, dict) and 'timestamp' in msg:
            return msg['timestamp']
        elif hasattr(msg, 'timestamp'):
            return msg.timestamp
    return None


def save_log(entry: dict, logs_dir: Optional[Path] = None) -> Path:
    """Save a log entry to a JSON file."""
    if logs_dir is None:
        logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    ts = find_last_timestamp(entry.get('messages', []))
    if not ts:
        ts = entry.get('timestamp', datetime.now())
    
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except:
            ts = datetime.now()
    elif not isinstance(ts, datetime):
        ts = datetime.now()

    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    rand_hex = secrets.token_hex(3)

    agent_name = entry.get('agent_name', 'sec_cybersecurity_agent').replace(" ", "_").lower()

    filename = f"{agent_name}_{ts_str}_{rand_hex}.json"
    filepath = logs_dir / filename

    with filepath.open("w", encoding="utf-8") as f_out:
        json.dump(entry, f_out, indent=2, default=serializer)

    return filepath

