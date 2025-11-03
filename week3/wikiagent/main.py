"""
Main entry point for Wikipedia Agent

Run this script to ask questions and get answers from Wikipedia.
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before importing agent
env_paths = [
    Path(__file__).parent / '.env',
    Path(__file__).parent.parent / '.env',
    Path(__file__).parent.parent.parent / '.env',
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"✓ Loaded .env from: {env_path}")
        break
else:
    # If no .env found, try loading from default location (current directory)
    load_dotenv(override=True)

# Check if API key is available
if not os.getenv('OPENAI_API_KEY'):
    print("⚠️  Warning: OPENAI_API_KEY not found in environment variables")
    print("   Make sure you have set OPENAI_API_KEY in your .env file or environment")
    print("   Checked for .env in:", [str(p) for p in env_paths])
    import sys
    sys.exit(1)
else:
    print(f"✓ OPENAI_API_KEY found (length: {len(os.getenv('OPENAI_API_KEY', ''))})")

from wikipedia_agent import wikipedia_agent


async def main():
    """Main function to run the Wikipedia agent."""
    
    # Question to ask
    question = "where do capybaras live?"
    
    print("=" * 80)
    print("Wikipedia Agent")
    print("=" * 80)
    print(f"\nQuestion: {question}\n")
    print("Processing...\n")
    
    # Run the agent
    result = await wikipedia_agent.run(user_prompt=question)
    
    # Print the answer
    print("=" * 80)
    print("ANSWER:")
    print("=" * 80)
    print(result.output)
    print("=" * 80)
    
    return result.output


if __name__ == "__main__":
    answer = asyncio.run(main())
    
    # Also print just the answer for easy copying
    print("\n" + "-" * 80)
    print("ANSWER (for form):")
    print("-" * 80)
    print(answer)
    print("-" * 80)

