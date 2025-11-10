from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Optional

from .schemas import LLMLogRecord, CheckResult, Feedback


class Database:
    """Lightweight DB layer with Postgres support and SQLite fallback.

    Uses the `DATABASE_URL` env var when provided. Examples:
    - postgresql://user:pass@host:5432/dbname
    - postgres://user:pass@host:5432/dbname
    - sqlite:///path/to/file.db (or omitted -> ./monitoring.db)
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            # default to local sqlite file in project
            self.database_url = "sqlite:///monitoring.db"

        self._driver = None  # "sqlite" | "postgres"
        self._conn = None
        self._param = "?"  # paramstyle placeholder

    def connect(self):
        if self._conn:
            return self._conn

        if self.database_url.startswith("sqlite://"):
            self._driver = "sqlite"
            db_path = self.database_url.split("sqlite:///")[-1]
            self._conn = sqlite3.connect(db_path, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._param = "?"
        elif self.database_url.startswith("postgres://") or self.database_url.startswith(
            "postgresql://"
        ):
            self._driver = "postgres"
            # Try psycopg (v3), then psycopg2
            conn = None
            try:
                import psycopg

                conn = psycopg.connect(self.database_url)
                conn.autocommit = True
            except Exception:
                try:
                    import psycopg2  # type: ignore

                    conn = psycopg2.connect(self.database_url)
                    conn.autocommit = True
                except Exception as e:  # pragma: no cover
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
                        raw_json TEXT,
                        input_cost NUMERIC,
                        output_cost NUMERIC,
                        total_cost NUMERIC,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                # eval_checks
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_checks (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        check_name TEXT NOT NULL,
                        passed BOOLEAN,
                        score DOUBLE PRECISION,
                        details TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                # feedback
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id SERIAL PRIMARY KEY,
                        log_id INTEGER NOT NULL REFERENCES llm_logs(id) ON DELETE CASCADE,
                        is_good BOOLEAN NOT NULL,
                        comments TEXT,
                        reference_answer TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            else:
                # SQLite
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
                        raw_json TEXT,
                        input_cost NUMERIC,
                        output_cost NUMERIC,
                        total_cost NUMERIC,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL,
                        check_name TEXT NOT NULL,
                        passed INTEGER,
                        score REAL,
                        details TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (log_id) REFERENCES llm_logs(id) ON DELETE CASCADE
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL,
                        is_good INTEGER NOT NULL,
                        comments TEXT,
                        reference_answer TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (log_id) REFERENCES llm_logs(id) ON DELETE CASCADE
                    );
                    """
                )

        # Backfill migration for existing llm_logs without cost columns
        self._ensure_cost_columns()

    def _ensure_cost_columns(self) -> None:
        with self.cursor() as cur:
            needed = ["input_cost", "output_cost", "total_cost"]
            existing = set()
            if self.is_postgres:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name='llm_logs';
                    """
                )
                existing = {row[0] for row in cur.fetchall()}
                for col in needed:
                    if col not in existing:
                        cur.execute(f"ALTER TABLE llm_logs ADD COLUMN {col} NUMERIC;")
                # Ensure numeric type if previously text
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name='llm_logs'
                      AND column_name IN ('input_cost','output_cost','total_cost');
                    """
                )
                for name, dtype in cur.fetchall():
                    if dtype.lower() not in ("numeric", "decimal"):
                        cur.execute(
                            f"ALTER TABLE llm_logs ALTER COLUMN {name} TYPE NUMERIC USING NULLIF({name},'')::numeric;"
                        )
            else:
                cur.execute("PRAGMA table_info(llm_logs);")
                existing = {row[1] for row in cur.fetchall()}
                for col in needed:
                    if col not in existing:
                        cur.execute(f"ALTER TABLE llm_logs ADD COLUMN {col} NUMERIC;")

    def insert_log(self, rec: LLMLogRecord) -> int:
        with self.cursor() as cur:
            sql = (
                "INSERT INTO llm_logs (filepath, agent_name, provider, model, user_prompt, instructions, "
                "total_input_tokens, total_output_tokens, assistant_answer, raw_json, input_cost, output_cost, total_cost) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                if self.is_postgres
                else "INSERT INTO llm_logs (filepath, agent_name, provider, model, user_prompt, instructions, "
                "total_input_tokens, total_output_tokens, assistant_answer, raw_json, input_cost, output_cost, total_cost) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            )
            # Adapt Decimals depending on driver
            def _adapt_decimal(val):
                if val is None:
                    return None
                if self.is_postgres:
                    return val  # psycopg handles Decimal
                # sqlite: store as string to preserve precision
                return str(val)

            params = (
                rec.filepath,
                rec.agent_name,
                rec.provider,
                rec.model,
                rec.user_prompt,
                rec.instructions,
                rec.total_input_tokens,
                rec.total_output_tokens,
                rec.assistant_answer,
                rec.raw_json,
                _adapt_decimal(rec.input_cost),
                _adapt_decimal(rec.output_cost),
                _adapt_decimal(rec.total_cost),
            )
            cur.execute(sql, params)
            if self.is_postgres:
                # fetch id
                cur.execute("SELECT currval(pg_get_serial_sequence('llm_logs','id'))")
                new_id = cur.fetchone()[0]
            else:
                new_id = cur.lastrowid
        return int(new_id)

    # --------- Read helpers for app ----------
    def list_logs(self, limit: int = 100, offset: int = 0, provider: Optional[str] = None, model: Optional[str] = None):
        where = []
        params = []
        if provider:
            where.append("provider = %s" if self.is_postgres else "provider = ?")
            params.append(provider)
        if model:
            where.append("model = %s" if self.is_postgres else "model = ?")
            params.append(model)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        limit_sql = "LIMIT %s OFFSET %s" if self.is_postgres else "LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        sql = (
            "SELECT id, created_at, filepath, agent_name, provider, model, user_prompt, total_input_tokens, total_output_tokens, total_cost "
            f"FROM llm_logs{where_sql} ORDER BY id DESC {limit_sql}"
        )
        with self.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        # Normalize rows to dicts
        result = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                d = dict(r)
            else:
                (
                    id_, created_at, filepath, agent_name, provider_, model_, user_prompt,
                    tin, tout, total_cost,
                ) = r
                d = {
                    "id": id_,
                    "created_at": created_at,
                    "filepath": filepath,
                    "agent_name": agent_name,
                    "provider": provider_,
                    "model": model_,
                    "user_prompt": user_prompt,
                    "total_input_tokens": tin,
                    "total_output_tokens": tout,
                    "total_cost": total_cost,
                }
            result.append(d)
        return result

    def get_log(self, log_id: int):
        sql = (
            "SELECT id, created_at, filepath, agent_name, provider, model, user_prompt, instructions, total_input_tokens, total_output_tokens, assistant_answer, input_cost, output_cost, total_cost "
            "FROM llm_logs WHERE id = %s"
            if self.is_postgres
            else "SELECT id, created_at, filepath, agent_name, provider, model, user_prompt, instructions, total_input_tokens, total_output_tokens, assistant_answer, input_cost, output_cost, total_cost FROM llm_logs WHERE id = ?"
        )
        with self.cursor() as cur:
            cur.execute(sql, (log_id,))
            r = cur.fetchone()
        if r is None:
            return None
        if isinstance(r, sqlite3.Row):
            return dict(r)
        (
            id_, created_at, filepath, agent_name, provider_, model_, user_prompt, instructions,
            tin, tout, assistant_answer, in_cost, out_cost, total_cost,
        ) = r
        return {
            "id": id_,
            "created_at": created_at,
            "filepath": filepath,
            "agent_name": agent_name,
            "provider": provider_,
            "model": model_,
            "user_prompt": user_prompt,
            "instructions": instructions,
            "total_input_tokens": tin,
            "total_output_tokens": tout,
            "assistant_answer": assistant_answer,
            "input_cost": in_cost,
            "output_cost": out_cost,
            "total_cost": total_cost,
        }

    def get_checks(self, log_id: int):
        sql = (
            "SELECT check_name, passed, score, details, created_at FROM eval_checks WHERE log_id = %s ORDER BY id ASC"
            if self.is_postgres
            else "SELECT check_name, passed, score, details, created_at FROM eval_checks WHERE log_id = ? ORDER BY id ASC"
        )
        with self.cursor() as cur:
            cur.execute(sql, (log_id,))
            rows = cur.fetchall()
        result = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                d = dict(r)
            else:
                check_name, passed, score, details, created_at = r
                d = {
                    "check_name": check_name,
                    "passed": passed,
                    "score": score,
                    "details": details,
                    "created_at": created_at,
                }
            # Normalize passed for SQLite (0/1 -> bool)
            if isinstance(d.get("passed"), int):
                d["passed"] = bool(d["passed"]) if d["passed"] is not None else None
            result.append(d)
        return result

    def get_feedback(self, log_id: int):
        sql = (
            "SELECT is_good, comments, reference_answer, created_at FROM feedback WHERE log_id = %s ORDER BY id DESC"
            if self.is_postgres
            else "SELECT is_good, comments, reference_answer, created_at FROM feedback WHERE log_id = ? ORDER BY id DESC"
        )
        with self.cursor() as cur:
            cur.execute(sql, (log_id,))
            rows = cur.fetchall()
        result = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                d = dict(r)
            else:
                is_good, comments, ref, created_at = r
                d = {
                    "is_good": is_good,
                    "comments": comments,
                    "reference_answer": ref,
                    "created_at": created_at,
                }
            if isinstance(d.get("is_good"), int):
                d["is_good"] = bool(d["is_good"]) if d["is_good"] is not None else None
            result.append(d)
        return result

    def insert_checks(self, checks: Iterable[CheckResult]) -> None:
        checks = list(checks)
        if not checks:
            return
        with self.cursor() as cur:
            sql = (
                "INSERT INTO eval_checks (log_id, check_name, passed, score, details) VALUES (%s,%s,%s,%s,%s)"
                if self.is_postgres
                else "INSERT INTO eval_checks (log_id, check_name, passed, score, details) VALUES (?,?,?,?,?)"
            )
            for c in checks:
                # normalize booleans for sqlite
                passed = c.passed
                if not self.is_postgres and passed is not None:
                    passed = 1 if passed else 0
                cur.execute(
                    sql,
                    (
                        c.log_id,
                        getattr(c.check_name, "value", str(c.check_name)),
                        passed,
                        c.score,
                        c.details,
                    ),
                )

    def insert_feedback(self, fb: Feedback) -> int:
        with self.cursor() as cur:
            sql = (
                "INSERT INTO feedback (log_id, is_good, comments, reference_answer) VALUES (%s,%s,%s,%s)"
                if self.is_postgres
                else "INSERT INTO feedback (log_id, is_good, comments, reference_answer) VALUES (?,?,?,?)"
            )
            is_good = fb.is_good
            if not self.is_postgres:
                is_good = 1 if fb.is_good else 0
            cur.execute(
                sql,
                (
                    fb.log_id,
                    is_good,
                    fb.comments,
                    fb.reference_answer,
                ),
            )
            if self.is_postgres:
                cur.execute("SELECT currval(pg_get_serial_sequence('feedback','id'))")
                new_id = cur.fetchone()[0]
            else:
                new_id = cur.lastrowid
        return int(new_id)
