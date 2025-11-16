#!/usr/bin/env python3
"""
Re-index companies that had 0 chunks in the previous run.

This script will re-index:
- Home Depot, Inc. (CIK: 0000354950)
- Uber Technologies, Inc. (CIK: 0001543151)
- Sony Group Corp. (CIK: 0000313838)
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import time
import json

from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch

# Companies that need re-indexing (had 0 chunks)
COMPANIES_TO_REINDEX = [
    {"name": "Home Depot, Inc.", "cik": "0000354950", "years": [2014], "incident": "Vendor credential compromise"},
    {"name": "Uber Technologies, Inc.", "cik": "0001543151", "years": [2016], "incident": "Credential compromise, concealed breach"},
    {"name": "Sony Group Corp.", "cik": "0000313838", "years": [2014], "incident": "Nation-state attack"},
]

# Include foreign issuer forms (20-F, 6-K) for companies like Sony
FORM_TYPES = ["10-K", "10-Q", "8-K", "20-F", "6-K"]
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 1000


def calculate_years_to_fetch(incident_years):
    """Calculate how many years back to fetch filings."""
    current_year = datetime.now().year
    oldest_year = min(incident_years)
    years_back = current_year - oldest_year + 1
    return max(years_back, 3)


def enhance_chunks_with_metadata(chunks, filing, cik):
    """Enhance chunks with filing metadata."""
    enhanced = []
    for i, chunk in enumerate(chunks):
        enhanced_chunk = {
            "id": f"{filing.get('primary_document', 'unknown')}_chunk_{i}",
            "content": chunk.get("content", ""),
            "metadata": {
                **chunk.get("metadata", {}),
                "cik": cik,
                "filing_date": filing.get("filing_date", ""),
                "form": filing.get("form", ""),
                "accession_number": filing.get("accession_number", ""),
                "document_name": filing.get("primary_document", ""),
            }
        }
        enhanced.append(enhanced_chunk)
    return enhanced


def index_company_filings(company, client, es_client, output_dir):
    """Index SEC filings for a single company."""
    company_name = company["name"]
    cik = company["cik"]
    incident_years = company["years"]
    
    print(f"\n{'='*80}")
    print(f"Processing: {company_name}")
    print(f"CIK: {cik}")
    print(f"Incident: {company['incident']}")
    print(f"Years of interest: {incident_years}")
    print(f"{'='*80}")
    
    years_to_fetch = calculate_years_to_fetch(incident_years)
    print(f"Fetching filings for last {years_to_fetch} years...")
    
    try:
        filings = client.fetch_filings(cik, years=years_to_fetch)
        print(f"Found {len(filings)} total filings")
        
        # For Sony (foreign issuer), also include 20-F and 6-K forms
        if cik == "0000313838":  # Sony Group Corp
            relevant_filings = [f for f in filings if f.get("form") in ["20-F", "6-K", "8-K"]]
        else:
            relevant_filings = [f for f in filings if f.get("form") in FORM_TYPES]
        print(f"Filtered to {len(relevant_filings)} relevant filings ({', '.join(FORM_TYPES)})")
        
        if not relevant_filings:
            print(f"⚠️  No relevant filings found for {company_name}")
            return {
                "company": company_name,
                "cik": cik,
                "filings_found": 0,
                "filings_indexed": 0,
                "chunks_indexed": 0,
                "error": "No relevant filings found"
            }
        
        total_chunks = 0
        filings_indexed = 0
        errors = []
        
        for filing in relevant_filings:
            filing_date = filing.get("filing_date", "")
            form = filing.get("form", "")
            doc_name = filing.get("primary_document", "")
            
            # Process filings from incident year and a few years around it
            # This captures disclosures that may reference the incident even if filed later
            filing_year = int(filing_date.split("-")[0]) if filing_date and filing_date.split("-")[0].isdigit() else 0
            min_year = min(incident_years) - 1  # Include year before incident
            max_year = max(incident_years) + 3  # Include 3 years after incident
            if filing_year == 0 or filing_year < min_year or filing_year > max_year:
                # Skip if date parsing failed or outside range
                if filing_year > 0:  # Only skip if we successfully parsed the year
                    continue
            
            print(f"\n  Processing: {form} filed {filing_date} ({doc_name})")
            
            try:
                output_path = output_dir / cik / f"{doc_name}"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if output_path.exists():
                    print(f"    ✓ Already downloaded, using cached file")
                    file_path = str(output_path)
                else:
                    print(f"    Downloading...")
                    downloaded_path = client.download_filing_document(
                        accession_number=filing.get("accession_number", ""),
                        primary_document=doc_name,
                        cik=cik,
                        output_dir=str(output_path.parent)
                    )
                    if downloaded_path and Path(downloaded_path).exists():
                        file_path = downloaded_path
                    else:
                        print(f"    ⚠️  Download failed, skipping")
                        errors.append(f"Download failed: {doc_name}")
                        continue
                
                print(f"    Parsing...")
                parsed = parse_sec_filing(file_path, document_name=doc_name)
                
                print(f"    Chunking...")
                chunks = chunk_sec_documents(
                    [parsed],
                    size=CHUNK_SIZE,
                    step=CHUNK_SIZE - CHUNK_OVERLAP
                )
                
                enhanced_chunks = enhance_chunks_with_metadata(chunks, filing, cik)
                
                print(f"    Indexing {len(enhanced_chunks)} chunks...")
                indexed_count = index_sec_chunks(
                    enhanced_chunks,
                    index_name="sec_filings",
                    es_client=es_client,
                    create_index=True
                )
                
                total_chunks += indexed_count
                filings_indexed += 1
                print(f"    ✓ Indexed {indexed_count} chunks")
                
                time.sleep(0.1)
                
            except Exception as e:
                error_msg = f"Error processing {doc_name}: {str(e)}"
                print(f"    ❌ {error_msg}")
                errors.append(error_msg)
                continue
        
        print(f"\n✓ Completed {company_name}")
        print(f"  Filings indexed: {filings_indexed}/{len(relevant_filings)}")
        print(f"  Total chunks indexed: {total_chunks}")
        
        return {
            "company": company_name,
            "cik": cik,
            "filings_found": len(relevant_filings),
            "filings_indexed": filings_indexed,
            "chunks_indexed": total_chunks,
            "errors": errors
        }
        
    except Exception as e:
        error_msg = f"Error processing {company_name}: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "company": company_name,
            "cik": cik,
            "filings_found": 0,
            "filings_indexed": 0,
            "chunks_indexed": 0,
            "error": error_msg
        }


def main():
    """Main function to re-index missing companies."""
    print("="*80)
    print("Re-indexing Companies with 0 Chunks")
    print("="*80)
    print(f"Re-indexing {len(COMPANIES_TO_REINDEX)} companies")
    print()
    
    # Check Elasticsearch connection
    print("Checking Elasticsearch connection...")
    es = Elasticsearch('http://localhost:9200')
    try:
        if not es.ping():
            print("❌ Cannot connect to Elasticsearch. Make sure it's running on localhost:9200")
            return
        print("✓ Elasticsearch is connected")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    # Initialize SEC client
    print("\nInitializing SEC EDGAR client...")
    client = SECEdgarClient()
    print("✓ SEC client initialized")
    
    # Create output directory
    output_dir = Path("sec_downloads")
    output_dir.mkdir(exist_ok=True)
    print(f"✓ Using cache directory: {output_dir}")
    
    # Process each company
    results = []
    start_time = time.time()
    
    for i, company in enumerate(COMPANIES_TO_REINDEX, 1):
        print(f"\n\n[{i}/{len(COMPANIES_TO_REINDEX)}]")
        result = index_company_filings(company, client, es, output_dir)
        results.append(result)
        
        if i < len(COMPANIES_TO_REINDEX):
            print("\nWaiting 2 seconds before next company...")
            time.sleep(2)
    
    # Summary
    elapsed = time.time() - start_time
    print("\n\n" + "="*80)
    print("RE-INDEXING SUMMARY")
    print("="*80)
    
    total_filings = sum(r.get("filings_indexed", 0) for r in results)
    total_chunks = sum(r.get("chunks_indexed", 0) for r in results)
    successful = sum(1 for r in results if r.get("chunks_indexed", 0) > 0)
    
    print(f"Companies processed: {len(COMPANIES_TO_REINDEX)}")
    print(f"Successfully indexed: {successful}")
    print(f"Total filings indexed: {total_filings}")
    print(f"Total chunks indexed: {total_chunks:,}")
    print(f"Time elapsed: {elapsed/60:.1f} minutes")
    print()
    
    print("Per-company results:")
    for result in results:
        status = "✓" if result.get("chunks_indexed", 0) > 0 else "✗"
        print(f"  {status} {result['company']}: {result.get('chunks_indexed', 0)} chunks")
        if result.get("error"):
            print(f"      Error: {result['error']}")
    
    # Check final index status
    print("\n" + "="*80)
    print("FINAL INDEX STATUS")
    print("="*80)
    try:
        count = es.count(index="sec_filings")['count']
        print(f"Total documents in 'sec_filings' index: {count:,}")
    except Exception as e:
        print(f"Could not get index count: {e}")


if __name__ == "__main__":
    main()

