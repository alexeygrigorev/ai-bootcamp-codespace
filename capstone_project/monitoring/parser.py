"""
Parser for SEC agent log files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from .schemas import LLMLogRecord


def _get_first_user_prompt(messages: list[dict]) -> Optional[str]:
    """Extract the first user prompt from messages."""
    for msg in messages:
        # Handle pydantic_ai message format with "kind" and "parts"
        if msg.get("kind") in ("user", "request"):
            parts = msg.get("parts", [])
            for p in parts:
                if p.get("part_kind") == "user-prompt":
                    content = p.get("content")
                    if isinstance(content, str):
                        return content
        # Handle standard format with "role"
        elif msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str):
                        return part
                    elif isinstance(part, dict) and "text" in part:
                        return part["text"]
    return None


def _get_instructions(doc: Dict[str, Any]) -> Optional[str]:
    """Extract instructions from document."""
    # Prefer system_prompt field
    sys = doc.get("system_prompt")
    if isinstance(sys, str):
        return sys
    if isinstance(sys, list):
        try:
            return "\n".join([s for s in sys if isinstance(s, str)])
        except Exception:
            pass
    return None


def _get_model(doc: Dict[str, Any]) -> Optional[str]:
    """Extract model name from document."""
    model = doc.get("model")
    if model:
        return str(model)
    return None


def _get_total_usage(doc: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    """Extract token usage from document."""
    usage = doc.get("usage") or {}
    input_tokens = usage.get("input_tokens") or usage.get("total_input_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("total_output_tokens")
    return (input_tokens, output_tokens)


def _extract_answer(doc: Dict[str, Any]) -> Optional[str]:
    """Extract assistant answer from document."""
    # Prefer top-level "output" field
    out = doc.get("output")
    if isinstance(out, str):
        return out
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
    # Fallback: last assistant message content
    messages = doc.get("messages") or []
    for msg in reversed(messages):
        if msg.get("kind") == "assistant" or msg.get("role") == "assistant":
            parts = msg.get("parts", [])
            for p in parts:
                c = p.get("content")
                if isinstance(c, str):
                    return c
    return None


def _extract_timestamp(doc: Dict[str, Any]) -> Optional[datetime]:
    """Extract timestamp from document."""
    # Try various timestamp fields
    for field in ["timestamp", "created_at", "date"]:
        ts = doc.get(field)
        if ts:
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    pass
            elif isinstance(ts, datetime):
                return ts
    # Try to extract from messages
    messages = doc.get("messages") or []
    for msg in reversed(messages):
        if "timestamp" in msg:
            ts = msg["timestamp"]
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    pass
    return None


def parse_log_file(path: str | Path) -> LLMLogRecord:
    """Parse a log file and return an LLMLogRecord."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    messages = doc.get("messages") or []

    user_prompt = _get_first_user_prompt(messages)
    instructions = _get_instructions(doc)
    model = _get_model(doc)
    provider = doc.get("provider") or "openai"  # Default to openai
    agent_name = doc.get("agent_name") or "sec_cybersecurity_agent"
    total_in, total_out = _get_total_usage(doc)
    answer = _extract_answer(doc)
    created_at = _extract_timestamp(doc)

    return LLMLogRecord(
        filepath=str(p),
        agent_name=str(agent_name) if agent_name else "sec_cybersecurity_agent",
        provider=str(provider) if provider else "openai",
        model=str(model) if model else None,
        user_prompt=str(user_prompt) if user_prompt else "",
        instructions=str(instructions) if instructions else None,
        total_input_tokens=int(total_in) if isinstance(total_in, int) else None,
        total_output_tokens=int(total_out) if isinstance(total_out, int) else None,
        assistant_answer=str(answer) if answer else None,
        created_at=created_at,
    )

