import json
import secrets

from pathlib import Path
from datetime import datetime
from typing import List

import pydantic
from pydantic import BaseModel

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
    output: str
):
    tools = []

    for ts in agent.toolsets:
        tools.extend(ts.tools.keys())

    dict_messages = ModelMessagesTypeAdapter.dump_python(messages)
    dict_usage = UsageTypeAdapter.dump_python(usage)

    return {
        "agent_name": agent.name,
        "system_prompt": agent._instructions,
        "provider": agent.model.system,
        "model": agent.model.model_name,
        "tools": tools,
        "messages": dict_messages,
        "usage": dict_usage,
        "output": output,
    }


async def log_streamed_run(
    agent: Agent,
    result: StreamedRunResult
):
    output = await result.get_output()
    usage = result.usage()
    messages = result.all_messages()

    log = create_log_entry(
        agent=agent,
        messages=messages,
        usage=usage,
        output=output
    )

    return log


def log_run(
    agent: Agent,
    result: AgentRunResult
):
    output = result.output
    usage = result.usage()
    messages = result.all_messages()

    log = create_log_entry(
        agent=agent,
        messages=messages,
        usage=usage,
        output=output
    )

    return log



def serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj)} not serializable")


def find_last_timestamp(messages):
    for msg in reversed(messages):
        if 'timestamp' in msg:
            return msg['timestamp']


def save_log(entry: dict):
    logs_folder = Path('logs')
    logs_folder.mkdir(exist_ok=True)

    ts = find_last_timestamp(entry['messages'])
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    rand_hex = secrets.token_hex(3)

    agent_name = entry['agent_name'].replace(" ", "_").lower()

    filename = f"{agent_name}_{ts_str}_{rand_hex}.json"
    filepath = logs_folder / filename

    with filepath.open("w", encoding="utf-8") as f_out:
        json.dump(entry, f_out, indent=2, default=serializer)

    return filepath