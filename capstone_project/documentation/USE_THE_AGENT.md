# Using the SEC Cybersecurity Agent

Your data is indexed! Here's how to use the agent to query it.

## Quick Start

### Option 1: Use the Jupyter Notebook (Recommended)

1. **Open the notebook:**
   ```bash
   cd capstone_project
   jupyter notebook sec_cybersecurity_agent.ipynb
   ```

2. **Run all setup cells** (Cells 1-11) to initialize the agent

3. **Ask questions** in a new cell:
   ```python
   # Example query
   result = await cybersecurity_agent.run(
       user_prompt="Summarize all cybersecurity disclosures for Equifax (CIK: 0000033185) in 2017"
   )
   
   print(result.output)
   ```

### Option 2: Use Python Script

Create a script with the agent code and run it:

```python
import asyncio
from pydantic_ai import Agent
from sec_search_tools import search_cybersecurity_disclosures
from sec_edgar_client import SECEdgarClient

# Define tools (from notebook)
def get_company_info(cik: str):
    # ... (copy from notebook)
    pass

def search_company_cybersecurity_disclosures(cik: str, query: str = "cybersecurity", years: int = 3):
    # ... (copy from notebook)
    pass

# Create agent
cybersecurity_agent = Agent(
    name='sec_cybersecurity_agent',
    instructions="...",  # Copy from notebook
    tools=[get_company_info, search_company_cybersecurity_disclosures],
    model='openai:gpt-4o-mini'
)

# Run query
async def main():
    result = await cybersecurity_agent.run(
        user_prompt="What cybersecurity incidents did Equifax disclose in 2017?"
    )
    print(result.output)

asyncio.run(main())
```

## Example Queries

### Single Company
```python
result = await cybersecurity_agent.run(
    user_prompt="Summarize all cybersecurity disclosures for Capital One (CIK: 0000927628) in 2019"
)
```

### Multiple Companies
```python
result = await cybersecurity_agent.run(
    user_prompt='''
    Compare cybersecurity disclosures between:
    - Equifax (CIK: 0000033185) in 2017
    - Capital One (CIK: 0000927628) in 2019
    '''
)
```

### Specific Incident Type
```python
result = await cybersecurity_agent.run(
    user_prompt="What ransomware incidents did UnitedHealth Group (CIK: 0000731766) disclose in 2024?"
)
```

## Indexed Companies

You have data for these companies:

- **UnitedHealth Group Inc.** (CIK: 0000731766) - 8,947 chunks
- **Target Corporation** (CIK: 0000027419) - 79 chunks  
- **Capital One Financial Corp.** (CIK: 0000927628) - 21,967 chunks
- **Equifax Inc.** (CIK: 0000033185) - 1,786 chunks
- **Marriott International Inc.** (CIK: 0001048286) - 4,750 chunks
- **MGM Resorts International** (CIK: 0000789570) - 11,491 chunks
- **SolarWinds Corporation** (CIK: 0001739942) - 11,406 chunks
- **T-Mobile US, Inc.** (CIK: 0001283699) - 30,647 chunks
- **First American Financial Corp.** (CIK: 0001472787) - 12,062 chunks
- **Altaba Inc. (formerly Yahoo! Inc.)** (CIK: 0001011006) - 4,090 chunks

## What the Agent Does

1. **Identifies the company** using `get_company_info(cik)`
2. **Searches Elasticsearch** for cybersecurity-related chunks using `search_company_cybersecurity_disclosures(cik)`
3. **Analyzes the results** and generates a structured summary with:
   - Company information
   - Security incidents
   - Risk factors
   - Security measures
   - Filing timeline

## Troubleshooting

### "Elasticsearch is not running"
```bash
docker start elasticsearch
# Or
./setup_elasticsearch.sh
```

### "No cybersecurity disclosures found"
- Check if the company is in your indexed list
- Verify the CIK is correct
- Check the date range (some companies only have data for specific years)

### "Index does not exist"
- The index should have been created automatically
- Check: `curl http://localhost:9200/sec_filings/_count`

## Next Steps

1. **Test with a known incident** (e.g., Equifax 2017)
2. **Try comparing companies** to see different disclosure patterns
3. **Ask about specific incident types** (ransomware, data breaches, etc.)
4. **Explore trends over time** for companies with multi-year data

