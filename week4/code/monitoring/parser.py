from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .schemas import LLMLogRecord


def _get_first_user_prompt(messages: list[dict]) -> Optional[str]:
    for msg in messages:
        parts = msg.get("parts") or []
        for p in parts:
            if p.get("part_kind") == "user-prompt":
                content = p.get("content")
                if content:
                    return str(content)
    # fallback: any message content field
    for msg in messages:
        parts = msg.get("parts") or []
        for p in parts:
            if isinstance(p.get("content"), str):
                return p["content"]
    return None


def _get_instructions(doc: Dict[str, Any]) -> Optional[str]:
    # Prefer message-level instructions from the first message
    messages = doc.get("messages") or []
    if messages:
        first = messages[0]
        instr = first.get("instructions")
        if instr:
            return str(instr)
    # Fallback to system_prompt list
    sys = doc.get("system_prompt")
    if isinstance(sys, list):
        try:
            return "\n".join([s for s in sys if isinstance(s, str)])
        except Exception:
            return None
    if isinstance(sys, str):
        return sys
    return None


def _get_model(doc: Dict[str, Any]) -> Optional[str]:
    model = doc.get("model")
    if model:
        return str(model)
    # fallback to last response model_name
    messages = doc.get("messages") or []
    for msg in reversed(messages):
        name = msg.get("model_name")
        if name:
            return str(name)
    return None


def _get_total_usage(doc: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    usage = doc.get("usage") or {}
    return (
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )


def _extract_answer(doc: Dict[str, Any]) -> Optional[str]:
    # Prefer top-level "output" aggregate
    out = doc.get("output")
    if isinstance(out, dict):
        chunks: list[str] = []
        title = out.get("title")
        if isinstance(title, str):
            chunks.append(title)
        sections = out.get("sections")
        if isinstance(sections, list):
            for s in sections:
                if isinstance(s, dict):
                    heading = s.get("heading")
                    content = s.get("content")
                    if isinstance(heading, str):
                        chunks.append(heading)
                    if isinstance(content, str):
                        chunks.append(content)
        if chunks:
            return "\n\n".join(chunks)
    # Fallback: last assistant message content, if any
    messages = doc.get("messages") or []
    for msg in reversed(messages):
        parts = msg.get("parts") or []
        for p in parts:
            c = p.get("content")
            if isinstance(c, str):
                return c
    return None


def parse_log_file(path: str | Path) -> LLMLogRecord:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = f.read()
    doc = json.loads(raw)

    messages = doc.get("messages") or []

    user_prompt = _get_first_user_prompt(messages)
    instructions = _get_instructions(doc)
    model = _get_model(doc)
    provider = doc.get("provider") or doc.get("provider_name")
    agent_name = doc.get("agent_name")
    total_in, total_out = _get_total_usage(doc)
    answer = _extract_answer(doc)

    return LLMLogRecord(
        filepath=str(p),
        agent_name=str(agent_name) if agent_name is not None else None,
        provider=str(provider) if provider is not None else None,
        model=str(model) if model is not None else None,
        user_prompt=str(user_prompt) if user_prompt is not None else None,
        instructions=str(instructions) if instructions is not None else None,
        total_input_tokens=int(total_in) if isinstance(total_in, int) else None,
        total_output_tokens=int(total_out) if isinstance(total_out, int) else None,
        assistant_answer=str(answer) if answer is not None else None,
        raw_json=raw,
    )

