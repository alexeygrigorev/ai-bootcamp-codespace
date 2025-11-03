"""
SEC Filing Search Tools

Tools for searching SEC filings in Elasticsearch with filtering by company CIK,
date range, and cybersecurity-relevant sections.

These tools are designed to work with chunks that have been indexed in Elasticsearch
with the following structure:
- content: text field (searchable content)
- metadata.cik: keyword field (company CIK)
- metadata.filing_date: date field
- metadata.form: keyword field (10-K, 10-Q, etc.)
- metadata.section_title: text field (Item 1A, Item 1B, etc.)
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from elasticsearch import Elasticsearch


# Cybersecurity-relevant sections in SEC filings
# Item 1A: Risk Factors (often contains cybersecurity risks)
# Item 1B: Cybersecurity (specific cybersecurity disclosure)
# Item 7: Management's Discussion and Analysis (may discuss cyber incidents)
CYBERSECURITY_SECTIONS = [
    "Item 1A",
    "Item 1B", 
    "Item 7",
    "Risk Factors",
    "Cybersecurity",
    "Management's Discussion"
]


def search_sec_filings(
    company_cik: str,
    query: str,
    date_range: Tuple[str, str],
    index_name: str = "sec_filings",
    num_results: int = 20,
    form_types: Optional[List[str]] = None,
    es_client: Optional[Elasticsearch] = None
) -> List[Dict[str, Any]]:
    """
    Search SEC filings for a given company, query, and date range.
    
    Searches Elasticsearch index for relevant SEC filing chunks filtered by:
    - Company CIK
    - Date range (start_date, end_date)
    - Optional form type filter (10-K, 10-Q, etc.)
    
    Args:
        company_cik: Central Index Key (CIK) of the company to search
        query: Search query text (e.g., "cybersecurity", "data breach", "ransomware")
        date_range: Tuple of (start_date, end_date) in format "YYYY-MM-DD"
        index_name: Name of the Elasticsearch index (default: "sec_filings")
        num_results: Maximum number of results to return (default: 20)
        form_types: Optional list of form types to filter by (e.g., ["10-K", "10-Q"])
        es_client: Optional Elasticsearch client (defaults to localhost:9200)
    
    Returns:
        List of dictionaries containing search results with:
        - content: Chunk content text
        - metadata: Filing metadata (CIK, date, form, section, etc.)
        - score: Relevance score from Elasticsearch
    
    Example:
        >>> results = search_sec_filings(
        ...     company_cik="1048695",
        ...     query="cybersecurity incident",
        ...     date_range=("2021-01-01", "2024-12-31"),
        ...     form_types=["10-K"]
        ... )
    """
    # Initialize Elasticsearch client if not provided
    if es_client is None:
        es_client = Elasticsearch('http://localhost:9200')
    
    # Normalize CIK to 10 digits with leading zeros
    cik_normalized = str(company_cik).zfill(10)
    
    # Parse date range
    start_date, end_date = date_range
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"Invalid date format. Use 'YYYY-MM-DD': {e}")
    
    # Build Elasticsearch query
    must_clauses = []
    
    # Text search in content
    if query:
        must_clauses.append({
            "match": {
                "content": {
                    "query": query,
                    "boost": 2.0  # Boost content matches
                }
            }
        })
    
    # Filter by CIK
    must_clauses.append({
        "term": {
            "metadata.cik": cik_normalized
        }
    })
    
    # Filter by date range
    must_clauses.append({
        "range": {
            "metadata.filing_date": {
                "gte": start_date,
                "lte": end_date,
                "format": "yyyy-MM-dd"
            }
        }
    })
    
    # Filter by form type if specified
    if form_types:
        must_clauses.append({
            "terms": {
                "metadata.form": form_types
            }
        })
    
    # Build full query
    es_query = {
        "size": num_results,
        "query": {
            "bool": {
                "must": must_clauses
            }
        },
        "sort": [
            {"_score": {"order": "desc"}},  # Sort by relevance
            {"metadata.filing_date": {"order": "desc"}}  # Then by date (newest first)
        ]
    }
    
    try:
        response = es_client.search(index=index_name, body=es_query)
        
        # Extract results
        results = []
        for hit in response['hits']['hits']:
            result = {
                'content': hit['_source'].get('content', ''),
                'metadata': hit['_source'].get('metadata', {}),
                'score': hit['_score'],
                'id': hit['_id']
            }
            results.append(result)
        
        return results
    
    except Exception as e:
        raise RuntimeError(f"Error searching Elasticsearch: {e}")


def search_cybersecurity_sections(
    filing_chunks: List[Dict[str, Any]],
    additional_keywords: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Filter filing chunks to focus on cybersecurity-relevant sections.
    
    Identifies chunks from sections most likely to contain cybersecurity disclosures:
    - Item 1A (Risk Factors)
    - Item 1B (Cybersecurity) 
    - Item 7 (Management's Discussion and Analysis)
    
    Args:
        filing_chunks: List of chunk dictionaries from search_sec_filings()
        additional_keywords: Optional list of keywords to match in section titles
    
    Returns:
        Filtered list of chunks from cybersecurity-relevant sections
    
    Example:
        >>> all_chunks = search_sec_filings("1048695", "security", ("2021-01-01", "2024-12-31"))
        >>> cyber_chunks = search_cybersecurity_sections(all_chunks, ["breach", "ransomware"])
    """
    if not filing_chunks:
        return []
    
    # Combine default sections with additional keywords if provided
    search_terms = CYBERSECURITY_SECTIONS.copy()
    if additional_keywords:
        search_terms.extend(additional_keywords)
    
    # Normalize search terms for matching
    search_terms_lower = [term.lower() for term in search_terms]
    
    filtered_chunks = []
    
    for chunk in filing_chunks:
        metadata = chunk.get('metadata', {})
        section_title = metadata.get('section_title', '')
        section_lower = section_title.lower()
        
        # Check if section title matches any cybersecurity-related term
        is_cybersecurity_section = any(
            term in section_lower for term in search_terms_lower
        )
        
        # Also check content for cybersecurity keywords if section doesn't match
        if not is_cybersecurity_section:
            content = chunk.get('content', '').lower()
            cybersecurity_keywords = ['cyber', 'security', 'breach', 'ransomware', 
                                     'data breach', 'hack', 'incident', 'vulnerability']
            
            # Check if content contains cybersecurity keywords in first 500 chars
            content_preview = content[:500]
            has_cyber_content = any(
                keyword in content_preview for keyword in cybersecurity_keywords
            )
            
            if has_cyber_content:
                is_cybersecurity_section = True
        
        if is_cybersecurity_section:
            filtered_chunks.append(chunk)
    
    return filtered_chunks


def get_company_filing_summary(
    company_cik: str,
    date_range: Tuple[str, str],
    index_name: str = "sec_filings",
    es_client: Optional[Elasticsearch] = None
) -> Dict[str, Any]:
    """
    Get a summary of filings available for a company in a date range.
    
    Useful for understanding what filings are indexed before performing searches.
    
    Args:
        company_cik: Central Index Key (CIK) of the company
        date_range: Tuple of (start_date, end_date) in format "YYYY-MM-DD"
        index_name: Name of the Elasticsearch index
        es_client: Optional Elasticsearch client
    
    Returns:
        Dictionary with:
        - total_chunks: Total number of chunks for this company/date range
        - filings_by_form: Count of chunks grouped by form type
        - sections_found: List of unique section titles
        - date_range: The date range queried
    """
    if es_client is None:
        es_client = Elasticsearch('http://localhost:9200')
    
    cik_normalized = str(company_cik).zfill(10)
    start_date, end_date = date_range
    
    # Aggregation query to get summary statistics
    es_query = {
        "size": 0,  # Don't return documents, just aggregations
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.cik": cik_normalized}},
                    {
                        "range": {
                            "metadata.filing_date": {
                                "gte": start_date,
                                "lte": end_date,
                                "format": "yyyy-MM-dd"
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "forms": {
                "terms": {
                    "field": "metadata.form",
                    "size": 20
                }
            },
            "sections": {
                "terms": {
                    "field": "metadata.section_title",
                    "size": 50
                }
            }
        }
    }
    
    try:
        response = es_client.search(index=index_name, body=es_query)
        
        filings_by_form = {
            bucket['key']: bucket['doc_count']
            for bucket in response['aggregations']['forms']['buckets']
        }
        
        sections_found = [
            bucket['key'] for bucket in response['aggregations']['sections']['buckets']
        ]
        
        return {
            'total_chunks': response['hits']['total']['value'],
            'filings_by_form': filings_by_form,
            'sections_found': sections_found,
            'date_range': date_range,
            'cik': cik_normalized
        }
    
    except Exception as e:
        raise RuntimeError(f"Error getting filing summary: {e}")


# Convenience function that combines both search functions
def search_cybersecurity_disclosures(
    company_cik: str,
    query: str,
    date_range: Tuple[str, str],
    index_name: str = "sec_filings",
    num_results: int = 20,
    form_types: Optional[List[str]] = None,
    es_client: Optional[Elasticsearch] = None
) -> List[Dict[str, Any]]:
    """
    Combined search that finds SEC filings and filters for cybersecurity sections.
    
    This is a convenience function that calls search_sec_filings() followed by
    search_cybersecurity_sections() to get cybersecurity-relevant chunks.
    
    Args:
        company_cik: Central Index Key (CIK) of the company
        query: Search query text
        date_range: Tuple of (start_date, end_date) in format "YYYY-MM-DD"
        index_name: Name of the Elasticsearch index
        num_results: Maximum number of results to return
        form_types: Optional list of form types to filter by
        es_client: Optional Elasticsearch client
    
    Returns:
        Filtered list of cybersecurity-relevant chunks
    
    Example:
        >>> results = search_cybersecurity_disclosures(
        ...     company_cik="1048695",
        ...     query="data breach incident",
        ...     date_range=("2021-01-01", "2024-12-31"),
        ...     form_types=["10-K"]
        ... )
    """
    # First, get all matching chunks
    all_chunks = search_sec_filings(
        company_cik=company_cik,
        query=query,
        date_range=date_range,
        index_name=index_name,
        num_results=num_results * 2,  # Get more results for filtering
        form_types=form_types,
        es_client=es_client
    )
    
    # Then filter for cybersecurity sections
    cyber_chunks = search_cybersecurity_sections(all_chunks)
    
    # Return top N results
    return cyber_chunks[:num_results]


def index_sec_chunks(
    chunks: List[Dict[str, Any]],
    index_name: str = "sec_filings",
    es_client: Optional[Elasticsearch] = None,
    create_index: bool = True
) -> int:
    """
    Index SEC filing chunks into Elasticsearch.
    
    Works with chunks created by the existing sec_xml_parser chunking pipeline.
    Expects chunks in the format from sec_filing_chunker_example.ipynb:
    - id: unique chunk identifier
    - content: chunk text content
    - metadata: dictionary with cik, filing_date, form, section_title, etc.
    
    Args:
        chunks: List of chunk dictionaries (from chunk_sec_documents + metadata enhancement)
        index_name: Name of the Elasticsearch index (default: "sec_filings")
        es_client: Optional Elasticsearch client (defaults to localhost:9200)
        create_index: If True, creates the index with proper mapping if it doesn't exist
    
    Returns:
        Number of chunks successfully indexed
    
    Example:
        >>> from sec_edgar_client import SECEdgarClient
        >>> from sec_xml_parser import parse_sec_filing, chunk_sec_documents
        >>> # ... download and parse filings ...
        >>> chunks = chunk_sec_documents([parsed_doc])
        >>> # Enhance with metadata (as shown in sec_filing_chunker_example.ipynb)
        >>> enhanced_chunks = [...]
        >>> indexed_count = index_sec_chunks(enhanced_chunks)
    """
    if es_client is None:
        es_client = Elasticsearch('http://localhost:9200')
    
    # Create index with proper mapping if needed
    if create_index:
        if not es_client.indices.exists(index=index_name):
            index_settings = {
                "mappings": {
                    "properties": {
                        "content": {"type": "text", "analyzer": "standard"},
                        "metadata.cik": {"type": "keyword"},
                        "metadata.filing_date": {"type": "date"},
                        "metadata.form": {"type": "keyword"},
                        "metadata.section_title": {"type": "text"},
                        "metadata.filing_type": {"type": "keyword"},
                        "metadata.document_name": {"type": "text"},
                        "metadata.start_pos": {"type": "integer"},
                        "metadata.chunk_index": {"type": "integer"}
                    }
                }
            }
            es_client.indices.create(index=index_name, body=index_settings)
            print(f"Created index: {index_name}")
    
    # Index chunks
    indexed_count = 0
    for chunk in chunks:
        try:
            # Use the chunk's id if available, otherwise generate one
            doc_id = chunk.get('id', f"{chunk.get('metadata', {}).get('document_name', 'unknown')}_{indexed_count}")
            
            es_client.index(
                index=index_name,
                id=doc_id,
                document=chunk
            )
            indexed_count += 1
        except Exception as e:
            print(f"Error indexing chunk {chunk.get('id', 'unknown')}: {e}")
            continue
    
    print(f"Indexed {indexed_count} chunks into {index_name}")
    return indexed_count


if __name__ == "__main__":
    # Example usage
    print("SEC Filing Search Tools")
    print("=" * 80)
    print("\nAvailable functions:")
    print("1. search_sec_filings() - Search SEC filings by CIK, query, date range")
    print("2. search_cybersecurity_sections() - Filter chunks for cyber sections")
    print("3. search_cybersecurity_disclosures() - Combined search + filter")
    print("4. get_company_filing_summary() - Get summary of available filings")
    print("5. index_sec_chunks() - Index chunks from your chunking pipeline into Elasticsearch")
    print("\nThese tools work with chunks created by:")
    print("- sec_edgar_client.py (downloads filings)")
    print("- sec_xml_parser.py (parses and chunks)")
    print("- sec_filing_chunker_example.ipynb (shows the full pipeline)")

