# Question 3 Answer: Agent Creation and Prompt Refinement

## Final Prompt

After iterative testing and refinement with the agent, here is the final prompt I arrived at:

```
You are an expert SEC filing analyst specializing in cybersecurity disclosures for supply chain risk assessment.

Your primary function is to analyze SEC filings and extract all cybersecurity-related information for a given company.

WORKFLOW - When given a CIK number, you MUST follow these steps:
1. Call get_company_info(cik) FIRST to identify the company
2. Call search_company_cybersecurity_disclosures(cik) to retrieve all cybersecurity-related chunks from SEC filings
3. Analyze the retrieved chunks systematically
4. Generate a comprehensive summary following the structure below

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
List the filings reviewed with dates:
- [Form Type] - [Filing Date]: Brief note on what was disclosed

IMPORTANT GUIDELINES:
- Always use the tools - never provide information without first calling get_company_info and search_company_cybersecurity_disclosures
- If no cybersecurity disclosures are found, clearly state "No cybersecurity disclosures found in the analyzed filings"
- Cite specific filing dates and form types for all information
- Use professional, clear language appropriate for supply chain and procurement professionals
- Group similar information together rather than listing every chunk separately
- Highlight trends or changes in disclosure patterns over time
- If disclosures mention vendors, suppliers, or third parties, note this clearly
```

## Iterative Refinement Process

### Version 1 (Initial Prompt)
Started with a basic prompt explaining the agent's role and listing general steps.

**Issues Observed:**
- Agent sometimes skipped tool calls
- Summary structure was inconsistent
- Missing emphasis on tool usage requirements

### Version 2 (After First Test)
Added stronger emphasis on MUST use tools and more detailed summary structure.

**Issues Observed:**
- Agent still occasionally tried to answer without sufficient data
- Needed more structure around how to handle empty results
- Needed guidance on grouping and synthesis

### Version 3 (Final Version - Current)
Key improvements:
- Explicit workflow steps with "MUST" in all caps for emphasis
- Detailed REQUIRED SUMMARY STRUCTURE with subsections
- Specific guidelines for handling edge cases (no disclosures found)
- Emphasis on citation and filing references
- Guidance on grouping similar information
- Note about vendors/third parties (important for supply chain context)

## Key Prompt Design Decisions

1. **Explicit Workflow**: Used numbered steps with "MUST" to ensure tool calls happen
2. **Structured Output**: Provided a detailed template so summaries are consistent
3. **Supply Chain Context**: Included language about vendors and third parties relevant to the use case
4. **Professional Tone**: Specified language appropriate for supply chain professionals
5. **Error Handling**: Included explicit instruction for handling "no disclosures found" cases
6. **Citation Requirements**: Emphasized citing specific filing dates and form types

## Summary

The final prompt emphasizes:
1. **Mandatory tool usage** - Uses "MUST" to ensure tools are always called
2. **Structured output** - Detailed template ensures consistent summaries
3. **Supply chain context** - Notes vendors/third parties for target audience
4. **Error handling** - Explicit instructions for edge cases
5. **Citation requirements** - Ensures traceability to source filings

**Framework**: Pydantic AI with GPT-4o-mini  
**Tools**: `get_company_info()` and `search_company_cybersecurity_disclosures()`

The iterative refinement process showed that the agent needed explicit structure and mandatory directives to consistently use tools and produce well-formatted summaries suitable for supply chain professionals.

