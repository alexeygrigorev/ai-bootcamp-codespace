#!/usr/bin/env python3
"""
Quick test script for the SEC Cybersecurity Agent.

This script tests the agent with a sample query to verify everything is working.
"""

import asyncio
from sec_cybersecurity_agent import cybersecurity_agent

async def test_agent():
    """Test the agent with a sample query."""
    
    print("=" * 80)
    print("Testing SEC Cybersecurity Agent")
    print("=" * 80)
    print()
    
    # Test query - ask about Equifax (known cybersecurity incident in 2017)
    test_query = "Summarize all cybersecurity disclosures for Equifax (CIK: 0000033185) in 2017"
    
    print(f"Query: {test_query}")
    print()
    print("Running agent...")
    print("-" * 80)
    
    try:
        result = await cybersecurity_agent.run(user_prompt=test_query)
        
        print()
        print("=" * 80)
        print("AGENT RESPONSE:")
        print("=" * 80)
        print(result.output)
        print()
        print("=" * 80)
        print("✓ Agent test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())

