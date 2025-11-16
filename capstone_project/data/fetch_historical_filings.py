#!/usr/bin/env python3
"""
Fetch specific historical filings that aren't in the "recent" filings list.

This script directly accesses historical filing files for companies where
we need older filings (pre-2017) that aren't in the standard recent filings.
"""

import requests
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def fetch_historical_filings_for_company(cik: str, target_years: list, target_forms: list):
    """
    Fetch historical filings from the SEC API's historical files.
    
    Returns list of filing dictionaries matching target years and forms.
    """
    headers = {'User-Agent': os.getenv('SEC_USER_AGENT', 'Test')}
    base_url = "https://data.sec.gov/submissions"
    
    # Get company submissions
    url = f"{base_url}/CIK{cik}.json"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching submissions: {e}")
        return []
    
    all_filings = []
    
    # Get recent filings
    recent = data.get('filings', {}).get('recent', {})
    if recent:
        accession_numbers = recent.get('accessionNumber', [])
        filing_dates = recent.get('filingDate', [])
        forms = recent.get('form', [])
        primary_docs = recent.get('primaryDocument', [])
        
        for i in range(len(filing_dates)):
            try:
                filing_year = int(filing_dates[i].split('-')[0])
                if filing_year in target_years and forms[i] in target_forms:
                    all_filings.append({
                        'accession_number': accession_numbers[i],
                        'filing_date': filing_dates[i],
                        'form': forms[i],
                        'primary_document': primary_docs[i],
                        'cik': cik
                    })
            except (ValueError, IndexError):
                continue
    
    # Get historical filings
    historical_files = data.get('filings', {}).get('files', [])
    for hist_file in historical_files:
        hist_url = f"{base_url}/{hist_file['name']}"
        try:
            hist_response = requests.get(hist_url, headers=headers, timeout=30)
            hist_response.raise_for_status()
            hist_data = hist_response.json()
            
            hist_recent = hist_data.get('filings', {}).get('recent', {})
            if hist_recent:
                hist_accession = hist_recent.get('accessionNumber', [])
                hist_dates = hist_recent.get('filingDate', [])
                hist_forms = hist_recent.get('form', [])
                hist_docs = hist_recent.get('primaryDocument', [])
                
                for j in range(len(hist_dates)):
                    try:
                        filing_year = int(hist_dates[j].split('-')[0])
                        if filing_year in target_years and hist_forms[j] in target_forms:
                            all_filings.append({
                                'accession_number': hist_accession[j],
                                'filing_date': hist_dates[j],
                                'form': hist_forms[j],
                                'primary_document': hist_docs[j],
                                'cik': cik
                            })
                    except (ValueError, IndexError):
                        continue
            
            # Small delay
            import time
            time.sleep(0.1)
        except Exception as e:
            print(f"Error fetching historical file {hist_file['name']}: {e}")
            continue
    
    return all_filings


if __name__ == "__main__":
    # Test with Home Depot
    cik = "0000354950"
    target_years = [2014, 2015]
    target_forms = ["8-K"]
    
    print(f"Fetching historical filings for CIK {cik}")
    print(f"Target years: {target_years}, Forms: {target_forms}")
    
    filings = fetch_historical_filings_for_company(cik, target_years, target_forms)
    
    print(f"\nFound {len(filings)} matching filings:")
    for f in filings:
        print(f"  {f['filing_date']} - {f['form']} - {f['primary_document']}")

