"""
Company name to CIK lookup mapping.

This module provides a mapping of company names (including common variations),
historical names, and ticker symbols to their CIK numbers for accurate company identification.
"""

# Mapping of company names and variations to CIK numbers
# Based on indexed companies and known cybersecurity incidents
COMPANY_CIK_MAP = {
    # UnitedHealth Group / Change Healthcare
    "unitedhealth group": "0000731766",
    "unitedhealth group inc": "0000731766",
    "unitedhealth": "0000731766",
    "change healthcare": "0000731766",  # Subsidiary of UnitedHealth
    "change healthcare inc": "0000731766",
    
    # Target
    "target": "0000027419",
    "target corporation": "0000027419",
    "target corp": "0000027419",
    
    # Capital One
    "capital one": "0000927628",
    "capital one financial": "0000927628",
    "capital one financial corp": "0000927628",
    "capital one financial corporation": "0000927628",
    
    # Equifax
    "equifax": "0000033185",
    "equifax inc": "0000033185",
    "equifax inc.": "0000033185",
    
    # Marriott
    "marriott": "0001048286",
    "marriott international": "0001048286",
    "marriott international inc": "0001048286",
    "marriott international inc.": "0001048286",
    "starwood": "0001048286",  # Acquired by Marriott
    
    # Home Depot
    "home depot": "0000354950",
    "home depot inc": "0000354950",
    "home depot, inc.": "0000354950",
    "the home depot": "0000354950",
    
    # MGM Resorts
    "mgm": "0000789570",
    "mgm resorts": "0000789570",
    "mgm resorts international": "0000789570",
    "mgm resorts international inc": "0000789570",
    
    # SolarWinds
    "solarwinds": "0001739942",
    "solarwinds corporation": "0001739942",
    "solarwinds corp": "0001739942",
    
    # T-Mobile
    "t-mobile": "0001283699",
    "t-mobile us": "0001283699",
    "t-mobile us inc": "0001283699",
    "t-mobile usa": "0001283699",
    "tmobile": "0001283699",
    
    # Uber
    "uber": "0001543151",
    "uber technologies": "0001543151",
    "uber technologies inc": "0001543151",
    "uber technologies, inc.": "0001543151",
    
    # Sony
    "sony": "0000313838",
    "sony group": "0000313838",
    "sony group corp": "0000313838",
    "sony group corporation": "0000313838",
    "sony pictures": "0000313838",  # Subsidiary
    "sony pictures entertainment": "0000313838",
    
    # First American Financial
    "first american": "0001472787",
    "first american financial": "0001472787",
    "first american financial corp": "0001472787",
    "first american financial corporation": "0001472787",
    
    # Yahoo / Altaba (historical name change - same CIK)
    "yahoo": "0001011006",
    "yahoo inc": "0001011006",
    "yahoo!": "0001011006",
    "yahoo! inc": "0001011006",
    "yahoo! inc.": "0001011006",
    "altaba": "0001011006",
    "altaba inc": "0001011006",
    "altaba inc.": "0001011006",
    "altaba inc. (formerly yahoo! inc.)": "0001011006",
}

# Historical name changes - maps old names to current CIK
# Format: old_name -> (cik, current_name, name_change_date)
HISTORICAL_NAMES = {
    "yahoo": ("0001011006", "Altaba Inc.", "2017-06-16"),  # Renamed to Altaba
    "yahoo inc": ("0001011006", "Altaba Inc.", "2017-06-16"),
    "yahoo!": ("0001011006", "Altaba Inc.", "2017-06-16"),
    "yahoo! inc": ("0001011006", "Altaba Inc.", "2017-06-16"),
    "yahoo! inc.": ("0001011006", "Altaba Inc.", "2017-06-16"),
}

# Ticker symbol to CIK mapping
# Format: ticker -> cik
TICKER_TO_CIK = {
    # UnitedHealth Group
    "UNH": "0000731766",
    "unh": "0000731766",
    
    # Target
    "TGT": "0000027419",
    "tgt": "0000027419",
    
    # Capital One
    "COF": "0000927628",
    "cof": "0000927628",
    
    # Equifax
    "EFX": "0000033185",
    "efx": "0000033185",
    
    # Marriott
    "MAR": "0001048286",
    "mar": "0001048286",
    
    # Home Depot
    "HD": "0000354950",
    "hd": "0000354950",
    
    # MGM Resorts
    "MGM": "0000789570",
    "mgm": "0000789570",
    
    # SolarWinds
    "SWI": "0001739942",
    "swi": "0001739942",
    
    # T-Mobile
    "TMUS": "0001283699",
    "tmus": "0001283699",
    
    # Uber
    "UBER": "0001543151",
    "uber": "0001543151",
    
    # Sony
    "SONY": "0000313838",
    "sony": "0000313838",
    
    # First American Financial
    "FAF": "0001472787",
    "faf": "0001472787",
}


def lookup_company_cik(company_name: str) -> str:
    """
    Look up CIK number for a company name.
    
    Supports:
    - Current company names
    - Historical names (Yahoo → Altaba)
    - Ticker symbols (UBER, MGM, EFX, etc.)
    
    Args:
        company_name: Company name or ticker symbol (case-insensitive, will be normalized)
        
    Returns:
        CIK number as 10-digit string with leading zeros, or empty string if not found
    """
    # Normalize: lowercase, strip whitespace
    normalized = company_name.lower().strip()
    
    # Remove common suffixes and punctuation
    normalized_clean = normalized.replace(",", "").replace(".", "").replace("!", "")
    
    # 1. Try direct lookup in current names
    if normalized_clean in COMPANY_CIK_MAP:
        return COMPANY_CIK_MAP[normalized_clean]
    
    # 2. Try ticker symbol lookup
    if normalized in TICKER_TO_CIK:
        return TICKER_TO_CIK[normalized]
    
    # 3. Try historical name lookup
    if normalized_clean in HISTORICAL_NAMES:
        cik, current_name, change_date = HISTORICAL_NAMES[normalized_clean]
        return cik
    
    # 4. Try partial matches (contains) in current names
    for key, cik in COMPANY_CIK_MAP.items():
        if key in normalized_clean or normalized_clean in key:
            return cik
    
    # 5. Try partial matches in ticker symbols
    for ticker, cik in TICKER_TO_CIK.items():
        if ticker in normalized or normalized in ticker:
            return cik
    
    return ""


def lookup_by_ticker(ticker: str) -> str:
    """
    Look up CIK number by ticker symbol.
    
    Args:
        ticker: Ticker symbol (e.g., "UBER", "MGM", "EFX")
        
    Returns:
        CIK number as 10-digit string with leading zeros, or empty string if not found
    """
    normalized = ticker.upper().strip()
    return TICKER_TO_CIK.get(normalized, "")


def get_historical_name_info(company_name: str) -> dict:
    """
    Get information about historical name changes.
    
    Args:
        company_name: Company name (current or historical)
        
    Returns:
        Dictionary with historical name information, or empty dict if not found
    """
    normalized = company_name.lower().strip().replace(",", "").replace(".", "").replace("!", "")
    
    if normalized in HISTORICAL_NAMES:
        cik, current_name, change_date = HISTORICAL_NAMES[normalized]
        return {
            "cik": cik,
            "historical_name": company_name,
            "current_name": current_name,
            "name_change_date": change_date,
            "is_historical": True
        }
    
    return {}


def find_companies_in_text(text: str) -> list:
    """
    Find all company names mentioned in text and return their CIKs.
    
    Args:
        text: Text to search for company names
        
    Returns:
        List of tuples (company_name, cik) found in the text
    """
    found = []
    text_lower = text.lower()
    
    # Check each company name
    for company_name, cik in COMPANY_CIK_MAP.items():
        # Check if company name appears in text
        if company_name in text_lower:
            # Avoid duplicates
            if not any(c[1] == cik for c in found):
                found.append((company_name, cik))
    
    return found

