from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .schemas import CheckName, CheckResult, LLMLogRecord


class Evaluator:
    def evaluate(self, log_id: int, record: LLMLogRecord) -> List[CheckResult]:  # pragma: no cover - interface
        raise NotImplementedError


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


@dataclass
class RuleBasedEvaluator(Evaluator):
    """A simple evaluator that produces heuristic pass/fail signals.

    This is designed to be replaced by a real LLM-based evaluator later,
    but provides immediate value without external dependencies.
    """

    def evaluate(self, log_id: int, record: LLMLogRecord) -> List[CheckResult]:
        checks: List[CheckResult] = []
        prompt = record.user_prompt or ""
        answer = record.assistant_answer or ""
        instructions = record.instructions or ""

        # Parse raw json once to inspect tool calls or metadata
        search_calls = 0
        try:
            doc = json.loads(record.raw_json or "{}")
            for msg in doc.get("messages", []):
                for part in msg.get("parts", []) or []:
                    if part.get("tool_name") == "search":
                        search_calls += 1
        except Exception:
            pass

        # instructions_follow: if instructions require a References section, check presence
        requires_references = "references" in instructions.lower()
        has_references = "references" in answer.lower() or "http://" in answer or "https://" in answer
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.instructions_follow,
                passed=(has_references if requires_references else None),
                details=(
                    "Instructions mention references; answer contains references."
                    if requires_references and has_references
                    else (
                        "Instructions mention references; answer missing references."
                        if requires_references
                        else "No explicit reference requirement detected."
                    )
                ),
            )
        )

        # instructions_avoid: if instructions limit searches to <=6 and >=3, check count
        requires_search_bounds = "at most 6" in instructions.lower() and "at least 3" in instructions.lower()
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.instructions_avoid,
                passed=(3 <= search_calls <= 6 if requires_search_bounds else None),
                details=(
                    f"search_calls={search_calls} within [3,6]"
                    if requires_search_bounds
                    else "No explicit search bounds requirement detected."
                ),
            )
        )

        # answer_clear: basic readability heuristic (length + sentence length)
        sentences = re.split(r"[.!?]+\s+", answer.strip()) if answer.strip() else []
        words = _tokenize(answer)
        avg_sent_len = (len(words) / max(1, len(sentences))) if sentences else 0
        passed_clear = len(words) >= 40 and avg_sent_len <= 35
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.answer_clear,
                passed=(passed_clear if answer else None),
                details=f"words={len(words)}, sentences={len(sentences)}, avg_sentence_len={avg_sent_len:.1f}",
            )
        )

        # answer_match: overlap between prompt terms and answer terms
        p_tokens = set(_tokenize(prompt))
        a_tokens = set(_tokenize(answer))
        overlap = len(p_tokens & a_tokens)
        jaccard = overlap / max(1, len(p_tokens | a_tokens))
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.answer_match,
                passed=(jaccard >= 0.08 if answer and prompt else None),
                score=jaccard,
                details=f"token_overlap={overlap}, jaccard={jaccard:.3f}",
            )
        )

        # answer_citations: references or links present
        has_link = ("http://" in answer) or ("https://" in answer)
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.answer_citations,
                passed=(has_link or ("references" in answer.lower()) if answer else None),
                details="Contains URLs or a references section" if answer else "No answer text",
            )
        )

        # completeness: ensure multiple concrete suggestions or structured sections
        has_bullets = bool(re.search(r"(^|\n)\s*(?:[-*]|\d+\.)\s+", answer))
        passed_complete = len(words) >= 120 or has_bullets
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.completeness,
                passed=(passed_complete if answer else None),
                details=f"len(words)={len(words)}, bullets={has_bullets}",
            )
        )

        # tool_call_search: was the search tool used
        checks.append(
            CheckResult(
                log_id=log_id,
                check_name=CheckName.tool_call_search,
                passed=(search_calls > 0),
                details=f"search_calls={search_calls}",
            )
        )

        return checks

