"""
SEC EDGAR Client - Pull all SEC filings for a given CIK number for the last three years.

This script accesses the SEC EDGAR API to retrieve company filings based on CIK number.

Requirements:
- A valid User-Agent header (SEC requirement)
- Internet connection to access data.sec.gov

Configuration:
- Set SEC_USER_AGENT in .env file or pass user_agent parameter
- Format: "Your Name (your.email@example.com)"

References:
- https://www.sec.gov/edgar/sec-api-documentation
- https://www.sec.gov/accessing-edgar-data
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    import pathlib
    
    # Try to load from current directory (capstone_project) or parent directory
    env_path = pathlib.Path(__file__).parent / '.env'
    if not env_path.exists():
        env_path = pathlib.Path(__file__).parent.parent / '.env'
    
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, will use provided user_agent

# Import XML parsing and chunking functionality
try:
    from src.sec_xml_parser import parse_sec_filing as _parse_sec_filing, chunk_sec_documents as _chunk_sec_documents, SECXMLParser as _SECXMLParser
    XML_PARSING_AVAILABLE = True
except ImportError:
    XML_PARSING_AVAILABLE = False


class SECEdgarClient:
    """Client for accessing SEC EDGAR API to retrieve company filings."""
    
    BASE_URL = "https://data.sec.gov"
    
    def __init__(self, user_agent: Optional[str] = None):
        """
        Initialize the SEC EDGAR client.
        
        Args:
            user_agent: User-Agent string required by SEC API.
                       Should be in format: "Your Name (your.email@example.com)"
                       If None, will try to load from SEC_USER_AGENT env var.
        """
        if user_agent is None:
            user_agent = os.getenv('SEC_USER_AGENT', "Your Company (your.email@example.com)")
        
        self.headers = {'User-Agent': user_agent}
    
    def fetch_filings(self, cik: str, years: int = 3) -> List[Dict]:
        """
        Fetch all SEC filings for a given CIK for the last N years.
        
        Args:
            cik: Central Index Key (CIK) of the company
            years: Number of years to look back (default: 3)
        
        Returns:
            List of dictionaries containing filing information
        
        Example:
            client = SECEdgarClient("My Company (me@example.com)")
            filings = client.fetch_filings("0000320193")  # Apple Inc.
        """
        # Format CIK to 10 digits with leading zeros
        cik = str(cik).zfill(10)
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=years * 365)
        
        # Construct API URL
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
        
        print(f"Fetching filings for CIK {cik}...")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract recent filings
            filings = data.get('filings', {}).get('recent', {})
            
            if not filings:
                print("No recent filings found.")
                return []
            
            # Get lists of filing data
            accession_numbers = filings.get('accessionNumber', [])
            filing_dates = filings.get('filingDate', [])
            forms = filings.get('form', [])
            primary_documents = filings.get('primaryDocument', [])
            primary_doc_descriptions = filings.get('primaryDocDescription', [])
            
            # Filter filings from the last N years
            recent_filings = []
            for i in range(len(filing_dates)):
                filing_date = datetime.strptime(filing_dates[i], '%Y-%m-%d')
                
                if filing_date >= cutoff_date:
                    filing_info = {
                        'accession_number': accession_numbers[i],
                        'filing_date': filing_dates[i],
                        'form': forms[i],
                        'primary_document': primary_documents[i],
                        'primary_doc_description': primary_doc_descriptions[i],
                        'cik': cik
                    }
                    recent_filings.append(filing_info)
            
            # Also get historical filings if they exist
            if 'files' in data.get('filings', {}):
                for historical_file in data['filings']['files']:
                    historical_url = f"{self.BASE_URL}/submissions/{historical_file['name']}"
                    try:
                        hist_response = requests.get(historical_url, headers=self.headers, timeout=30)
                        hist_response.raise_for_status()
                        hist_data = hist_response.json()
                        
                        hist_filings = hist_data.get('filings', {}).get('recent', {})
                        hist_accession_numbers = hist_filings.get('accessionNumber', [])
                        hist_filing_dates = hist_filings.get('filingDate', [])
                        hist_forms = hist_filings.get('form', [])
                        hist_primary_docs = hist_filings.get('primaryDocument', [])
                        hist_primary_doc_descs = hist_filings.get('primaryDocDescription', [])
                        
                        for j in range(len(hist_filing_dates)):
                            hist_filing_date = datetime.strptime(hist_filing_dates[j], '%Y-%m-%d')
                            
                            if hist_filing_date >= cutoff_date:
                                filing_info = {
                                    'accession_number': hist_accession_numbers[j],
                                    'filing_date': hist_filing_dates[j],
                                    'form': hist_forms[j],
                                    'primary_document': hist_primary_docs[j],
                                    'primary_doc_description': hist_primary_doc_descs[j],
                                    'cik': cik
                                }
                                recent_filings.append(filing_info)
                        
                        # Be respectful of rate limits
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"Error fetching historical filing {historical_file['name']}: {e}")
                        continue
            
            print(f"Found {len(recent_filings)} filings in the last {years} years.")
            return recent_filings
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return []
    
    def get_company_info(self, cik: str) -> Optional[Dict]:
        """
        Get company information for a given CIK.
        
        Args:
            cik: Central Index Key (CIK) of the company
        
        Returns:
            Dictionary containing company information or None
        """
        cik = str(cik).zfill(10)
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'cik': data.get('cik'),
                'entityType': data.get('entityType'),
                'sic': data.get('sic'),
                'sicDescription': data.get('sicDescription'),
                'name': data.get('name'),
                'tickers': data.get('tickers', []),
                'exchanges': data.get('exchanges', [])
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching company info: {e}")
            return None
    
    def download_and_parse_filing(
        self, 
        accession_number: str, 
        primary_document: str,
        cik: str,
        output_dir: Optional[str] = None,
        parse_content: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Download and parse a filing document with XML parsing.
        
        Args:
            accession_number: e.g., "0000320193-24-000001"
            primary_document: e.g., "aapl-10k_20220930.htm"
            cik: Company CIK
            output_dir: Directory to save the file
            parse_content: If True, parse and return structured content
            
        Returns:
            Parsed document dictionary or None if failed
        """
        # Download the file
        file_path = self.download_filing_document(
            accession_number, primary_document, cik, output_dir
        )
        
        if not file_path or not parse_content:
            return None
        
        # Parse the document
        if not XML_PARSING_AVAILABLE:
            print("XML parsing not available. Install required dependencies.")
            return None
            
        try:
            parsed = _parse_sec_filing(file_path, document_name=primary_document)
            return parsed
        except Exception as e:
            print(f"Error parsing document: {e}")
            return None
    
    def download_filing_document(self, accession_number: str, primary_document: str, 
                                cik: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Download the actual filing document.
        
        Args:
            accession_number: e.g., "0000320193-24-000001"
            primary_document: e.g., "aapl-10k_20220930.htm"
            cik: Company CIK
            output_dir: Directory to save the file (default: current directory)
        
        Returns:
            Path to downloaded file or None if failed
        """
        # Convert CIK to integer (remove leading zeros) for URL
        cik_int = str(int(cik))
        
        # Convert accession number to directory format (remove dashes)
        # e.g., "0000731766-25-000310" -> "000073176625000310"
        accession_dir = accession_number.replace('-', '')
        
        # SEC EDGAR uses www.sec.gov/Archives/edgar/data/ format
        # URL format: https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_dir}/{primary_document}
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_dir}/{primary_document}"
        
        try:
            response = requests.get(doc_url, headers=self.headers, timeout=30)
            
            response.raise_for_status()
            
            # Determine output file path
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{primary_document}"
            else:
                output_path = primary_document
            
            # Save the document
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"Downloaded: {output_path}")
            return output_path
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading document: {e}")
            print(f"URL attempted: {doc_url}")
            return None


def main():
    """Example usage of the SEC Edgar Client."""
    
    # Initialize the client with your user agent
    # IMPORTANT: Replace with your actual name and email
    client = SECEdgarClient(user_agent="Your Name (your.email@example.com)")
    
    # Example: Fetch filings for Apple Inc. (CIK: 320193)
    cik = "320193"
    
    print("=" * 80)
    print("SEC EDGAR Client - Example Usage")
    print("=" * 80)
    print()
    
    # Get company information
    print(f"Fetching company information for CIK {cik}...")
    company_info = client.get_company_info(cik)
    
    if company_info:
        print("Company Information:")
        print(json.dumps(company_info, indent=2))
        print()
    
    # Fetch filings
    print("Fetching filings for the last 3 years...")
    filings = client.fetch_filings(cik, years=3)
    
    if filings:
        print(f"\nTotal filings found: {len(filings)}")
        print("\nFirst 5 filings:")
        for filing in filings[:5]:
            print(json.dumps(filing, indent=2))
        
        # Group by form type
        print("\nFilings by form type:")
        form_counts = {}
        for filing in filings:
            form_type = filing['form']
            form_counts[form_type] = form_counts.get(form_type, 0) + 1
        
        for form_type, count in sorted(form_counts.items()):
            print(f"  {form_type}: {count}")
    
    print("\n" + "=" * 80)
    print("Note: To download actual filing documents, use client.download_filing_document()")
    print("=" * 80)


if __name__ == "__main__":
    main()

