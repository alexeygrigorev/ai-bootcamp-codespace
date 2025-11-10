"""Monitoring package for ingesting LLM logs, evaluating results,
and storing records and feedback in a database.

Modules:
- config: configuration helpers
- schemas: dataclasses and enums for typed records
- db: database access layer (Postgres-ready, SQLite fallback)
- parser: JSON log parsing utilities
- sources: pluggable log sources (filesystem implementation)
- evaluator: simple rule-based evaluator (LLM-pluggable)
- runner: CLI entry to process a directory of logs
- feedback: helpers to save user feedback
"""

__all__ = [
    "config",
    "schemas",
    "db",
    "parser",
    "sources",
    "evaluator",
    "runner",
    "feedback",
]

