#!/usr/bin/env python3
"""
Run stress test questions against the SEC Cybersecurity Agent.

This script:
1. Reads questions from stress_test_questions.csv
2. Runs each question through the agent
3. Saves questions and responses to stress_test_results.json
"""

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Import agent setup from notebook
from pydantic_ai import Agent
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.sec_search_tools import search_cybersecurity_disclosures, search_sec_filings
from src.sec_edgar_client import SECEdgarClient
from src.company_cik_lookup import lookup_company_cik, find_companies_in_text, lookup_by_ticker, get_historical_name_info
from src.subsidiary_cik_mapping import find_parent_cik_for_subsidiary, get_parent_company_info

# Import the tools and agent setup (same as notebook)
def lookup_subsidiary_parent(company_name: str, incident_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up if a company name is a subsidiary and return the parent company CIK.
    
    This tool should be used when a question mentions a company that might be a subsidiary.
    It checks if the company is a subsidiary and returns the parent company CIK to search.
    
    Args:
        company_name: Name of the company (e.g., "Change Healthcare")
        incident_date: Optional date of incident (YYYY-MM-DD) to check if subsidiary
                      was acquired by that date
    
    Returns:
        Dictionary with:
        - is_subsidiary: True if found as subsidiary, False otherwise
        - parent_cik: Parent company CIK if found
        - parent_name: Parent company name if found
        - subsidiary_info: Subsidiary metadata if found
        - error: Error message if not found
    """
    result = find_parent_cik_for_subsidiary(company_name, incident_date)
    
    if result:
        parent_cik, subsidiary_info = result
        parent_info = get_parent_company_info(parent_cik)
        
        return {
            "is_subsidiary": True,
            "parent_cik": parent_cik,
            "parent_name": parent_info.get("parent_name", "Unknown") if parent_info else "Unknown",
            "subsidiary_name": company_name,
            "subsidiary_info": subsidiary_info,
            "found": True,
            "error": None
        }
    else:
        return {
            "is_subsidiary": False,
            "parent_cik": None,
            "parent_name": None,
            "subsidiary_name": company_name,
            "found": False,
            "error": f"'{company_name}' is not found in subsidiary mapping. It may be a standalone company or not yet added to the mapping."
        }


def lookup_company_by_name(company_name: str) -> Dict[str, Any]:
    """
    Look up CIK number for a company by name.
    
    This tool supports:
    - Current company names
    - Historical names (e.g., "Yahoo" maps to Altaba's CIK)
    - Ticker symbols (e.g., "UBER", "MGM", "EFX")
    
    This tool should be used when a question mentions a company name
    but doesn't provide a CIK number. It maps common company name variations
    to their correct CIK numbers.
    
    Args:
        company_name: Company name or ticker symbol (e.g., "UnitedHealth Group", "Change Healthcare", "UBER", "MGM")
        
    Returns:
        Dictionary with:
        - cik: CIK number if found (10 digits with leading zeros)
        - company_name: The normalized company name
        - found: True if CIK was found, False otherwise
        - is_ticker: True if found via ticker symbol
        - is_historical: True if found via historical name
        - historical_info: Information about name change if applicable
        - error: Error message if not found
    """
    # Check if it's a ticker symbol first (short, uppercase-like)
    if len(company_name.strip()) <= 5 and company_name.strip().isalnum():
        ticker_cik = lookup_by_ticker(company_name)
        if ticker_cik:
            return {
                "cik": ticker_cik,
                "company_name": company_name,
                "found": True,
                "is_ticker": True,
                "is_historical": False,
                "historical_info": None,
                "error": None
            }
    
    # Try regular company name lookup
    cik = lookup_company_cik(company_name)
    
    if cik:
        # Check if it's a historical name
        historical_info = get_historical_name_info(company_name)
        is_historical = bool(historical_info)
        
        return {
            "cik": cik,
            "company_name": company_name,
            "found": True,
            "is_ticker": False,
            "is_historical": is_historical,
            "historical_info": historical_info if is_historical else None,
            "error": None
        }
    else:
        return {
            "cik": None,
            "company_name": company_name,
            "found": False,
            "is_ticker": False,
            "is_historical": False,
            "historical_info": None,
            "error": f"Company '{company_name}' not found in lookup table. Please provide the CIK number directly, use a known company name variation, or try the ticker symbol."
        }


def get_company_info(cik: str) -> Dict[str, Any]:
    """
    Get company information from SEC EDGAR API.
    
    Args:
        cik: Central Index Key (CIK) of the company (can be with or without leading zeros)
        
    Returns:
        Dictionary with company information (name, ticker, industry, cik, etc.)
        or dictionary with 'error' key if fetch fails
    """
    try:
        # Normalize CIK - handle various input formats
        cik_str = str(cik).strip()
        if cik_str.upper().startswith("CIK"):
            cik_str = cik_str[3:].strip()
        cik_digits = ''.join(filter(str.isdigit, cik_str))
        
        if not cik_digits or len(cik_digits) > 10:
            return {"error": f"Invalid CIK format: {cik}. CIK must be 1-10 digits."}
        
        cik_normalized = cik_digits.zfill(10)
        
        # Initialize SEC EDGAR client (reads SEC_USER_AGENT from .env)
        client = SECEdgarClient()
        
        # Try with the normalized CIK
        company_info = client.get_company_info(cik_normalized)
        
        if company_info and not company_info.get("error"):
            # Extract ticker - handle both single value and list
            tickers = company_info.get("tickers", [])
            ticker = tickers[0] if tickers and len(tickers) > 0 else "N/A"
            
            # Use the CIK returned from API (properly formatted)
            returned_cik = company_info.get("cik", cik_normalized)
            
            return {
                "name": company_info.get("name", "Unknown"),
                "ticker": ticker,
                "industry": company_info.get("sicDescription", "Unknown"),
                "cik": str(returned_cik).zfill(10) if returned_cik else cik_normalized,
                "entity_type": company_info.get("entityType", "Unknown"),
                "sic_code": company_info.get("sic", "N/A")
            }
        else:
            return {"error": f"CIK {cik} (normalized: {cik_normalized}) not found in SEC database. The company may not exist, may have merged, or the CIK may be incorrect. Please verify the CIK on the SEC website."}
    except Exception as e:
        error_str = str(e)
        if "404" in error_str or "Not Found" in error_str:
            return {"error": f"CIK {cik} not found in SEC database (404 error). The CIK may be incorrect or the company may no longer exist."}
        return {"error": f"Error fetching company info: {error_str}"}


def search_company_cybersecurity_disclosures(
    cik: str, 
    query: str = "cybersecurity OR data breach OR ransomware OR security incident",
    years: int = 3
) -> List[Dict[str, Any]]:
    """
    Search for cybersecurity disclosures in SEC filings for a given company.
    
    Args:
        cik: Central Index Key (CIK) of the company (can be with or without leading zeros)
        query: Search query string (default includes common cybersecurity terms)
        years: Number of years to search back (default: 3)
        
    Returns:
        List of chunks containing cybersecurity-related disclosures
    """
    try:
        # Normalize CIK - same logic as get_company_info
        cik_str = str(cik).strip()
        if cik_str.upper().startswith("CIK"):
            cik_str = cik_str[3:].strip()
        cik_digits = ''.join(filter(str.isdigit, cik_str))
        
        if not cik_digits or len(cik_digits) > 10:
            return [{"content": f"Invalid CIK format: {cik}. CIK must be 1-10 digits.", "metadata": {}, "error": True}]
        
        cik_normalized = cik_digits.zfill(10)
        
        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        date_range = (start_date, end_date)
        
        # Check if Elasticsearch is available
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch('http://localhost:9200')
            if not es.ping():
                return [{"content": "Elasticsearch is not running. Please start Elasticsearch first.", "metadata": {"cik": cik_normalized}, "error": True}]
            
            # Check if index exists
            if not es.indices.exists(index="sec_filings"):
                return [{"content": "Elasticsearch index 'sec_filings' does not exist. Please index your SEC filing chunks first using sec_search_tools.index_sec_chunks().", "metadata": {"cik": cik_normalized}, "error": True}]
        except ImportError:
            return [{"content": "Elasticsearch package not installed. Install with: pip install elasticsearch", "metadata": {"cik": cik_normalized}, "error": True}]
        except Exception as e:
            return [{"content": f"Error connecting to Elasticsearch: {str(e)}", "metadata": {"cik": cik_normalized}, "error": True}]
        
        # Determine form types based on company (Sony uses foreign issuer forms)
        if cik_normalized == "0000313838":  # Sony Group Corp
            form_types = ["20-F", "6-K", "8-K"]
        else:
            form_types = ["10-K", "10-Q", "8-K", "20-F", "6-K"]  # Include foreign issuer forms
        
        # Search for cybersecurity disclosures
        results = search_cybersecurity_disclosures(
            company_cik=cik_normalized,
            query=query,
            date_range=date_range,
            form_types=form_types,
            num_results=30  # Get more results for comprehensive summary
        )
        
        if not results:
            return [{"content": "No cybersecurity disclosures found in SEC filings for this company and date range. The filings may not have been indexed in Elasticsearch, or no cybersecurity disclosures exist in the searched filings.", "metadata": {"cik": cik_normalized}, "no_results": True}]
        
        return results
    except Exception as e:
        import traceback
        error_msg = f"Error searching for cybersecurity disclosures: {str(e)}\n{traceback.format_exc()}"
        return [{"content": error_msg, "metadata": {"cik": cik}, "error": True}]


# Agent instructions (from notebook)
final_instructions = """
You are an expert SEC filing analyst specializing in cybersecurity disclosures for supply chain risk assessment.

Your primary function is to analyze SEC filings and extract all cybersecurity-related information for a given company.

CRITICAL: CIK LOOKUP WORKFLOW
When a question mentions a company NAME (not a CIK), you MUST:
1. FIRST check if it's a subsidiary by calling lookup_subsidiary_parent(company_name)
   - If it's a subsidiary, use the parent_cik returned
   - If not a subsidiary, proceed to step 2
2. Call lookup_company_by_name(company_name) to get the correct CIK
3. Verify the CIK by calling get_company_info(cik) to confirm the company name matches
4. If the company name from get_company_info doesn't match what was asked, report an error - DO NOT proceed with wrong CIK
5. Only then proceed to search for cybersecurity disclosures

SUBSIDIARY AND DIVISION HANDLING:
- If lookup_subsidiary_parent returns a parent_cik, use that CIK for all searches
- Cybersecurity incidents for subsidiaries and divisions appear in the parent company's SEC filings
- Always mention in your response that you're searching the parent company's filings for the subsidiary/division's incident
- Examples: "Change Healthcare" (subsidiary) → UnitedHealth Group filings, "Sony Pictures" (division) → Sony Group Corp filings

HISTORICAL NAME HANDLING:
- Some companies have changed names but kept the same CIK (e.g., Yahoo → Altaba)
- lookup_company_by_name will automatically map historical names to current CIK
- If historical_info is returned, note the name change in your response

TICKER SYMBOL HANDLING:
- If company name lookup fails, try ticker symbols (UBER, MGM, EFX, etc.)
- lookup_company_by_name supports ticker symbols directly
- Examples: "UBER" → Uber Technologies, "MGM" → MGM Resorts, "EFX" → Equifax

WORKFLOW - When given a CIK number directly, you MUST follow these steps:
1. Call get_company_info(cik) FIRST to identify and verify the company
2. Verify the company name matches what was asked in the question
3. Call search_company_cybersecurity_disclosures(cik) to retrieve all cybersecurity-related chunks from SEC filings
4. Analyze the retrieved chunks systematically
5. Generate a comprehensive summary following the structure below

WORKFLOW - When given a company NAME (not CIK), you MUST follow these steps:
1. FIRST call lookup_subsidiary_parent(company_name) to check if it's a subsidiary
   - If is_subsidiary is True, use the parent_cik for all subsequent steps
   - If is_subsidiary is False, proceed to step 2
2. Call lookup_company_by_name(company_name) to get the CIK (if not a subsidiary)
3. Call get_company_info(cik) to verify the company name matches
4. If company name doesn't match, STOP and report the mismatch - DO NOT use wrong CIK
5. Call search_company_cybersecurity_disclosures(cik) to retrieve all cybersecurity-related chunks
   - If using parent_cik for a subsidiary, note this in your analysis
6. Analyze the retrieved chunks systematically
7. Generate a comprehensive summary following the structure below

REQUIRED SUMMARY STRUCTURE:

## Company Information
- Company Name: [name]
- Ticker Symbol: [ticker]
- Industry: [industry]
- CIK: [cik]

## Cybersecurity Disclosures Summary

### Security Incidents
List and describe any disclosed cybersecurity incidents, data breaches, unauthorized access, ransomware attacks, or other security events. Include:
- Nature of the incident
- When it occurred (if disclosed)
- Impact or scope (if disclosed)
- Filing date and form type where disclosed

### Risk Factors
Summarize cybersecurity-related risk factors mentioned in the filings, such as:
- Risks related to data security and privacy
- Dependencies on third-party vendors or cloud providers
- Potential impact of cyber attacks on operations
- Regulatory compliance challenges
- Any specific vulnerabilities or threats identified

### Security Measures and Improvements
Describe any cybersecurity measures, controls, or improvements mentioned:
- Security investments or initiatives
- Remediation efforts following incidents
- Improvements to security infrastructure
- Compliance measures or certifications

### Filing Timeline
List ALL filings reviewed with specific dates and form types:
- [Form Type] filed [Filing Date]: [Specific disclosure or information found]
- Example: "Form 8-K filed July 19, 2019: Capital One disclosed the data breach affecting 106 million customers"
- Example: "Form 10-K filed February 2, 2024: T-Mobile reported ongoing litigation from August 2021 cyberattack"
- If no filings were found, state: "No SEC filings found containing cybersecurity disclosures for this company"

CRITICAL DATA SOURCE REQUIREMENTS - ABSOLUTE PROHIBITION:
- YOU MUST ONLY USE INFORMATION FROM SEC FILINGS - NEVER use general knowledge, public information, or any source other than SEC filings
- If search_company_cybersecurity_disclosures returns no results or empty results, you MUST state "No cybersecurity disclosures found in SEC filings" and STOP IMMEDIATELY
- NEVER supplement SEC filing data with general knowledge, even if you know the information
- NEVER say "based on general knowledge", "based on publicly available information", "while there are no documented disclosures", "we can outline general risks", "even though specific SEC filings are not available", or any similar phrases
- If you cannot find information in SEC filings, the answer is ONLY "No information available in SEC filings" - do NOT provide alternative information, general advice, or explanations
- DO NOT provide "general risks" or "typical implications" when no SEC filings are found
- DO NOT explain what "could" or "might" happen - only state what IS in SEC filings
- If no filings found, your ENTIRE response should be: "No cybersecurity disclosures found in SEC filings for this company" - nothing else

CITATION REQUIREMENTS:
- ALWAYS cite specific SEC filings for EVERY piece of information you provide
- Format: "[Form Type] filed [Date]: [specific information]"
- Examples: "Form 8-K filed July 19, 2019: Capital One disclosed the breach", "Form 10-K filed February 2, 2024: T-Mobile reported..."
- If you cannot cite a specific filing, DO NOT include that information in your response
- List all filings reviewed in the Filing Timeline section with specific dates and form types

IMPORTANT GUIDELINES:
- ALWAYS check for subsidiaries first using lookup_subsidiary_parent() before looking up company names
- If a company is a subsidiary, use the parent company's CIK for all searches
- NEVER guess or approximate CIK numbers - always use lookup_subsidiary_parent() or lookup_company_by_name() first
- ALWAYS verify company name matches after getting CIK - if it doesn't match, report error and stop
- Always use the tools - never provide information without first calling lookup_subsidiary_parent (for subsidiaries), lookup_company_by_name (for names) or get_company_info (for CIKs) and search_company_cybersecurity_disclosures
- If no cybersecurity disclosures are found, clearly state "No cybersecurity disclosures found in the analyzed SEC filings" and DO NOT provide any additional information
- Cite specific filing dates and form types for ALL information - if you cannot cite a filing, do not include that information
- Use professional, clear language appropriate for supply chain and procurement professionals
- Group similar information together rather than listing every chunk separately
- Highlight trends or changes in disclosure patterns over time
- If disclosures mention vendors, suppliers, or third parties, note this clearly

ERROR HANDLING - STRICT PROHIBITIONS:
- If lookup_company_by_name returns "found: False", DO NOT proceed - report that the company name could not be found
- If get_company_info returns a company name that doesn't match the question, DO NOT proceed - report the mismatch
- Never use a CIK if the company name doesn't match what was asked in the question
- If search_company_cybersecurity_disclosures returns no results, DO NOT provide information from other sources
- If search_company_cybersecurity_disclosures returns no results, your response MUST be ONLY: "No cybersecurity disclosures found in SEC filings for this company" - DO NOT add explanations, general advice, implications, or any other information
- FORBIDDEN PHRASES when no filings found: "while there are no documented disclosures", "we can outline general risks", "even though specific SEC filings are not available", "based on general context", "here is an overview based on", "the implications can be", "it is important to highlight that while I could not find"
- If no filings found, DO NOT provide: risk assessments, general implications, typical scenarios, or any analysis - ONLY state that no filings were found
""".strip()

# Create the agent
cybersecurity_agent = Agent(
    name='sec_cybersecurity_agent',
    instructions=final_instructions,
    tools=[lookup_subsidiary_parent, lookup_company_by_name, get_company_info, search_company_cybersecurity_disclosures],
    model='openai:gpt-4o-mini'
)


def load_questions(csv_path: str) -> List[Dict[str, str]]:
    """Load questions from CSV file."""
    questions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append({
                'question_number': row['Question_Number'],
                'primary_focus': row['Primary_Focus'],
                'question_text': row['Question_Text'],
                'companies_involved': row['Companies_Involved'],
                'difficulty_level': row['Difficulty_Level'],
                'num_capabilities_tested': row['Num_Capabilities_Tested']
            })
    return questions


async def run_question(question: Dict[str, str]) -> Dict[str, Any]:
    """Run a single question through the agent."""
    print(f"\n{'='*80}")
    print(f"Question {question['question_number']}: {question['primary_focus']}")
    print(f"{'='*80}")
    print(f"Question: {question['question_text']}")
    print(f"Difficulty: {question['difficulty_level']}")
    print(f"Companies: {question['companies_involved']}")
    print()
    print("Running agent...")
    
    start_time = datetime.now()
    
    try:
        result = await cybersecurity_agent.run(user_prompt=question['question_text'])
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✓ Completed in {duration:.1f} seconds")
        
        return {
            'question_number': question['question_number'],
            'primary_focus': question['primary_focus'],
            'question_text': question['question_text'],
            'companies_involved': question['companies_involved'],
            'difficulty_level': question['difficulty_level'],
            'num_capabilities_tested': question['num_capabilities_tested'],
            'response': result.output,
            'duration_seconds': duration,
            'timestamp': end_time.isoformat(),
            'status': 'success',
            'error': None
        }
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        
        return {
            'question_number': question['question_number'],
            'primary_focus': question['primary_focus'],
            'question_text': question['question_text'],
            'companies_involved': question['companies_involved'],
            'difficulty_level': question['difficulty_level'],
            'num_capabilities_tested': question['num_capabilities_tested'],
            'response': None,
            'duration_seconds': duration,
            'timestamp': end_time.isoformat(),
            'status': 'error',
            'error': error_msg
        }


async def main():
    """Main function to run all stress tests."""
    print("="*80)
    print("SEC Cybersecurity Agent - Stress Test Suite")
    print("="*80)
    print()
    
    # Load questions
    csv_path = Path(__file__).parent.parent / "eval" / "stress_test_questions.csv"
    if not csv_path.exists():
        print(f"❌ Error: {csv_path} not found")
        return
    
    questions = load_questions(str(csv_path))
    print(f"Loaded {len(questions)} questions from {csv_path}")
    print()
    
    # Check Elasticsearch
    print("Checking Elasticsearch connection...")
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch('http://localhost:9200')
        if not es.ping():
            print("❌ Elasticsearch is not running. Please start it first.")
            return
        count = es.count(index="sec_filings")['count']
        print(f"✓ Elasticsearch connected - {count:,} documents indexed")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    print()
    print("Starting stress tests...")
    print()
    
    # Run all questions
    results = []
    start_time = datetime.now()
    
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}]")
        result = await run_question(question)
        results.append(result)
        
        # Small delay between questions to avoid rate limiting
        if i < len(questions):
            await asyncio.sleep(2)
    
    # Calculate summary
    total_time = (datetime.now() - start_time).total_seconds()
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'error')
    avg_duration = sum(r['duration_seconds'] for r in results) / len(results) if results else 0
    
    # Save results
    output_file = Path(__file__).parent.parent / "eval" / "stress_test_results.json"
    output_data = {
        'test_run_timestamp': datetime.now().isoformat(),
        'total_questions': len(questions),
        'successful': successful,
        'failed': failed,
        'total_duration_seconds': total_time,
        'average_duration_seconds': avg_duration,
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*80)
    print("STRESS TEST SUMMARY")
    print("="*80)
    print(f"Total questions: {len(questions)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Average time per question: {avg_duration:.1f} seconds")
    print()
    print(f"✓ Results saved to: {output_file}")
    print("="*80)
    
    # Print per-question status
    print("\nPer-question status:")
    for result in results:
        status_icon = "✓" if result['status'] == 'success' else "✗"
        print(f"  {status_icon} Question {result['question_number']}: {result['primary_focus']} ({result['duration_seconds']:.1f}s)")
        if result['status'] == 'error':
            print(f"      Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())

