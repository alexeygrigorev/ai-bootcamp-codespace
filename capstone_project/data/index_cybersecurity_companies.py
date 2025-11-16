#!/usr/bin/env python3
"""
Index SEC filings for companies with known cybersecurity incidents.

This script fetches, parses, chunks, and indexes SEC filings for a list of companies
that have experienced cybersecurity incidents. The indexed data can then be searched
by the SEC Cybersecurity Agent.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathlib import Path
from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch

# Companies with cybersecurity incidents to index
COMPANIES = [
    {"name": "UnitedHealth Group Inc.", "cik": "0000731766", "years": [2024], "incident": "Ransomware (Change Healthcare subsidiary)"},
    {"name": "Target Corporation", "cik": "0000027419", "years": [2013, 2014], "incident": "Point-of-sale malware"},
    {"name": "Capital One Financial Corp.", "cik": "0000927628", "years": [2019], "incident": "Cloud misconfiguration"},
    {"name": "Equifax Inc.", "cik": "0000033185", "years": [2017], "incident": "Unpatched vulnerability"},
    {"name": "Marriott International Inc.", "cik": "0001048286", "years": [2014, 2015, 2016, 2017, 2018], "incident": "Multi-year breach (Starwood)"},
    {"name": "Home Depot, Inc.", "cik": "0000354950", "years": [2014], "incident": "Vendor credential compromise"},
    {"name": "MGM Resorts International", "cik": "0000789570", "years": [2023], "incident": "Social engineering/ransomware"},
    {"name": "SolarWinds Corporation", "cik": "0001739942", "years": [2020], "incident": "Supply chain attack (SUNBURST)"},
    {"name": "T-Mobile US, Inc.", "cik": "0001283699", "years": [2021, 2022, 2023], "incident": "Multiple data breaches"},
    {"name": "Uber Technologies, Inc.", "cik": "0001543151", "years": [2016], "incident": "Credential compromise, concealed breach"},
    {"name": "Sony Group Corp.", "cik": "0000313838", "years": [2014], "incident": "Nation-state attack"},
    {"name": "First American Financial Corp.", "cik": "0001472787", "years": [2019], "incident": "Web application vulnerability (IDOR)"},
    {"name": "Altaba Inc. (formerly Yahoo! Inc.)", "cik": "0001011006", "years": [2013, 2014], "incident": "Multiple breaches, delayed disclosure"},
]

# Focus on these form types (most likely to contain cybersecurity disclosures)
FORM_TYPES = ["10-K", "10-Q", "8-K"]

# Chunking parameters (from README_data_strategy.md)
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 1000


def calculate_years_to_fetch(incident_years: List[int]) -> int:
    """Calculate how many years back to fetch filings."""
    current_year = datetime.now().year
    oldest_year = min(incident_years)
    # Fetch from oldest incident year to current year, plus 1 year buffer
    years_back = current_year - oldest_year + 1
    return max(years_back, 3)  # At least 3 years


def enhance_chunks_with_metadata(chunks: List[Dict], filing: Dict, cik: str) -> List[Dict]:
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


def index_company_filings(
    company: Dict,
    client: SECEdgarClient,
    es_client: Elasticsearch,
    output_dir: Path,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Index SEC filings for a single company.
    
    Returns:
        Dictionary with indexing statistics
    """
    company_name = company["name"]
    cik = company["cik"]
    incident_years = company["years"]
    
    print(f"\n{'='*80}")
    print(f"Processing: {company_name}")
    print(f"CIK: {cik}")
    print(f"Incident: {company['incident']}")
    print(f"Years of interest: {incident_years}")
    print(f"{'='*80}")
    
    # Calculate years to fetch
    years_to_fetch = calculate_years_to_fetch(incident_years)
    print(f"Fetching filings for last {years_to_fetch} years...")
    
    try:
        # Fetch filings
        filings = client.fetch_filings(cik, years=years_to_fetch)
        print(f"Found {len(filings)} total filings")
        
        # Filter to form types of interest
        relevant_filings = [
            f for f in filings 
            if f.get("form") in FORM_TYPES
        ]
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
        
        # Process each filing
        total_chunks = 0
        filings_indexed = 0
        errors = []
        
        for filing in relevant_filings:
            filing_date = filing.get("filing_date", "")
            form = filing.get("form", "")
            doc_name = filing.get("primary_document", "")
            
            # Check if we should skip this filing (not in incident years)
            filing_year = int(filing_date.split("-")[0]) if filing_date else 0
            if filing_year not in incident_years and filing_year not in [y+1 for y in incident_years]:  # Include year after incident
                continue
            
            print(f"\n  Processing: {form} filed {filing_date} ({doc_name})")
            
            try:
                # Download filing document
                output_path = output_dir / cik / f"{doc_name}"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download or use cached filing
                if skip_existing and output_path.exists():
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
                
                # Parse filing
                print(f"    Parsing...")
                parsed = parse_sec_filing(file_path, document_name=doc_name)
                
                # Chunk documents
                print(f"    Chunking...")
                chunks = chunk_sec_documents(
                    [parsed],
                    size=CHUNK_SIZE,
                    step=CHUNK_SIZE - CHUNK_OVERLAP  # step = size - overlap
                )
                
                # Enhance with metadata
                enhanced_chunks = enhance_chunks_with_metadata(chunks, filing, cik)
                
                # Index in Elasticsearch
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
                
                # Rate limiting - be respectful to SEC API
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
    """Main function to index all companies."""
    print("="*80)
    print("SEC Cybersecurity Filings Indexer")
    print("="*80)
    print(f"Indexing filings for {len(COMPANIES)} companies with cybersecurity incidents")
    print()
    
    # Check Elasticsearch connection
    print("Checking Elasticsearch connection...")
    es = Elasticsearch('http://localhost:9200')
    try:
        if not es.ping():
            print("❌ Cannot connect to Elasticsearch. Make sure it's running on localhost:9200")
            print("   Run: ./setup_elasticsearch.sh")
            return
        print("✓ Elasticsearch is connected")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        print("   Make sure Elasticsearch is running: docker ps | grep elasticsearch")
        return
    
    # Initialize SEC client
    print("\nInitializing SEC EDGAR client...")
    client = SECEdgarClient()
    print("✓ SEC client initialized")
    
    # Create output directory for cached filings
    output_dir = Path("sec_downloads")
    output_dir.mkdir(exist_ok=True)
    print(f"✓ Using cache directory: {output_dir}")
    
    # Process each company
    results = []
    start_time = time.time()
    
    for i, company in enumerate(COMPANIES, 1):
        print(f"\n\n[{i}/{len(COMPANIES)}]")
        result = index_company_filings(
            company,
            client,
            es,
            output_dir,
            skip_existing=True
        )
        results.append(result)
        
        # Rate limiting between companies
        if i < len(COMPANIES):
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
    
    print(f"Companies processed: {len(COMPANIES)}")
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
    
    # Save results to file
    results_file = Path("indexing_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: {results_file}")
    
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

