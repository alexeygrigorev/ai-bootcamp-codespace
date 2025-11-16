# Indexing SEC Filings for Cybersecurity Companies

This guide explains how to index SEC filings for companies with known cybersecurity incidents.

## Prerequisites

1. **Elasticsearch running** - Make sure Elasticsearch is running:
   ```bash
   ./setup_elasticsearch.sh
   # Or check status:
   python check_elasticsearch.py
   ```

2. **SEC User-Agent configured** - Create a `.env` file in `capstone_project/`:
   ```bash
   echo 'SEC_USER_AGENT="Your Name (your.email@example.com)"' > .env
   ```
   The SEC requires a valid User-Agent header. Use your real name and email.

3. **Dependencies installed** - Make sure you have all Python packages:
   ```bash
   poetry install
   ```

## Running the Indexing Script

The script `index_cybersecurity_companies.py` will:
- Fetch SEC filings for 13 companies with cybersecurity incidents
- Download 10-K, 10-Q, and 8-K forms for the relevant years
- Parse and chunk the documents
- Index them in Elasticsearch

### Quick Start

```bash
cd capstone_project
poetry run python index_cybersecurity_companies.py
```

### What It Does

1. **Fetches filings** for each company from the SEC EDGAR API
2. **Filters** to relevant form types (10-K, 10-Q, 8-K) and incident years
3. **Downloads** filing documents (cached locally in `sec_downloads/`)
4. **Parses** XML/HTML documents into structured sections
5. **Chunks** documents into 2000-character chunks with 1000-character overlap
6. **Indexes** chunks in Elasticsearch under the `sec_filings` index

### Companies Being Indexed

The script indexes filings for these companies:

- UnitedHealth Group Inc. (2024) - Ransomware
- Target Corporation (2013-2014) - Point-of-sale malware
- Capital One Financial Corp. (2019) - Cloud misconfiguration
- Equifax Inc. (2017) - Unpatched vulnerability
- Marriott International Inc. (2014-2018) - Multi-year breach
- Home Depot, Inc. (2014) - Vendor credential compromise
- MGM Resorts International (2023) - Social engineering/ransomware
- SolarWinds Corporation (2020) - Supply chain attack
- T-Mobile US, Inc. (2021-2023) - Multiple data breaches
- Uber Technologies, Inc. (2016) - Credential compromise
- Sony Group Corp. (2014) - Nation-state attack
- First American Financial Corp. (2019) - Web application vulnerability
- Altaba Inc. (formerly Yahoo! Inc.) (2013-2014) - Multiple breaches

### Expected Runtime

- **First run**: 30-60 minutes (downloads all filings)
- **Subsequent runs**: 5-10 minutes (uses cached files)

The script respects SEC API rate limits and includes delays between requests.

### Output

The script will:
- Show progress for each company
- Display statistics (filings found, chunks indexed)
- Save results to `indexing_results.json`
- Cache downloaded filings in `sec_downloads/` directory

### Verifying Index

After indexing, verify the data:

```python
from elasticsearch import Elasticsearch

es = Elasticsearch('http://localhost:9200')
count = es.count(index="sec_filings")['count']
print(f"Total chunks indexed: {count:,}")
```

Or use the check script:
```bash
python check_elasticsearch.py
```

## Using the Indexed Data

Once indexed, you can use the SEC Cybersecurity Agent to search:

```python
from sec_cybersecurity_agent import cybersecurity_agent

result = await cybersecurity_agent.run(
    user_prompt="What cybersecurity incidents did Equifax disclose in 2017?"
)
print(result.output)
```

## Troubleshooting

### "Cannot connect to Elasticsearch"
- Make sure Elasticsearch is running: `docker ps | grep elasticsearch`
- Start it: `./setup_elasticsearch.sh`

### "SEC_USER_AGENT not found"
- Create `.env` file with: `SEC_USER_AGENT="Your Name (your.email@example.com)"`

### "Download failed" errors
- Check your internet connection
- Verify the CIK is correct
- Some older filings may not be available
- The script will continue with other companies

### "No relevant filings found"
- Some companies may not have filings for the specified years
- Check if the company existed during those years
- Some companies may have merged or changed names

## Next Steps

After indexing:
1. Test the agent with a simple query
2. Try asking about specific incidents
3. Compare disclosures across companies
4. Analyze trends over time

