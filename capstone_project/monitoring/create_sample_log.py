"""Create a sample log file for demonstration."""

import json
from pathlib import Path
from datetime import datetime
from monitoring.agent_logging import save_log

# Create a sample log entry
sample_log = {
    "agent_name": "sec_cybersecurity_agent",
    "system_prompt": "You are an expert at extracting cybersecurity disclosures from SEC filings. Only use information from SEC filings.",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "tools": ["lookup_subsidiary_parent", "lookup_company_by_name", "get_company_info", "search_company_cybersecurity_disclosures"],
    "messages": [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "What was the primary attack vector used in the Change Healthcare ransomware incident?"
                }
            ],
            "timestamp": datetime.now()
        },
        {
            "kind": "assistant",
            "parts": [
                {
                    "part_kind": "text",
                    "content": "Based on SEC filings for UnitedHealth Group (parent company of Change Healthcare), the ransomware incident occurred in February 2024. Form 10-K filed February 28, 2024 disclosed the incident but did not provide specific technical details about the attack vector or vulnerability exploited."
                }
            ],
            "timestamp": datetime.now()
        }
    ],
    "usage": {
        "input_tokens": 150,
        "output_tokens": 85,
        "total_input_tokens": 150,
        "total_output_tokens": 85
    },
    "output": "Based on SEC filings for UnitedHealth Group (parent company of Change Healthcare), the ransomware incident occurred in February 2024. Form 10-K filed February 28, 2024 disclosed the incident but did not provide specific technical details about the attack vector or vulnerability exploited.",
    "user_prompt": "What was the primary attack vector used in the Change Healthcare ransomware incident?",
    "timestamp": datetime.now()
}

# Save the log
log_path = save_log(sample_log)
print(f"Created sample log: {log_path}")

