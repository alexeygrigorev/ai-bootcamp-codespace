#!/usr/bin/env python3
"""
Index all Home Depot 2014 data breach related SEC filings.

Filings to index:
1. September 18, 2014 8-K - Initial breach disclosure
2. November 6, 2014 8-K - Comprehensive breach findings (already done, but will verify)
3. Q3 2014 10-Q - August 31, 2014 - $43M expenses
4. FY 2015 10-K - March 2017 - $198M total costs
"""

from pathlib import Path
import time
from datetime import datetime

from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch

# Home Depot CIK
CIK = "0000354950"

# Specific filings to index
FILINGS_TO_INDEX = [
    {
        "accession_number": "0000354950-14-000037",
        "document_name": "HD_8K_09.18.2014",
        "filing_date": "2014-09-18",
        "form": "8-K",
        "description": "Initial breach disclosure - September 18, 2014"
    },
    {
        "accession_number": "0000354950-14-000042",
        "document_name": "hd_8kx110614.htm",
        "filing_date": "2014-11-06",
        "form": "8-K",
        "description": "Comprehensive breach findings - November 6, 2014"
    },
]

# Additional filings to find and index
ADDITIONAL_FILINGS = [
    {
        "form": "10-Q",
        "filing_date_range": ("2014-08-01", "2014-09-30"),
        "description": "Q3 2014 10-Q - August 31, 2014 - $43M expenses"
    },
    {
        "form": "10-K",
        "filing_date_range": ("2017-03-01", "2017-03-31"),
        "description": "FY 2015 10-K - March 2017 - $198M total costs"
    },
]

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 1000


def enhance_chunks_with_metadata(chunks, filing_info):
    """Enhance chunks with filing metadata."""
    enhanced = []
    for i, chunk in enumerate(chunks):
        enhanced_chunk = {
            "id": f"{filing_info['document_name']}_chunk_{i}",
            "content": chunk.get("content", ""),
            "metadata": {
                **chunk.get("metadata", {}),
                "cik": CIK,
                "filing_date": filing_info["filing_date"],
                "form": filing_info["form"],
                "accession_number": filing_info.get("accession_number", ""),
                "document_name": filing_info["document_name"],
            }
        }
        enhanced.append(enhanced_chunk)
    return enhanced


def find_filing_by_date_range(client, form_type, date_range):
    """Find a filing by form type and date range."""
    start_date, end_date = date_range
    start_year = int(start_date.split("-")[0])
    
    # Fetch filings for the year
    years_back = datetime.now().year - start_year + 1
    filings = client.fetch_filings(CIK, years=years_back)
    
    # Filter by form and date range
    matching_filings = []
    for filing in filings:
        if filing.get("form") == form_type:
            filing_date = filing.get("filing_date", "")
            if filing_date and start_date <= filing_date <= end_date:
                matching_filings.append(filing)
    
    return matching_filings


def index_specific_filing(client, es_client, output_dir, filing_info):
    """Index a specific filing with known accession number and document name."""
    print(f"\n{'='*80}")
    print(f"Indexing: {filing_info['description']}")
    print(f"  Form: {filing_info['form']}")
    print(f"  Date: {filing_info['filing_date']}")
    print(f"  Accession: {filing_info.get('accession_number', 'N/A')}")
    print(f"  Document: {filing_info['document_name']}")
    print(f"{'='*80}")
    
    try:
        # Check if already indexed
        existing = es_client.count(
            index="sec_filings",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.cik": CIK}},
                            {"term": {"metadata.form": filing_info["form"]}},
                            {"term": {"metadata.filing_date": filing_info["filing_date"]}}
                        ]
                    }
                }
            }
        )['count']
        
        if existing > 0:
            print(f"⚠️  Filing already indexed ({existing} chunks found)")
            print("   Skipping to avoid duplicates...")
            return {"status": "skipped", "chunks": existing}
        
        # Download the filing
        print(f"\nDownloading filing...")
        downloaded_path = client.download_filing_document(
            accession_number=filing_info["accession_number"],
            primary_document=filing_info["document_name"],
            cik=CIK,
            output_dir=str(output_dir)
        )
        
        if downloaded_path and Path(downloaded_path).exists():
            print(f"✓ Downloaded to: {downloaded_path}")
            file_path = downloaded_path
        else:
            print(f"❌ Download failed")
            return {"status": "error", "error": "Download failed"}
        
        # Parse the filing
        print(f"Parsing filing...")
        parsed = parse_sec_filing(file_path, document_name=filing_info["document_name"])
        print(f"✓ Parsed successfully")
        
        # Chunk the document
        print(f"Chunking document...")
        chunks = chunk_sec_documents(
            [parsed],
            size=CHUNK_SIZE,
            step=CHUNK_SIZE - CHUNK_OVERLAP
        )
        print(f"✓ Created {len(chunks)} chunks")
        
        # Enhance with metadata
        enhanced_chunks = enhance_chunks_with_metadata(chunks, filing_info)
        
        # Index the chunks
        print(f"Indexing {len(enhanced_chunks)} chunks...")
        indexed_count = index_sec_chunks(
            enhanced_chunks,
            index_name="sec_filings",
            es_client=es_client,
            create_index=True
        )
        
        print(f"✓ Indexed {indexed_count} chunks")
        return {"status": "success", "chunks": indexed_count}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": error_msg}


def index_filing_by_search(client, es_client, output_dir, filing_spec):
    """Find and index a filing by searching for it."""
    print(f"\n{'='*80}")
    print(f"Searching for: {filing_spec['description']}")
    print(f"  Form: {filing_spec['form']}")
    print(f"  Date range: {filing_spec['filing_date_range']}")
    print(f"{'='*80}")
    
    try:
        matching_filings = find_filing_by_date_range(
            client,
            filing_spec["form"],
            filing_spec["filing_date_range"]
        )
        
        if not matching_filings:
            print(f"⚠️  No filings found matching criteria")
            return {"status": "not_found", "chunks": 0}
        
        print(f"Found {len(matching_filings)} matching filing(s)")
        
        total_chunks = 0
        for filing in matching_filings:
            filing_date = filing.get("filing_date", "")
            doc_name = filing.get("primary_document", "")
            accession = filing.get("accession_number", "")
            
            print(f"\n  Processing: {filing_date} - {doc_name}")
            
            # Check if already indexed
            existing = es_client.count(
                index="sec_filings",
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"metadata.cik": CIK}},
                                {"term": {"metadata.form": filing_spec["form"]}},
                                {"term": {"metadata.filing_date": filing_date}}
                            ]
                        }
                    }
                }
            )['count']
            
            if existing > 0:
                print(f"    ⚠️  Already indexed ({existing} chunks)")
                total_chunks += existing
                continue
            
            # Download
            print(f"    Downloading...")
            downloaded_path = client.download_filing_document(
                accession_number=accession,
                primary_document=doc_name,
                cik=CIK,
                output_dir=str(output_dir)
            )
            
            if not downloaded_path or not Path(downloaded_path).exists():
                print(f"    ❌ Download failed")
                continue
            
            # Parse and chunk
            print(f"    Parsing and chunking...")
            parsed = parse_sec_filing(downloaded_path, document_name=doc_name)
            chunks = chunk_sec_documents(
                [parsed],
                size=CHUNK_SIZE,
                step=CHUNK_SIZE - CHUNK_OVERLAP
            )
            
            # Enhance and index
            filing_info = {
                "accession_number": accession,
                "document_name": doc_name,
                "filing_date": filing_date,
                "form": filing_spec["form"]
            }
            enhanced_chunks = enhance_chunks_with_metadata(chunks, filing_info)
            
            indexed_count = index_sec_chunks(
                enhanced_chunks,
                index_name="sec_filings",
                es_client=es_client,
                create_index=True
            )
            
            print(f"    ✓ Indexed {indexed_count} chunks")
            total_chunks += indexed_count
            
            time.sleep(0.1)
        
        return {"status": "success", "chunks": total_chunks}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        return {"status": "error", "error": error_msg}


def main():
    """Index all Home Depot 2014 data breach filings."""
    print("="*80)
    print("Indexing All Home Depot 2014 Data Breach Filings")
    print("="*80)
    print()
    
    # Check Elasticsearch connection
    print("Checking Elasticsearch connection...")
    es = Elasticsearch('http://localhost:9200')
    try:
        if not es.ping():
            print("❌ Cannot connect to Elasticsearch. Make sure it's running on localhost:9200")
            return
        print("✓ Elasticsearch is connected")
        
        count = es.count(index="sec_filings")['count']
        print(f"✓ Current index has {count:,} documents")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    # Initialize SEC client
    print("\nInitializing SEC EDGAR client...")
    client = SECEdgarClient()
    print("✓ SEC client initialized")
    
    # Create output directory
    output_dir = Path("sec_downloads") / CIK
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Using cache directory: {output_dir}")
    
    # Index specific filings
    print("\n" + "="*80)
    print("INDEXING SPECIFIC FILINGS")
    print("="*80)
    
    results = []
    
    for filing_info in FILINGS_TO_INDEX:
        result = index_specific_filing(client, es, output_dir, filing_info)
        result["filing"] = filing_info["description"]
        results.append(result)
        
        if len(FILINGS_TO_INDEX) > 1:
            time.sleep(1)
    
    # Search for and index additional filings
    print("\n" + "="*80)
    print("SEARCHING FOR ADDITIONAL FILINGS")
    print("="*80)
    
    for filing_spec in ADDITIONAL_FILINGS:
        result = index_filing_by_search(client, es, output_dir, filing_spec)
        result["filing"] = filing_spec["description"]
        results.append(result)
        
        time.sleep(1)
    
    # Summary
    print("\n" + "="*80)
    print("INDEXING SUMMARY")
    print("="*80)
    
    total_chunks = sum(r.get("chunks", 0) for r in results)
    successful = sum(1 for r in results if r.get("status") == "success")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    
    print(f"Filings processed: {len(results)}")
    print(f"Successfully indexed: {successful}")
    print(f"Already indexed (skipped): {skipped}")
    print(f"Total chunks indexed: {total_chunks}")
    
    print("\nPer-filing results:")
    for result in results:
        status_icon = {
            "success": "✓",
            "skipped": "⊘",
            "error": "✗",
            "not_found": "?"
        }.get(result.get("status"), "?")
        
        print(f"  {status_icon} {result.get('filing', 'Unknown')}: {result.get('chunks', 0)} chunks")
        if result.get("error"):
            print(f"      Error: {result['error']}")
    
    # Final index status
    print("\n" + "="*80)
    print("FINAL INDEX STATUS")
    print("="*80)
    try:
        total_count = es.count(index="sec_filings")['count']
        print(f"Total documents in 'sec_filings' index: {total_count:,}")
        
        hd_count = es.count(index="sec_filings", body={"query": {"term": {"metadata.cik": CIK}}})['count']
        print(f"Home Depot (CIK {CIK}) chunks: {hd_count:,}")
    except Exception as e:
        print(f"Could not get index count: {e}")
    
    print("\n✅ Indexing complete!")


if __name__ == "__main__":
    main()

