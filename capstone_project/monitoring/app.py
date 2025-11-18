"""
Streamlit dashboard for monitoring SEC agent logs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from decimal import Decimal
from typing import Optional

import streamlit as st

# Add parent directory to path so we can import monitoring
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.db import Database
from monitoring.schemas import Feedback


def format_dec(d: Optional[Decimal]) -> str:
    """Format decimal for display."""
    if d is None:
        return "-"
    try:
        s = f"{d:.6f}"
        return s.rstrip("0").rstrip(".")
    except Exception:
        return str(d)


def load_distinct(db: Database, col: str):
    """Load distinct values for a column."""
    assert col in {"provider", "model", "agent_name"}
    sql = f"SELECT DISTINCT {col} FROM llm_logs WHERE {col} IS NOT NULL ORDER BY {col} ASC"
    with db.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    vals = []
    for r in rows:
        vals.append(r[0] if not hasattr(r, "keys") else r[col])
    return [v for v in vals if v]


def main():
    """Main Streamlit app."""
    st.set_page_config(page_title="SEC Agent Monitor", layout="wide")

    st.title("SEC Cybersecurity Agent Monitor")
    st.caption("Browse agent logs, view evaluation results, add feedback, and generate ground truth datasets.")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///capstone_project/monitoring/monitoring.db")
    db = Database(db_url)
    db.ensure_schema()

    with st.sidebar:
        st.subheader("Filters")
        try:
            providers = [""] + load_distinct(db, "provider")
            models = [""] + load_distinct(db, "model")
            agents = [""] + load_distinct(db, "agent_name")
        except Exception:
            providers, models, agents = [""], [""], [""]
        
        provider = st.selectbox("Provider", providers, index=0, format_func=lambda x: x or "All")
        model = st.selectbox("Model", models, index=0, format_func=lambda x: x or "All")
        agent = st.selectbox("Agent", agents, index=0, format_func=lambda x: x or "All")
        limit = st.number_input("Page Size", min_value=10, max_value=1000, value=100, step=10)
        st.markdown(f"DB: `{db_url}`")

    # Filter logs
    logs = db.list_logs(limit=int(limit), provider=provider or None, model=model or None)
    if agent and agent != "":
        logs = [log for log in logs if log.get("agent_name") == agent]

    # Build selection list
    options = []
    for row in logs:
        label = f"#{row['id']} • {row.get('model') or '?'} • {row.get('provider') or '?'} • {str(row.get('created_at'))[:19]}"
        options.append((row["id"], label))

    st.subheader("Logs")
    if not options:
        st.info("No logs found. Run the agent to generate logs, then process them with the monitoring runner.")
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

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Prompt & Response", "Evaluation Checks", "Feedback", "Ground Truth"])

    with tab1:
        st.subheader("User Prompt")
        st.text_area("", log.get("user_prompt") or "", height=100, disabled=True, key="prompt")
        
        st.subheader("Instructions")
        instructions = log.get("instructions") or ""
        st.text_area("", instructions, height=150, disabled=True, key="instructions")
        
        st.subheader("Assistant Answer")
        answer = log.get("assistant_answer") or ""
        st.text_area("", answer, height=400, disabled=True, key="answer")

    with tab2:
        st.subheader("Evaluation Checks")
        if not checks:
            st.info("No evaluation checks found.")
        else:
            for check in checks:
                status = check.get("passed")
                if status is True:
                    st.success(f"✓ {check.get('check_name')}: {check.get('message')}")
                elif status is False:
                    st.error(f"✗ {check.get('check_name')}: {check.get('message')}")
                else:
                    st.info(f"○ {check.get('check_name')}: {check.get('message')}")

    with tab3:
        st.subheader("User Feedback")
        
        # Display existing feedback
        if feedbacks:
            st.write("**Existing Feedback:**")
            for fb in feedbacks:
                rating = fb.get("rating")
                comment = fb.get("comment")
                ref_answer = fb.get("reference_answer")
                created_at = fb.get("created_at")
                
                st.write(f"**Rating:** {rating}/5" if rating else "**Rating:** Not provided")
                if comment:
                    st.write(f"**Comment:** {comment}")
                if ref_answer:
                    st.write(f"**Reference Answer:** {ref_answer}")
                st.write(f"**Date:** {created_at}")
                st.divider()
        
        # Feedback form
        with st.form("feedback_form"):
            st.write("**Add Feedback:**")
            rating = st.slider("Rating (1-5)", min_value=1, max_value=5, value=3)
            comment = st.text_area("Comment (optional)")
            reference_answer = st.text_area("Reference Answer (optional)", height=200)
            
            submitted = st.form_submit_button("Submit Feedback")
            
            if submitted:
                feedback = Feedback(
                    log_id=selected_id,
                    rating=rating,
                    comment=comment if comment else None,
                    reference_answer=reference_answer if reference_answer else None
                )
                db.insert_feedback(feedback)
                st.success("Feedback submitted!")
                st.rerun()

    with tab4:
        st.subheader("Ground Truth Dataset")
        st.write("Add this log entry to the ground truth dataset for evaluation.")
        
        with st.form("ground_truth_form"):
            question_text = st.text_area("Question Text", value=log.get("user_prompt") or "", height=100)
            expected_answer = st.text_area("Expected Answer (optional)", height=200)
            company_name = st.text_input("Company Name (optional)")
            cik = st.text_input("CIK (optional)")
            form_type = st.text_input("Form Type (optional, e.g., 8-K, 10-K)")
            filing_date = st.text_input("Filing Date (optional, YYYY-MM-DD)")
            
            submitted = st.form_submit_button("Add to Ground Truth Dataset")
            
            if submitted:
                db.insert_ground_truth_entry(
                    log_id=selected_id,
                    question_text=question_text,
                    expected_answer=expected_answer if expected_answer else None,
                    company_name=company_name if company_name else None,
                    cik=cik if cik else None,
                    form_type=form_type if form_type else None,
                    filing_date=filing_date if filing_date else None
                )
                st.success("Added to ground truth dataset!")
        
        # Show existing ground truth entries
        st.subheader("Recent Ground Truth Entries")
        gt_entries = db.get_ground_truth_entries(limit=10)
        if gt_entries:
            for entry in gt_entries:
                st.write(f"**Q{entry.get('id')}:** {entry.get('question_text')[:100]}...")
                if entry.get('company_name'):
                    st.write(f"  Company: {entry.get('company_name')}")
                if entry.get('cik'):
                    st.write(f"  CIK: {entry.get('cik')}")
        else:
            st.info("No ground truth entries yet.")


if __name__ == "__main__":
    main()

