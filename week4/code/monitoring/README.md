Monitoring: Log Ingest, Eval, and Feedback

Overview
- Watches a logs/ directory (or other sources later) and ingests JSON logs.
- Extracts user prompt, instructions, model, and total token usage.
- Stores records in Postgres (via DATABASE_URL) with SQLite fallback.
- Runs rule-based evaluations and stores per-check results.
- Supports saving user feedback (thumbs up/down, comments, reference answer).
 - Calculates estimated cost using genai_prices (if installed) and stores it per log.

Environment
- LOGS_DIR: directory to monitor (default: logs)
- DATABASE_URL: e.g. postgresql://user:pass@host:5432/db (default: sqlite:///monitoring.db)
- LOG_FILE_GLOB: file pattern (default: *.json)
- PROCESSED_PREFIX: rename prefix after success (default: _)
- POLL_SECONDS: watch mode sleep (default: 2)
 - DEBUG or MONITORING_DEBUG: set to 1/true to enable debug logs

Run
- One-shot: python -m monitoring.runner
- Watch mode: python -m monitoring.runner --watch
- Debug: add --debug flag or set DEBUG=1

Streamlit App
- Launch: streamlit run monitoring/app.py
- The app reads from the database only (no log polling)
- Views: logs list, details (prompt/instructions/answer), eval checks, feedback viewer + form

Docker Compose (Postgres, App, Poller)
- Ensure Docker is installed, then from the repo root:
  - Start everything: `docker compose up -d`
  - Or start only DB: `docker compose up -d postgres`
  - Then App: `docker compose up -d app` (opens on http://localhost:8501)
  - Then Poller: `docker compose up -d poller`

What it runs
- `postgres`: Postgres 16 with db `monitoring`, user/pass `monitoring`.
- `app`: Streamlit UI, env `DATABASE_URL=postgresql://monitoring:monitoring@postgres:5432/monitoring`.
- `poller`: Runner in watch mode, same `DATABASE_URL` and `LOGS_DIR=/app/logs`.

Data & Logs
- Your project directory is mounted into the containers at `/app`.
- Place JSON logs in `logs/` locally; the poller ingests and prefixes processed files with `_`.
- Postgres data persists in the `pgdata` Docker volume.

Common commands
- Check services: `docker compose ps`
- See logs: `docker compose logs -f app` and `docker compose logs -f poller`
- Stop: `docker compose down` (add `-v` to remove the Postgres volume)

Customizing
- To change DB credentials/host, edit `docker-compose.yml` and update `DATABASE_URL` for `app` and `poller`.
- To compute prices via genai_prices, install it in the containers (e.g., extend the pip install lines) or in your local environment if not containerized.

Run Locally (outside Docker) with Postgres
- Start Postgres via Compose: `docker compose up -d postgres`
- Set your local env to use localhost (not the service name `postgres`):
  - `export DATABASE_URL=postgresql://monitoring:monitoring@localhost:5432/monitoring`
- Then run locally:
  - Poller: `python -m monitoring.runner --watch --debug`
  - App: `streamlit run monitoring/app.py`

Note: The hostname `postgres` only resolves inside the Docker Compose network. When running from your host environment (e.g., uv run, python, streamlit on your machine), use `localhost` instead.

Grafana Dashboards
- Compose includes a `grafana` service on http://localhost:3000 (admin/admin by default).
- It auto-loads a Postgres datasource and the following dashboards:
  - "LLM Monitoring - Overview":
    - Total requests, tokens in/out, total cost
    - Requests over time
    - Tokens over time (in/out)
    - Top models by requests
    - Last 5 requests table
  - "LLM Monitoring - Feedback":
    - Good feedback % and counts
    - Recent feedback table (joined with logs)
  - "LLM Monitoring - Eval":
    - Total eval checks
    - Pass rate by check
    - Checks over time
    - Recent checks table
- Files live under `monitoring/grafana/` (provisioning + dashboards JSON). Edit queries as needed.

Fake Data Generator
- To generate sample data into Postgres for dashboards:
  - Docker: `docker compose run --rm faker`
  - Locally (using your env `DATABASE_URL`): `python -m monitoring.fake_data --count 300 --hours 24`
  - Options:
    - `--count`: number of fake logs to insert (default 200)
    - `--hours`: spread timestamps across last N hours (default 24)
    - `--feedback-rate`: probability a log gets feedback (default 0.5)
    - `--good-ratio`: probability feedback is good among those with feedback (default 0.65)

Schema
- llm_logs: one row per log file
- eval_checks: multiple rows per log (one per CheckName)
- feedback: user feedback linked to a log

Postgres
- Provide DATABASE_URL. Requires psycopg (v3) or psycopg2 installed.

Pricing
- Optional dependency: genai_prices
- If available, costs are computed and stored as text in llm_logs.input_cost, output_cost, total_cost.
  Example internal usage:
  from genai_prices import Usage, calc_price
  token_usage = Usage(input_tokens=..., output_tokens=...)
  price_data = calc_price(token_usage, provider_id=..., model_ref=...)
  # Decimal fields on price_data: input_price, output_price, total_price

Feedback API (Python)
from monitoring.db import Database
from monitoring.feedback import save_feedback

db = Database()  # uses env DATABASE_URL
db.ensure_schema()
save_feedback(db, log_id=1, is_good=True, comments="Looks good", reference_answer=None)

Replaceable Sources
- The LocalDirectorySource implements a simple filesystem watcher via polling.
- To add S3/Kafka later, implement LogSource.iter_files() and mark_processed().
