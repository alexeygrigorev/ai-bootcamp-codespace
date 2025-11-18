# SEC Cybersecurity Disclosure Agent

[![Tests](https://github.com/your-username/your-repo/actions/workflows/tests.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/tests.yml)
[![Evaluations](https://github.com/your-username/your-repo/actions/workflows/evaluations.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/evaluations.yml)

An AI agent that extracts and analyzes cybersecurity disclosures from SEC filings using Pydantic AI.

## Problem Statement

Organizations face a critical challenge in **supply chain cybersecurity risk assessment**: they need to evaluate the cybersecurity posture of vendors and suppliers, but the information required for these assessments is scattered across thousands of SEC filings, making manual analysis impractical and error-prone.

### Core Challenges

1. **Information Scattered Across Multiple Filings**: Cybersecurity disclosures appear in various SEC form types (8-K for incidents, 10-K/10-Q for risk factors, Item 1.05 for material incidents) across multiple filing dates. A single company's cybersecurity story may span dozens of filings over several years.

2. **Incomplete Document Availability**: Not all expected SEC filings are available in searchable indexes:
   - **Historical filings** (pre-2017) may not be accessible through standard APIs
   - **Non-standard document types** (SEC Enforcement Orders, FTC Consent Orders) aren't regular SEC filings
   - **Missing accession numbers** or document naming issues prevent retrieval
   - **Private companies** don't file with the SEC at all

3. **Entity Resolution Complexity**:
   - Companies may have changed names (Yahoo → Altaba) but kept the same CIK
   - Subsidiaries and divisions (e.g., "Change Healthcare" subsidiary of UnitedHealth) have incidents reported in parent company filings
   - Ticker symbols, historical names, and current names must all map to correct CIKs

4. **Strict Data Source Requirements**: For reliable risk assessment, the agent must:
   - **Only use information from SEC filings** (no general knowledge or external sources)
   - **Clearly identify when information is missing** rather than filling gaps with assumptions
   - **Provide transparent citations** for every piece of information
   - **Handle incomplete information gracefully** while maintaining accuracy

5. **Actionable Risk Assessment**: The extracted information must be:
   - Synthesized into clear, non-technical summaries for business executives
   - Formatted for supply chain risk evaluation (Tier 1 vs. Tier 2 vendor classification)
   - Comparable across multiple companies and incidents
   - Based solely on verifiable SEC filing data

### Solution Approach

This agent addresses these challenges by:

- **Automated Extraction**: Systematically searches and extracts cybersecurity disclosures from indexed SEC filings
- **Missing Document Handling**: Identifies when expected filings are unavailable, explains why, and provides assessments based on available information
- **Robust Entity Resolution**: Handles company name variations, subsidiaries, historical names, and ticker symbols
- **Strict Data Source Adherence**: Only uses SEC filing data, clearly states when information is missing, and provides transparent citations
- **Comprehensive Evaluation Framework**: Tests agent performance against 21 ground truth cases covering major cybersecurity incidents from 2014-2024

## Agent Tools

The agent uses four specialized tools to extract and analyze cybersecurity disclosures from SEC filings. Each tool handles a specific aspect of the workflow and is implemented with detailed error handling and validation.

### 1. `lookup_subsidiary_parent(company_name, incident_date=None)`

**Purpose**: Identifies if a company is a subsidiary and returns the parent company's CIK for searching.

**Why it's needed**: Cybersecurity incidents for subsidiaries (e.g., "Change Healthcare") are reported in parent company filings (UnitedHealth Group). This tool ensures the agent searches the correct company's filings.

**Implementation**:

- **Tool wrapper function**: `src/run_stress_tests.py` (lines 28-71)
  - Wraps the core logic and formats the return value for the agent
  - Handles error cases and returns structured dictionaries
- **Core lookup logic**: `src/subsidiary_cik_mapping.py`
  - `find_parent_cik_for_subsidiary()` (lines 72-130): Main lookup function that searches `SUBSIDIARY_MAP`
  - `SUBSIDIARY_MAP` (lines 13-69): Dictionary mapping parent CIKs to subsidiary metadata
  - `get_parent_company_info()` (lines 132-162): Retrieves parent company information
  - Handles temporal logic: checks if incident occurred after acquisition date

**Returns**: Dictionary with `is_subsidiary`, `parent_cik`, `parent_name`, `subsidiary_info`, and `found` status.

**Example**: Input "Change Healthcare" → Returns `parent_cik: "0000731766"` (UnitedHealth Group) with subsidiary metadata.

---

### 2. `lookup_company_by_name(company_name)`

**Purpose**: Maps company names, ticker symbols, and historical names to correct CIK numbers.

**Why it's needed**: Users may provide company names, tickers (e.g., "UBER", "MGM"), or historical names (e.g., "Yahoo" → Altaba). This tool normalizes all variations to the correct CIK.

**Implementation**:

- **Tool wrapper function**: `src/run_stress_tests.py` (lines 74-140)
  - Orchestrates the lookup process and formats results
  - Handles ticker symbol detection and historical name checking
- **Core lookup logic**: `src/company_cik_lookup.py`
  - `lookup_company_cik()` (lines 108-169): Main function that searches `COMPANY_CIK_MAP`
  - `COMPANY_CIK_MAP` (lines 10-95): Dictionary of company name variations to CIKs
  - `lookup_by_ticker()` (lines 171-195): Ticker symbol lookup function
  - `TICKER_CIK_MAP` (lines 197-220): Dictionary mapping ticker symbols to CIKs
  - `get_historical_name_info()` (lines 222-240): Detects historical name changes
  - `HISTORICAL_NAMES` (lines 99-106): Dictionary of old names to current CIKs

**Returns**: Dictionary with `cik`, `found`, `is_ticker`, `is_historical`, `historical_info`, and `error` if not found.

**Example**: Input "Yahoo" → Returns `cik: "0001011006"` with `is_historical: True` and historical info indicating name change to "Altaba Inc."

---

### 3. `get_company_info(cik)`

**Purpose**: Retrieves company metadata (name, ticker, industry) from the SEC EDGAR API to verify company identity.

**Why it's needed**: Validates that the CIK matches the expected company name, preventing errors from incorrect CIK lookups. Also provides context about the company being analyzed.

**Implementation**:

- **Tool wrapper function**: `src/run_stress_tests.py` (lines 143-194)
  - Normalizes CIK format (handles various input formats)
  - Formats API response into structured dictionary
  - Handles errors and edge cases
- **Core API client**: `src/sec_edgar_client.py`
  - `SECEdgarClient.get_company_info()` (lines 176-206): Queries SEC EDGAR API
  - API endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`
  - Extracts company name, ticker, industry (SIC code/description), entity type
  - `SECEdgarClient.__init__()` (lines 53-65): Initializes client with User-Agent header from environment

**Returns**: Dictionary with `name`, `ticker`, `industry`, `cik`, `entity_type`, `sic_code`, or `error` if CIK not found.

**Example**: Input CIK `"731766"` → Returns `name: "UnitedHealth Group Inc."`, `ticker: "UNH"`, industry information, etc.

---

### 4. `search_company_cybersecurity_disclosures(cik, query="cybersecurity OR data breach OR ransomware OR security incident", years=3)`

**Purpose**: Searches Elasticsearch index for cybersecurity-related disclosures in SEC filings for a given company.

**Why it's needed**: This is the core retrieval tool that finds relevant cybersecurity information from indexed SEC filing chunks.

**Implementation**:

- **Tool wrapper function**: `src/run_stress_tests.py` (lines 197-267)
  - Normalizes CIK format
  - Calculates date range based on `years` parameter
  - Calls underlying search functions
  - Handles errors and returns structured results
- **Core search functions**: `src/sec_search_tools.py`
  - `search_cybersecurity_disclosures()` (lines 321-371): Convenience function that combines search and filtering
  - `search_sec_filings()` (lines 35-163): Core Elasticsearch query builder
    - Builds Elasticsearch query with CIK, date range, form type filters
    - Performs text search on chunk content
    - Returns chunks with relevance scores and metadata
  - `search_cybersecurity_sections()` (lines 164-230): Filters chunks to cybersecurity-relevant sections
    - Uses `CYBERSECURITY_SECTIONS` list (lines 25-32): Item 1A, Item 1B, Item 7, etc.
    - Filters by section title or content keywords
  - `index_sec_chunks()` (lines 374-467): Utility to index chunks into Elasticsearch (used during data ingestion)

**Workflow**:

1. Normalizes CIK format (handles various input formats)
2. Calculates date range: `(current_date - years*365, current_date)`
3. Calls `search_cybersecurity_disclosures()` which:
   - Queries Elasticsearch with company CIK, date range, and cybersecurity query terms
   - Filters results to cybersecurity-relevant sections (Item 1A, 1B, 7)
   - Returns top N most relevant chunks sorted by relevance score

**Returns**: List of chunk dictionaries, each containing:

- `content`: Text content of the chunk
- `metadata`: Dictionary with `cik`, `filing_date`, `form`, `section_title`, `accession_number`, `company_name`
- `score`: Elasticsearch relevance score
- `id`: Document ID in Elasticsearch

**Example**: Searches for "cybersecurity OR data breach OR ransomware" in UnitedHealth Group (CIK: 0000731766) filings from last 3 years → Returns relevant chunks from 8-K filings about the Change Healthcare ransomware incident.

---

### Tool Integration and Workflow

These tools work together in a specific orchestrated workflow:

1. **Entity Resolution Phase**:
   - `lookup_subsidiary_parent()` → Checks if company is a subsidiary
   - `lookup_company_by_name()` → Maps company name/ticker to CIK
   - `get_company_info()` → Verifies CIK matches expected company

2. **Data Retrieval Phase**:
   - `get_company_info()` → Confirms company identity
   - `search_company_cybersecurity_disclosures()` → Retrieves relevant filing chunks

3. **Error Handling**:
   - Each tool validates inputs and returns structured error messages
   - Agent workflow stops if any tool returns an error
   - Prevents incorrect CIK usage or invalid searches

**Agent Definition Locations**:

- **Jupyter Notebook**: `src/sec_cybersecurity_agent.ipynb` - Interactive agent setup and testing
- **Stress Test Runner**: `src/run_stress_tests.py` - Contains all tool implementations used for automated evaluation
- **Tool implementations**: All tools are Python functions that can be imported and used by the Pydantic AI agent framework

## Knowledge Base and Retrieval

This project uses a structured knowledge base with evaluated retrieval methods to enable accurate and efficient access to SEC cybersecurity disclosures.

### Knowledge Base Architecture

**Knowledge Base**: Elasticsearch index (`sec_filings`) containing processed SEC filing chunks

**Current Scale**: 135,481 documents indexed, covering:

- 21 ground truth cybersecurity incident cases
- Multiple companies with cybersecurity disclosures from 2014-2024
- Various SEC form types (8-K, 10-K, 10-Q, 8-K/A)

**Index Structure** (`src/sec_search_tools.py`, lines 413-428):

```python
{
  "mappings": {
    "properties": {
      "content": {"type": "text", "analyzer": "standard"},      # Full-text searchable
      "metadata.cik": {"type": "keyword"},                        # Exact match filtering
      "metadata.filing_date": {"type": "date"},                  # Date range queries
      "metadata.form": {"type": "keyword"},                       # Form type filtering
      "metadata.section_title": {"type": "text"},                 # Section-based filtering
      "metadata.accession_number": {"type": "keyword"},          # Filing identification
      "metadata.company_name": {"type": "text"}                  # Company name search
    }
  }
}
```

**Data Ingestion Pipeline**:

1. **Download**: `src/sec_edgar_client.py` - Fetches SEC filings from EDGAR API
2. **Parse**: `src/sec_xml_parser.py` - Parses XML/HTML into structured sections
3. **Chunk**: `chunk_sec_documents()` - Creates ~2000-character chunks with overlap
4. **Index**: `src/sec_search_tools.py::index_sec_chunks()` (lines 374-449) - Indexes chunks into Elasticsearch

### Retrieval Method

**Multi-Stage Retrieval Approach** (`src/sec_search_tools.py`):

#### Stage 1: Elasticsearch Query (`search_sec_filings()`, lines 35-163)

**Query Strategy**:

- **Text Search**: Elasticsearch `match` query on `content` field with relevance scoring
- **Metadata Filtering**: Boolean `must` clauses for:
  - Company CIK (exact match)
  - Date range (filing_date between start and end dates)
  - Form types (optional filter for 8-K, 10-K, etc.)
- **Relevance Ranking**: Results sorted by Elasticsearch relevance score, then by filing date (newest first)

**Why This Approach**:

- **Precision**: Metadata filters ensure results are from the correct company and time period
- **Recall**: Text search captures relevant content even with varied terminology
- **Performance**: Elasticsearch handles complex queries efficiently with sub-100ms response times
- **Scalability**: Index structure supports growth to millions of documents

#### Stage 2: Section-Based Filtering (`search_cybersecurity_sections()`, lines 164-230)

**Filtering Strategy**:

- Targets cybersecurity-relevant sections:
  - **Item 1A**: Risk Factors (cybersecurity risks)
  - **Item 1B**: Cybersecurity (dedicated cybersecurity disclosure)
  - **Item 7**: Management's Discussion and Analysis (incident discussions)
  - **Item 8.01**: Other Events (cybersecurity incident disclosures)
- Filters by section title matching or content keyword detection
- Uses `CYBERSECURITY_SECTIONS` list (lines 25-32) for consistent filtering

**Why This Approach**:

- **Relevance**: Focuses on sections most likely to contain cybersecurity information
- **Efficiency**: Reduces noise from unrelated sections (e.g., financial statements)
- **Completeness**: Captures both dedicated cybersecurity sections and incident disclosures

#### Combined Retrieval Function (`search_cybersecurity_disclosures()`, lines 321-371)

**Workflow**:

1. Calls `search_sec_filings()` with expanded result set (2x requested size)
2. Applies `search_cybersecurity_sections()` to filter to relevant sections
3. Returns top N results sorted by relevance

**Default Query**: `"cybersecurity OR data breach OR ransomware OR security incident"`

**Why This Combined Approach**:

- **Balanced Precision/Recall**: Broad initial search ensures coverage, section filtering improves precision
- **Handles Varied Terminology**: Companies use different terms (e.g., "cyber incident" vs "data breach")
- **Optimized for Domain**: Specifically tuned for cybersecurity disclosure patterns in SEC filings

### Retrieval Evaluation

**Evaluation Framework**:

1. **Ground Truth Cases** (`eval/ground_truth_21_cases.csv`):
   - 21 real-world cybersecurity incidents with known SEC filings
   - Includes company CIK, form type, filing date, accession number
   - Covers major incidents: UnitedHealth (2024), Capital One (2019), Home Depot (2014), etc.

2. **Index Coverage Tracking** (`eval/ground_truth_indexing_results.json`):
   - Tracks which ground truth filings are successfully indexed
   - Current status: 22 of 32 filings indexed (19 newly indexed, 3 already present)
   - Identifies missing filings and reasons (old filings, non-standard types, etc.)

3. **Stress Test Questions** (`eval/stress_test_questions.csv`):
   - 20 comprehensive questions testing retrieval accuracy
   - Questions 11-20 specifically test handling of missing documents
   - Validates that agent correctly identifies when information is unavailable

4. **Retrieval Performance Metrics**:
   - **Query Response Time**: <100ms for typical queries
   - **Index Coverage**: 68.75% of ground truth filings indexed (22/32)
   - **Retrieval Accuracy**: Validated against known ground truth cases

**Evaluation Results**:

- **Successful Retrieval**: Agent successfully retrieves relevant chunks for indexed filings
- **Missing Document Handling**: Agent correctly identifies when expected filings are not in index
- **Section Filtering**: Effectively filters to cybersecurity-relevant sections
- **Multi-Company Support**: Retrieval works across different companies and time periods

### Why This Retrieval Approach is Optimal

**1. Hybrid Search Strategy**:

- Combines **metadata filtering** (CIK, date, form type) for precision
- With **full-text search** (content matching) for recall
- **Section-based filtering** adds domain-specific relevance

**2. Elasticsearch Advantages**:

- **Built-in Relevance Scoring**: Uses BM25 algorithm for optimal ranking
- **Fast Metadata Filtering**: Keyword fields enable sub-millisecond filtering
- **Scalable Architecture**: Handles growth from thousands to millions of documents
- **Production-Ready**: Used by major companies for search at scale

**3. Domain-Specific Optimization**:

- **Cybersecurity Query Terms**: Pre-tuned keywords for common disclosure patterns
- **Section Targeting**: Focuses on SEC sections most likely to contain cybersecurity info
- **Temporal Filtering**: Date ranges ensure relevance to specific incident periods

**4. Evaluated and Validated**:

- Tested against 21 ground truth cases
- Validated retrieval accuracy through stress tests
- Tracks index coverage to identify gaps
- Handles edge cases (missing documents, old filings, non-standard types)

### Knowledge Base and Retrieval Documentation

**Implementation Documentation**:

- **Search Tools**: `src/sec_search_tools.py` - Complete implementation with docstrings
- **Index Structure**: `src/sec_search_tools.py::index_sec_chunks()` (lines 374-449) - Index creation and mapping
- **Data Strategy**: `documentation/README_data_strategy.md` - Architecture and design decisions
- **Search Tools Guide**: `documentation/README_search_tools.md` - Usage and integration guide

**Evaluation Documentation**:

- **Ground Truth Cases**: `eval/ground_truth_21_cases.csv` - Test cases with expected filings
- **Indexing Status**: `eval/ground_truth_indexing_results.json` - Current index coverage
- **Test Questions**: `eval/stress_test_questions.csv` - Comprehensive test suite
- **Test Results**: `eval/stress_test_results.json` - Evaluation outcomes

**This Documentation**:

- This README section provides complete overview of knowledge base and retrieval
- Agent Tools section documents retrieval tool implementation
- Evaluation Framework section describes testing methodology

## Project Structure

```text
capstone_project/
├── src/                    # Agent mechanisms and application code
│   ├── sec_edgar_client.py          # SEC EDGAR API client
│   ├── sec_xml_parser.py            # SEC filing parser and chunker
│   ├── sec_search_tools.py          # Elasticsearch search tools
│   ├── company_cik_lookup.py        # Company name to CIK mapping
│   ├── subsidiary_cik_mapping.py    # Subsidiary to parent company mapping
│   ├── run_stress_tests.py          # Stress test runner
│   ├── sec_cybersecurity_agent.ipynb # Main agent notebook
│   └── ...
│
├── eval/                   # Evaluation and testing
│   ├── tests/                       # Unit tests and judge tests
│   │   ├── agent_tests/             # Unit tests for agent responses
│   │   └── test_judge_evaluation.py # Judge evaluation tests
│   ├── judge_evaluator.py           # LLM-based judge for evaluating responses
│   ├── ground_truth_21_cases.csv    # Ground truth cases for evaluation
│   ├── stress_test_questions.csv    # Comprehensive test questions (20 questions)
│   ├── stress_test_questions_21_cases.csv  # Questions aligned with ground truth
│   ├── stress_test_results.json     # Stress test results
│   ├── judge_evaluation_results.json # Judge evaluation results
│   ├── ground_truth_indexing_results.json  # Indexing status for ground truth filings
│   └── test_notebooks/              # Evaluation notebooks
│
├── monitoring/              # Monitoring and logging system
│   ├── __init__.py                 # Package init
│   ├── agent_logging.py             # Logging utilities
│   ├── app.py                       # Streamlit dashboard
│   ├── db.py                        # Database layer
│   ├── evaluator.py                 # Rule-based evaluator
│   ├── export_ground_truth.py       # Ground truth export
│   ├── parser.py                    # Log file parser
│   ├── runner.py                    # Log processing runner
│   └── schemas.py                   # Data schemas
│
├── logs/                    # Agent run logs (JSON files)
│   └── _processed/                  # Processed logs
│
├── documentation/          # Documentation and guides
│   ├── USE_THE_AGENT.md            # How to use the agent
│   ├── CIK_LOOKUP_FIX.md            # CIK lookup improvements
│   ├── SUBSIDIARY_MAPPING_GUIDE.md  # Subsidiary mapping guide
│   └── ...
│
└── data/                   # SEC data download and indexing
    ├── sec_downloads/               # Downloaded SEC filings
    ├── index_cybersecurity_companies.py  # Index cybersecurity company filings
    ├── check_and_index_ground_truth.py   # Check and index ground truth filings
    ├── index_ground_truth_filings.py     # Index filings from ground truth CSV
    └── ...
```

## Getting Started

This section provides complete instructions for setting up and running the project from scratch.

### System Requirements

- **Python**: 3.12 or 3.13 (3.14 not supported)
- **Poetry**: For dependency management
- **Docker**: For running Elasticsearch (or native Elasticsearch installation)
- **Git**: For cloning the repository
- **OpenAI API Key**: Required for the agent to function

### Step-by-Step Setup

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-bootcamp-codespace
```

#### 2. Install Poetry (if not already installed)

```bash
# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# Or using pip
pip install poetry
```

#### 3. Install Python Dependencies

```bash
cd capstone_project
poetry install
```

This will install all required dependencies including:

- `pydantic-ai` - Agent framework
- `elasticsearch` - Search engine client
- `streamlit` - Monitoring dashboard
- `pytest` - Testing framework
- And all other dependencies listed in `pyproject.toml`

#### 4. Set Up Environment Variables

Create a `.env` file in the `capstone_project/` directory:

```bash
cd capstone_project
cat > .env << EOF
SEC_USER_AGENT=YourName YourEmail@example.com
OPENAI_API_KEY=your-openai-api-key-here
EOF
```

**Important Notes**:

- `SEC_USER_AGENT`: Must be your real name and email (SEC requirement)
- `OPENAI_API_KEY`: Get from <https://platform.openai.com/api-keys>

#### 5. Start Elasticsearch

##### Option A: Using Docker (Recommended)

```bash
cd capstone_project
./src/setup_elasticsearch.sh
```

This script will:

- Pull the Elasticsearch Docker image
- Start Elasticsearch container on port 9200
- Wait for Elasticsearch to be ready

##### Option B: Native Installation

```bash
cd capstone_project
./src/setup_elasticsearch_native.sh
```

**Verify Elasticsearch is Running**:

```bash
curl http://localhost:9200
# Should return JSON with cluster information
```

Or use the check script:

```bash
poetry run python src/check_elasticsearch.py
```

#### 6. Verify Installation

Run a quick test to ensure everything is set up correctly:

```bash
cd capstone_project
poetry run python -c "
from src.sec_search_tools import search_sec_filings
from elasticsearch import Elasticsearch
es = Elasticsearch('http://localhost:9200')
print('✅ Elasticsearch connection:', 'OK' if es.ping() else 'FAILED')
print('✅ Imports successful')
"
```

### Data Accessibility

#### Pre-Indexed Data

The project includes an Elasticsearch index with **135,481 documents** covering:

- 21 ground truth cybersecurity incident cases
- Multiple companies with cybersecurity disclosures (2014-2024)
- Various SEC form types (8-K, 10-K, 10-Q, 8-K/A)

**Note**: The index is created when you run indexing scripts. If starting fresh, you'll need to index data first (see below).

#### Indexing Your Own Data

To index SEC filings:

1. **Index Ground Truth Filings** (recommended first step):

   ```bash
   cd capstone_project
   poetry run python data/check_and_index_ground_truth.py
   ```

   This will:
   - Check which filings from `eval/ground_truth_21_cases.csv` are indexed
   - Download and index any missing filings
   - Generate a report in `eval/ground_truth_indexing_results.json`

2. **Index Additional Companies**:

   ```bash
   poetry run python data/index_cybersecurity_companies.py
   ```

   This indexes filings for 13 companies with known cybersecurity incidents.

#### Data Sources

- **SEC EDGAR API**: All data is fetched from the public SEC EDGAR API
- **No external data required**: All data is publicly accessible
- **Cached locally**: Downloaded filings are cached in `data/sec_downloads/` for faster re-indexing

### Running the Main Application

#### Option 1: Using the Jupyter Notebook (Interactive)

```bash
cd capstone_project
poetry run jupyter notebook src/sec_cybersecurity_agent.ipynb
```

This opens an interactive notebook where you can:

- Run the agent interactively
- Test different queries
- See tool calls and responses

#### Option 2: Using the Stress Test Runner (Automated)

```bash
cd capstone_project
poetry run python src/run_stress_tests.py
```

This will:

- Load questions from `eval/stress_test_questions.csv`
- Run each question through the agent
- Save results to `eval/stress_test_results.json`
- Automatically log each run to `logs/` directory

#### Option 3: Using Python Scripts Directly

```python
from src.sec_search_tools import search_cybersecurity_disclosures
from src.company_cik_lookup import lookup_company_cik

# Look up a company
result = lookup_company_cik("UnitedHealth Group")
print(f"CIK: {result['cik']}")

# Search for cybersecurity disclosures
disclosures = search_cybersecurity_disclosures(
    cik="0000731766",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
print(f"Found {len(disclosures)} disclosures")
```

### Quick Start Summary

**Using Makefile (Recommended)**:

```bash
# Complete setup and run tests
cd capstone_project
make quickstart
```

**Manual Setup**:

For a quick test run:

```bash
# 1. Install dependencies
cd capstone_project
poetry install

# 2. Set up environment
echo 'SEC_USER_AGENT=YourName YourEmail@example.com' > .env
echo 'OPENAI_API_KEY=your-key' >> .env

# 3. Start Elasticsearch
./src/setup_elasticsearch.sh

# 4. Index ground truth data
poetry run python data/check_and_index_ground_truth.py

# 5. Run a test
poetry run python src/run_stress_tests.py
```

### Using the Makefile

The project includes a `Makefile` for common operations. **All Makefile commands should be run from the `capstone_project/` directory.**

Run `make help` to see all available commands:

```bash
cd capstone_project
make help
```

**Common Makefile Commands**:

**Setup**:

- `make install` - Install Python dependencies
- `make setup` - Complete setup (install + elasticsearch + verify)
- `make check-elasticsearch` - Check if Elasticsearch is running

**Data Indexing**:

- `make index-ground-truth` - Index ground truth filings
- `make index-companies` - Index cybersecurity company filings

**Running**:

- `make run-stress-tests` - Run stress test suite
- `make run-unit-tests` - Run unit tests
- `make run-judge-tests` - Run judge evaluation tests
- `make run-judge-eval` - Run judge evaluation on stress test results
- `make test` - Run all tests (unit + judge)

**Monitoring**:

- `make process-logs` - Process logs into database
- `make watch-logs` - Watch logs directory (continuous processing)
- `make dashboard` - Start monitoring dashboard
- `make export-ground-truth` - Export ground truth dataset to CSV

**Utilities**:

- `make verify` - Verify installation
- `make clean` - Clean up temporary files
- `make quickstart` - Complete setup, index data, and run tests

## CI/CD

The project includes GitHub Actions workflows for automated testing and evaluation, following industry best practices for cost management and efficiency.

### CI/CD Strategy

**Best Practice Approach**:

1. **Fast Tests Run on Every Push** (Tests Workflow):
   - Unit tests and integration tests
   - Quick feedback (< 10 minutes)
   - Low cost (no LLM API calls)
   - Catches issues early

2. **Expensive Evaluations Run Selectively** (Evaluations Workflow):
   - Full stress tests and judge evaluations
   - Only on main/master branches (after merge)
   - On PRs with `run-evaluations` label (optional)
   - Weekly scheduled runs
   - Manual trigger for on-demand runs
   - Prevents unnecessary API costs

3. **Smart Path Filtering**:
   - Skips CI on documentation-only changes
   - Reduces unnecessary workflow runs

### Workflows

#### 1. Tests Workflow (`.github/workflows/tests.yml`)

Runs fast tests on every push and pull request:

- **Unit Tests**: Runs unit tests and judge tests (no API calls)
- **Integration Tests**: Tests with Elasticsearch service
- **Verification**: Checks Elasticsearch connection and imports

**Triggers**:

- Push to `main`, `master`, or `develop` branches (skips docs-only changes)
- Pull requests to `main`, `master`, or `develop` (skips docs-only changes)
- Manual trigger via `workflow_dispatch`

**Duration**: ~5-10 minutes  
**Cost**: Free (no API calls)

#### 2. Evaluations Workflow (`.github/workflows/evaluations.yml`)

Runs expensive stress tests and judge evaluations selectively:

- **Stress Tests**: Runs full stress test suite with Elasticsearch
- **Judge Evaluation**: Evaluates stress test results using LLM judge
- **Artifacts**: Uploads test results and evaluation results

**Triggers**:

- **Push to `main` or `master`** (after code is merged)
- **Pull requests with `run-evaluations` label** (optional, for important PRs)
- **Weekly schedule** (Mondays at 2 AM UTC)
- **Manual trigger** via `workflow_dispatch` (on-demand)

**Duration**: ~15-30 minutes  
**Cost**: Uses OpenAI API (controlled via selective triggers)

**Why This Approach**:

- Prevents expensive API calls on every push
- Still ensures evaluations run on merged code
- Allows optional evaluation on PRs when needed
- Weekly runs track performance over time

#### 3. Lint Workflow (`.github/workflows/lint.yml`)

Checks code quality:

- **Python Syntax**: Validates Python file syntax
- **README Formatting**: Checks markdown formatting (if markdownlint available)

**Triggers**:

- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop`

### Setting Up CI/CD

#### Required GitHub Secrets

Add these secrets to your GitHub repository settings:

1. **`OPENAI_API_KEY`**: Your OpenAI API key for running the agent
   - Go to: Repository Settings → Secrets and variables → Actions
   - Add new secret: `OPENAI_API_KEY` with your API key

2. **`SEC_USER_AGENT`** (optional): SEC User-Agent string

   - Defaults to "CI/CD Test Runner (test at example.com)" if not set

#### Viewing CI/CD Results

1. **GitHub Actions Tab**: Go to your repository → Actions tab
2. **Workflow Runs**: See all workflow runs and their status
3. **Artifacts**: Download test results and evaluation results from workflow runs
4. **Logs**: View detailed logs for each step

#### Running Evaluations on Pull Requests

By default, evaluations don't run on every PR to save costs. To run evaluations on a specific PR:

1. Add the `run-evaluations` label to your pull request
2. The evaluations workflow will automatically trigger

This allows you to:

- Run evaluations only when needed
- Control API costs
- Get full evaluation results for important changes

#### Running CI/CD Locally

You can test CI/CD workflows locally using [act](<https://github.com/nektos/act>):

```bash
# Install act
brew install act  # macOS
# or download from <https://github.com/nektos/act/releases>

# Run tests workflow
act -W .github/workflows/tests.yml

# Run evaluations workflow (requires OPENAI_API_KEY)
act -W .github/workflows/evaluations.yml --secret OPENAI_API_KEY=your-key
```

#### Cost Management

**Best Practices for CI/CD Costs**:

1. **Fast tests run on every push** - These are free and catch issues early
2. **Evaluations run selectively** - Only when needed to control API costs
3. **Use labels for PR evaluations** - Run expensive evaluations only on important PRs
4. **Weekly scheduled runs** - Track performance without manual intervention
5. **Manual triggers** - Run evaluations on-demand when needed

**Estimated Costs** (if running evaluations on every push):

- Stress tests: ~$0.10-0.50 per run (20 questions × API calls)
- Judge evaluation: ~$0.20-1.00 per run (20 evaluations × API calls)
- **Total per push**: ~$0.30-1.50

**With selective triggers**: Costs only when evaluations actually run (main branch, labeled PRs, scheduled, or manual).

### CI/CD Status Badge

Add a status badge to your README:

```markdown
![Tests](https://github.com/your-username/your-repo/actions/workflows/tests.yml/badge.svg)
![Evaluations](https://github.com/your-username/your-repo/actions/workflows/evaluations.yml/badge.svg)
```

### Troubleshooting

#### Elasticsearch Connection Issues

```bash
# Check if Elasticsearch is running
curl http://localhost:9200

# Check Docker container
docker ps | grep elasticsearch

# Restart Elasticsearch
docker restart elasticsearch
```

#### Import Errors

```bash
# Ensure you're in the capstone_project directory
cd capstone_project

# Reinstall dependencies
poetry install

# Activate the virtual environment
poetry shell
```

#### Missing Data

If the Elasticsearch index is empty:

```bash
# Index ground truth filings
poetry run python data/check_and_index_ground_truth.py

# Verify index has data
poetry run python -c "
from elasticsearch import Elasticsearch
es = Elasticsearch('http://localhost:9200')
count = es.count(index='sec_filings')['count']
print(f'Documents in index: {count:,}')
"
```

#### API Key Issues

```bash
# Verify .env file exists and has correct format
cat capstone_project/.env

# Test API key
poetry run python -c "
import os
from dotenv import load_dotenv
load_dotenv('capstone_project/.env')
key = os.getenv('OPENAI_API_KEY')
print('API Key:', 'SET' if key else 'MISSING')
"
```

### Additional Resources

- **Agent Usage Guide**: `documentation/USE_THE_AGENT.md`
- **Indexing Guide**: `documentation/INDEXING_GUIDE.md`
- **Data Strategy**: `documentation/README_data_strategy.md`
- **Search Tools**: `documentation/README_search_tools.md`

### Using the Agent

See `documentation/USE_THE_AGENT.md` for detailed instructions.

### Running Tests

#### Unit Tests

```bash
cd capstone_project
poetry run pytest eval/tests/ -v
```

#### Stress Tests

The stress test suite includes 20 comprehensive questions covering:

1. **Basic Capabilities** (Questions 1-3): Extract key facts, non-technical summaries, supply chain risk assessment
2. **Moderate Complexity** (Questions 4-6): Multiple incidents, nation-state attacks, regulatory failures
3. **Complex Scenarios** (Questions 7-10): Supply chain attacks, cover-ups, operational impact, comprehensive vendor evaluation
4. **Missing Document Handling** (Questions 11-20): Tests for handling incomplete information:
   - Old filings (Home Depot 2014)
   - Partial information (Yahoo/Altaba regulatory actions)
   - Non-standard document types (SEC Enforcement Orders)
   - Missing accession numbers (Capital One)
   - Private companies (Santander)
   - Multiple missing documents (SolarWinds)
   - Historical records (Sony 2014)
   - Documentation gaps across companies
   - Transparency assessment (Roku)
   - Comprehensive missing document scenarios

Run stress tests:

```bash
cd capstone_project
poetry run python src/run_stress_tests.py
```

Results are saved to `eval/stress_test_results.json`.

#### Judge Tests (LLM-Based Evaluation)

The judge evaluation system uses an LLM-based judge agent to evaluate agent responses on quality criteria:

**Evaluation Criteria**:

1. **Data Source Adherence**: Only uses SEC filings, no general knowledge
2. **Citation Quality**: Proper SEC filing citations with form types and dates
3. **Information Accuracy**: Correct extraction from SEC filings
4. **Completeness**: Addresses all aspects of the question
5. **Missing Document Handling**: Identifies gaps and explains why
6. **Response Structure**: Well-organized and professional
7. **Entity Resolution**: Correct company identification (CIKs, subsidiaries, historical names)

**Run Judge Evaluation**:

```bash
cd capstone_project
poetry run python eval/judge_evaluator.py
```

This will:

- Load stress test results from `eval/stress_test_results.json`
- Evaluate each agent response using the LLM judge
- Generate scores and feedback for each criterion
- Save results to `eval/judge_evaluation_results.json`

**Run Judge Tests** (pytest):

```bash
cd capstone_project
poetry run pytest eval/tests/test_judge_evaluation.py -v
```

Judge tests verify:

- Judge can evaluate all responses
- Evaluation structure is correct
- Judge identifies data source violations
- Citation quality is evaluated
- Average scores are meaningful
- Summary statistics are complete

**Judge Evaluation Results**:

The judge evaluation provides:

- **Overall Score**: 0-1 score for each response
- **Criteria Scores**: Pass/fail and scores for each criterion
- **Strengths/Weaknesses**: Identified by the judge
- **Summary Statistics**: Average scores, pass rates, etc.

See `eval/judge_evaluation_results.json` for detailed evaluation results.

## Monitoring

The project includes a comprehensive monitoring system for tracking agent performance, collecting user feedback, and generating ground truth datasets.

### Overview

The monitoring system:

- **Collects logs** from all agent runs (automatically logged during stress tests)
- **Evaluates responses** using rule-based checks (data source adherence, citations, etc.)
- **Provides a dashboard** for viewing logs, evaluations, and adding feedback
- **Collects user feedback** (ratings, comments, reference answers)
- **Generates ground truth datasets** from logged interactions

### Log Collection

Agent runs are automatically logged when using `run_stress_tests.py`. Logs are saved as JSON files in `capstone_project/logs/` directory.

**Log Structure**:

- Agent name, provider, model
- User prompt and system instructions
- Full message history
- Token usage (input/output)
- Agent output/response
- Timestamp

**Process Logs**:

Logs are automatically processed into a database for monitoring:

```bash
cd capstone_project
poetry run python -m monitoring.runner
```

**Watch Mode** (continuous processing):

```bash
poetry run python -m monitoring.runner --watch
```

This will:

- Process all JSON files in `logs/` directory
- Store logs in database (SQLite by default, or PostgreSQL via `DATABASE_URL`)
- Run rule-based evaluations on each log
- Move processed files to `logs/_processed/` directory

### Monitoring Dashboard

**Launch Dashboard**:

```bash
cd capstone_project
streamlit run monitoring/app.py
```

The dashboard will open at `http://localhost:8501`

**Dashboard Features**:

1. **Log Browser**: View all agent logs with filters (provider, model, agent name)
2. **Log Details**: View full prompt, instructions, and response for each log
3. **Evaluation Checks**: See rule-based evaluation results:
   - Data Source Adherence (SEC-only data)
   - Citation Quality
   - Information Accuracy
   - Completeness
   - Missing Document Handling
   - Response Structure
   - Entity Resolution
4. **User Feedback**: Add ratings (1-5), comments, and reference answers
5. **Ground Truth Dataset**: Add logs to ground truth dataset for evaluation

### User Feedback Collection

The dashboard includes a feedback form where users can:

- **Rate responses** (1-5 scale)
- **Add comments** about response quality
- **Provide reference answers** for comparison

Feedback is stored in the database and can be used to:

- Identify areas for improvement
- Generate training data
- Track agent performance over time

### Ground Truth Dataset Generation

**Add to Ground Truth**:

1. Open the monitoring dashboard
2. Select a log entry
3. Go to the "Ground Truth" tab
4. Fill in the form with:

   - Question text
   - Expected answer (optional)
   - Company name, CIK, form type, filing date (optional)
5. Click "Add to Ground Truth Dataset"

**Export Ground Truth Dataset**:

```bash
cd capstone_project
poetry run python monitoring/export_ground_truth.py
```

This exports all ground truth entries to `eval/ground_truth_from_logs.csv` for use in evaluation.

**Automatic Ground Truth Generation**:

The system automatically tracks which logs have been added to the ground truth dataset, allowing you to:

- Build evaluation datasets from real agent interactions
- Track which questions have been validated
- Export datasets for testing and evaluation

### Configuration

**Environment Variables**:

- `DATABASE_URL`: Database connection string (default: `sqlite:///capstone_project/monitoring/monitoring.db`)
  - SQLite: `sqlite:///path/to/db.db`
  - PostgreSQL: `postgresql://user:pass@host:5432/dbname`
- `LOGS_DIR`: Directory to watch for logs (default: `capstone_project/logs`)
- `POLL_SECONDS`: Polling interval for watch mode (default: `2`)

**Database Schema**:

The monitoring system uses three main tables:

- `llm_logs`: Agent run logs
- `checks`: Rule-based evaluation results
- `feedback`: User feedback on responses
- `ground_truth_dataset`: Ground truth entries for evaluation

### Log Processing Workflow

1. **Agent runs** → Logs saved to `logs/` directory as JSON
2. **Runner processes logs** → Parses JSON, extracts metadata, calculates costs
3. **Evaluator runs checks** → Rule-based evaluation on each response
4. **Results stored in database** → Available in dashboard
5. **User feedback collected** → Via dashboard interface
6. **Ground truth entries added** → Via dashboard interface
7. **Export ground truth** → CSV export for evaluation

### Accessing the Dashboard

1. **Start the dashboard**:

   ```bash
   streamlit run monitoring/app.py
   ```

2. **Open in browser**: `http://localhost:8501`

3. **Process logs first** (if not already done):

   ```bash
   poetry run python -m monitoring.runner
   ```

The dashboard will show all processed logs with evaluation results, allowing you to browse, filter, and add feedback.

### Indexing SEC Filings

See `documentation/INDEXING_GUIDE.md` for instructions on downloading and indexing SEC filings.

#### Indexing Ground Truth Filings

To ensure all ground truth cases are indexed in Elasticsearch:

```bash
cd capstone_project
poetry run python data/check_and_index_ground_truth.py
```

This script will:

- Check which filings from `eval/ground_truth_21_cases.csv` are already indexed
- Download and index any missing filings
- Generate a report in `eval/ground_truth_indexing_results.json`

**Current Index Status**: 135,481 documents indexed

- 19 of 29 missing filings successfully indexed (1,648 chunks)
- 3 filings were already indexed
- 10 filings failed (mostly due to very old filings, non-standard document types, or missing accession numbers)

## Key Features

- **Exact CIK Lookup**: Maps company names, ticker symbols, and historical names to correct CIKs
- **Subsidiary Mapping**: Automatically maps subsidiaries to parent company SEC filings
- **SEC-Only Data**: Strictly uses SEC filings as data source (no general knowledge)
- **Comprehensive Citations**: All information cited with specific SEC form types and dates
- **Missing Document Handling**: Agent can identify and handle cases where expected filings are not available in the index
- **Ground Truth Validation**: Evaluation framework with 21 ground truth cases covering major cybersecurity incidents

## Evaluation Framework

The project includes a comprehensive evaluation framework:

### Ground Truth Cases

`eval/ground_truth_21_cases.csv` contains 21 real-world cybersecurity incidents with:

- Company information (name, CIK, ticker)
- SEC filing details (form type, filing date, accession number)
- Key disclosure items
- Incident dates

These cases cover major incidents from 2014-2024 including:

- UnitedHealth Group (Change Healthcare ransomware, 2024)
- Capital One (2019)
- Home Depot (2014)
- T-Mobile (multiple breaches 2021-2023)
- Sony Pictures (2014 nation-state attack)
- Yahoo/Altaba (2014 breach, SEC enforcement)
- SolarWinds (SUNBURST supply chain attack, 2020)
- Uber (2016 breach and cover-up)
- MGM Resorts (2023 ransomware)
- Equifax (2017)
- And more...

### Stress Test Questions

`eval/stress_test_questions.csv` contains 20 test questions designed to evaluate:

- **Information Extraction**: Can the agent extract key facts from SEC filings?
- **Non-Technical Communication**: Can the agent explain technical incidents to business executives?
- **Risk Assessment**: Can the agent provide supply chain risk evaluations?
- **Missing Document Handling**: Can the agent identify and work with incomplete information?
- **Comparative Analysis**: Can the agent compare multiple companies and incidents?

### Indexing Status

The evaluation framework tracks which ground truth filings are available in the Elasticsearch index:

- **Indexed Filings**: Filings successfully downloaded and indexed
- **Missing Filings**: Filings that couldn't be indexed (old filings, non-standard types, etc.)
- **Index Coverage**: Current coverage of ground truth cases

This allows the evaluation to test the agent's ability to:

1. Work with available information
2. Identify missing information
3. Provide assessments based on partial data
4. Recommend alternative information sources

## Documentation

All documentation is in the `documentation/` folder:

- `USE_THE_AGENT.md` - How to use the agent
- `CIK_LOOKUP_FIX.md` - CIK lookup improvements
- `SUBSIDIARY_MAPPING_GUIDE.md` - Subsidiary mapping system
- `ENTITY_RESOLUTION_IMPROVEMENTS.md` - Entity resolution enhancements
- `INDEXING_GUIDE.md` - SEC filing indexing guide
- `MISSING_DISCLOSURES_INDEXING.md` - Guide for indexing missing disclosures
