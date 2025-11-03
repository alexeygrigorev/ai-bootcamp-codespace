from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple

from .db import Database
from .schemas import LLMLogRecord, CheckResult, CheckName


PROVIDERS_MODELS = [
    ("openai", "gpt-4o-mini"),
    ("openai", "gpt-4o"),
    ("anthropic", "claude-3-5-sonnet"),
    ("google", "gemini-1.5-pro"),
]


# Very rough per-token pricing (USD) for fake data; not authoritative.
# input_rate and output_rate are price per 1 token.
PRICING = {
    ("openai", "gpt-4o-mini"): (Decimal("0.00000015"), Decimal("0.0000006")),
    ("openai", "gpt-4o"): (Decimal("0.0000005"), Decimal("0.0000015")),
    ("anthropic", "claude-3-5-sonnet"): (Decimal("0.0000008"), Decimal("0.0000024")),
    ("google", "gemini-1.5-pro"): (Decimal("0.0000005"), Decimal("0.0000015")),
}


def rand_text(n: int) -> str:
    words = (
        "monitor", "evaluate", "drift", "tokens", "cost", "pipeline", "dashboard", "check", "quality",
        "feedback", "reference", "citations", "search", "tool", "answer", "instructions",
    )
    return " ".join(random.choice(words) for _ in range(n)).capitalize() + "."


def calc_cost(provider: str, model: str, tin: int, tout: int) -> Tuple[Decimal, Decimal, Decimal]:
    rate_in, rate_out = PRICING.get((provider, model), (Decimal("0.0000005"), Decimal("0.000001")))
    ic = (Decimal(tin) * rate_in).quantize(Decimal("0.000001"))
    oc = (Decimal(tout) * rate_out).quantize(Decimal("0.000001"))
    tc = (ic + oc).quantize(Decimal("0.000001"))
    return ic, oc, tc


def spread_times(count: int, hours: int) -> List[datetime]:
    now = datetime.utcnow()
    start = now - timedelta(hours=hours)
    if count <= 1:
        return [now]
    step = (now - start) / (count - 1)
    return [start + i * step for i in range(count)]


def update_created_at(db: Database, table: str, row_id: int, ts: datetime) -> None:
    sql = f"UPDATE {table} SET created_at = %s WHERE id = %s" if db.is_postgres else f"UPDATE {table} SET created_at = ? WHERE id = ?"
    with db.cursor() as cur:
        cur.execute(sql, (ts, row_id))


def generate(count: int, hours: int, feedback_rate: float, good_ratio: float) -> None:
    db = Database()
    db.ensure_schema()

    times = spread_times(count, hours)

    total_inserted = 0
    for i in range(count):
        provider, model = random.choice(PROVIDERS_MODELS)
        user_prompt = f"How do I {random.choice(['monitor','audit','evaluate','tune'])} {random.choice(['data drift','LLM costs','tool usage','feedback'])}?"
        instructions = "You are a search assistant. Provide references and keep the answer clear."
        tin = random.randint(500, 22000)
        tout = random.randint(100, 4000)
        ic, oc, tc = calc_cost(provider, model, tin, tout)

        rec = LLMLogRecord(
            filepath=f"logs/fake_{i:04d}.json",
            agent_name=random.choice(["search", "answer", "support"]),
            provider=provider,
            model=model,
            user_prompt=user_prompt,
            instructions=instructions,
            total_input_tokens=tin,
            total_output_tokens=tout,
            assistant_answer=rand_text(random.randint(40, 120)),
            raw_json=None,
            input_cost=ic,
            output_cost=oc,
            total_cost=tc,
        )
        log_id = db.insert_log(rec)
        update_created_at(db, "llm_logs", log_id, times[i])

        # Checks
        checks = []
        # Slightly better pass chance for smaller tokens
        base = 0.6 if tin < 5000 else 0.4
        checks.append(CheckResult(log_id, CheckName.instructions_follow, passed=random.random() < base + 0.1, details=None))
        checks.append(CheckResult(log_id, CheckName.instructions_avoid, passed=random.random() < base, details=None))
        checks.append(CheckResult(log_id, CheckName.answer_clear, passed=random.random() < base + 0.15, details=None))
        checks.append(CheckResult(log_id, CheckName.answer_match, passed=random.random() < base + 0.05, score=random.random(), details=None))
        checks.append(CheckResult(log_id, CheckName.answer_citations, passed=random.random() < base, details=None))
        checks.append(CheckResult(log_id, CheckName.completeness, passed=random.random() < base + 0.1, details=None))
        checks.append(CheckResult(log_id, CheckName.tool_call_search, passed=random.random() < 0.8, details=None))
        db.insert_checks(checks)

        # Backdate checks created_at roughly near the log time
        # (Keep it the same for simplicity)
        if db.is_postgres:
            with db.cursor() as cur:
                cur.execute("UPDATE eval_checks SET created_at = %s WHERE log_id = %s", (times[i], log_id))
        else:
            with db.cursor() as cur:
                cur.execute("UPDATE eval_checks SET created_at = ? WHERE log_id = ?", (times[i], log_id))

        # Feedback
        if random.random() < feedback_rate:
            is_good = random.random() < good_ratio
            from .feedback import save_feedback

            fb_id = save_feedback(db, log_id=log_id, is_good=is_good, comments=random.choice([
                "Looks fine", "Missed references", "Great explanation", "Too verbose", "Off-topic"
            ]), reference_answer=None)
            # Backdate feedback timestamp
            if db.is_postgres:
                with db.cursor() as cur:
                    cur.execute("UPDATE feedback SET created_at = %s WHERE id = %s", (times[i], fb_id))
            else:
                with db.cursor() as cur:
                    cur.execute("UPDATE feedback SET created_at = ? WHERE id = ?", (times[i], fb_id))

        total_inserted += 1

    print(f"[faker] Inserted {total_inserted} fake logs over last {hours} hours.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate fake logs into the monitoring database")
    p.add_argument("--count", type=int, default=200, help="Number of logs to generate")
    p.add_argument("--hours", type=int, default=24, help="Spread data across last N hours")
    p.add_argument("--feedback-rate", type=float, default=0.5, help="Probability a log gets feedback")
    p.add_argument("--good-ratio", type=float, default=0.65, help="Among feedback, chance of good feedback")
    args = p.parse_args(argv)

    generate(args.count, args.hours, args.feedback_rate, args.good_ratio)


if __name__ == "__main__":
    main()

