from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from decimal import Decimal


class CheckName(str, Enum):
    instructions_follow = "instructions_follow"
    instructions_avoid = "instructions_avoid"
    answer_clear = "answer_clear"
    answer_match = "answer_match"
    answer_citations = "answer_citations"
    completeness = "completeness"
    tool_call_search = "tool_call_search"


@dataclass
class LLMLogRecord:
    filepath: str
    agent_name: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    user_prompt: Optional[str]
    instructions: Optional[str]
    total_input_tokens: Optional[int]
    total_output_tokens: Optional[int]
    assistant_answer: Optional[str]
    raw_json: Optional[str]
    # Cost fields represented as Decimal in code
    input_cost: Optional[Decimal] = None
    output_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None


@dataclass
class CheckResult:
    log_id: int
    check_name: CheckName
    passed: Optional[bool] = None
    score: Optional[float] = None
    details: Optional[str] = None


@dataclass
class Feedback:
    log_id: int
    is_good: bool
    comments: Optional[str] = None
    reference_answer: Optional[str] = None
