# Subsidiary to Parent Company CIK Mapping

## Overview

This system maps subsidiary companies to their parent companies' CIK numbers, ensuring that cybersecurity incidents for subsidiaries are correctly found in parent company SEC filings.

## Problem Solved

**Issue**: Change Healthcare is a subsidiary of UnitedHealth Group (acquired October 2022). Cybersecurity incidents for Change Healthcare appear in UnitedHealth Group's SEC filings (CIK: 0000731766), not under a separate Change Healthcare CIK.

**Solution**: The agent now checks if a company is a subsidiary before looking up its CIK, and uses the parent company's CIK for all searches.

## Architecture

### Files

1. **`subsidiary_cik_mapping.py`** - Core mapping module with:
   - `SUBSIDIARY_MAP` - Dictionary structure mapping parent CIKs to subsidiaries
   - `find_parent_cik_for_subsidiary()` - Main lookup function
   - `add_subsidiary()` - Function to add new subsidiaries
   - `remove_subsidiary()` - Function to remove subsidiaries

2. **`run_stress_tests.py`** - Updated agent with:
   - `lookup_subsidiary_parent()` - Agent tool for subsidiary lookup
   - Updated workflow to check subsidiaries first

### Data Structure

```python
SUBSIDIARY_MAP = {
    "0000731766": {  # Parent CIK
        "parent_name": "UnitedHealth Group Inc.",
        "parent_ticker": "UNH",
        "subsidiaries": [
            {
                "legal_name": "Change Healthcare",
                "common_names": ["Change Healthcare", "Change Healthcare Inc.", ...],
                "acquired_date": "2022-10-03",
                "acquired_year": 2022,
                "notes": "Acquisition details..."
            }
        ]
    }
}
```

## Usage

### Adding a New Subsidiary

```python
from subsidiary_cik_mapping import add_subsidiary

add_subsidiary(
    parent_cik="0000731766",  # UnitedHealth Group
    legal_name="New Subsidiary Inc.",
    common_names=["New Subsidiary", "New Subsidiary Inc.", "NSI"],
    acquired_date="2023-01-15",
    notes="Acquired in 2023"
)
```

### Removing a Subsidiary

```python
from subsidiary_cik_mapping import remove_subsidiary

remove_subsidiary(
    parent_cik="0000731766",
    subsidiary_name="Change Healthcare"
)
```

### Looking Up a Subsidiary

```python
from subsidiary_cik_mapping import find_parent_cik_for_subsidiary

# Basic lookup
result = find_parent_cik_for_subsidiary("Change Healthcare")
if result:
    parent_cik, sub_info = result
    print(f"Parent CIK: {parent_cik}")

# With incident date (only returns if subsidiary was acquired by that date)
result = find_parent_cik_for_subsidiary("Change Healthcare", "2024-02-01")
# Returns parent CIK because Change Healthcare was acquired in 2022

result = find_parent_cik_for_subsidiary("Change Healthcare", "2021-01-01")
# Returns None because Change Healthcare wasn't acquired until 2022
```

## Agent Integration

The agent now follows this workflow:

1. **Question mentions "Change Healthcare"**
2. Agent calls `lookup_subsidiary_parent("Change Healthcare")`
3. Returns: `{is_subsidiary: True, parent_cik: "0000731766", parent_name: "UnitedHealth Group Inc."}`
4. Agent uses parent CIK `0000731766` for all searches
5. Agent searches UnitedHealth Group's SEC filings for Change Healthcare incidents

## Current Mappings

### UnitedHealth Group Inc. (CIK: 0000731766)

- **Change Healthcare**
  - Acquired: October 3, 2022
  - Common names: "Change Healthcare", "Change Healthcare Inc.", "Change Healthcare, Inc.", "Change Healthcare LLC"
  - Notes: Cybersecurity incidents appear in parent filings

## Adding More Subsidiaries

To add more subsidiaries, edit `subsidiary_cik_mapping.py` and add entries to `SUBSIDIARY_MAP`:

```python
SUBSIDIARY_MAP = {
    "0000731766": {  # UnitedHealth Group
        # ... existing subsidiaries ...
    },
    "0001048286": {  # Marriott International Inc.
        "parent_name": "Marriott International Inc.",
        "parent_ticker": "MAR",
        "subsidiaries": [
            {
                "legal_name": "Starwood Hotels & Resorts",
                "common_names": ["Starwood", "Starwood Hotels", "Starwood Resorts"],
                "acquired_date": "2016-09-23",
                "acquired_year": 2016,
                "notes": "Acquired in 2016, breach occurred pre-acquisition"
            }
        ]
    }
}
```

## Date-Based Logic

The system includes date-based logic to handle acquisitions:

- **If incident_date is provided**: Only returns parent CIK if subsidiary was acquired by that date
- **If incident_date is None**: Assumes current date, so returns parent CIK if subsidiary exists

This ensures that:
- Pre-acquisition incidents aren't incorrectly mapped to parent
- Post-acquisition incidents are correctly mapped to parent

## Testing

Run the test script:

```bash
poetry run python subsidiary_cik_mapping.py
```

This will test:
- Change Healthcare lookup
- Date-based filtering (2024 vs 2021 incidents)
- Parent company info retrieval

## Benefits

1. **Accurate CIK Lookup**: Subsidiaries are correctly mapped to parent companies
2. **Temporal Accuracy**: Date-based logic ensures correct mapping based on acquisition dates
3. **Easy Maintenance**: Simple functions to add/remove subsidiaries
4. **Flexible**: Supports multiple name variations for each subsidiary
5. **Agent Integration**: Seamlessly integrated into agent workflow

