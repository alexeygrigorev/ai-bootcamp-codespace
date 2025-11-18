"""
Schemas for monitoring system.
"""

from enum import Enum
from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class CheckName(str, Enum):
    """Types of evaluation checks."""
    data_source_adherence = "data_source_adherence"
    citation_quality = "citation_quality"
    information_accuracy = "information_accuracy"
    completeness = "completeness"
    missing_document_handling = "missing_document_handling"
    response_structure = "response_structure"
    entity_resolution = "entity_resolution"


class LLMLogRecord(BaseModel):
    """Record parsed from a log file."""
    filepath: str
    agent_name: str
    provider: str
    model: str
    user_prompt: str
    instructions: Optional[str] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    assistant_answer: Optional[str] = None
    input_cost: Optional[Decimal] = None
    output_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    created_at: Optional[datetime] = None


class CheckResult(BaseModel):
    """Result of a single check."""
    log_id: int
    check_name: CheckName
    passed: Optional[bool] = None  # None = not applicable
    message: Optional[str] = None


class Feedback(BaseModel):
    """User feedback on a log entry."""
    log_id: int
    rating: Optional[int] = None  # 1-5 or None
    comment: Optional[str] = None
    reference_answer: Optional[str] = None
    created_at: Optional[datetime] = None

