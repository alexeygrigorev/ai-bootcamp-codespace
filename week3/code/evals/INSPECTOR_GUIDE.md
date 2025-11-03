# Inspector Tools Quick Reference

## 🔍 Ground Truth Inspector

**Purpose**: Review, edit, and curate ground truth questions

**Launch:**
```bash
uv run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
```

**Key Features:**
- ✏️ Edit questions inline
- ✓ Select good questions
- 🔍 Search and filter
- View source lines that generated each question
- Export curated dataset

**Common Tasks:**

1. **Review all questions:**
   - Browse through the list
   - Use search to find specific topics

2. **Edit a question:**
   - Click in the text area
   - Make your changes
   - Changes are tracked (see "Edited" indicator)

3. **Select good questions:**
   - Check the box next to each good question
   - Or use "Select All Visible" after filtering

4. **View source lines:**
   - Inspector loads documents from GitHub (cached for speed)
   - Click on "View source: [filename]" expander
   - See the exact lines from the document that were used
   - Lines marked with `>>>` are the relevant ones
   - Context lines are shown before and after
   - Summary answer is displayed below
   - Source content is fetched dynamically, not stored in CSV

5. **Export curated dataset:**
   - Enter output filename (e.g., `evals/gt-curated.csv`)
   - Click "Export Selected Questions"
   - Use this file for your evaluations

---

## 🔬 Evaluation Results Inspector

**Purpose**: Deep dive into evaluation results, identify issues

**Launch:**
```bash
# Auto-detect latest results
uv run streamlit run evals/inspect_eval_results.py

# Or specify file
uv run streamlit run evals/inspect_eval_results.py -- --input reports/eval-run-2025-10-23-12-00.bin
```

**Key Features:**
- 📊 Summary metrics (including eval check pass rates)
- ✅ View and filter by evaluation checks
- 🔍 Filter by criteria
- 🎯 Quick jump navigation between views
- 🛠️ View tool calls
- ⚠️ Identify issues

**Common Tasks:**

1. **Review evaluation check results:**
   - Inspector auto-loads judge results if available
   - See pass rates in Summary Metrics sidebar
   - Evaluation checks shown in detailed view with ✓/✗ indicators

2. **Filter by specific check failures:**
   - Use radio buttons under "Filter by Eval Checks"
   - Select "Failed" for any check to see only failures
   - Example: Find all results that failed "answer_citations"

3. **Quick navigation between views:**
   - In List View: note the `idx` number of interest
   - Switch to Detailed View
   - Enter index in "Jump to index" box
   - Click "Jump to Result" button

4. **Find results with many tool calls:**
   - Use "Tool Calls Range" slider
   - Set min to high value (e.g., 8-20)
   - Review what caused excessive calls

5. **Find short/incomplete answers:**
   - Use "Answer Length Range" slider
   - Set max to low value (e.g., 0-200)
   - Check why answers are short

6. **Search specific topics:**
   - Use search box
   - Enter keywords
   - Review matching results

7. **Debug a specific question:**
   - Find result in list
   - Expand "Tool Calls" to see what was called
   - Expand "Full Message Log" for complete details
   - Check "Evaluation Checks" to see what passed/failed

8. **Identify potential issues:**
   - Check "Show only potential issues"
   - Review flagged results
   - Look for patterns

9. **Export filtered results:**
   - Apply your filters
   - Click "Export Filtered Results to CSV"
   - Analyze in spreadsheet tool

---

## 📋 Typical Workflow

### Initial Setup
```bash
# 1. Install dependencies
uv sync --dev

# 2. Curate ground truth
uv run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
# Select good questions → export to evals/gt-curated.csv
```

### Run Evaluation
```bash
# 3. Sample questions
uv run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --input evals/gt-curated.csv \
    --output evals/gt-sample.csv

# 4. Run evaluation
uv run python -m evals.eval_orchestrator --csv evals/gt-sample.csv
```

### Analyze Results
```bash
# 5. Inspect results
uv run streamlit run evals/inspect_eval_results.py
# Review, filter, identify issues
```

### Iterate
```bash
# 6. Fix issues in code/prompts
# 7. Re-run evaluation with same sample
uv run python -m evals.eval_orchestrator --csv evals/gt-sample.csv

# 8. Compare results in inspector
uv run streamlit run evals/inspect_eval_results.py
```

---

## 💡 Tips

### Ground Truth Inspector
- Use "Show only selected" to review your selections before exporting
- Search for specific topics to focus curation
- Edit questions to make them clearer or more specific
- Original questions are preserved in "Show original"
- View source lines to understand context of each question
- Verify question quality by checking the source material
- Use metadata badges (difficulty, intent) to filter questions

### Evaluation Results Inspector
- Start with summary metrics to get overview
- Use "Show only potential issues" for quick problem identification
- Sort by tool calls or answer length to find extremes
- Compare tool call patterns across results
- Export filtered results for offline analysis
- Use search to find results about specific topics

### Both Tools
- Both tools preserve your work in session state
- Browser refresh will reset selections/filters
- Export frequently to save your work
- Run from project root directory
