"""
Rule-based evaluator for SEC agent logs.
"""

import re
from typing import List
from .schemas import LLMLogRecord, CheckResult, CheckName


# Forbidden phrases that indicate general knowledge usage
FORBIDDEN_PHRASES = [
    "based on general knowledge",
    "based on publicly available",
    "while there are no documented disclosures",
    "we can outline general risks",
    "even though specific sec filings are not available",
    "based on general context",
    "here is an overview based on",
    "it is important to highlight that while i could not find",
    "however, based on",
]

# Required SEC form types for citations
SEC_FORM_TYPES = ["8-k", "10-k", "10-q", "6-k", "20-f", "8-k/a"]


class RuleBasedEvaluator:
    """Rule-based evaluator for SEC agent responses."""

    def evaluate(self, log_id: int, rec: LLMLogRecord) -> List[CheckResult]:
        """Evaluate a log record and return check results."""
        checks = []
        answer = rec.assistant_answer or ""

        # Check 1: Data Source Adherence
        checks.append(self._check_data_source_adherence(log_id, answer))

        # Check 2: Citation Quality
        checks.append(self._check_citation_quality(log_id, answer))

        # Check 3: Information Accuracy (basic check - can't fully validate without ground truth)
        checks.append(self._check_information_accuracy(log_id, answer))

        # Check 4: Completeness
        checks.append(self._check_completeness(log_id, answer, rec.user_prompt))

        # Check 5: Missing Document Handling
        checks.append(self._check_missing_document_handling(log_id, answer))

        # Check 6: Response Structure
        checks.append(self._check_response_structure(log_id, answer))

        # Check 7: Entity Resolution (basic check)
        checks.append(self._check_entity_resolution(log_id, answer))

        return checks

    def _check_data_source_adherence(self, log_id: int, answer: str) -> CheckResult:
        """Check if response uses only SEC filings (no general knowledge)."""
        answer_lower = answer.lower()
        violations = [phrase for phrase in FORBIDDEN_PHRASES if phrase in answer_lower]

        if violations:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.data_source_adherence,
                passed=False,
                message=f"Found forbidden phrases indicating general knowledge usage: {', '.join(violations[:3])}"
            )
        else:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.data_source_adherence,
                passed=True,
                message="Response adheres to SEC-only data sources"
            )

    def _check_citation_quality(self, log_id: int, answer: str) -> CheckResult:
        """Check if response has proper SEC filing citations."""
        answer_lower = answer.lower()
        has_citations = False
        citation_count = 0

        # Check for form type mentions
        for form_type in SEC_FORM_TYPES:
            if form_type in answer_lower:
                has_citations = True
                citation_count += answer_lower.count(form_type)

        # Check for "filed" or "filing" mentions (indicating citations)
        if "filed" in answer_lower or "filing" in answer_lower:
            has_citations = True

        if has_citations and citation_count > 0:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.citation_quality,
                passed=True,
                message=f"Response includes SEC filing citations ({citation_count} form types mentioned)"
            )
        elif "no cybersecurity disclosures found" in answer_lower or "no information available" in answer_lower:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.citation_quality,
                passed=None,  # Not applicable if no filings found
                message="No filings found, citation check not applicable"
            )
        else:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.citation_quality,
                passed=False,
                message="Response lacks proper SEC filing citations"
            )

    def _check_information_accuracy(self, log_id: int, answer: str) -> CheckResult:
        """Basic check for information accuracy (can't fully validate without ground truth)."""
        # This is a placeholder - full accuracy requires ground truth comparison
        if len(answer) < 10:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.information_accuracy,
                passed=False,
                message="Response is too short to evaluate accuracy"
            )
        return CheckResult(
            log_id=log_id,
            check_name=CheckName.information_accuracy,
            passed=None,  # Requires ground truth for full validation
            message="Accuracy check requires ground truth comparison"
        )

    def _check_completeness(self, log_id: int, answer: str, user_prompt: str) -> CheckResult:
        """Check if response addresses the question."""
        if not answer or len(answer.strip()) < 10:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.completeness,
                passed=False,
                message="Response is empty or too short"
            )

        # Basic check: response should be substantial
        if len(answer) < 50:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.completeness,
                passed=False,
                message="Response appears incomplete (too short)"
            )

        return CheckResult(
            log_id=log_id,
            check_name=CheckName.completeness,
            passed=True,
            message="Response appears complete"
        )

    def _check_missing_document_handling(self, log_id: int, answer: str) -> CheckResult:
        """Check if response handles missing documents appropriately."""
        answer_lower = answer.lower()
        
        # Check if response mentions missing information
        missing_indicators = [
            "not available",
            "not found",
            "missing",
            "unavailable",
            "not in the index",
            "not disclosed",
            "no filings found"
        ]

        has_missing_mention = any(indicator in answer_lower for indicator in missing_indicators)

        if has_missing_mention:
            # Check if it explains why
            explanation_indicators = [
                "because",
                "due to",
                "reason",
                "explain",
                "why",
                "may not be available"
            ]
            has_explanation = any(indicator in answer_lower for indicator in explanation_indicators)

            if has_explanation:
                return CheckResult(
                    log_id=log_id,
                    check_name=CheckName.missing_document_handling,
                    passed=True,
                    message="Response identifies missing information and explains why"
                )
            else:
                return CheckResult(
                    log_id=log_id,
                    check_name=CheckName.missing_document_handling,
                    passed=None,
                    message="Response mentions missing information but doesn't explain why"
                )

        return CheckResult(
            log_id=log_id,
            check_name=CheckName.missing_document_handling,
            passed=None,  # Not applicable if no missing documents mentioned
            message="No missing documents mentioned"
        )

    def _check_response_structure(self, log_id: int, answer: str) -> CheckResult:
        """Check if response is well-structured."""
        if not answer or len(answer.strip()) < 10:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.response_structure,
                passed=False,
                message="Response is empty or too short"
            )

        # Check for section headers (markdown or plain text)
        has_sections = (
            "##" in answer or  # Markdown headers
            "**" in answer or  # Bold text (likely section headers)
            answer.count("\n\n") >= 2  # Multiple paragraphs
        )

        if has_sections:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.response_structure,
                passed=True,
                message="Response has clear structure with sections"
            )
        else:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.response_structure,
                passed=None,
                message="Response structure could be improved with clearer sections"
            )

    def _check_entity_resolution(self, log_id: int, answer: str) -> CheckResult:
        """Basic check for entity resolution (CIK mentions, company names)."""
        # Check for CIK mentions (10-digit numbers)
        cik_pattern = r'\b\d{10}\b'
        has_cik = bool(re.search(cik_pattern, answer))

        # Check for company name mentions
        has_company_name = bool(re.search(r'\b(Company|Corporation|Inc\.|LLC|Ltd\.)', answer, re.IGNORECASE))

        if has_cik or has_company_name:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.entity_resolution,
                passed=True,
                message="Response includes company identification (CIK or company name)"
            )
        else:
            return CheckResult(
                log_id=log_id,
                check_name=CheckName.entity_resolution,
                passed=None,
                message="Cannot verify entity resolution without explicit CIK or company name"
            )

