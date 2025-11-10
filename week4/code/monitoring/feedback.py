from __future__ import annotations

from .db import Database
from .schemas import Feedback


def save_feedback(db: Database, log_id: int, is_good: bool, comments: str | None = None, reference_answer: str | None = None) -> int:
    """Save user feedback for a given log record.

    Returns the new feedback id.
    """
    return db.insert_feedback(Feedback(log_id=log_id, is_good=is_good, comments=comments, reference_answer=reference_answer))

