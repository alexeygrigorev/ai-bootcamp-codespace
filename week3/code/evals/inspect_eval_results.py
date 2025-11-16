"""
Evaluation Results Inspector - Streamlit App

Interactive tool to inspect evaluation results in depth.
View reports, filter by criteria, inspect tool calls, and identify issues.

Usage:
    poetry run streamlit run evals/inspect_eval_results.py -- --input reports/eval-run-2025-10-23-12-00.bin
"""

import streamlit as st
import pandas as pd
import pickle
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path to import docs module
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_eval_results(bin_path: str) -> list[dict]:
    """Load evaluation results from pickle file."""
    with open(bin_path, 'rb') as f_in:
        return pickle.load(f_in)


def load_judge_results(bin_path: str) -> Optional[pd.DataFrame]:
    """Try to load judge results if available."""
    # Try to find matching judge results
    judge_path = bin_path.replace('eval-run-', 'eval-judge-')
    if Path(judge_path).exists():
        try:
            with open(judge_path, 'rb') as f_in:
                judge_data = pickle.load(f_in)
                # Judge results are list of (original_row, result) tuples
                # Extract evaluation checks
                all_checks = []
                for original_row, result in judge_data:
                    checks = result.output.checklist
                    checks_formatted = {'question': original_row['question']}
                    for check in checks:
                        # Convert enum to string value
                        check_name = check.check_name.value if hasattr(check.check_name, 'value') else str(check.check_name)
                        checks_formatted[check_name] = check.check_pass
                    all_checks.append(checks_formatted)
                return pd.DataFrame(all_checks)
        except Exception as e:
            st.warning(f"Could not load judge results: {e}")
            import traceback
            st.error(f"Error details: {traceback.format_exc()}")
            return None
    return None


def extract_tool_calls(messages: list[dict]) -> list[dict]:
    """Extract tool calls from messages."""
    tool_calls = []
    for msg in messages:
        if msg.get('kind') == 'tool-call':
            tool_calls.append({
                'tool_name': msg.get('tool_name'),
                'args': msg.get('args', {})
            })
    return tool_calls


def count_tool_calls(messages: list[dict]) -> int:
    """Count total tool calls."""
    return sum(1 for msg in messages if msg.get('kind') == 'tool-call')


def initialize_session_state():
    """Initialize session state variables."""
    if 'expanded_results' not in st.session_state:
        st.session_state.expanded_results = set()
    if 'selected_index' not in st.session_state:
        st.session_state.selected_index = None


def format_tool_call(tool_call: dict) -> str:
    """Format a tool call for display."""
    tool_name = tool_call.get('tool_name', 'unknown')
    args = tool_call.get('args', {})
    
    if isinstance(args, dict):
        args_str = json.dumps(args, indent=2)
    else:
        args_str = str(args)
    
    return f"**{tool_name}**\n```json\n{args_str}\n```"


def main():
    st.set_page_config(page_title="Evaluation Results Inspector", layout="wide")
    
    st.title("🔬 Evaluation Results Inspector")
    st.markdown("Deep dive into agent evaluation results with filtering and detailed inspection")
    
    initialize_session_state()
    
    # Sidebar for file and filter operations
    st.sidebar.header("📁 Load Results")
    
    # Get input file from command line or sidebar
    if len(sys.argv) > 1 and sys.argv[1] == "--input" and len(sys.argv) > 2:
        default_input = sys.argv[2]
    else:
        # Try to find the most recent eval-run file
        reports_dir = Path("reports")
        if reports_dir.exists():
            eval_files = sorted(reports_dir.glob("eval-run-*.bin"), reverse=True)
            default_input = str(eval_files[0]) if eval_files else "reports/eval-run-latest.bin"
        else:
            default_input = "reports/eval-run-latest.bin"
    
    input_file = st.sidebar.text_input("Results File (.bin)", value=default_input)
    
    if not Path(input_file).exists():
        st.error(f"❌ File not found: {input_file}")
        st.info("💡 Run an evaluation first:\n```bash\npoetry run python -m evals.eval_orchestrator --csv evals/gt-sample.csv\n```")
        st.stop()
    
    # Load data
    results = load_eval_results(input_file)
    df = pd.DataFrame(results)
    
    # Add computed columns
    df['tool_call_count'] = df['messages'].apply(count_tool_calls)
    df['answer_length'] = df['answer'].str.len()
    
    # Try to load judge results
    judge_df = load_judge_results(input_file)
    if judge_df is not None:
        # Merge judge results with main df
        df = df.merge(judge_df, on='question', how='left')
        st.sidebar.success(f"✅ Loaded {len(df)} results (with eval checks)")
    else:
        st.sidebar.success(f"✅ Loaded {len(df)} results")
        st.sidebar.info("💡 No judge results found. Run judge evaluation to see checks.")
    
    # Summary metrics
    st.sidebar.header("📊 Summary Metrics")
    st.sidebar.metric("Total Questions", len(df))
    st.sidebar.metric("Avg Tool Calls", f"{df['tool_call_count'].mean():.1f}")
    st.sidebar.metric("Avg Answer Length", f"{df['answer_length'].mean():.0f} chars")
    
    # Show eval check scores if available
    if judge_df is not None:
        # Get check columns from judge_df (exclude 'question')
        check_columns = [col for col in judge_df.columns if col != 'question']
        if check_columns:
            st.sidebar.markdown("**Eval Check Pass Rates:**")
            for check_col in check_columns:
                if check_col in df.columns and df[check_col].notna().any():
                    # Ensure we're working with boolean values
                    try:
                        pass_rate = df[check_col].astype(bool).mean()
                        st.sidebar.metric(check_col, f"{pass_rate:.1%}")
                    except Exception as e:
                        st.sidebar.warning(f"{check_col}: Error - {e}")
    
    # Filters
    st.sidebar.header("🔍 Filters")
    
    # Tool call range filter
    min_tools, max_tools = st.sidebar.slider(
        "Tool Calls Range",
        min_value=0,
        max_value=int(df['tool_call_count'].max()),
        value=(0, int(df['tool_call_count'].max()))
    )
    
    # Answer length filter
    min_length, max_length = st.sidebar.slider(
        "Answer Length Range",
        min_value=0,
        max_value=int(df['answer_length'].max()),
        value=(0, int(df['answer_length'].max()))
    )
    
    # Search filter
    search_query = st.sidebar.text_input("🔎 Search in questions/answers", "")
    
    # Evaluation check filters
    selected_checks = {}
    if judge_df is not None:
        st.sidebar.markdown("**Filter by Eval Checks:**")
        # Get check columns from judge_df (exclude 'question')
        check_columns = [col for col in judge_df.columns if col != 'question']
        for check_col in check_columns:
            if check_col in df.columns and df[check_col].notna().any():
                filter_option = st.sidebar.radio(
                    check_col,
                    options=["All", "Passed", "Failed"],
                    key=f"filter_{check_col}",
                    horizontal=True
                )
                if filter_option != "All":
                    selected_checks[check_col] = (filter_option == "Passed")
    
    # Show only issues
    show_issues_only = st.sidebar.checkbox("Show only potential issues")
    
    # Apply filters
    filtered_df = df.copy()
    
    filtered_df = filtered_df[
        (filtered_df['tool_call_count'] >= min_tools) &
        (filtered_df['tool_call_count'] <= max_tools) &
        (filtered_df['answer_length'] >= min_length) &
        (filtered_df['answer_length'] <= max_length)
    ]
    
    if search_query:
        filtered_df = filtered_df[
            filtered_df['question'].str.contains(search_query, case=False, na=False) |
            filtered_df['answer'].str.contains(search_query, case=False, na=False)
        ]
    
    # Apply evaluation check filters
    if judge_df is not None and selected_checks:
        for check_col, should_pass in selected_checks.items():
            filtered_df = filtered_df[filtered_df[check_col] == should_pass]
    
    if show_issues_only:
        # Define "issues" as too many or too few tool calls, or very short/long answers
        filtered_df = filtered_df[
            (filtered_df['tool_call_count'] > 10) |
            (filtered_df['tool_call_count'] < 2) |
            (filtered_df['answer_length'] < 100) |
            (filtered_df['answer_length'] > 2000)
        ]
    
    # Main content
    st.info(f"📋 Showing {len(filtered_df)} of {len(df)} results")
    
    # Tabs for different views
    tab_list, tab_details = st.tabs(["📃 List View", "🔎 Detailed View"])
    
    with tab_list:
        # Quick overview table with evaluation checks
        display_columns = ['question', 'tool_call_count', 'answer_length']
        list_check_columns = []
        if judge_df is not None:
            # Get check columns from judge_df
            list_check_columns = [col for col in judge_df.columns if col != 'question' and col in filtered_df.columns]
            display_columns.extend(list_check_columns)
        
        display_df = filtered_df[display_columns].copy()
        display_df['question_preview'] = display_df['question'].str[:80] + '...'
        
        # Show index for navigation
        display_df['idx'] = filtered_df.index
        
        # Reorder columns to put idx first
        cols = ['idx', 'question_preview', 'tool_call_count', 'answer_length']
        if judge_df is not None:
            cols.extend(list_check_columns)
        
        st.markdown("💡 **Tip:** Note the `idx` number, then switch to Detailed View and enter it in the navigation box")
        
        st.dataframe(
            display_df[cols],
            use_container_width=True,
            height=600,
            column_config={
                "idx": st.column_config.NumberColumn("Index", help="Use this to navigate in Detailed View")
            }
        )
    
    with tab_details:
        # Navigation controls
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            # Sort options
            sort_by = st.selectbox(
                "Sort by",
                ["Index", "Tool Calls (High to Low)", "Tool Calls (Low to High)", 
                 "Answer Length (Long to Short)", "Answer Length (Short to Long)"]
            )
        
        with col2:
            # Jump to specific index
            jump_to_idx = st.number_input(
                "Jump to index",
                min_value=int(filtered_df.index.min()) if len(filtered_df) > 0 else 0,
                max_value=int(filtered_df.index.max()) if len(filtered_df) > 0 else 0,
                value=int(filtered_df.index.min()) if len(filtered_df) > 0 else 0,
                step=1,
                help="Enter the index from List View to jump directly to that result"
            )
        
        with col3:
            if st.button("🎯 Jump to Result"):
                st.session_state.selected_index = jump_to_idx
        
        if sort_by == "Tool Calls (High to Low)":
            filtered_df = filtered_df.sort_values('tool_call_count', ascending=False)
        elif sort_by == "Tool Calls (Low to High)":
            filtered_df = filtered_df.sort_values('tool_call_count', ascending=True)
        elif sort_by == "Answer Length (Long to Short)":
            filtered_df = filtered_df.sort_values('answer_length', ascending=False)
        elif sort_by == "Answer Length (Short to Long)":
            filtered_df = filtered_df.sort_values('answer_length', ascending=True)
        
        # Scroll to selected index if set
        if st.session_state.selected_index is not None:
            if st.session_state.selected_index in filtered_df.index:
                st.success(f"🎯 Jumped to result #{st.session_state.selected_index}")
            else:
                st.warning(f"⚠️ Index {st.session_state.selected_index} not found in filtered results")
            st.session_state.selected_index = None
        
        # Display detailed results
        for idx, row in filtered_df.iterrows():
            # Create anchor for this result
            result_container = st.container()
            
            with result_container:
                # Header with metrics
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"### 📝 Result #{idx}")
                
                with col2:
                    st.metric("Tool Calls", row['tool_call_count'])
                
                with col3:
                    st.metric("Requests", row.get('requests', 'N/A'))
                
                with col4:
                    st.metric("Answer Length", row['answer_length'])
                
                # Question
                with st.expander("❓ Question", expanded=True):
                    st.markdown(row['question'])
                    
                    # Show original question metadata if available
                    if 'original_question' in row and isinstance(row['original_question'], dict):
                        orig = row['original_question']
                        if 'filename' in orig:
                            st.caption(f"📄 Source: {orig['filename']}")
                        if 'section' in orig:
                            st.caption(f"§ Section: {orig['section']}")
                
                # Evaluation Checks
                if judge_df is not None:
                    # Get check columns from judge_df
                    detail_check_columns = [col for col in judge_df.columns if col != 'question' and col in row.index]
                    if detail_check_columns:
                        with st.expander("✅ Evaluation Checks", expanded=True):
                            check_cols = st.columns(len(detail_check_columns))
                            for i, check_col in enumerate(detail_check_columns):
                                with check_cols[i]:
                                    if pd.notna(row[check_col]):
                                        if row[check_col]:
                                            st.success(f"✓ {check_col}")
                                        else:
                                            st.error(f"✗ {check_col}")
                                    else:
                                        st.info(f"? {check_col}")
                
                # Answer
                with st.expander("💬 Answer", expanded=False):
                    st.markdown(row['answer'])
                
                # Tool Calls
                with st.expander(f"🛠️ Tool Calls ({row['tool_call_count']})", expanded=False):
                    tool_calls = extract_tool_calls(row['messages'])
                    
                    if not tool_calls:
                        st.info("No tool calls found")
                    else:
                        for i, tc in enumerate(tool_calls, 1):
                            st.markdown(f"**Call #{i}**")
                            st.markdown(format_tool_call(tc))
                            if i < len(tool_calls):
                                st.divider()
                
                # Full Message Log
                with st.expander("📜 Full Message Log", expanded=False):
                    st.json(row['messages'])
                
                # Flags for potential issues
                issues = []
                if row['tool_call_count'] > 10:
                    issues.append("⚠️ High number of tool calls")
                if row['tool_call_count'] < 2:
                    issues.append("⚠️ Very few tool calls")
                if row['answer_length'] < 100:
                    issues.append("⚠️ Very short answer")
                if row['answer_length'] > 2000:
                    issues.append("⚠️ Very long answer")
                
                if issues:
                    st.warning(" | ".join(issues))
                
                st.divider()
    
    # Export options
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Export")
    
    if st.sidebar.button("📥 Export Filtered Results to CSV"):
        export_df = filtered_df[['question', 'answer', 'tool_call_count', 'answer_length']].copy()
        export_path = "reports/filtered_results.csv"
        export_df.to_csv(export_path, index=True)
        st.sidebar.success(f"✅ Exported to {export_path}")


if __name__ == "__main__":
    main()
