from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional

import streamlit as st

from monitoring.db import Database


def format_dec(d: Optional[Decimal]) -> str:
    if d is None:
        return "-"
    try:
        # Show up to 6 decimal places, trim trailing zeros
        s = f"{d:.6f}"
        return s.rstrip("0").rstrip(".")
    except Exception:
        return str(d)


def load_distinct(db: Database, col: str):
    assert col in {"provider", "model"}
    sql = f"SELECT DISTINCT {col} FROM llm_logs WHERE {col} IS NOT NULL ORDER BY {col} ASC"
    with db.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    vals = []
    for r in rows:
        vals.append(r[0] if not hasattr(r, "keys") else r[col])
    return [v for v in vals if v]


def main():
    st.set_page_config(page_title="LLM Log Monitor", layout="wide")

    st.title("LLM Log Monitor")
    st.caption("Browse ingested logs, view evaluation results, and add feedback.")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///monitoring.db")
    db = Database(db_url)
    db.ensure_schema()

    with st.sidebar:
        st.subheader("Filters")
        try:
            providers = [""] + load_distinct(db, "provider")
            models = [""] + load_distinct(db, "model")
        except Exception:
            providers, models = [""], [""]
        provider = st.selectbox("Provider", providers, index=0, format_func=lambda x: x or "All")
        model = st.selectbox("Model", models, index=0, format_func=lambda x: x or "All")
        limit = st.number_input("Page Size", min_value=10, max_value=1000, value=100, step=10)
        st.markdown(f"DB: `{db_url}`")

    logs = db.list_logs(limit=int(limit), provider=provider or None, model=model or None)

    # Build selection list
    options = []
    for row in logs:
        label = f"#{row['id']} • {row.get('model') or '?'} • {row.get('provider') or '?'} • {str(row.get('created_at'))[:19]}"
        options.append((row["id"], label))

    st.subheader("Logs")
    if not options:
        st.info("No logs found.")
        return

    selected_label = st.selectbox("Select a log", options=[lbl for _, lbl in options])
    selected_id = next((id_ for id_, lbl in options if lbl == selected_label), options[0][0])

    # Load selected
    log = db.get_log(selected_id)
    checks = db.get_checks(selected_id)
    feedbacks = db.get_feedback(selected_id)

    # Overview
    st.markdown("**Overview**")
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        st.text("Provider")
        st.write(log.get("provider") or "-")
        st.text("Model")
        st.write(log.get("model") or "-")
    with col2:
        st.text("Tokens (in/out)")
        st.write(f"{log.get('total_input_tokens') or 0} / {log.get('total_output_tokens') or 0}")
        st.text("Total Cost")
        st.write(format_dec(log.get("total_cost")))
    with col3:
        st.text("Input Cost")
        st.write(format_dec(log.get("input_cost")))
        st.text("Output Cost")
        st.write(format_dec(log.get("output_cost")))
    with col4:
        st.text("Agent")
        st.write(log.get("agent_name") or "-")
        st.text("Created At")
        st.write(str(log.get("created_at"))[:19])

    # Prompt & instructions
    with st.expander("Prompt & Instructions", expanded=True):
        st.markdown("- Prompt:")
        st.code(log.get("user_prompt") or "", language=None)
        st.markdown("- Instructions:")
        st.code(log.get("instructions") or "", language=None)

    # Answer
    with st.expander("Assistant Answer", expanded=False):
        st.write(log.get("assistant_answer") or "")

    # Checks
    st.markdown("**Evaluation Checks**")
    if not checks:
        st.info("No checks for this log.")
    else:
        # Normalize check_name labels for older rows
        def clean_name(name: str) -> str:
            if name and name.startswith("CheckName."):
                return name.split(".", 1)[1]
            return name

        rows = []
        for c in checks:
            rows.append({
                "check_name": clean_name(c.get("check_name")),
                "passed": c.get("passed"),
                "score": c.get("score"),
                "details": c.get("details"),
                "created_at": str(c.get("created_at"))[:19],
            })
        st.dataframe(rows, use_container_width=True)

    # Feedback
    st.markdown("**Feedback**")
    if feedbacks:
        st.write("Existing feedback:")
        fb_rows = [
            {
                "is_good": "👍" if (f.get("is_good") is True or f.get("is_good") == 1) else ("👎" if (f.get("is_good") is False or f.get("is_good") == 0) else "-"),
                "comments": f.get("comments"),
                "reference": f.get("reference_answer"),
                "created_at": str(f.get("created_at"))[:19],
            }
            for f in feedbacks
        ]
        st.dataframe(fb_rows, use_container_width=True)
    else:
        st.info("No feedback yet.")

    st.write("Add feedback:")
    with st.form("feedback_form", clear_on_submit=True):
        is_good = st.radio("Is the answer good?", options=["👍 Yes", "👎 No"], horizontal=True)
        comments = st.text_area("Comments", placeholder="What’s good/bad? Any notes.")
        ref = st.text_area("Reference Answer (optional)")
        submitted = st.form_submit_button("Submit Feedback")
        if submitted:
            ok = True
            try:
                from monitoring.feedback import save_feedback
                good_flag = True if is_good.startswith("👍") else False
                save_feedback(db, log_id=selected_id, is_good=good_flag, comments=comments or None, reference_answer=ref or None)
            except Exception as e:
                ok = False
                st.error(f"Failed to save feedback: {e}")
            if ok:
                st.success("Feedback saved.")
                # Streamlit 1.27+ uses st.rerun(); older versions had experimental_rerun
                if hasattr(st, "rerun"):
                    st.rerun()
                elif hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()


if __name__ == "__main__":
    main()
