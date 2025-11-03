from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from .config import get_settings
from .db import Database
from .evaluator import RuleBasedEvaluator
from .parser import parse_log_file
from .sources import LocalDirectorySource
from decimal import Decimal


def _calc_prices(provider: str | None, model: str | None, input_tokens: int | None, output_tokens: int | None):
    try:
        from genai_prices import Usage, calc_price  # type: ignore
    except Exception:
        return None

    it = int(input_tokens or 0)
    ot = int(output_tokens or 0)
    try:
        token_usage = Usage(input_tokens=it, output_tokens=ot)
        price_data = calc_price(
            token_usage,
            provider_id=provider,
            model_ref=model,
        )
        # price_data.* are Decimal
        return (
            price_data.input_price,
            price_data.output_price,
            price_data.total_price,
        )
    except Exception:
        return None


def process_file(db: Database, evaluator: RuleBasedEvaluator, source: LocalDirectorySource, path, debug: bool = False) -> Optional[int]:
    try:
        rec = parse_log_file(str(path))
        # Price calculation
        prices = _calc_prices(rec.provider, rec.model, rec.total_input_tokens, rec.total_output_tokens)
        if prices is not None:
            rec.input_cost, rec.output_cost, rec.total_cost = prices

        if debug:
            print(
                "[monitoring][debug] file=", path,
                "agent=", rec.agent_name,
                "provider=", rec.provider,
                "model=", rec.model,
                "tokens=", (rec.total_input_tokens, rec.total_output_tokens),
                "costs=", (rec.input_cost, rec.output_cost, rec.total_cost),
            )

        log_id = db.insert_log(rec)
        checks = evaluator.evaluate(log_id, rec)
        db.insert_checks(checks)
        if debug:
            ok = sum(1 for c in checks if c.passed is True)
            unknown = sum(1 for c in checks if c.passed is None)
            fail = sum(1 for c in checks if c.passed is False)
            print(
                f"[monitoring][debug] log_id={log_id} checks total={len(checks)} pass={ok} fail={fail} n/a={unknown}"
            )
        source.mark_processed(path)
        if debug:
            print(f"[monitoring][debug] renamed to processed with prefix")
        return log_id
    except Exception as e:  # pylint: disable=broad-except
        # Do not rename on failure; just print and continue
        print(f"[monitoring] Failed to process {path}: {e}", file=sys.stderr)
        return None


def run_once(debug: bool = False) -> None:
    settings = get_settings()
    db = Database(settings.database_url)
    db.ensure_schema()
    if debug or settings.debug:
        print(f"[monitoring][debug] driver={'postgres' if db.is_postgres else 'sqlite'}")

    source = LocalDirectorySource(settings.logs_dir, pattern=settings.file_glob, processed_prefix=settings.processed_prefix)
    evaluator = RuleBasedEvaluator()

    count = 0
    for path in source.iter_files():
        if process_file(db, evaluator, source, path, debug=debug or settings.debug) is not None:
            count += 1
    print(f"[monitoring] Processed {count} file(s)")


def run_watch(debug: bool = False) -> None:
    settings = get_settings()
    db = Database(settings.database_url)
    db.ensure_schema()
    if debug or settings.debug:
        print(f"[monitoring][debug] driver={'postgres' if db.is_postgres else 'sqlite'}")

    source = LocalDirectorySource(settings.logs_dir, pattern=settings.file_glob, processed_prefix=settings.processed_prefix)
    evaluator = RuleBasedEvaluator()

    print(f"[monitoring] Watching {settings.logs_dir} for {settings.file_glob} (prefix '{settings.processed_prefix}')")
    while True:
        processed_any = False
        for path in source.iter_files():
            if process_file(db, evaluator, source, path, debug=debug or settings.debug) is not None:
                processed_any = True
        if not processed_any:
            time.sleep(settings.poll_seconds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Monitor logs and store them in Postgres (SQLite fallback)")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode (poll directory)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output during processing")
    args = parser.parse_args(argv)

    if args.watch:
        run_watch(debug=args.debug)
    else:
        run_once(debug=args.debug)


if __name__ == "__main__":
    main()
