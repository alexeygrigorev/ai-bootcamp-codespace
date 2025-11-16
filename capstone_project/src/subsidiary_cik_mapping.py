"""
Subsidiary to Parent Company CIK Mapping.

This module provides mappings of subsidiary companies to their parent companies'
CIK numbers, including acquisition dates for temporal accuracy.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Structure: parent_CIK -> list of subsidiaries with metadata
SUBSIDIARY_MAP = {
    "0000731766": {  # UnitedHealth Group Inc.
        "parent_name": "UnitedHealth Group Inc.",
        "parent_ticker": "UNH",
        "subsidiaries": [
            {
                "legal_name": "Change Healthcare",
                "common_names": [
                    "Change Healthcare",
                    "Change Healthcare Inc.",
                    "Change Healthcare, Inc.",
                    "Change Healthcare LLC",
                ],
                "acquired_date": "2022-10-03",  # Acquisition completed October 3, 2022
                "acquired_year": 2022,
                "entity_type": "subsidiary",  # Can be "subsidiary" or "division"
                "notes": "Acquired from private equity, cybersecurity incidents appear in parent filings"
            },
            # Add more UnitedHealth subsidiaries here as needed
        ]
    },
    "0000313838": {  # Sony Group Corp.
        "parent_name": "Sony Group Corp.",
        "parent_ticker": "SONY",
        "subsidiaries": [
            {
                "legal_name": "Sony Pictures",
                "common_names": [
                    "Sony Pictures",
                    "Sony Pictures Entertainment",
                    "Sony Pictures Entertainment Inc.",
                    "Sony Pictures Inc.",
                ],
                "acquired_date": "1989-01-01",  # Long-standing division
                "acquired_year": 1989,
                "entity_type": "division",  # Operating division, not acquired subsidiary
                "notes": "Operating division of Sony Group Corp. 2014 breach was at Sony Pictures division."
            },
        ]
    },
    # Add more parent companies and their subsidiaries/divisions here
    # Example structure:
    # "0001048286": {  # Marriott International Inc.
    #     "parent_name": "Marriott International Inc.",
    #     "parent_ticker": "MAR",
    #     "subsidiaries": [
    #         {
    #             "legal_name": "Starwood Hotels & Resorts",
    #             "common_names": ["Starwood", "Starwood Hotels", "Starwood Resorts"],
    #             "acquired_date": "2016-09-23",
    #             "acquired_year": 2016,
    #             "entity_type": "subsidiary",
    #             "notes": "Acquired in 2016, breach occurred pre-acquisition"
    #         }
    #     ]
    # },
}


def find_parent_cik_for_subsidiary(
    subsidiary_name: str,
    incident_date: Optional[str] = None
) -> Optional[Tuple[str, Dict]]:
    """
    Find the parent company CIK for a given subsidiary name.
    
    Args:
        subsidiary_name: Name of the subsidiary company
        incident_date: Optional date of incident (YYYY-MM-DD format) to check if
                      subsidiary was acquired by that date. If None, assumes current date.
    
    Returns:
        Tuple of (parent_CIK, subsidiary_info) if found, None otherwise.
        subsidiary_info contains the subsidiary metadata including acquisition date.
    """
    subsidiary_name_lower = subsidiary_name.lower().strip()
    
    # Search through all parent companies
    for parent_cik, parent_info in SUBSIDIARY_MAP.items():
        for subsidiary in parent_info["subsidiaries"]:
            # Check legal name
            if subsidiary_name_lower == subsidiary["legal_name"].lower():
                # Check if incident date is after acquisition (or no date provided)
                if _is_subsidiary_active(subsidiary, incident_date):
                    return (parent_cik, subsidiary)
                continue
            
            # Check common names
            for common_name in subsidiary.get("common_names", []):
                if subsidiary_name_lower == common_name.lower():
                    if _is_subsidiary_active(subsidiary, incident_date):
                        return (parent_cik, subsidiary)
                    break
            
            # Check partial matches (subsidiary name contains or is contained in search term)
            if subsidiary_name_lower in subsidiary["legal_name"].lower() or \
               subsidiary["legal_name"].lower() in subsidiary_name_lower:
                if _is_subsidiary_active(subsidiary, incident_date):
                    return (parent_cik, subsidiary)
    
    return None


def _is_subsidiary_active(subsidiary: Dict, incident_date: Optional[str]) -> bool:
    """
    Check if subsidiary was active (acquired) by the incident date.
    
    Args:
        subsidiary: Subsidiary metadata dictionary
        incident_date: Date string in YYYY-MM-DD format, or None for current date
    
    Returns:
        True if subsidiary was acquired by the incident date (or no date provided)
    """
    if incident_date is None:
        return True  # Assume current date, so subsidiary is active
    
    try:
        incident_dt = datetime.strptime(incident_date, "%Y-%m-%d")
        acquired_dt = datetime.strptime(subsidiary["acquired_date"], "%Y-%m-%d")
        return incident_dt >= acquired_dt
    except (ValueError, KeyError):
        # If date parsing fails, assume active
        return True


def get_parent_company_info(parent_cik: str) -> Optional[Dict]:
    """
    Get parent company information from the mapping.
    
    Args:
        parent_cik: Parent company CIK
    
    Returns:
        Dictionary with parent company info, or None if not found
    """
    if parent_cik in SUBSIDIARY_MAP:
        info = SUBSIDIARY_MAP[parent_cik].copy()
        info.pop("subsidiaries", None)  # Remove subsidiaries list for cleaner output
        return info
    return None


def list_all_subsidiaries(parent_cik: Optional[str] = None) -> Dict:
    """
    List all subsidiaries, optionally filtered by parent CIK.
    
    Args:
        parent_cik: Optional parent CIK to filter by
    
    Returns:
        Dictionary mapping parent CIKs to their subsidiaries
    """
    if parent_cik:
        if parent_cik in SUBSIDIARY_MAP:
            return {parent_cik: SUBSIDIARY_MAP[parent_cik]}
        return {}
    
    return SUBSIDIARY_MAP.copy()


def add_subsidiary(
    parent_cik: str,
    legal_name: str,
    common_names: List[str],
    acquired_date: str,
    notes: str = ""
) -> bool:
    """
    Add a new subsidiary to the mapping.
    
    Args:
        parent_cik: Parent company CIK
        legal_name: Legal name of the subsidiary
        common_names: List of common name variations
        acquired_date: Acquisition date in YYYY-MM-DD format
        notes: Optional notes about the subsidiary
    
    Returns:
        True if added successfully, False if parent CIK doesn't exist
    """
    if parent_cik not in SUBSIDIARY_MAP:
        return False
    
    try:
        acquired_dt = datetime.strptime(acquired_date, "%Y-%m-%d")
        acquired_year = acquired_dt.year
    except ValueError:
        return False
    
    new_subsidiary = {
        "legal_name": legal_name,
        "common_names": common_names,
        "acquired_date": acquired_date,
        "acquired_year": acquired_year,
        "notes": notes
    }
    
    SUBSIDIARY_MAP[parent_cik]["subsidiaries"].append(new_subsidiary)
    return True


def remove_subsidiary(parent_cik: str, subsidiary_name: str) -> bool:
    """
    Remove a subsidiary from the mapping.
    
    Args:
        parent_cik: Parent company CIK
        subsidiary_name: Name of subsidiary to remove
    
    Returns:
        True if removed successfully, False otherwise
    """
    if parent_cik not in SUBSIDIARY_MAP:
        return False
    
    subsidiaries = SUBSIDIARY_MAP[parent_cik]["subsidiaries"]
    subsidiary_name_lower = subsidiary_name.lower()
    
    for i, sub in enumerate(subsidiaries):
        if sub["legal_name"].lower() == subsidiary_name_lower:
            subsidiaries.pop(i)
            return True
    
    return False


# Example usage and testing
if __name__ == "__main__":
    # Test Change Healthcare lookup
    result = find_parent_cik_for_subsidiary("Change Healthcare")
    if result:
        parent_cik, sub_info = result
        print(f"Found: Change Healthcare -> Parent CIK: {parent_cik}")
        print(f"  Parent: {SUBSIDIARY_MAP[parent_cik]['parent_name']}")
        print(f"  Acquired: {sub_info['acquired_date']}")
    
    # Test with incident date
    result = find_parent_cik_for_subsidiary("Change Healthcare", "2024-02-01")
    if result:
        print(f"\nChange Healthcare incident in 2024 -> Parent CIK: {result[0]}")
    
    # Test with pre-acquisition date
    result = find_parent_cik_for_subsidiary("Change Healthcare", "2021-01-01")
    if result:
        print(f"Change Healthcare incident in 2021 -> Parent CIK: {result[0]}")
    else:
        print(f"\nChange Healthcare incident in 2021 -> Not found (not yet acquired)")

