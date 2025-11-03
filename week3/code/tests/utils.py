import json
from dataclasses import dataclass


@dataclass
class ToolCall:
    name: str
    args: dict


def get_tool_calls(result) -> list[ToolCall]:
    calls = []

    for m in result.new_messages():
        for p in m.parts:
            kind = p.part_kind
            if kind == 'tool-call':
                if p.tool_name == 'final_result':
                    continue
                call = ToolCall(
                    name=p.tool_name,
                    args=json.loads(p.args)
                )
                calls.append(call)

    return calls
