"""
Quick test script for SEC EDGAR client with F5, Inc. (CIK: 0001048695)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sec_edgar_client import SECEdgarClient
import json

# Initialize the client (reads from .env)
client = SECEdgarClient()

# F5, Inc. CIK
f5_cik = "1048695"  # No leading zeros needed

print("=" * 80)
print("Testing SEC EDGAR Client with F5, Inc. (CIK: 0001048695)")
print("=" * 80)
print()

# Get company information
print("Fetching company information...")
company_info = client.get_company_info(f5_cik)

if company_info:
    print(f"Company: {company_info.get('name', 'N/A')}")
    print(f"CIK: {company_info.get('cik', 'N/A')}")
    print(f"Ticker: {company_info.get('tickers', 'N/A')}")
    print(f"Entity Type: {company_info.get('entityType', 'N/A')}")
    print()
else:
    print("Could not fetch company information")
    print()

# Fetch filings for the last 3 years
print("Fetching filings for the last 3 years...")
filings = client.fetch_filings(f5_cik, years=3)

if filings:
    print(f"\nTotal filings found: {len(filings)}")
    print()
    
    # Group by form type
    form_counts = {}
    for filing in filings:
        form_type = filing['form']
        form_counts[form_type] = form_counts.get(form_type, 0) + 1
    
    print("Filings by form type:")
    for form_type, count in sorted(form_counts.items()):
        print(f"  {form_type}: {count}")
    
    print()
    
    # Show first 10 filings
    print("Recent filings:")
    for i, filing in enumerate(filings[:10]):
        print(f"  {i+1}. {filing['filing_date']} - {filing['form']}")
    
    # Try to download a recent 10-K or 10-Q if available
    print()
    print("Looking for recent 10-K or 10-Q to download...")
    
    # Prioritize 10-K, then 10-Q
    for filing in filings:
        if filing['form'] in ['10-K', '10-Q']:
            print(f"\nFound {filing['form']} from {filing['filing_date']}")
            print(f"Downloading: {filing['primary_document']}")
            
            output_dir = Path(__file__).parent / "sec_downloads"
            output_dir.mkdir(exist_ok=True)
            
            file_path = client.download_filing_document(
                accession_number=filing['accession_number'],
                primary_document=filing['primary_document'],
                cik=f5_cik,
                output_dir=output_dir
            )
            
            if file_path:
                print(f"✓ Downloaded to: {file_path}")
                
                # Check file size
                import os
                file_size = os.path.getsize(file_path)
                print(f"  File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            break
else:
    print("No filings found for the specified period")

print()
print("=" * 80)
print("Test completed!")
print("=" * 80)
