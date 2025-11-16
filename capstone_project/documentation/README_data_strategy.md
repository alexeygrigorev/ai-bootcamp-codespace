# SEC EDGAR Data Strategy

This document outlines the data processing and storage strategy for the SEC EDGAR capstone project.

## Overview

The project enables AI agents to search and analyze SEC filings using intelligent chunking, file-based caching, and Elasticsearch for retrieval.

---

## 1. Chunking Strategy

### Do We Need Chunking?

**Yes, chunking is required.** SEC filings (10-K, 10-Q) are extremely long documents (often 100-200 pages) that far exceed token limits for LLM context windows.

### Chunking Approach: Hybrid Section-Aware + Sliding Window

**Two-stage approach:**

1. **Section preservation** - Preserve logical document structure (Item 1. Business, Item 7. Financials, etc.)
2. **Sliding window chunking** - For large sections that still exceed limits

### Recommended Configuration

- **Chunk size:** 2,000 characters  
- **Step size:** 1,000 characters (50% overlap)  
- **Strategy:** Section-aware chunking with overlap

### Rationale

| Consideration | Rationale |
|---------------|-----------|
| **Context Preservation** | 50% overlap ensures continuity and captures cross-boundary context |
| **Optimal Size** | 2,000 chars captures full paragraphs with financial detail; balances detail vs. token efficiency |
| **Document Coherence** | Section-aware approach preserves semantic boundaries; minimizes mid-paragraph breaks |
| **Retrieval Quality** | Overlapping chunks help capture multi-section questions with complete context |

### Implementation

```python
from sec_xml_parser import chunk_sec_documents

chunks = chunk_sec_documents(
    [parsed_document],
    size=2000,      # Maximum 2000 characters per chunk
    step=1000,      # 1000 character overlap (50%)
    chunk_by_section=True  # Preserves section boundaries
)
```

### Alternative Approaches Considered

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| 500 chars, 250 step | Very granular, precise retrieval | Too small for full paragraphs, loses context | Simple fact retrieval |
| **2000 chars, 1000 step** | **Good balance, captures context** | **Requires 2x embeddings** | **General Q&A (RECOMMENDED)** |
| 4000 chars, 2000 step | Captures full sections easily | Misses detailed nuances, more expensive | High-level summaries |

### Why This Works Best

- **Context:** 2,000 chars with 50% overlap maintains semantic flow and catches cross-boundary context
- **Size:** Full paragraphs plus context without fragmentation
- **Coherence:** Section boundaries preserved; overlap aids multi-section queries
- **Retrieval:** Overlap improves coverage for broader questions while staying focused

---

## 2. Persistent vs. In-Memory Storage

### Recommended Approach: Hybrid Two-Layer Storage

**Two components:**

1. **File-based cache** - For raw documents and processed data
2. **Elasticsearch** - For search and retrieval of chunks

### File-Based Cache

**Purpose:** Persistent storage for raw filings and processed chunks

**Why it makes sense:**
- **Avoids expensive reprocessing** - SEC filings require time to download and parse
- **Session persistence** - Survives program restarts, enables continuation of work
- **Incremental processing** - Only fetch new filings; reuse cached data
- **Easy to manage** - Delete cache when switching companies for testing

**Implementation:**
```python
# Storage structure
sec_downloads/
    ├── 0001048695/  # F5, Inc. CIK
    │   ├── ffiv-10k_2023.htm
    │   └── ffiv-10k_2022.htm
    └── chunks/
        ├── chunks_ffiv-10k_2023.json
        └── chunks_ffiv-10k_2022.json
```

**File format:**
```json
{
  "id": "ffiv-10k_2023_chunk_0",
  "content": "Business Overview section content...",
  "metadata": {
    "document_name": "ffiv-10k_2023",
    "filing_type": "Annual Report",
    "section_title": "Item 1. Business",
    "filing_date": "2023-09-30",
    "cik": "1048695",
    "form": "10-K",
    "start_pos": 0,
    "chunk_index": 0
  }
}
```

### Elasticsearch

**Purpose:** Full-text search and retrieval of processed chunks

**Why it makes sense:**
- **Full-text search** - Built for searching across large text datasets
- **Metadata filtering** - Filter by company, date, section, form type
- **Retrieval efficiency** - Fast semantic search with relevance ranking
- **Scalable** - Handles growth from a few companies to many

**Index structure:**
```python
# Elasticsearch index mapping
{
  "mappings": {
    "properties": {
      "content": {"type": "text", "analyzer": "standard"},
      "metadata.cik": {"type": "keyword"},
      "metadata.filing_date": {"type": "date"},
      "metadata.form": {"type": "keyword"},
      "metadata.section_title": {"type": "text"},
      "metadata.filing_type": {"type": "keyword"}
    }
  }
}
```

### Why Not In-Memory?

| Reason | In-Memory Problem | Our Solution |
|--------|-------------------|--------------|
| **Reprocessing Cost** | Download + parse ~250 minutes (50 filings × 5 min) | Cache = instant load |
| **Dataset Size** | Multiple companies × filings = huge memory | Elasticsearch handles efficiently |
| **Session Persistence** | Lose work between runs | Survives restarts |
| **Data Sharing** | Can't share between runs/users | File cache + Elasticsearch support sharing |

### Production vs. Prototype

**Production System (Hypothetical):**
- Store ALL SEC filings across all companies
- Automated daily/weekly updates
- Millions of filings and billions of chunks
- Requires distributed architecture

**Agent Use Case (Our Prototype):**
- One company at a time (1–4 annual reports per company)
- ~3 years of filings = ~100–400 filings × ~20–50 chunks each
- Roughly 5,000–10,000 docs per company analysis
- Elasticsearch handles this easily in a single index

### Data Flow

```
┌─────────────────┐
│  SEC EDGAR API │
└────────┬────────┘
         │ Fetch filings
         ▼
┌─────────────────┐      ┌──────────────┐
│ File Cache      │─────▶│  JSON Files  │
│ (Raw Documents) │      │  (Parsed)    │
└────────┬────────┘      └──────────────┘
         │ Parse & Chunk
         ▼
┌─────────────────┐
│ Elasticsearch   │◀───── Cache chunks for
│ (Search Index)  │      agent retrieval
└─────────────────┘
         │
         ▼
    AI Agent queries
```

### Implementation

**Basic workflow:**

```python
from sec_edgar_client import SECEdgarClient
from sec_xml_parser import parse_sec_filing, chunk_sec_documents
from elasticsearch import Elasticsearch

# 1. Fetch and download filings
client = SECEdgarClient()
filings = client.fetch_filings("1048695", years=3)  # F5, Inc.

# 2. Parse and chunk (with caching)
for filing in filings:
    if not cached(filing):
        file_path = client.download_filing_document(...)
        parsed = parse_sec_filing(file_path)
        chunks = chunk_sec_documents([parsed])
        cache_to_disk(chunks, f"chunks_{filing['primary_document']}.json")

# 3. Index in Elasticsearch
es = Elasticsearch()
for chunk in chunks:
    es.index(index="sec_filings", document=chunk)

# 4. Agent queries
results = es.search(
    index="sec_filings",
    query={"match": {"content": "revenue growth"}},
    filter={"metadata.cik": "1048695"}
)
```

---

## 3. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Source** | SEC EDGAR API | Public filings |
| **Downloader** | `sec_edgar_client.py` | Fetch filings by CIK |
| **Parser** | `sec_xml_parser.py` | Parse XML/HTML documents |
| **Chunker** | `chunk_sec_documents()` | Intelligent text chunking |
| **Cache** | File system + JSON | Persistent storage |
| **Search** | Elasticsearch | Full-text retrieval |
| **Agent** | Pydantic AI / LangChain | LLM-powered analysis |

---

## 4. Performance Characteristics

### Data Volume

**Single company analysis (e.g., F5, Inc.):**
- Raw documents: ~100–400 KB per filing × 50–200 filings = 5–80 MB
- Chunks: 5,000–10,000 chunks × ~2,000 chars = 10–20 MB
- Elasticsearch index: ~50–100 MB (with analysis overhead)

**Estimated processing time:**
- Download: 10–30 minutes (respecting rate limits)
- Parsing: 2–5 minutes
- Chunking: 1–2 minutes
- Indexing: 1–2 minutes
- **Total (with cache):** ~20–40 minutes first run, <1 minute subsequent runs

### Query Performance

**Elasticsearch (typical hardware):**
- Query time: <100ms for most searches
- Concurrent queries: Handles 100+ QPS easily
- Metadata filtering: Near-instant (keyword fields)

---

## 5. Best Practices

### Cache Management

1. **Organize by CIK** - Separate directories per company
2. **Version control** - Include filing date in filenames
3. **Cleanup** - Delete when switching companies for testing
4. **Incremental updates** - Only fetch new filings since last run

### Elasticsearch Tips

1. **Single index** - Use one index with CIK metadata for filtering
2. **Metadata fields** - Index key fields as keywords for fast filtering
3. **Bulk indexing** - Use bulk API for efficient loading
4. **Index management** - Create/delete indices per company if needed

### Chunking Best Practices

1. **Validate chunk size** - Ensure no chunks exceed model limits
2. **Preserve structure** - Always maintain section boundaries when possible
3. **Add metadata** - Enrich chunks with source, section, date information
4. **Test overlap** - Adjust step size based on retrieval quality

---

## 6. Future Enhancements

### Potential Optimizations

1. **Embedding cache** - Pre-compute and store embeddings
2. **Delta updates** - Only process new filings since last run
3. **Distributed caching** - Redis for hot data, file cache for cold
4. **Multi-company support** - Per-company indices or tagged data

### Production Considerations

For a full production system:
- Store ALL SEC data (all companies, all time)
- Automated daily sync via scheduled jobs
- Distributed Elasticsearch cluster
- Embedding pre-computation pipeline
- Versioning and data archival strategies

---

## Conclusion

This hybrid approach provides:
- ✅ **Efficient processing** - Avoid reprocessing expensive operations
- ✅ **Fast retrieval** - Elasticsearch enables semantic search
- ✅ **Session persistence** - Work survives restarts
- ✅ **Scalability** - Handles prototype to moderate production loads
- ✅ **Simplicity** - File cache + Elasticsearch is easy to manage

The strategy balances performance, persistence, and simplicity for an AI agent analyzing SEC filings.

