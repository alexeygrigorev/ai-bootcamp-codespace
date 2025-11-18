"""
Log processing runner for monitoring system.

Watches a logs directory and ingests JSON logs into the database.
"""

import sys
import os
from pathlib import Path
from typing import Optional
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.db import Database
from monitoring.parser import parse_log_file
from monitoring.evaluator import RuleBasedEvaluator
from monitoring.schemas import LLMLogRecord


def _calc_prices(provider: str | None, model: str | None, input_tokens: int | None, output_tokens: int | None):
    """Calculate estimated costs using genai_prices if available."""
    try:
        from genai_prices import get_price
        if provider and model and input_tokens is not None and output_tokens is not None:
            price = get_price(provider, model, input_tokens, output_tokens)
            if price:
                return Decimal(str(price.get("input_cost", 0))), Decimal(str(price.get("output_cost", 0))), Decimal(str(price.get("total_cost", 0)))
    except ImportError:
        pass
    except Exception:
        pass
    return None


def process_file(db: Database, evaluator: RuleBasedEvaluator, source: Path, path: Path, debug: bool = False) -> Optional[int]:
    """Process a single log file."""
    try:
        rec = parse_log_file(path)
        
        # Price calculation
        prices = _calc_prices(rec.provider, rec.model, rec.total_input_tokens, rec.total_output_tokens)
        if prices is not None:
            rec.input_cost, rec.output_cost, rec.total_cost = prices

        if debug:
            print(
                f"[monitoring][debug] file={path}",
                f"agent={rec.agent_name}",
                f"provider={rec.provider}",
                f"model={rec.model}",
                f"tokens=({rec.total_input_tokens}, {rec.total_output_tokens})",
                f"costs=({rec.input_cost}, {rec.output_cost}, {rec.total_cost})",
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
        
        # Mark as processed by moving to processed subdirectory
        processed_dir = source / "_processed"
        processed_dir.mkdir(exist_ok=True)
        processed_path = processed_dir / path.name
        path.rename(processed_path)
        
        if debug:
            print(f"[monitoring][debug] moved to {processed_path}")
        
        return log_id
    except Exception as e:
        print(f"[monitoring] Failed to process {path}: {e}", file=sys.stderr)
        return None


def run_once(debug: bool = False) -> None:
    """Run log processing once."""
    # Default to logs directory relative to project root
    default_logs = Path(__file__).parent.parent / "logs"
    logs_dir = Path(os.environ.get("LOGS_DIR", str(default_logs)))
    db_url = os.environ.get("DATABASE_URL")
    
    db = Database(db_url)
    db.ensure_schema()
    
    evaluator = RuleBasedEvaluator()
    
    if not logs_dir.exists():
        print(f"[monitoring] Logs directory does not exist: {logs_dir}")
        return
    
    log_files = list(logs_dir.glob("*.json"))
    
    if not log_files:
        if debug:
            print("[monitoring][debug] No log files found")
        return
    
    print(f"[monitoring] Processing {len(log_files)} log files...")
    
    for log_file in log_files:
        if log_file.name.startswith("_"):
            continue  # Skip already processed files
        process_file(db, evaluator, logs_dir, log_file, debug=debug)
    
    print("[monitoring] Processing complete")


def run_watch(debug: bool = False) -> None:
    """Run log processing in watch mode."""
    import time
    
    poll_seconds = int(os.environ.get("POLL_SECONDS", "2"))
    
    print(f"[monitoring] Starting watch mode (polling every {poll_seconds} seconds)")
    print("[monitoring] Press Ctrl+C to stop")
    
    try:
        while True:
            run_once(debug=debug)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\n[monitoring] Stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process SEC agent logs")
    parser.add_argument("--watch", action="store_true", help="Watch mode (continuous polling)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    if args.watch:
        run_watch(debug=args.debug)
    else:
        run_once(debug=args.debug)


if __name__ == "__main__":
    main()

