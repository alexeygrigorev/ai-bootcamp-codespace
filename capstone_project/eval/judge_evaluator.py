"""
LLM-based Judge Evaluator for SEC Cybersecurity Agent.

This module provides a judge agent that evaluates agent responses based on
quality criteria such as accuracy, completeness, citation quality, and adherence
to SEC-only data requirements.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Try capstone_project/.env first, then root .env
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, will use environment variables


class JudgeCriterion(BaseModel):
    """A single evaluation criterion with pass/fail status."""
    criterion_description: str = Field(description="Description of what is being evaluated")
    passed: bool = Field(description="Whether the criterion passed")
    judgement: str = Field(description="Explanation of the judgment")
    score: Optional[float] = Field(default=None, description="Optional score from 0-1")


class JudgeFeedback(BaseModel):
    """Complete judge feedback for an agent response."""
    criteria: List[JudgeCriterion] = Field(description="List of evaluation criteria")
    overall_score: float = Field(description="Overall score from 0-1")
    summary: str = Field(description="Summary of the evaluation")
    strengths: List[str] = Field(description="List of strengths identified")
    weaknesses: List[str] = Field(description="List of weaknesses identified")


JUDGE_INSTRUCTIONS = """
You are an expert judge evaluating the performance of a SEC Cybersecurity Disclosure Agent.

The agent's purpose is to extract and analyze cybersecurity disclosures from SEC filings
for supply chain risk assessment. The agent must ONLY use information from SEC filings
and must clearly identify when information is missing.

Evaluate agent responses based on the following criteria:

1. **Data Source Adherence**: Does the response ONLY use information from SEC filings?
   - Should NOT use general knowledge or external sources
   - Should clearly state when information is not available in SEC filings
   - Should NOT contain phrases like "based on general knowledge" or "publicly available information"

2. **Citation Quality**: Are all claims properly cited with specific SEC filings?
   - Should cite form types (8-K, 10-K, 10-Q) and filing dates
   - Should provide specific filing information for each piece of information
   - Format: "Form 8-K filed [date]: [information]"

3. **Information Accuracy**: Is the information extracted correctly from SEC filings?
   - Company names, CIKs, and dates should be accurate
   - Subsidiaries should be correctly mapped to parent companies
   - Historical names should be correctly handled (e.g., Yahoo → Altaba)

4. **Completeness**: Does the response address all aspects of the question?
   - Should extract key facts as requested
   - Should provide non-technical summaries when requested
   - Should include risk assessments when requested
   - Should identify missing information when applicable

5. **Missing Document Handling**: When expected filings are not available, does the agent:
   - Clearly identify what information is missing
   - Explain why it might be unavailable
   - Provide assessment based on available information
   - Recommend alternative sources

6. **Response Structure**: Is the response well-organized and professional?
   - Should have clear sections (Company Information, Cybersecurity Disclosures, etc.)
   - Should be appropriate for the target audience (executives, CFOs, etc.)
   - Should be clear and actionable

7. **Entity Resolution**: Are companies correctly identified?
   - CIKs should match the companies mentioned
   - Subsidiaries should be mapped to correct parent companies
   - Ticker symbols and historical names should be correctly resolved

Provide detailed feedback on each criterion, assign scores, and give an overall assessment.
"""


def create_judge(model: str = "openai:gpt-4o-mini") -> Agent:
    """
    Create a judge agent for evaluating agent responses.
    
    Args:
        model: Model to use for the judge (default: gpt-4o-mini)
        
    Returns:
        Configured judge Agent
    """
    judge = Agent(
        name="sec_cybersecurity_judge",
        instructions=JUDGE_INSTRUCTIONS,
        model=model,
        output_type=JudgeFeedback
    )
    return judge


async def evaluate_response(
    question: Dict[str, str],
    agent_response: str,
    judge: Optional[Agent] = None
) -> JudgeFeedback:
    """
    Evaluate a single agent response using the judge.
    
    Args:
        question: Dictionary containing question details (question_text, primary_focus, etc.)
        agent_response: The agent's response text
        judge: Optional judge agent (will create one if not provided)
        
    Returns:
        JudgeFeedback with evaluation results
    """
    if judge is None:
        judge = create_judge()
    
    # Build evaluation prompt
    evaluation_prompt = f"""
Evaluate the agent's response to the following question:

**Question**: {question.get('question_text', '')}
**Primary Focus**: {question.get('primary_focus', '')}
**Difficulty Level**: {question.get('difficulty_level', '')}
**Companies Involved**: {question.get('companies_involved', '')}

**Agent Response**:
{agent_response}

Evaluate this response based on the criteria in your instructions:
1. Data Source Adherence (SEC-only data)
2. Citation Quality (proper SEC filing citations)
3. Information Accuracy (correct extraction from filings)
4. Completeness (addresses all aspects of question)
5. Missing Document Handling (identifies gaps appropriately)
6. Response Structure (well-organized, professional)
7. Entity Resolution (correct company identification)

Provide detailed feedback for each criterion with pass/fail status, scores, and explanations.
"""
    
    result = await judge.run(user_prompt=evaluation_prompt)
    return result.output


async def evaluate_stress_test_results(
    results_file: Optional[Path] = None,
    judge: Optional[Agent] = None
) -> Dict[str, Any]:
    """
    Evaluate all stress test results using the judge.
    
    Args:
        results_file: Path to stress_test_results.json (defaults to eval/stress_test_results.json)
        judge: Optional judge agent (will create one if not provided)
        
    Returns:
        Dictionary with evaluation results for all questions
    """
    if results_file is None:
        results_file = Path(__file__).parent / "stress_test_results.json"
    
    if not results_file.exists():
        raise FileNotFoundError(f"Stress test results not found: {results_file}")
    
    with open(results_file, 'r', encoding='utf-8') as f:
        stress_test_data = json.load(f)
    
    if judge is None:
        judge = create_judge()
    
    results = stress_test_data.get('results', [])
    evaluations = []
    
    print(f"Evaluating {len(results)} agent responses with judge...")
    
    for i, result in enumerate(results, 1):
        if result.get('status') != 'success':
            print(f"[{i}/{len(results)}] Skipping failed response: {result.get('error', 'Unknown error')}")
            evaluations.append({
                'question_number': result.get('question_number'),
                'status': 'skipped',
                'reason': 'Agent response failed'
            })
            continue
        
        print(f"[{i}/{len(results)}] Evaluating Question {result.get('question_number')}: {result.get('primary_focus', '')}")
        
        try:
            feedback = await evaluate_response(
                question=result,
                agent_response=result.get('response', ''),
                judge=judge
            )
            
            evaluations.append({
                'question_number': result.get('question_number'),
                'primary_focus': result.get('primary_focus'),
                'overall_score': feedback.overall_score,
                'criteria': [
                    {
                        'description': c.criterion_description,
                        'passed': c.passed,
                        'score': c.score,
                        'judgement': c.judgement
                    }
                    for c in feedback.criteria
                ],
                'summary': feedback.summary,
                'strengths': feedback.strengths,
                'weaknesses': feedback.weaknesses,
                'status': 'evaluated'
            })
        except Exception as e:
            print(f"  ⚠️  Error evaluating: {e}")
            evaluations.append({
                'question_number': result.get('question_number'),
                'status': 'error',
                'error': str(e)
            })
    
    # Calculate summary statistics
    evaluated = [e for e in evaluations if e.get('status') == 'evaluated']
    if evaluated:
        avg_score = sum(e['overall_score'] for e in evaluated) / len(evaluated)
        passed_criteria = sum(
            sum(1 for c in e.get('criteria', []) if c.get('passed', False))
            for e in evaluated
        )
        total_criteria = sum(
            len(e.get('criteria', []))
            for e in evaluated
        )
        criteria_pass_rate = passed_criteria / total_criteria if total_criteria > 0 else 0
    else:
        avg_score = 0
        criteria_pass_rate = 0
    
    return {
        'evaluation_timestamp': stress_test_data.get('test_run_timestamp'),
        'total_questions': len(results),
        'evaluated': len(evaluated),
        'skipped': len([e for e in evaluations if e.get('status') == 'skipped']),
        'errors': len([e for e in evaluations if e.get('status') == 'error']),
        'average_score': avg_score,
        'criteria_pass_rate': criteria_pass_rate,
        'evaluations': evaluations
    }


async def main():
    """Main function to run judge evaluation on stress test results."""
    import asyncio
    
    print("="*80)
    print("SEC Cybersecurity Agent - Judge Evaluation")
    print("="*80)
    print()
    
    results_file = Path(__file__).parent / "stress_test_results.json"
    
    if not results_file.exists():
        print(f"❌ Error: {results_file} not found")
        print("   Please run stress tests first: poetry run python src/run_stress_tests.py")
        return
    
    print(f"Loading stress test results from: {results_file}")
    print()
    
    evaluation_results = await evaluate_stress_test_results(results_file)
    
    # Save results
    output_file = Path(__file__).parent / "judge_evaluation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*80)
    print("JUDGE EVALUATION SUMMARY")
    print("="*80)
    print(f"Total questions: {evaluation_results['total_questions']}")
    print(f"Evaluated: {evaluation_results['evaluated']}")
    print(f"Skipped: {evaluation_results['skipped']}")
    print(f"Errors: {evaluation_results['errors']}")
    print(f"Average Score: {evaluation_results['average_score']:.2%}")
    print(f"Criteria Pass Rate: {evaluation_results['criteria_pass_rate']:.2%}")
    print()
    print(f"✓ Results saved to: {output_file}")
    print("="*80)
    
    # Print per-question scores
    print("\nPer-question scores:")
    for eval_result in evaluation_results['evaluations']:
        if eval_result.get('status') == 'evaluated':
            score = eval_result.get('overall_score', 0)
            q_num = eval_result.get('question_number', '?')
            focus = eval_result.get('primary_focus', '')
            print(f"  Q{q_num} ({focus}): {score:.2%}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

