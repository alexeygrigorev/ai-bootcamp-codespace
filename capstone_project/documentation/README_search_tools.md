# SEC Filing Search Tools

This module provides tools for searching SEC filings in Elasticsearch, specifically designed for finding cybersecurity disclosures relevant to supply chain security analysis.

## Overview

The `sec_search_tools.py` module contains two main search tools:

1. **`search_sec_filings()`** - Core search function that queries Elasticsearch for SEC filing chunks
2. **`search_cybersecurity_sections()`** - Filters chunks to focus on cybersecurity-relevant sections

Additionally, a convenience function **`search_cybersecurity_disclosures()`** combines both operations.

## Tools Implemented

### Tool 1: `search_sec_filings()`

**Purpose:** Search SEC filings in Elasticsearch filtered by company CIK, date range, and form type.

**Parameters:**
- `company_cik` (str): Company Central Index Key
- `query` (str): Search query text (e.g., "cybersecurity", "data breach")
- `date_range` (Tuple[str, str]): (start_date, end_date) in "YYYY-MM-DD" format
- `index_name` (str): Elasticsearch index name (default: "sec_filings")
- `num_results` (int): Maximum results to return (default: 20)
- `form_types` (Optional[List[str]]): Filter by form types like ["10-K", "10-Q"]
- `es_client` (Optional[Elasticsearch]): Elasticsearch client (defaults to localhost:9200)

**Returns:**
List of dictionaries with:
- `content`: Chunk content text
- `metadata`: Filing metadata (CIK, date, form, section, etc.)
- `score`: Elasticsearch relevance score
- `id`: Document ID

**Example:**
```python
from sec_search_tools import search_sec_filings

results = search_sec_filings(
    company_cik="1048695",  # F5, Inc.
    query="cybersecurity incident",
    date_range=("2021-01-01", "2024-12-31"),
    form_types=["10-K"],
    num_results=20
)
```

### Tool 2: `search_cybersecurity_sections()`

**Purpose:** Filter filing chunks to focus on sections most likely to contain cybersecurity disclosures.

**Targets sections:**
- Item 1A (Risk Factors)
- Item 1B (Cybersecurity)
- Item 7 (Management's Discussion and Analysis)

**Parameters:**
- `filing_chunks` (List[Dict]): Chunks from `search_sec_filings()`
- `additional_keywords` (Optional[List[str]]): Extra keywords to match in section titles

**Returns:**
Filtered list of chunks from cybersecurity-relevant sections.

**Example:**
```python
from sec_search_tools import search_sec_filings, search_cybersecurity_sections

# Get all chunks
all_chunks = search_sec_filings("1048695", "security", ("2021-01-01", "2024-12-31"))

# Filter for cybersecurity sections
cyber_chunks = search_cybersecurity_sections(all_chunks, ["breach", "ransomware"])
```

### Convenience Function: `search_cybersecurity_disclosures()`

**Purpose:** Combined function that searches and filters in one call.

**Example:**
```python
from sec_search_tools import search_cybersecurity_disclosures

results = search_cybersecurity_disclosures(
    company_cik="1048695",
    query="data breach incident",
    date_range=("2021-01-01", "2024-12-31"),
    form_types=["10-K"]
)
```

## How It Works

### Elasticsearch Query Structure

The search tool builds a boolean query with:
- **Text matching** in the `content` field (boosted for relevance)
- **CIK filtering** using exact term match
- **Date range filtering** on `metadata.filing_date`
- **Form type filtering** (optional, e.g., 10-K only)

Results are sorted by:
1. Relevance score (highest first)
2. Filing date (newest first)

### Section Filtering

The cybersecurity section filter:
1. Checks section titles for keywords (Item 1A, Item 1B, Item 7, etc.)
2. Falls back to content analysis if section title doesn't match
3. Looks for cybersecurity keywords in content preview

### Expected Elasticsearch Index Structure

The tools expect chunks indexed with this structure:

```json
{
  "content": "Full chunk text content...",
  "metadata": {
    "cik": "0001048695",
    "filing_date": "2023-09-30",
    "form": "10-K",
    "section_title": "Item 1A. Risk Factors",
    "document_name": "ffiv-10k_2023",
    "filing_type": "Annual Report",
    "start_pos": 0,
    "chunk_index": 0
  }
}
```

Index mapping should include:
- `content`: `text` type (searchable)
- `metadata.cik`: `keyword` type (exact match)
- `metadata.filing_date`: `date` type
- `metadata.form`: `keyword` type
- `metadata.section_title`: `text` type (for aggregations)

## Integration with Existing Code

These tools integrate with:
- **`sec_edgar_client.py`** - For fetching filings from SEC EDGAR API
- **`sec_xml_parser.py`** - For parsing and chunking filings
- **Elasticsearch** - For indexing and searching chunks

### Typical Workflow

1. **Index filings** (using existing chunking pipeline):
   ```python
   from sec_edgar_client import SECEdgarClient
   from sec_xml_parser import parse_sec_filing, chunk_sec_documents
   from elasticsearch import Elasticsearch
   
   # Download and parse
   client = SECEdgarClient()
   filings = client.fetch_filings("1048695", years=3)
   # ... download and parse filings ...
   chunks = chunk_sec_documents([parsed_doc])
   
   # Index in Elasticsearch
   es = Elasticsearch()
   for chunk in chunks:
       es.index(index="sec_filings", document=chunk)
   ```

2. **Search with tools**:
   ```python
   from sec_search_tools import search_cybersecurity_disclosures
   
   results = search_cybersecurity_disclosures(
       company_cik="1048695",
       query="cybersecurity",
       date_range=("2021-01-01", "2024-12-31")
   )
   ```

## Dependencies

- `elasticsearch` - Python Elasticsearch client
- Existing SEC filing infrastructure (`sec_edgar_client.py`, `sec_xml_parser.py`)

## Error Handling

The tools raise:
- `ValueError` - For invalid date formats
- `RuntimeError` - For Elasticsearch connection or query errors

## Future Enhancements

Potential improvements:
- Add semantic search support (vector embeddings)
- Support for multi-company searches
- Advanced relevance ranking customization
- Caching for frequently queried results
- Support for additional section filtering criteria

