#!/usr/bin/env python3
"""
Check and index ground truth filings from CSV.

This script:
1. Reads the ground truth CSV file
2. Checks which filings are already in Elasticsearch
3. Downloads and indexes any missing filings
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch


def parse_filing_date(date_str: str) -> Optional[str]:
    """Parse filing date from various formats to ISO format (YYYY-MM-DD)."""
    if not date_str or date_str.strip() == '':
        return None
    
    date_str = date_str.strip()
    
    # Try different date formats
    formats = [
        '%m/%d/%y',      # 7/12/24
        '%m/%d/%Y',      # 7/12/2024
        '%Y-%m-%d',      # 2024-07-12
        '%m-%d-%Y',      # 07-12-2024
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # Try dateutil parser as fallback
    try:
        from dateutil.parser import parse
        dt = parse(date_str)
        return dt.strftime('%Y-%m-%d')
    except:
        pass
    
    return None


def check_filing_in_elasticsearch(
    es: Elasticsearch,
    cik: str,
    form_type: str,
    filing_date: Optional[str],
    accession_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if a filing exists in Elasticsearch.
    
    Returns:
        Dict with 'exists' (bool) and 'count' (int) of chunks found
    """
    cik_normalized = str(cik).zfill(10)
    
    # Build query
    must_clauses = [
        {"term": {"metadata.cik": cik_normalized}},
        {"term": {"metadata.form": form_type}}
    ]
    
    # Add date filter if we have a date
    if filing_date:
        must_clauses.append({
            "term": {"metadata.filing_date": filing_date}
        })
    
    # Add accession number if available
    if accession_number:
        must_clauses.append({
            "term": {"metadata.accession_number": accession_number}
        })
    
    query = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }
    
    try:
        result = es.count(index="sec_filings", body=query)
        count = result['count']
        return {
            'exists': count > 0,
            'count': count
        }
    except Exception as e:
        print(f"    ⚠️  Error checking Elasticsearch: {e}")
        return {'exists': False, 'count': 0, 'error': str(e)}


def load_ground_truth_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load ground truth filings from CSV file."""
    filings = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cik = row.get('CIK', '').strip()
            accession_number = row.get('Accession Number', '').strip()
            company_name = row.get('Company', '').strip()
            form_type = row.get('Form Type', '').strip()
            filing_date_str = row.get('Filing Date', '').strip()
            
            # Skip if CIK is missing or N/A
            if not cik or cik.startswith('N/A') or cik == '':
                print(f"⚠️  Skipping {company_name}: Missing or invalid CIK")
                continue
            
            # Skip if form type indicates it's not a SEC filing
            if form_type and ('Private company' in form_type or 'N/A' in form_type):
                print(f"⚠️  Skipping {company_name}: {form_type}")
                continue
            
            # Parse filing date
            filing_date_iso = parse_filing_date(filing_date_str)
            
            # Check if accession number is valid
            has_accession = (
                accession_number and 
                not accession_number.startswith('Referenced') and 
                not accession_number.startswith('N/A') and
                accession_number != ''
            )
            
            filing_info = {
                'cik': cik,
                'company_name': company_name,
                'form_type': form_type,
                'filing_date': filing_date_str,
                'filing_date_iso': filing_date_iso,
                'accession_number': accession_number if has_accession else None,
                'key_item': row.get('Key Item', '').strip() if row.get('Key Item') else None,
                'incident_date': row.get('Incident Date', '').strip() if row.get('Incident Date') else None,
            }
            
            filings.append(filing_info)
    
    return filings


def index_filing(
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
    filing_date_str = filing_info['filing_date']
    
    result = {
        'company_name': company_name,
        'cik': cik,
        'form_type': form_type,
        'filing_date': filing_date_str,
        'accession_number': accession_number,
        'status': 'pending',
        'chunks_indexed': 0,
        'error': None
    }
    
    try:
        # Determine how many years to look back based on filing date
        filing_date_iso = filing_info.get('filing_date_iso')
        if filing_date_iso:
            try:
                target_date = datetime.strptime(filing_date_iso, '%Y-%m-%d')
                years_back = (datetime.now() - target_date).days // 365 + 2  # Add 2 years buffer
                years_back = max(5, min(years_back, 15))  # Between 5 and 15 years
            except:
                years_back = 10  # Default to 10 years for older filings
        else:
            years_back = 10  # Default to 10 years if date parsing fails
        
        # Fetch recent filings to find the matching one
        print(f"    Fetching filings for CIK {cik} (looking back {years_back} years)...")
        recent_filings = client.fetch_filings(cik, years=years_back)
        
        matching_filing = None
        
        if accession_number:
            # Try to find by accession number first
            for filing in recent_filings:
                if filing.get('accession_number') == accession_number:
                    matching_filing = filing
                    break
        
        # If not found by accession, try by form type and date
        if not matching_filing:
            filing_date_iso = filing_info.get('filing_date_iso')
            if filing_date_iso:
                target_date = datetime.strptime(filing_date_iso, '%Y-%m-%d')
                
                for filing in recent_filings:
                    if filing.get('form') == form_type:
                        filing_date = filing.get('filing_date', '')
                        if filing_date:
                            try:
                                file_date = datetime.strptime(filing_date, '%Y-%m-%d')
                                # Match if within 30 days
                                days_diff = abs((file_date - target_date).days)
                                if days_diff <= 30:
                                    matching_filing = filing
                                    break
                            except:
                                continue
        
        # If still not found, try just form type match (for cases with vague dates)
        if not matching_filing:
            for filing in recent_filings:
                if filing.get('form') == form_type:
                    # Take the first match if we can't match by date
                    matching_filing = filing
                    break
        
        if not matching_filing:
            result['status'] = 'error'
            result['error'] = 'Could not find matching filing in recent filings'
            print(f"    ❌ Could not find matching filing")
            return result
        
        # Update accession number if we found it
        if not accession_number:
            accession_number = matching_filing.get('accession_number')
            result['accession_number'] = accession_number
        
        document_name = matching_filing.get('primary_document')
        if not document_name:
            result['status'] = 'error'
            result['error'] = 'No primary document found in filing'
            print(f"    ❌ No primary document found")
            return result
        
        print(f"    Found: {document_name} ({accession_number})")
        
        # Download the filing
        print(f"    Downloading...")
        file_path = client.download_filing_document(
            accession_number=accession_number,
            primary_document=document_name,
            cik=cik,
            output_dir=str(output_dir)
        )
        
        # If download failed, try to find alternative document names
        if not file_path or not Path(file_path).exists():
            # Try common document name patterns
            print(f"    ⚠️  Initial download failed, trying alternative document names...")
            import requests
            cik_int = str(int(cik))
            accession_dir = accession_number.replace('-', '')
            
            # First, try to get the filing index (index.txt) to see all available documents
            index_txt_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_dir}/index.txt"
            try:
                index_response = requests.get(index_txt_url, headers=client.headers, timeout=30)
                if index_response.status_code == 200:
                    # Parse index.txt to find document names
                    index_content = index_response.text
                    # Look for document names in the index
                    lines = index_content.split('\n')
                    potential_docs = []
                    for line in lines:
                        if form_type.lower() in line.lower() or '.htm' in line.lower() or '.txt' in line.lower():
                            # Extract potential document names
                            parts = line.split()
                            for part in parts:
                                if ('.htm' in part or '.txt' in part) and '/' not in part:
                                    potential_docs.append(part)
                    
                    # Try downloading from the index
                    for doc_name in potential_docs[:5]:  # Try first 5 potential documents
                        try:
                            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_dir}/{doc_name}"
                            doc_response = requests.get(doc_url, headers=client.headers, timeout=30)
                            if doc_response.status_code == 200:
                                output_path = output_dir / doc_name
                                with open(output_path, 'wb') as f:
                                    f.write(doc_response.content)
                                file_path = str(output_path)
                                document_name = doc_name  # Update document name
                                print(f"    ✓ Downloaded from index: {doc_name}")
                                break
                        except:
                            continue
            except:
                pass
            
            # If still not found, try common document name patterns
            if not file_path or not Path(file_path).exists():
                alt_names = [
                    document_name,
                    document_name.replace('.htm', '.txt'),
                    f"{form_type.lower()}.htm",
                    f"{form_type.lower()}.txt",
                    f"d{accession_dir[-6:]}d{form_type.lower()}.htm",  # Common pattern like d123456d8k.htm
                ]
                
                # Try downloading with alternative names
                for alt_name in alt_names:
                    try:
                        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_dir}/{alt_name}"
                        response = requests.get(doc_url, headers=client.headers, timeout=30)
                        if response.status_code == 200:
                            output_path = output_dir / alt_name
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            file_path = str(output_path)
                            document_name = alt_name  # Update document name
                            print(f"    ✓ Downloaded with alternative name: {alt_name}")
                            break
                    except:
                        continue
            
            if not file_path or not Path(file_path).exists():
                result['status'] = 'error'
                result['error'] = 'Failed to download filing (tried multiple document names)'
                print(f"    ❌ Failed to download filing after trying alternatives")
                return result
        
        print(f"    ✓ Downloaded")
        
        # Parse the filing
        print(f"    Parsing...")
        parsed_data = parse_sec_filing(file_path, document_name=document_name)
        
        if not parsed_data or isinstance(parsed_data, str):
            result['status'] = 'error'
            result['error'] = 'Failed to parse filing'
            print(f"    ❌ Failed to parse filing")
            return result
        
        print(f"    ✓ Parsed: {len(parsed_data.get('sections', []))} sections")
        
        # Chunk the documents
        print(f"    Chunking...")
        chunks = chunk_sec_documents([parsed_data])
        
        if not chunks:
            result['status'] = 'error'
            result['error'] = 'No chunks generated'
            print(f"    ❌ No chunks generated")
            return result
        
        print(f"    ✓ Generated {len(chunks)} chunks")
        
        # Add metadata to chunks
        filing_date_iso = filing_info.get('filing_date_iso')
        if not filing_date_iso and matching_filing.get('filing_date'):
            filing_date_iso = matching_filing['filing_date']
        
        for chunk in chunks:
            chunk_metadata = {
                'cik': cik,
                'form': form_type,
                'accession_number': accession_number,
                'company_name': company_name
            }
            if filing_date_iso:
                chunk_metadata['filing_date'] = filing_date_iso
            chunk['metadata'] = chunk_metadata
        
        # Index chunks
        print(f"    Indexing...")
        indexed_count = index_sec_chunks(chunks, es_client=es, create_index=True)
        
        result['status'] = 'success'
        result['chunks_indexed'] = indexed_count
        print(f"    ✓ Indexed {indexed_count} chunks")
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def main():
    """Main function to check and index ground truth filings."""
    print("="*80)
    print("Ground Truth Filings Checker and Indexer")
    print("="*80)
    print()
    
    # Paths
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "eval" / "ground_truth_21_cases.csv"
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
        
        if not es.indices.exists(index="sec_filings"):
            print("⚠️  Index 'sec_filings' does not exist - will be created")
        else:
            count_before = es.count(index="sec_filings")['count']
            print(f"✓ Elasticsearch connected - {count_before:,} documents currently indexed")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    print()
    print("Checking which filings are already indexed...")
    print()
    
    # Check each filing
    missing_filings = []
    indexed_filings = []
    
    for i, filing_info in enumerate(filings, 1):
        cik = filing_info['cik']
        company_name = filing_info['company_name']
        form_type = filing_info['form_type']
        filing_date_iso = filing_info.get('filing_date_iso')
        accession_number = filing_info.get('accession_number')
        
        print(f"[{i}/{len(filings)}] {company_name} - {form_type} ({filing_info['filing_date']})")
        
        check_result = check_filing_in_elasticsearch(
            es, cik, form_type, filing_date_iso, accession_number
        )
        
        if check_result.get('exists'):
            count = check_result['count']
            print(f"    ✓ Already indexed ({count} chunks)")
            indexed_filings.append({
                'filing_info': filing_info,
                'chunks_count': count
            })
        else:
            print(f"    ⚠️  Not found in index - will download and index")
            missing_filings.append(filing_info)
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total filings in CSV: {len(filings)}")
    print(f"Already indexed: {len(indexed_filings)}")
    print(f"Missing: {len(missing_filings)}")
    print()
    
    if not missing_filings:
        print("✅ All filings are already indexed!")
        return
    
    print(f"Indexing {len(missing_filings)} missing filings...")
    print()
    
    # Initialize client
    client = SECEdgarClient()
    
    # Index missing filings
    results = []
    start_time = datetime.now()
    
    for i, filing_info in enumerate(missing_filings, 1):
        print(f"\n[{i}/{len(missing_filings)}] {filing_info['company_name']} - {filing_info['form_type']}")
        result = index_filing(client, es, filing_info, output_dir)
        results.append(result)
        
        # Small delay between filings to avoid rate limiting
        if i < len(missing_filings):
            time.sleep(2)
    
    # Calculate summary
    total_time = (datetime.now() - start_time).total_seconds()
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'error')
    total_chunks = sum(r['chunks_indexed'] for r in results)
    
    # Get final count
    try:
        count_after = es.count(index="sec_filings")['count']
        print(f"\n✓ Final index count: {count_after:,} documents")
    except:
        pass
    
    # Save results
    results_file = project_root / "eval" / "ground_truth_indexing_results.json"
    output_data = {
        'indexing_timestamp': datetime.now().isoformat(),
        'total_filings_checked': len(filings),
        'already_indexed': len(indexed_filings),
        'missing_filings': len(missing_filings),
        'successful': successful,
        'failed': failed,
        'total_chunks_indexed': total_chunks,
        'total_duration_seconds': total_time,
        'results': results
    }
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*80)
    print("INDEXING SUMMARY")
    print("="*80)
    print(f"Missing filings processed: {len(missing_filings)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total chunks indexed: {total_chunks:,}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print()
    print(f"✓ Results saved to: {results_file}")
    print("="*80)
    
    # Print failed filings
    if failed > 0:
        print("\nFailed filings:")
        for result in results:
            if result['status'] == 'error':
                print(f"  ✗ {result['company_name']} - {result['form_type']} ({result['filing_date']})")
                print(f"      Error: {result['error']}")


if __name__ == "__main__":
    main()

