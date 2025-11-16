"""
Ground Truth Inspector - Streamlit App

Interactive tool to view, edit, and curate ground truth questions.
Allows manual selection of "good" questions into a separate file.

Usage:
    poetry run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path to import docs module
sys.path.insert(0, str(Path(__file__).parent.parent))
import docs


@st.cache_data
def load_documents():
    """Load and cache documents from GitHub."""
    raw_documents = docs.read_github_data()
    documents = docs.parse_data(raw_documents)
    # Create a lookup dict by filename
    return {doc['filename']: doc for doc in documents}


def load_data(csv_path: str) -> pd.DataFrame:
    """Load ground truth CSV file."""
    df = pd.read_csv(csv_path)
    return df


def extract_line_range(relevant_lines: str) -> tuple[int, int]:
    """
    Extract line range from relevant_lines string.
    
    Examples:
        "lines 45-67" -> (45, 67)
        "line 23" -> (23, 23)
        "45-67" -> (45, 67)
        "23" -> (23, 23)
    
    Returns:
        Tuple of (start_line, end_line) or None if parsing fails
    """
    if pd.isna(relevant_lines):
        return None
    
    import re
    
    # Try to find numbers in the string
    numbers = re.findall(r'\d+', str(relevant_lines))
    
    if not numbers:
        return None
    
    if len(numbers) == 1:
        line_num = int(numbers[0])
        return (line_num, line_num)
    else:
        return (int(numbers[0]), int(numbers[1]))


def get_source_lines(filename: str, relevant_lines: str, documents_dict: dict, context: int = 5) -> str:
    """
    Extract the relevant lines from source document.
    
    Args:
        filename: The source file name
        relevant_lines: Line range specification (e.g., "lines 45-67")
        documents_dict: Dictionary mapping filename to document data
        context: Number of context lines to include before/after
        
    Returns:
        Formatted string with line numbers
    """
    if pd.isna(filename) or pd.isna(relevant_lines):
        return "Source file or line range not available"
    
    # Get document content from docs module
    if filename not in documents_dict:
        return f"Document not found: {filename}"
    
    source_content = documents_dict[filename].get('content', '')
    if not source_content:
        return "Source content not available"
    
    line_range = extract_line_range(relevant_lines)
    if not line_range:
        return "Could not parse line range"
    
    start_line, end_line = line_range
    lines = source_content.split('\n')
    
    # Add context
    start_idx = max(0, start_line - 1 - context)
    end_idx = min(len(lines), end_line + context)
    
    # Format with line numbers
    result_lines = []
    for i in range(start_idx, end_idx):
        line_num = i + 1
        prefix = ">>>" if start_line <= line_num <= end_line else "   "
        result_lines.append(f"{prefix} {line_num:4d} | {lines[i]}")
    
    return '\n'.join(result_lines)


def save_data(df: pd.DataFrame, output_path: str):
    """Save dataframe to CSV."""
    df.to_csv(output_path, index=False)
    return output_path


def initialize_session_state():
    """Initialize session state variables."""
    if 'selected_indices' not in st.session_state:
        st.session_state.selected_indices = set()
    if 'edited_questions' not in st.session_state:
        st.session_state.edited_questions = {}


def main():
    st.set_page_config(page_title="Ground Truth Inspector", layout="wide")
    
    st.title("🔍 Ground Truth Inspector")
    st.markdown("View, edit, and curate ground truth questions for evaluation")
    
    initialize_session_state()
    
    # Sidebar for file operations
    st.sidebar.header("📁 File Operations")
    
    # Get input file from command line or sidebar
    if len(sys.argv) > 1 and sys.argv[1] == "--input" and len(sys.argv) > 2:
        default_input = sys.argv[2]
    else:
        default_input = "evals/ground_truth_evidently.csv"
    
    input_file = st.sidebar.text_input("Input CSV Path", value=default_input)
    
    if not Path(input_file).exists():
        st.error(f"❌ File not found: {input_file}")
        st.stop()
    
    # Load data
    df = load_data(input_file)
    
    # Load documents from GitHub (cached)
    with st.spinner("Loading source documents from GitHub..."):
        documents_dict = load_documents()
    
    st.sidebar.success(f"✅ Loaded {len(df)} questions")
    
    # Display dataset info
    st.sidebar.metric("Total Questions", len(df))
    st.sidebar.metric("Selected", len(st.session_state.selected_indices))
    
    # Export options
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Export Options")
    
    output_file = st.sidebar.text_input(
        "Output CSV Path",
        value="evals/ground_truth_curated.csv"
    )
    
    if st.sidebar.button("📥 Export Selected Questions"):
        if len(st.session_state.selected_indices) == 0:
            st.sidebar.warning("⚠️ No questions selected")
        else:
            selected_df = df.loc[list(st.session_state.selected_indices)].copy()
            
            # Apply any edits
            for idx, edited_q in st.session_state.edited_questions.items():
                if idx in st.session_state.selected_indices:
                    selected_df.loc[idx, 'question'] = edited_q
            
            save_data(selected_df, output_file)
            st.sidebar.success(f"✅ Exported {len(selected_df)} questions to {output_file}")
    
    # Main content area
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Filters")
        
        # Search filter
        search_query = st.text_input("🔎 Search in questions", "")
        
        # Filter by filename/source if available
        if 'filename' in df.columns:
            filenames = ['All'] + sorted(df['filename'].unique().tolist())
            selected_filename = st.selectbox("📄 Filter by filename", filenames)
        else:
            selected_filename = 'All'
        
        # Show only selected
        show_selected_only = st.checkbox("Show only selected")
    
    with col2:
        st.subheader("Questions")
        
        # Apply filters
        filtered_df = df.copy()
        
        if search_query:
            filtered_df = filtered_df[
                filtered_df['question'].str.contains(search_query, case=False, na=False)
            ]
        
        if selected_filename != 'All' and 'filename' in df.columns:
            filtered_df = filtered_df[filtered_df['filename'] == selected_filename]
        
        if show_selected_only:
            filtered_df = filtered_df.loc[
                filtered_df.index.isin(st.session_state.selected_indices)
            ]
        
        st.info(f"Showing {len(filtered_df)} of {len(df)} questions")
        
        # Display questions
        for idx, row in filtered_df.iterrows():
            with st.container():
                col_check, col_content = st.columns([0.5, 9.5])
                
                with col_check:
                    is_selected = idx in st.session_state.selected_indices
                    if st.checkbox("✓", value=is_selected, key=f"select_{idx}"):
                        st.session_state.selected_indices.add(idx)
                    else:
                        st.session_state.selected_indices.discard(idx)
                
                with col_content:
                    # Show index and metadata
                    metadata_parts = [f"**ID: {idx}**"]
                    if 'filename' in row:
                        metadata_parts.append(f"📄 {row['filename']}")
                    if 'relevant_lines' in row and pd.notna(row['relevant_lines']):
                        metadata_parts.append(f"📍 {row['relevant_lines']}")
                    if 'section' in row:
                        metadata_parts.append(f"§ {row['section']}")
                    
                    st.markdown(" | ".join(metadata_parts))
                    
                    # Show additional metadata if available
                    meta_cols = st.columns([1, 1, 1])
                    with meta_cols[0]:
                        if 'difficulty' in row and pd.notna(row['difficulty']):
                            st.caption(f"🎯 {row['difficulty']}")
                    with meta_cols[1]:
                        if 'intent' in row and pd.notna(row['intent']):
                            st.caption(f"💡 {row['intent']}")
                    with meta_cols[2]:
                        if 'summary_answer' in row and pd.notna(row['summary_answer']):
                            st.caption("✓ Has summary")
                    
                    # Question text (editable)
                    current_question = st.session_state.edited_questions.get(idx, row['question'])
                    
                    edited_question = st.text_area(
                        "Question",
                        value=current_question,
                        key=f"question_{idx}",
                        height=100,
                        label_visibility="collapsed"
                    )
                    
                    # Track edits
                    if edited_question != row['question']:
                        st.session_state.edited_questions[idx] = edited_question
                        st.caption("✏️ *Edited*")
                    
                    # Show original if edited
                    if idx in st.session_state.edited_questions:
                        with st.expander("Show original"):
                            st.text(row['question'])
                    
                    # Show source lines if available
                    if 'filename' in row and 'relevant_lines' in row:
                        if pd.notna(row['filename']) and pd.notna(row['relevant_lines']):
                            with st.expander(f"📄 View source: {row['filename']} ({row['relevant_lines']})"):
                                source_lines = get_source_lines(
                                    row['filename'],
                                    row['relevant_lines'],
                                    documents_dict,
                                    context=5
                                )
                                st.code(source_lines, language=None)
                                
                                # Show summary answer if available
                                if 'summary_answer' in row and pd.notna(row['summary_answer']):
                                    st.markdown("**Summary Answer:**")
                                    st.info(row['summary_answer'])
                
                st.divider()
    
    # Bulk actions
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Bulk Actions")
    
    col_sel, col_desel = st.sidebar.columns(2)
    
    with col_sel:
        if st.button("Select All Visible"):
            st.session_state.selected_indices.update(filtered_df.index.tolist())
            st.rerun()
    
    with col_desel:
        if st.button("Deselect All"):
            st.session_state.selected_indices.clear()
            st.rerun()


if __name__ == "__main__":
    main()
