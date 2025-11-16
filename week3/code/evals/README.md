# Evaluation System

This directory contains a modular evaluation system for the search agent.

**Important**: All commands should be run from the project root directory (`/workspaces/ai-bootcamp-codespace/week3/code`), not from within the `evals/` directory.

**Quick Start**: See [INSPECTOR_GUIDE.md](INSPECTOR_GUIDE.md) for detailed instructions on using the interactive inspection tools.

## Structure

### Core Modules

1. **`sample_ground_truth.py`** - Ground truth sampler
   - Samples questions from full dataset
   - Ensures reproducibility with random seeds
   - Saves to CSV for evaluation

2. **`eval_common.py`** - Shared utilities
   - `map_progress()` - Async progress tracking
   - `calculate_cost()` - Cost calculation returning CostInfo from toyaikit
   - `simplify_messages()` - Message formatting

3. **`eval_agent_run.py`** - Agent evaluation runner
   - Runs agent on ground truth questions
   - Saves results for judge evaluation
   - Tracks costs and performance

4. **`eval_agent_judge.py`** - Judge evaluation
   - Evaluates agent outputs using LLM judge
   - Checks quality, relevance, completeness
   - Produces evaluation metrics

5. **`eval_orchestrator.py`** - Complete pipeline
   - Orchestrates run + judge evaluation
   - Displays comprehensive reports
   - Tracks total costs

6. **`inspect_ground_truth.py`** - Ground truth inspector (Streamlit)
   - View and edit ground truth questions
   - View source lines that generated each question
   - Select good questions for curation
   - Export curated datasets

7. **`inspect_eval_results.py`** - Evaluation results inspector (Streamlit)
   - Deep dive into evaluation results
   - Filter by criteria (tool calls, answer length, etc.)
   - View detailed tool calls and message logs
   - Identify potential issues

### Directory Structure

```
week3/code/
├── evals/
│   ├── sample_ground_truth.py
│   ├── eval_common.py
│   ├── eval_agent_run.py
│   ├── eval_agent_judge.py
│   ├── eval_orchestrator.py
│   ├── ground_truth_evidently.csv  # Full dataset
│   ├── gt-sample.csv               # Your sampled datasets
│   └── README.md
└── reports/                         # Auto-created for outputs
    ├── eval-run-<timestamp>.bin     # Agent run results
    └── eval-report-<timestamp>.txt  # Detailed reports
```

## Usage

### Complete Workflow (Recommended)

**Note**: Run all commands from the project root (`/workspaces/ai-bootcamp-codespace/week3/code`)

#### Step 0a: Generate Ground Truth Data (optional)

If you need to create a new ground truth dataset from documentation:

```bash
# Generate with default settings (gpt-4o-mini, 6 workers)
poetry run python -m evals.generate_data

# Use a different model
poetry run python -m evals.generate_data --model gpt-4o

# Customize output file
poetry run python -m evals.generate_data --output evals/ground_truth_custom.csv

# Adjust content filtering and generation parameters
poetry run python -m evals.generate_data \
    --min-content-length 500 \
    --chars-per-question 800 \
    --max-workers 10

# Exclude specific keywords from document titles
poetry run python -m evals.generate_data \
    --exclude unpublished legacy test draft
```

This will:
- Load documentation from the `docs` module
- Filter documents by length and keywords
- Generate questions using LLM with line number tracking
- Save to `evals/ground_truth_evidently.csv` (or custom output)
- Track total API costs

**Generated CSV includes:**
- `question` - Natural search-style query
- `summary_answer` - 1-2 sentence answer summary
- `difficulty` - Question complexity level
- `intent` - User's intent (informational/navigational/transactional)
- `filename` - Documentation file path
- `relevant_lines` - Line numbers used (e.g., "lines 45-67")

**Note:** Source content is not stored in the CSV. The inspector loads it dynamically from the docs module when viewing source lines.

#### Step 0b: Sample Ground Truth (for reproducibility)

```bash
# Sample 25 questions with random_state=1 for reproducibility
poetry run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --random-state 1 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample.csv

# Sample with specific extra indices
poetry run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --extra-indices 150 200 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample.csv

# Use all questions (no sampling)
poetry run python -m evals.sample_ground_truth \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-all.csv

# Save to specific file with custom size
poetry run python -m evals.sample_ground_truth \
    --sample-size 50 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample-50.csv
```

This creates a CSV file that you can use for reproducible evaluations.

#### Step 1+2: Run Complete Evaluation Pipeline

```bash
# Run with sampled dataset
poetry run python -m evals.eval_orchestrator --csv evals/gt-sample.csv

# Run with full dataset
poetry run python -m evals.eval_orchestrator --csv evals/ground_truth_evidently.csv

# Custom configuration
poetry run python -m evals.eval_orchestrator \
    --csv evals/gt-sample.csv \
    --agent-model gpt-4o-mini \
    --judge-model gpt-5-nano \
    --concurrency 10
```

### Run Individual Steps

#### Step 1: Run Agent Evaluation

```bash
# Use sampled dataset
poetry run python -m evals.eval_agent_run --csv evals/gt-sample.csv

# Or use full dataset
poetry run python -m evals.eval_agent_run --csv evals/ground_truth_evidently.csv

# With custom settings
poetry run python -m evals.eval_agent_run \
    --csv evals/gt-sample.csv \
    --model gpt-4o-mini \
    --concurrency 10
```

This will:
- Load ground truth questions from CSV
- Run the agent on each question
- Save results to `reports/eval-run-<timestamp>.bin`
- Display cost breakdown

#### Step 2: Run Judge Evaluation

```bash
poetry run python -m evals.eval_agent_judge reports/eval-run-<timestamp>.bin
```

This will:
- Load agent run results
- Evaluate each result with judge
- Display evaluation metrics
- Show cost breakdown

### Use as Library

#### Generate Ground Truth Programmatically

```python
from evals.generate_data import Config, main

# Use default configuration
config = Config()
main(config)

# Custom configuration
config = Config(
    model="gpt-4o",
    max_workers=10,
    min_content_length=500,
    chars_per_question=800,
    output_file="evals/ground_truth_custom.csv",
    exclude_keywords=["test", "draft", "unpublished"]
)
main(config)
```

#### Complete Evaluation Pipeline

```python
import asyncio
from evals.sample_ground_truth import sample_ground_truth
from evals.eval_orchestrator import run_full_evaluation

# First, create a reproducible sample
sample_path = sample_ground_truth(
    csv_path='evals/ground_truth_evidently.csv',
    sample_size=25,
    random_state=1,
    extra_indices=[150],
    output_path='evals/gt-sample.csv'
)

# Run complete pipeline
results = asyncio.run(run_full_evaluation(
    csv_path=sample_path,
    agent_model='gpt-4o-mini',
    judge_model='gpt-5-nano',
    max_concurrency=10
))

# Access results
print(f"Total cost: ${results['total_cost'].total_cost:.4f}")
print(f"Overall score: {results['metrics'].mean():.1%}")
```

#### Use Individual Components

```python

```python
from evals.eval_agent_run import run_agent_evaluation
from evals.eval_agent_judge import run_complete_judge_evaluation

# Run agent evaluation on pre-sampled dataset
saved_path, run_cost, df_run = await run_agent_evaluation(
    csv_path='evals/gt-sample.csv',
    model='gpt-4o-mini'
)

# Run judge evaluation
judge_cost, df_eval, metrics, judge_path = await run_complete_judge_evaluation(
    input_path=saved_path,
    model='gpt-5-nano'
)
```

## Output

### Console Output

The orchestrator provides:
- Real-time progress tracking
- Cost breakdowns per step
- Evaluation metrics with visual indicators
- Total costs and duration
- File paths for both run and judge results

### Files Generated

1. **`reports/eval-run-<timestamp>.bin`** - Agent run results (pickle format)
2. **`reports/eval-judge-<timestamp>.bin`** - Judge evaluation results (pickle format)
3. **`reports/eval-report-<timestamp>.txt`** - Detailed text report (if generated)

All reports are automatically saved to the `reports/` directory in the project root.

**Note**: The eval results inspector automatically looks for matching judge results by replacing `eval-run-` with `eval-judge-` in the filename.

### Evaluation Metrics

The judge evaluates on these dimensions:
- `instructions_follow` - Followed instructions
- `instructions_avoid` - Avoided prohibited actions
- `answer_relevant` - Relevance to question
- `answer_clear` - Clarity and correctness
- `answer_citations` - Proper citations
- `completeness` - Complete answer
- `tool_call_search` - Search tool usage

## Cost Tracking

The system uses the `CostInfo` dataclass:

```python
@dataclass
class CostInfo:
    input_cost: float      # Cost for input tokens
    output_cost: float     # Cost for output tokens
    total_cost: float      # Total cost
```

Costs are tracked separately for:
- Agent run (using agent model, e.g., gpt-4o-mini)
- Judge evaluation (using judge model, e.g., gpt-5-nano)
- Total pipeline cost (sum of both)

## Refactoring Benefits

✅ **No global variables** - All state passed as function parameters
✅ **Modular functions** - Each function has single responsibility
✅ **Reusable utilities** - Common code in eval_common.py
✅ **Importable** - Can be used as library or CLI
✅ **Type hints** - Better IDE support and documentation
✅ **Error handling** - Graceful error handling throughout
✅ **Progress tracking** - Visual feedback during execution
✅ **Comprehensive reports** - Detailed cost and metric tracking
✅ **Reproducibility** - Separate sampling step ensures consistent evaluations
✅ **Flexibility** - Point to any CSV file for evaluation

## Examples

### Complete Workflow from Scratch (Generate → Curate → Evaluate)

```bash
# 1. Generate ground truth from documentation
poetry run python -m evals.generate_data --output evals/ground_truth_evidently.csv

# 2. Inspect and curate ground truth
poetry run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
# - View source lines for each question
# - Select good questions and export to evals/gt-curated.csv

# 3. Create evaluation sample
poetry run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --input evals/gt-curated.csv \
    --output evals/gt-sample.csv

# 3. Run evaluation
poetry run python -m evals.eval_orchestrator --csv evals/gt-sample.csv

# 4. Inspect results
poetry run streamlit run evals/inspect_eval_results.py
# Review results, identify issues, filter by criteria
```

### Quick Test (5 samples)

```bash
# Step 1: Create sample
poetry run python -m evals.sample_ground_truth \
    --sample-size 5 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-test.csv

# Step 2: Run evaluation
poetry run python -m evals.eval_orchestrator --csv evals/gt-test.csv

# Step 3: Inspect results
poetry run streamlit run evals/inspect_eval_results.py
```

### Full Evaluation

```bash
# Use full dataset directly
poetry run python -m evals.eval_orchestrator --csv evals/ground_truth_evidently.csv
```

### Reproducible Evaluation

```bash
# Create reproducible sample with fixed random seed
poetry run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --random-state 42 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-eval-v1.csv

# Run evaluation (can be repeated with same results)
poetry run python -m evals.eval_orchestrator --csv evals/gt-eval-v1.csv
```

### Custom Models

```bash
poetry run python -m evals.eval_orchestrator \
    --csv evals/gt-sample.csv \
    --agent-model gpt-4o \
    --judge-model gpt-4o-mini
```

### Regenerate Ground Truth with Custom Settings

```bash
# Generate more questions per document (shorter content chunks)
poetry run python -m evals.generate_data \
    --chars-per-question 500 \
    --output evals/ground_truth_detailed.csv

# Use a more powerful model for generation
poetry run python -m evals.generate_data \
    --model gpt-4o \
    --output evals/ground_truth_gpt4.csv

# Generate from shorter documents with custom filtering
poetry run python -m evals.generate_data \
    --min-content-length 500 \
    --exclude draft test wip unpublished \
    --output evals/ground_truth_filtered.csv
```

## Interactive Inspector Tools

### Ground Truth Inspector

Interactive Streamlit app to view, edit, and curate ground truth questions.

```bash
# Launch the inspector
poetry run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
```

**Features:**
- 📋 View all ground truth questions
- ✏️ Edit questions inline
- ✓ Select "good" questions for curation
- 🔍 Search and filter questions
- 📄 View source document lines (loaded dynamically from docs module)
- 🎯 See metadata (difficulty, intent, summary)
- � Export curated dataset to new CSV
- ⚡ Bulk select/deselect operations

**Workflow:**
1. Load your ground truth CSV
2. Inspector fetches source documents from GitHub (cached)
3. Browse and review questions
4. Click to view source lines that generated each question
5. Edit any questions that need improvement
6. Check the boxes next to good questions
6. Export selected questions to a new file

### Evaluation Results Inspector

Interactive Streamlit app to deep dive into evaluation results.

```bash
# Launch the inspector (auto-detects latest results)
poetry run streamlit run evals/inspect_eval_results.py

# Or specify a results file
poetry run streamlit run evals/inspect_eval_results.py -- --input reports/eval-run-2025-10-23-12-00.bin
```

**Features:**
- 📊 Summary metrics (avg tool calls, answer length, eval check pass rates)
- ✅ View evaluation checks (if judge results available)
- 🔍 Filter by tool call count, answer length, search terms, eval checks
- 🎯 Quick jump from List View to Detailed View by index
- 🛠️ View detailed tool calls and arguments
- 📜 Inspect full message logs
- ⚠️ Identify potential issues (too many/few tool calls, short/long answers)
- 📃 List and detailed views with clickable navigation
- 💾 Export filtered results to CSV

**Use Cases:**
- Review evaluation check results (which checks passed/failed)
- Filter by specific check failures (e.g., show only missing citations)
- Find results with excessive tool calls
- Identify answers that are too short or too long
- Quick navigation: note index in List View, jump directly in Detailed View
- Debug specific questions
- Review tool usage patterns
- Export problematic cases for further analysis

## Dependencies

- pandas
- pydantic
- pydantic_ai
- toyaikit
- tqdm
- streamlit
- asyncio (stdlib)
