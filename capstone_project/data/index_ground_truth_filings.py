#!/usr/bin/env python3
"""
Index SEC filings from ground truth CSV file.

This script reads the ground truth CSV file and indexes all specified SEC filings
into Elasticsearch for use by the SEC Cybersecurity Agent.
"""

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import time
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from pathlib import Path
from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch


def load_ground_truth_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load ground truth filings from CSV file."""
    filings = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cik = row.get('CIK', '').strip()
            accession_number = row.get('Accession Number', '').strip()
            company_name = row.get('Company', '').strip()
            
            # Skip only if CIK is actually missing or N/A
            if not cik or cik.startswith('N/A'):
                print(f"⚠️  Skipping {company_name}: Missing or invalid CIK")
                continue
            
            # If accession number is missing/placeholder, we'll search by date/form type
            has_accession = accession_number and not accession_number.startswith('Referenced') and not accession_number.startswith('N/A')
            
            filing_info = {
                'cik': cik,
                'company_name': company_name,
                'form_type': row.get('Form Type', '').strip(),
                'filing_date': row.get('Filing Date', '').strip(),
                'accession_number': accession_number if has_accession else None,
                'document_name': None,  # Will be determined from filing
                'incident_date': row.get('Incident Date', '').strip() if row.get('Incident Date') else None,
                'key_item': row.get('Key Item', '').strip() if row.get('Key Item') else None,
                'needs_search': not has_accession,  # Flag to search by date/form instead
            }
            
            filings.append(filing_info)
    
    return filings


async def index_filing(
    client: SECEdgarClient,
    es: Elasticsearch,
    filing_info: Dict[str, Any],
    output_dir: Path
) -> Dict[str, Any]:
    """Index a single filing."""
    cik = filing_info['cik']
    company_name = filing_info['company_name']
    accession_number = filing_info['accession_number']
    form_type = filing_info['form_type']
    filing_date = filing_info['filing_date']
    
    print(f"\n{'='*80}")
    print(f"Processing: {company_name} - {form_type} ({filing_date})")
    print(f"Accession: {accession_number}")
    print(f"{'='*80}")
    
    result = {
        'company_name': company_name,
        'cik': cik,
        'form_type': form_type,
        'filing_date': filing_date,
        'accession_number': accession_number,
        'status': 'pending',
        'chunks_indexed': 0,
        'error': None
    }
    
    try:
        # If we have an accession number, find that specific filing
        # Otherwise, search by form type and date
        if filing_info.get('needs_search') or not accession_number:
            # Search by form type and approximate date
            print(f"Searching for filing by form type and date...")
            form_type = filing_info['form_type']
            filing_date_str = filing_info['filing_date']
            
            # Parse the filing date to get year/month
            try:
                if '/' in filing_date_str:
                    parts = filing_date_str.split('/')
                    month = int(parts[0])
                    year = int(parts[2]) if len(parts) > 2 and len(parts[2]) == 4 else 2000 + int(parts[2]) if len(parts) > 2 else 2024
                else:
                    year = 2024  # Default
                    month = 1
            except:
                year = 2024
                month = 1
            
            # Fetch recent filings and find matching one
            recent_filings = client.fetch_filings(cik, years=2)
            matching_filing = None
            
            for filing in recent_filings:
                # Match by form type and approximate date
                if filing.get('form') == form_type:
                    filing_date = filing.get('filing_date', '')
                    if filing_date:
                        try:
                            from datetime import datetime
                            file_date = datetime.strptime(filing_date, '%Y-%m-%d')
                            # Check if it's in the same month/year (within 1 month window)
                            if file_date.year == year and abs(file_date.month - month) <= 1:
                                matching_filing = filing
                                break
                        except:
                            continue
        else:
            # We have an accession number, find that specific filing
            print(f"Fetching recent filings to find document name...")
            recent_filings = client.fetch_filings(cik, years=2)
            matching_filing = None
            for filing in recent_filings:
                if filing.get('accession_number') == accession_number:
                    matching_filing = filing
                    break
        
        if not matching_filing:
            result['status'] = 'error'
            result['error'] = 'Could not find matching filing in recent filings'
            print(f"❌ Could not find matching filing")
            return result
        
        # Update accession number if we found it via search
        if not accession_number or filing_info.get('needs_search'):
            accession_number = matching_filing.get('accession_number')
            result['accession_number'] = accession_number
            print(f"Found filing: {accession_number}")
        
        document_name = matching_filing.get('primary_document')
        if not document_name:
            result['status'] = 'error'
            result['error'] = 'No primary document found in filing'
            print(f"❌ No primary document found")
            return result
        
        print(f"Primary document: {document_name}")
        result['document_name'] = document_name
        
        # Download the filing
        print(f"Downloading filing...")
        file_path = client.download_filing_document(
            accession_number=accession_number,
            primary_document=document_name,
            cik=cik,
            output_dir=str(output_dir)
        )
        
        if not file_path:
            result['status'] = 'error'
            result['error'] = 'Failed to download filing'
            print(f"❌ Failed to download filing")
            return result
        
        print(f"✓ Downloaded to: {file_path}")
        
        # Parse the filing
        print(f"Parsing filing...")
        parsed_data = parse_sec_filing(file_path)
        
        if not parsed_data:
            result['status'] = 'error'
            result['error'] = 'Failed to parse filing'
            print(f"❌ Failed to parse filing")
            return result
        
        # Check if parsed_data is a dict (expected) or string (error case)
        if isinstance(parsed_data, str):
            result['status'] = 'error'
            result['error'] = f'Parse returned string instead of dict: {parsed_data[:100]}'
            print(f"❌ Parse returned string: {parsed_data[:100]}")
            return result
        
        print(f"✓ Parsed filing: {len(parsed_data.get('sections', []))} sections")
        
        # Chunk the documents
        # chunk_sec_documents expects an iterable, so wrap in a list
        print(f"Chunking documents...")
        chunks = chunk_sec_documents([parsed_data])
        
        if not chunks:
            result['status'] = 'error'
            result['error'] = 'No chunks generated'
            print(f"❌ No chunks generated")
            return result
        
        print(f"✓ Generated {len(chunks)} chunks")
        
        # Index chunks
        # Add metadata to chunks before indexing
        # Convert filing_date to ISO format (YYYY-MM-DD) for Elasticsearch
        try:
            # Try parsing various date formats
            if '/' in filing_date:
                # Format: "7/12/24" or "7/12/2024"
                parts = filing_date.split('/')
                month, day = parts[0], parts[1]
                year = parts[2] if len(parts) > 2 else '2024'
                if len(year) == 2:
                    year = '20' + year  # Convert "24" to "2024"
                iso_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                # Assume it's already in a parseable format
                from dateutil.parser import parse
                parsed_date = parse(filing_date)
                iso_date = parsed_date.strftime('%Y-%m-%d')
        except Exception:
            # If parsing fails, use a default date or skip date field
            iso_date = None
        
        for chunk in chunks:
            chunk_metadata = {
                'cik': cik,
                'form': form_type,  # Use 'form' not 'form_type' to match expected schema
                'accession_number': accession_number,
                'company_name': company_name
            }
            if iso_date:
                chunk_metadata['filing_date'] = iso_date
            chunk['metadata'] = chunk_metadata
        
        print(f"Indexing chunks to Elasticsearch...")
        indexed_count = index_sec_chunks(chunks, es_client=es, create_index=True)
        
        result['status'] = 'success'
        result['chunks_indexed'] = indexed_count
        print(f"✓ Indexed {indexed_count} chunks")
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return result


async def main():
    """Main function to index all ground truth filings."""
    print("="*80)
    print("Ground Truth SEC Filings Indexer")
    print("="*80)
    print()
    
    # Paths
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "eval" / "ground_truth_2024_2025_sec_filings.csv"
    output_dir = Path(__file__).parent / "sec_downloads"
    output_dir.mkdir(exist_ok=True)
    
    # Load ground truth filings
    print(f"Loading ground truth filings from: {csv_path}")
    if not csv_path.exists():
        print(f"❌ Error: {csv_path} not found")
        return
    
    filings = load_ground_truth_csv(csv_path)
    print(f"✓ Loaded {len(filings)} filings from CSV")
    print()
    
    # Check Elasticsearch
    print("Checking Elasticsearch connection...")
    try:
        es = Elasticsearch('http://localhost:9200')
        if not es.ping():
            print("❌ Elasticsearch is not running. Please start it first.")
            return
        count_before = es.count(index="sec_filings")['count']
        print(f"✓ Elasticsearch connected - {count_before:,} documents currently indexed")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    print()
    print("Starting indexing process...")
    print()
    
    # Initialize client
    client = SECEdgarClient()
    
    # Index all filings
    results = []
    start_time = datetime.now()
    
    for i, filing_info in enumerate(filings, 1):
        print(f"\n[{i}/{len(filings)}]")
        result = await index_filing(client, es, filing_info, output_dir)
        results.append(result)
        
        # Small delay between filings to avoid rate limiting
        if i < len(filings):
            await asyncio.sleep(2)
    
    # Calculate summary
    total_time = (datetime.now() - start_time).total_seconds()
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'error')
    total_chunks = sum(r['chunks_indexed'] for r in results)
    
    # Get final count
    count_after = es.count(index="sec_filings")['count']
    new_documents = count_after - count_before
    
    # Save results
    results_file = project_root / "eval" / "ground_truth_indexing_results.json"
    output_data = {
        'indexing_timestamp': datetime.now().isoformat(),
        'total_filings': len(filings),
        'successful': successful,
        'failed': failed,
        'total_chunks_indexed': total_chunks,
        'new_documents': new_documents,
        'total_duration_seconds': total_time,
        'results': results
    }
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*80)
    print("INDEXING SUMMARY")
    print("="*80)
    print(f"Total filings processed: {len(filings)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total chunks indexed: {total_chunks:,}")
    print(f"New documents in Elasticsearch: {new_documents:,}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print()
    print(f"✓ Results saved to: {results_file}")
    print("="*80)
    
    # Print per-filing status
    if failed > 0:
        print("\nFailed filings:")
        for result in results:
            if result['status'] == 'error':
                print(f"  ✗ {result['company_name']} - {result['form_type']} ({result['filing_date']})")
                print(f"      Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())

