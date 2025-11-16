"""
Test script for the capybara guardrail

Tests both valid (capybara) and invalid (non-capybara) questions.
"""

import os
import sys
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
    load_dotenv(override=True)

# Check if API key is available
if not os.getenv('OPENAI_API_KEY'):
    print("⚠️  Warning: OPENAI_API_KEY not found in environment variables")
    import sys
    sys.exit(1)
else:
    print(f"✓ OPENAI_API_KEY found\n")

# Add parent directory to path to import from wikiagent
sys.path.insert(0, str(Path(__file__).parent.parent))

from wikipedia_agent import wikipedia_agent, capybara_guardrail
from logs.agent_logging import log_run, save_log


async def test_guardrail_function():
    """Test the guardrail function directly."""
    print("=" * 80)
    print("TESTING GUARDRAIL FUNCTION DIRECTLY")
    print("=" * 80)
    
    # Test 1: Valid capybara question
    test1 = "where do capybaras live?"
    result1 = capybara_guardrail(test1)
    print(f"\nTest 1 - Valid question: '{test1}'")
    print(f"  Result: fail={result1.fail}, reasoning={result1.reasoning}")
    assert result1.fail == False, "Should pass for capybara question"
    print("  ✓ PASSED")
    
    # Test 2: Invalid non-capybara question
    test2 = "what is the capital of France?"
    result2 = capybara_guardrail(test2)
    print(f"\nTest 2 - Invalid question: '{test2}'")
    print(f"  Result: fail={result2.fail}, reasoning={result2.reasoning}")
    assert result2.fail == True, "Should fail for non-capybara question"
    print("  ✓ PASSED")
    
    # Test 3: Question with capybara keyword
    test3 = "tell me about hydrochoerus"
    result3 = capybara_guardrail(test3)
    print(f"\nTest 3 - Valid question (scientific name): '{test3}'")
    print(f"  Result: fail={result3.fail}, reasoning={result3.reasoning}")
    assert result3.fail == False, "Should pass for hydrochoerus"
    print("  ✓ PASSED")
    
    print("\n" + "=" * 80)
    print("All guardrail function tests passed!")
    print("=" * 80 + "\n")


async def test_agent_with_valid_question():
    """Test agent with a valid capybara question."""
    print("=" * 80)
    print("TEST 1: AGENT WITH VALID CAPYBARA QUESTION")
    print("=" * 80)
    
    question = "where do capybaras live?"
    print(f"\nQuestion: {question}\n")
    print("Running agent...\n")
    
    try:
        result = await wikipedia_agent.run(user_prompt=question)
        
        # Log the interaction
        log_entry = log_run(agent=wikipedia_agent, result=result)
        log_filepath = save_log(log_entry)
        
        print("=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(result.output)
        print("=" * 80)
        print(f"\n✓ Log saved to: {log_filepath}")
        
        # Check if guardrail was called (should be in messages)
        messages = log_entry.get("messages", [])
        guardrail_called = False
        for msg in messages:
            if isinstance(msg, dict):
                parts = msg.get("parts", [])
                for part in parts:
                    if isinstance(part, dict) and part.get("tool_name") == "capybara_guardrail":
                        guardrail_called = True
                        print(f"✓ Guardrail was called: {part.get('args', 'N/A')}")
        
        if guardrail_called:
            print("✓ Guardrail was properly called by the agent")
        else:
            print("⚠️  Warning: Guardrail may not have been called")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_agent_with_invalid_question():
    """Test agent with an invalid non-capybara question."""
    print("\n" + "=" * 80)
    print("TEST 2: AGENT WITH INVALID NON-CAPYBARA QUESTION")
    print("=" * 80)
    
    question = "what is the capital of France?"
    print(f"\nQuestion: {question}\n")
    print("Running agent (should stop due to guardrail)...\n")
    
    try:
        result = await wikipedia_agent.run(user_prompt=question)
        
        # Log the interaction
        log_entry = log_run(agent=wikipedia_agent, result=result)
        log_filepath = save_log(log_entry)
        
        print("=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(result.output)
        print("=" * 80)
        print(f"\n✓ Log saved to: {log_filepath}")
        
        # Check if guardrail was called and if agent stopped
        messages = log_entry.get("messages", [])
        guardrail_called = False
        guardrail_failed = False
        
        for msg in messages:
            if isinstance(msg, dict):
                parts = msg.get("parts", [])
                for part in parts:
                    if isinstance(part, dict) and part.get("tool_name") == "capybara_guardrail":
                        guardrail_called = True
                        # Check tool result to see if it failed
                        # This would be in a subsequent message
                        print(f"✓ Guardrail was called: {part.get('args', 'N/A')}")
        
        # Check if output indicates guardrail stopped execution
        output_lower = result.output.lower()
        if "capybara" in output_lower and ("only" in output_lower or "not" in output_lower):
            guardrail_failed = True
            print("✓ Agent correctly stopped and informed user about capybara-only policy")
        else:
            print("⚠️  Warning: Agent may not have stopped properly")
        
        return guardrail_called and guardrail_failed
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def main():
    """Run all guardrail tests."""
    print("\n" + "=" * 80)
    print("GUARDRAIL TESTING SUITE")
    print("=" * 80 + "\n")
    
    # Test 1: Guardrail function directly
    await test_guardrail_function()
    
    # Test 2: Agent with valid question
    test1_passed = await test_agent_with_valid_question()
    
    # Test 3: Agent with invalid question
    test2_passed = await test_agent_with_invalid_question()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Guardrail function tests: ✓ PASSED")
    print(f"Agent with valid question: {'✓ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Agent with invalid question: {'✓ PASSED' if test2_passed else '❌ FAILED'}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

