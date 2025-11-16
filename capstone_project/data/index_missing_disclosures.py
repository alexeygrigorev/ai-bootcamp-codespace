#!/usr/bin/env python3
"""
Index additional SEC filings for companies with missing cybersecurity disclosures.

This script focuses on specific filings that contain important cybersecurity
disclosures that were missed in the initial indexing:
- Home Depot: Form 8-K in November 2014
- Sony Group Corp: Japanese ADR filings (20-F, 6-K)
- Equifax: Form 8-K and 10-K disclosures in 2017
- First American Financial: SEC enforcement action documents
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import time
import json

from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch

# Companies with specific missing disclosures - targeted filings only
COMPANIES_TO_INDEX = [
    {
        "name": "Home Depot, Inc.",
        "cik": "0000354950",
        "target_years": [2014, 2015],  # Focus on 2014 breach and 2015 disclosures
        "target_forms": ["8-K"],  # Specifically November 2014 8-K about data breach
        "target_months": [11],  # November 2014
        "notes": "Form 8-K in November 2014 about data breach"
    },
    {
        "name": "Sony Group Corp.",
        "cik": "0000313838",
        "target_years": [2014, 2015],  # 2014 breach disclosures
        "target_forms": ["20-F", "6-K"],  # Foreign issuer forms - focus on breach period
        "target_months": None,  # All months in target years
        "notes": "Japanese ADR filings - 2014 breach disclosures"
    },
    {
        "name": "Equifax Inc.",
        "cik": "0000033185",
        "target_years": [2017, 2018],  # 2017 breach and 2018 disclosures
        "target_forms": ["8-K", "10-K"],  # Major disclosures in 2017
        "target_months": None,  # All months - breach disclosed in Sept 2017
        "notes": "Major Form 8-K and 10-K disclosures in 2017"
    },
    {
        "name": "First American Financial Corp.",
        "cik": "0001472787",
        "target_years": [2019, 2020],  # 2019 breach and enforcement action
        "target_forms": ["8-K", "10-K"],  # Enforcement action documents
        "target_months": None,  # All months
        "notes": "SEC enforcement action documented in 2019"
    },
]

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 1000


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
    """Index SEC filings for a single company, focusing on target years and forms."""
    company_name = company["name"]
    cik = company["cik"]
    target_years = company["target_years"]
    target_forms = company["target_forms"]
    
    print(f"\n{'='*80}")
    print(f"Processing: {company_name}")
    print(f"CIK: {cik}")
    print(f"Target years: {target_years}")
    print(f"Target forms: {target_forms}")
    print(f"Notes: {company['notes']}")
    print(f"{'='*80}")
    
    # Calculate years back from current date to oldest target year
    current_year = datetime.now().year
    oldest_target_year = min(target_years)
    years_back = current_year - oldest_target_year + 1  # +1 to include current year
    print(f"Fetching filings for last {years_back} years (back to {oldest_target_year})...")
    
    # For old filings (pre-2017), we need to access historical filing files directly
    # Check if we need historical filings
    needs_historical = min(target_years) < 2017
    
    try:
        if needs_historical:
            # Fetch both recent and historical filings
            filings = client.fetch_filings(cik, years=years_back)
            print(f"Found {len(filings)} filings from recent API")
            
            # Also fetch historical filings directly
            import requests
            hist_headers = client.headers
            hist_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            hist_resp = requests.get(hist_url, headers=hist_headers, timeout=30)
            if hist_resp.status_code == 200:
                hist_data = hist_resp.json()
                hist_files = hist_data.get('filings', {}).get('files', [])
                for hist_file in hist_files:
                    # Check if this historical file covers our target years
                    filing_from = hist_file.get('filingFrom', '')
                    filing_to = hist_file.get('filingTo', '')
                    if filing_from and filing_to:
                        from_year = int(filing_from.split('-')[0])
                        to_year = int(filing_to.split('-')[0])
                        if from_year <= min(target_years) <= to_year or from_year <= max(target_years) <= to_year:
                            # Fetch this historical file
                            hist_file_url = f"https://data.sec.gov/submissions/{hist_file['name']}"
                            hist_file_resp = requests.get(hist_file_url, headers=hist_headers, timeout=30)
                            if hist_file_resp.status_code == 200:
                                hist_file_data = hist_file_resp.json()
                                hist_recent = hist_file_data.get('filings', {}).get('recent', {})
                                if hist_recent:
                                    hist_accession = hist_recent.get('accessionNumber', [])
                                    hist_dates = hist_recent.get('filingDate', [])
                                    hist_forms = hist_recent.get('form', [])
                                    hist_docs = hist_recent.get('primaryDocument', [])
                                    
                                    for j in range(len(hist_dates)):
                                        try:
                                            filing_year = int(hist_dates[j].split('-')[0])
                                            if filing_year in target_years:
                                                filing_info = {
                                                    'accession_number': hist_accession[j],
                                                    'filing_date': hist_dates[j],
                                                    'form': hist_forms[j],
                                                    'primary_document': hist_docs[j],
                                                    'cik': cik
                                                }
                                                filings.append(filing_info)
                                        except (ValueError, IndexError):
                                            continue
                            time.sleep(0.1)
        else:
            filings = client.fetch_filings(cik, years=years_back)
        
        print(f"Found {len(filings)} total filings (including historical)")
        
        # Filter to target forms
        relevant_filings = [f for f in filings if f.get("form") in target_forms]
        print(f"Filtered to {len(relevant_filings)} relevant filings ({', '.join(target_forms)})")
        
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
        
        # Filter to target years and months (if specified)
        min_year = min(target_years)
        max_year = max(target_years)
        target_months = company.get("target_months")
        
        filtered_filings = []
        for filing in relevant_filings:
            filing_date = filing.get("filing_date", "")
            if filing_date:
                try:
                    date_parts = filing_date.split("-")
                    filing_year = int(date_parts[0])
                    filing_month = int(date_parts[1]) if len(date_parts) > 1 else None
                    
                    # Check year match
                    if min_year <= filing_year <= max_year:
                        # Check month match if specified
                        if target_months is None or filing_month in target_months:
                            filtered_filings.append(filing)
                except (ValueError, IndexError):
                    # If date parsing fails, skip to be safe
                    continue
            # Skip filings without dates
        
        print(f"Filtered to {len(filtered_filings)} filings in target years ({min_year}-{max_year})")
        
        if not filtered_filings:
            print(f"⚠️  No filings found in target years for {company_name}")
            return {
                "company": company_name,
                "cik": cik,
                "filings_found": len(relevant_filings),
                "filings_indexed": 0,
                "chunks_indexed": 0,
                "error": f"No filings found in target years {target_years}"
            }
        
        total_chunks = 0
        filings_indexed = 0
        errors = []
        
        for filing in filtered_filings:
            filing_date = filing.get("filing_date", "")
            form = filing.get("form", "")
            doc_name = filing.get("primary_document", "")
            
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
        print(f"  Filings indexed: {filings_indexed}/{len(filtered_filings)}")
        print(f"  Total chunks indexed: {total_chunks}")
        
        return {
            "company": company_name,
            "cik": cik,
            "filings_found": len(filtered_filings),
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
    """Main function to index missing disclosures."""
    print("="*80)
    print("Indexing Missing SEC Cybersecurity Disclosures")
    print("="*80)
    print(f"Indexing {len(COMPANIES_TO_INDEX)} companies")
    print()
    
    # Check Elasticsearch connection
    print("Checking Elasticsearch connection...")
    es = Elasticsearch('http://localhost:9200')
    try:
        if not es.ping():
            print("❌ Cannot connect to Elasticsearch. Make sure it's running on localhost:9200")
            return
        print("✓ Elasticsearch is connected")
        
        # Check current index count
        if es.indices.exists(index="sec_filings"):
            count = es.count(index="sec_filings")['count']
            print(f"✓ Current index has {count:,} documents")
        else:
            print("⚠️  Index 'sec_filings' does not exist - will be created")
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
    
    for i, company in enumerate(COMPANIES_TO_INDEX, 1):
        print(f"\n\n[{i}/{len(COMPANIES_TO_INDEX)}]")
        result = index_company_filings(company, client, es, output_dir)
        results.append(result)
        
        if i < len(COMPANIES_TO_INDEX):
            print("\nWaiting 2 seconds before next company...")
            time.sleep(2)
    
    # Summary
    elapsed = time.time() - start_time
    print("\n\n" + "="*80)
    print("INDEXING SUMMARY")
    print("="*80)
    
    total_filings = sum(r.get("filings_indexed", 0) for r in results)
    total_chunks = sum(r.get("chunks_indexed", 0) for r in results)
    successful = sum(1 for r in results if r.get("chunks_indexed", 0) > 0)
    
    print(f"Companies processed: {len(COMPANIES_TO_INDEX)}")
    print(f"Successfully indexed: {successful}")
    print(f"Total filings indexed: {total_filings}")
    print(f"Total chunks indexed: {total_chunks:,}")
    print(f"Time elapsed: {elapsed/60:.1f} minutes")
    print()
    
    print("Per-company results:")
    for result in results:
        status = "✓" if result.get("chunks_indexed", 0) > 0 else "✗"
        print(f"  {status} {result['company']}: {result.get('chunks_indexed', 0)} chunks ({result.get('filings_indexed', 0)} filings)")
        if result.get("error"):
            print(f"      Error: {result['error']}")
        if result.get("errors"):
            print(f"      Errors: {len(result['errors'])} filing errors")
    
    # Check final index status
    print("\n" + "="*80)
    print("FINAL INDEX STATUS")
    print("="*80)
    try:
        count = es.count(index="sec_filings")['count']
        print(f"Total documents in 'sec_filings' index: {count:,}")
        
        # Show breakdown by CIK
        print("\nDocuments by company:")
        for result in results:
            cik = result['cik']
            company_count = es.count(index="sec_filings", body={"query": {"term": {"metadata.cik": cik}}})['count']
            print(f"  {result['company']} ({cik}): {company_count:,} chunks")
    except Exception as e:
        print(f"Could not get index count: {e}")
    
    # Save results
    results_file = Path("missing_disclosures_indexing_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: {results_file}")


if __name__ == "__main__":
    main()

