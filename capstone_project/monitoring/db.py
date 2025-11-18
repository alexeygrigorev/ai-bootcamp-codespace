"""
Database layer for monitoring system.

Supports both SQLite and PostgreSQL.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Optional, List, Dict, Any

from .schemas import LLMLogRecord, CheckResult, Feedback


class Database:
    """Lightweight DB layer with Postgres support and SQLite fallback."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            # default to local sqlite file in project
            self.database_url = "sqlite:///capstone_project/monitoring/monitoring.db"

        self._driver = None  # "sqlite" | "postgres"
        self._conn = None
        self._param = "?"  # paramstyle placeholder

    def connect(self):
        if self._conn:
            return self._conn

        if self.database_url.startswith("sqlite://"):
            self._driver = "sqlite"
            db_path = self.database_url.split("sqlite:///")[-1]
            # Create directory if it doesn't exist
            import pathlib
            pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._param = "?"
        elif self.database_url.startswith("postgres://") or self.database_url.startswith(
            "postgresql://"
        ):
            self._driver = "postgres"
            try:
                import psycopg
                conn = psycopg.connect(self.database_url)
                conn.autocommit = True
            except Exception:
                try:
                    import psycopg2
                    conn = psycopg2.connect(self.database_url)
                    conn.autocommit = True
                except Exception as e:
                    raise RuntimeError(
                        "Postgres URL provided but unable to import psycopg/psycopg2"
                    ) from e
            self._conn = conn
            self._param = "%s"
        else:
            raise ValueError(f"Unsupported DATABASE_URL scheme: {self.database_url}")

        return self._conn

    @property
    def is_postgres(self) -> bool:
        return self._driver == "postgres"

    @contextmanager
    def cursor(self):
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def ensure_schema(self) -> None:
        conn = self.connect()
        with self.cursor() as cur:
            # llm_logs
            if self.is_postgres:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS llm_logs (
                        id SERIAL PRIMARY KEY,
                        filepath TEXT NOT NULL,
                        agent_name TEXT,
                        provider TEXT,
                        model TEXT,
                        user_prompt TEXT,
                        instructions TEXT,
                        total_input_tokens BIGINT,
                        total_output_tokens BIGINT,
                        assistant_answer TEXT,
                        input_cost DECIMAL(10, 6),
                        output_cost DECIMAL(10, 6),
                        total_cost DECIMAL(10, 6),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS llm_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filepath TEXT NOT NULL,
                        agent_name TEXT,
                        provider TEXT,
                        model TEXT,
                        user_prompt TEXT,
                        instructions TEXT,
                        total_input_tokens INTEGER,
                        total_output_tokens INTEGER,
                        assistant_answer TEXT,
                        input_cost REAL,
                        output_cost REAL,
                        total_cost REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            # checks
            if self.is_postgres:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checks (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        check_name TEXT NOT NULL,
                        passed BOOLEAN,
                        message TEXT
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        check_name TEXT NOT NULL,
                        passed INTEGER,
                        message TEXT
                    )
                    """
                )

            # feedback
            if self.is_postgres:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        rating INTEGER,
                        comment TEXT,
                        reference_answer TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        rating INTEGER,
                        comment TEXT,
                        reference_answer TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            # ground_truth_dataset
            if self.is_postgres:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ground_truth_dataset (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        question_text TEXT NOT NULL,
                        expected_answer TEXT,
                        company_name TEXT,
                        cik TEXT,
                        form_type TEXT,
                        filing_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ground_truth_dataset (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        question_text TEXT NOT NULL,
                        expected_answer TEXT,
                        company_name TEXT,
                        cik TEXT,
                        form_type TEXT,
                        filing_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    def insert_log(self, rec: LLMLogRecord) -> int:
        with self.cursor() as cur:
            if self.is_postgres:
                cur.execute(
                    """
                    INSERT INTO llm_logs (
                        filepath, agent_name, provider, model, user_prompt, instructions,
                        total_input_tokens, total_output_tokens, assistant_answer,
                        input_cost, output_cost, total_cost, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                    """,
                    (
                        rec.filepath, rec.agent_name, rec.provider, rec.model,
                        rec.user_prompt, rec.instructions,
                        rec.total_input_tokens, rec.total_output_tokens, rec.assistant_answer,
                        rec.input_cost, rec.output_cost, rec.total_cost, rec.created_at or datetime.now()
                    )
                )
                row = cur.fetchone()
                return row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO llm_logs (
                        filepath, agent_name, provider, model, user_prompt, instructions,
                        total_input_tokens, total_output_tokens, assistant_answer,
                        input_cost, output_cost, total_cost, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec.filepath, rec.agent_name, rec.provider, rec.model,
                        rec.user_prompt, rec.instructions,
                        rec.total_input_tokens, rec.total_output_tokens, rec.assistant_answer,
                        rec.input_cost, rec.output_cost, rec.total_cost, rec.created_at or datetime.now()
                    )
                )
                return cur.lastrowid

    def insert_checks(self, checks: Iterable[CheckResult]) -> None:
        with self.cursor() as cur:
            for check in checks:
                if self.is_postgres:
                    cur.execute(
                        "INSERT INTO checks (log_id, check_name, passed, message) VALUES (%s, %s, %s, %s)",
                        (check.log_id, check.check_name.value, check.passed, check.message)
                    )
                else:
                    cur.execute(
                        "INSERT INTO checks (log_id, check_name, passed, message) VALUES (?, ?, ?, ?)",
                        (check.log_id, check.check_name.value, check.passed, check.message)
                    )

    def insert_feedback(self, feedback: Feedback) -> int:
        with self.cursor() as cur:
            if self.is_postgres:
                cur.execute(
                    """
                    INSERT INTO feedback (log_id, rating, comment, reference_answer, created_at)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (feedback.log_id, feedback.rating, feedback.comment, feedback.reference_answer, feedback.created_at or datetime.now())
                )
                row = cur.fetchone()
                return row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO feedback (log_id, rating, comment, reference_answer, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (feedback.log_id, feedback.rating, feedback.comment, feedback.reference_answer, feedback.created_at or datetime.now())
                )
                return cur.lastrowid

    def list_logs(self, limit: int = 100, provider: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.cursor() as cur:
            conditions = []
            params = []
            if provider:
                conditions.append(f"provider = {self._param}")
                params.append(provider)
            if model:
                conditions.append(f"model = {self._param}")
                params.append(model)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"SELECT * FROM llm_logs{where_clause} ORDER BY created_at DESC LIMIT {self._param}"
            params.append(limit)
            
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_log(self, log_id: int) -> Optional[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(f"SELECT * FROM llm_logs WHERE id = {self._param}", (log_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_checks(self, log_id: int) -> List[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(f"SELECT * FROM checks WHERE log_id = {self._param} ORDER BY check_name", (log_id,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_feedback(self, log_id: int) -> List[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(f"SELECT * FROM feedback WHERE log_id = {self._param} ORDER BY created_at DESC", (log_id,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_ground_truth_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(f"SELECT * FROM ground_truth_dataset ORDER BY created_at DESC LIMIT {self._param}", (limit,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def insert_ground_truth_entry(self, log_id: int, question_text: str, expected_answer: Optional[str] = None,
                                  company_name: Optional[str] = None, cik: Optional[str] = None,
                                  form_type: Optional[str] = None, filing_date: Optional[str] = None) -> int:
        with self.cursor() as cur:
            if self.is_postgres:
                cur.execute(
                    """
                    INSERT INTO ground_truth_dataset (
                        log_id, question_text, expected_answer, company_name, cik, form_type, filing_date, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (log_id, question_text, expected_answer, company_name, cik, form_type, filing_date, datetime.now())
                )
                row = cur.fetchone()
                return row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO ground_truth_dataset (
                        log_id, question_text, expected_answer, company_name, cik, form_type, filing_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (log_id, question_text, expected_answer, company_name, cik, form_type, filing_date, datetime.now())
                )
                return cur.lastrowid

