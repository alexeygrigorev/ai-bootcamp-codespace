# SEC EDGAR API Client

A Python client for accessing SEC EDGAR filings data via the SEC's public API.

## Files

- `sec_edgar_client.py` - Main client library for accessing SEC EDGAR API
- `sec_edgar_example.ipynb` - Jupyter notebook with examples and usage
- `.env.example` - Template for environment configuration

## Setup

### 1. Configure User-Agent

Create a `.env` file in the project root (or in `capstone_project/`) with your SEC User-Agent:

```bash
# In project root or capstone_project folder
echo 'SEC_USER_AGENT="Your Name (your.email@example.com)"' > .env
```

Or manually edit `.env`:
```
SEC_USER_AGENT="Your Name (your.email@example.com)"
```

The client will automatically load this from your `.env` file!

## Features

- Fetch all SEC filings for a given CIK (Central Index Key) number
- Filter filings by date range (default: last 3 years)
- Get company information (name, ticker, SIC code, etc.)
- Download individual filing documents
- Automatic rate limiting and respectful API usage

## Usage

### Basic Example

```python
from sec_edgar_client import SECEdgarClient

# Initialize the client - will automatically read from .env file
# Or pass user_agent parameter to override
client = SECEdgarClient()

# Fetch filings for Apple Inc. (CIK: 320193)
filings = client.fetch_filings("320193", years=3)

for filing in filings[:5]:
    print(f"{filing['filing_date']}: {filing['form']}")
```

### Get Company Information

```python
company_info = client.get_company_info("320193")
print(company_info)
# Output: {'name': 'Apple Inc.', 'tickers': ['AAPL'], ...}
```

### Download a Filing Document

```python
# Assuming you have a filing with accession_number and primary_document
doc_path = client.download_filing_document(
    accession_number="0000320193-24-000001",
    primary_document="aapl-10k_20220930.htm",
    cik="320193",
    output_dir="downloads"
)
```

## Important Notes

1. **User-Agent Header**: The SEC requires a valid User-Agent header. Set it in your `.env` file as `SEC_USER_AGENT`, or pass it as a parameter to `SECEdgarClient()`.

2. **Rate Limits**: The SEC tracks API usage. Be respectful of their systems:
   - Don't make excessive requests
   - Use sleep delays when fetching historical data
   - The client includes automatic rate limiting

3. **Timeout**: All requests include a 30-second timeout to prevent hanging

## Documentation References

- [SEC EDGAR API Documentation](https://www.sec.gov/edgar/sec-api-documentation)
- [SEC EDGAR Search Tools](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC API Token Management](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/create-manage-filer-user-api-tokens)
- [SEC EDGAR Data Site](https://data.sec.gov/)

## API Endpoints Used

- **Submissions API**: `https://data.sec.gov/submissions/CIK{10-digit-cik}.json`
- **Filing Documents**: `https://data.sec.gov/files/edgar/data/{cik}/{accession-number}/{document-name}`

## Example CIKs

- Apple Inc.: 320193
- Microsoft Corp: 789019
- Amazon.com Inc: 1018724
- Alphabet Inc: 1652044
- Meta Platforms Inc: 1326801

## Running the Examples

1. Set up your `.env` file with `SEC_USER_AGENT` (see Setup section above)
2. Open `sec_edgar_example.ipynb` in Jupyter
3. Run the cells to see examples of fetching and analyzing SEC filings

## Running as a Script

```bash
python sec_edgar_client.py
```

This will run a demonstration fetching Apple Inc.'s filings for the last 3 years.

