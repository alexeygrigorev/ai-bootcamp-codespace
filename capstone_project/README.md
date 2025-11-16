# SEC Cybersecurity Disclosure Agent

An AI agent that extracts and analyzes cybersecurity disclosures from SEC filings using Pydantic AI.

## Project Structure

```
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
│   ├── tests/                       # Unit tests for agent responses
│   ├── stress_test_questions.csv    # Test questions
│   └── stress_test_results.json    # Test results
│
├── documentation/          # Documentation and guides
│   ├── USE_THE_AGENT.md            # How to use the agent
│   ├── CIK_LOOKUP_FIX.md            # CIK lookup improvements
│   ├── SUBSIDIARY_MAPPING_GUIDE.md  # Subsidiary mapping guide
│   └── ...
│
└── data/                   # SEC data download and indexing
    ├── sec_downloads/               # Downloaded SEC filings
    ├── index_cybersecurity_companies.py
    └── ...
```

## Quick Start

### Prerequisites

1. **Elasticsearch**: Running via Docker
   ```bash
   ./src/setup_elasticsearch.sh
   ```

2. **Environment Variables**: Create `.env` file with:
   ```
   SEC_USER_AGENT=YourName YourEmail@example.com
   OPENAI_API_KEY=your-key-here
   ```

3. **Dependencies**: Install via Poetry
   ```bash
   poetry install
   ```

### Using the Agent

See `documentation/USE_THE_AGENT.md` for detailed instructions.

### Running Tests

```bash
cd capstone_project
poetry run pytest eval/tests/ -v
```

### Indexing SEC Filings

See `documentation/INDEXING_GUIDE.md` for instructions on downloading and indexing SEC filings.

## Key Features

- **Exact CIK Lookup**: Maps company names, ticker symbols, and historical names to correct CIKs
- **Subsidiary Mapping**: Automatically maps subsidiaries to parent company SEC filings
- **SEC-Only Data**: Strictly uses SEC filings as data source (no general knowledge)
- **Comprehensive Citations**: All information cited with specific SEC form types and dates

## Documentation

All documentation is in the `documentation/` folder:
- `USE_THE_AGENT.md` - How to use the agent
- `CIK_LOOKUP_FIX.md` - CIK lookup improvements
- `SUBSIDIARY_MAPPING_GUIDE.md` - Subsidiary mapping system
- `ENTITY_RESOLUTION_IMPROVEMENTS.md` - Entity resolution enhancements
- `INDEXING_GUIDE.md` - SEC filing indexing guide
