# Data Source Transparency Fix

## Problem

The agent was falling back to "general knowledge" when SEC filings were unavailable, without clearly indicating:
- That it's NOT using SEC filings
- What the actual data source is
- That this violates the core requirement to read SEC filings

This is dangerous because users may assume the information comes from official disclosures when it doesn't.

## Solution

### 1. Strict Data Source Requirements

Added explicit requirements to agent instructions:

```
CRITICAL DATA SOURCE REQUIREMENTS:
- YOU MUST ONLY USE INFORMATION FROM SEC FILINGS - NEVER use general knowledge, public information, or any source other than SEC filings
- If search_company_cybersecurity_disclosures returns no results or empty results, you MUST state "No cybersecurity disclosures found in SEC filings" and STOP
- NEVER supplement SEC filing data with general knowledge, even if you know the information
- NEVER say "based on general knowledge" or "based on publicly available information"
- If you cannot find information in SEC filings, the answer is "No information available in SEC filings" - do not provide alternative information
```

### 2. Mandatory Citation Requirements

All information must cite specific SEC filings:

```
CITATION REQUIREMENTS:
- ALWAYS cite specific SEC filings for EVERY piece of information you provide
- Format: "[Form Type] filed [Date]: [specific information]"
- Examples: "Form 8-K filed July 19, 2019: Capital One disclosed the breach"
- If you cannot cite a specific filing, DO NOT include that information in your response
```

### 3. Enhanced Filing Timeline

Updated Filing Timeline section to require specific citations:

```
### Filing Timeline
List ALL filings reviewed with specific dates and form types:
- [Form Type] filed [Filing Date]: [Specific disclosure or information found]
- Example: "Form 8-K filed July 19, 2019: Capital One disclosed the data breach affecting 106 million customers"
- If no filings were found, state: "No SEC filings found containing cybersecurity disclosures for this company"
```

### 4. No Results Handling

Updated the search function to clearly mark when no results are found:

```python
if not results:
    return [{"content": "No cybersecurity disclosures found in SEC filings...", "no_results": True}]
```

## Expected Behavior Changes

### Before (Problematic)
```
"Based on general knowledge of the situation that Yahoo faced, I'll summarize..."
"However, based on publicly available information about these incidents..."
```

### After (Correct)
```
"No cybersecurity disclosures found in SEC filings for this company and date range."
"If no cybersecurity disclosures are found, clearly state 'No cybersecurity disclosures found in the analyzed SEC filings'"
```

## Specific Filing Citation Examples

The agent should now cite filings like:

1. **Capital One (Question 2)**:
   - "Form 8-K filed July 19, 2019: Capital One disclosed the data breach"
   - "Form 10-Q filed [date]: Capital One reported $80 million OCC fine"

2. **T-Mobile (Question 4)**:
   - "Form 10-Q filed July 27, 2023: T-Mobile disclosed the January 2023 cyber incident"
   - "Form 10-K filed February 2, 2024: T-Mobile reported financial impacts from cybersecurity incidents"

3. **SolarWinds (Question 7)**:
   - "Form 8-K filed December 14, 2020: SolarWinds disclosed the SUNBURST attack"
   - "Form 10-K filed [date]: SolarWinds reported SEC enforcement action filed October 2023"

## Files Modified

1. **`run_stress_tests.py`**
   - Added "CRITICAL DATA SOURCE REQUIREMENTS" section
   - Added "CITATION REQUIREMENTS" section
   - Updated "Filing Timeline" section with specific citation format
   - Updated error handling to mark no_results

## Testing

After these changes, the agent should:
- ✅ Never use general knowledge
- ✅ Always cite specific SEC filings
- ✅ Clearly state when no filings are found
- ✅ Stop immediately if no SEC data is available

## Next Steps

1. **Re-run stress tests** to verify agent follows new requirements
2. **Check responses** for any "general knowledge" fallbacks
3. **Verify citations** - all information should cite specific filings
4. **Monitor** agent behavior to ensure strict adherence

