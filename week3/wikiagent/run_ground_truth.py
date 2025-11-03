"""
Script to run agent on ground truth questions and collect responses
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_paths = [
    Path(__file__).parent / '.env',
    Path(__file__).parent.parent / '.env',
    Path(__file__).parent.parent.parent / '.env',
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break
else:
    load_dotenv(override=True)

from wikipedia_agent import wikipedia_agent


QUESTIONS = [
    "where do capybaras live?",
    "what is the capital of Estonia?",
    "when was the first computer invented?",
    "who wrote Pride and Prejudice?",
    "what is the population of Tokyo?",
    "what are the main ingredients in pizza?",
    "when did World War II end?",
    "what is the largest planet in our solar system?",
    "who discovered penicillin?",
    "what is the speed of light?"
]


async def run_ground_truth_evaluation():
    """Run agent on all ground truth questions and collect responses"""
    print("=" * 80)
    print("GROUND TRUTH EVALUATION")
    print("=" * 80)
    print()
    
    results = []
    
    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'='*80}")
        print(f"QUESTION {i}/{len(QUESTIONS)}: {question}")
        print(f"{'='*80}\n")
        
        try:
            result = await wikipedia_agent.run(user_prompt=question)
            
            response = {
                'question': question,
                'answer': result.output,
                'status': 'success'
            }
            
            print(f"ANSWER:\n{result.output}\n")
            
        except Exception as e:
            response = {
                'question': question,
                'answer': f"ERROR: {str(e)}",
                'status': 'error'
            }
            print(f"ERROR: {str(e)}\n")
        
        results.append(response)
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(1)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total questions: {len(QUESTIONS)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Errors: {sum(1 for r in results if r['status'] == 'error')}")
    print()
    
    return results


if __name__ == "__main__":
    results = asyncio.run(run_ground_truth_evaluation())

