"""
Judge evaluation tests for SEC Cybersecurity Agent.

These tests use an LLM-based judge to evaluate agent responses from stress tests.
The judge evaluates responses based on quality criteria such as accuracy,
completeness, citation quality, and adherence to SEC-only data requirements.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any
import asyncio

# Import judge evaluator
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add eval directory to path
from judge_evaluator import (
    create_judge,
    evaluate_response,
    evaluate_stress_test_results,
    JudgeFeedback
)


@pytest.fixture
def stress_test_results() -> Dict[str, Any]:
    """Load stress test results."""
    results_path = Path(__file__).parent.parent / "stress_test_results.json"
    if not results_path.exists():
        pytest.skip(f"Stress test results not found at {results_path}. Run stress tests first.")
    with open(results_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def judge_evaluation_results() -> Dict[str, Any]:
    """Load judge evaluation results if they exist."""
    results_path = Path(__file__).parent.parent / "judge_evaluation_results.json"
    if not results_path.exists():
        pytest.skip(f"Judge evaluation results not found at {results_path}. Run judge evaluation first.")
    with open(results_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_judge_evaluates_all_responses(stress_test_results: Dict[str, Any]):
    """Test that judge can evaluate all successful stress test responses."""
    results = stress_test_results.get('results', [])
    successful = [r for r in results if r.get('status') == 'success']
    
    if not successful:
        pytest.skip("No successful stress test results to evaluate")
    
    # Evaluate first successful response as a test
    test_result = successful[0]
    
    judge = create_judge()
    feedback = await evaluate_response(
        question=test_result,
        agent_response=test_result.get('response', ''),
        judge=judge
    )
    
    # Verify feedback structure
    assert isinstance(feedback, JudgeFeedback)
    assert len(feedback.criteria) > 0
    assert 0 <= feedback.overall_score <= 1
    assert isinstance(feedback.summary, str)
    assert isinstance(feedback.strengths, list)
    assert isinstance(feedback.weaknesses, list)
    
    # Verify criteria structure
    for criterion in feedback.criteria:
        assert isinstance(criterion.criterion_description, str)
        assert isinstance(criterion.passed, bool)
        assert isinstance(criterion.judgement, str)


@pytest.mark.asyncio
async def test_judge_evaluation_completeness(judge_evaluation_results: Dict[str, Any]):
    """Test that judge evaluation covers all successful responses."""
    evaluations = judge_evaluation_results.get('evaluations', [])
    evaluated = [e for e in evaluations if e.get('status') == 'evaluated']
    
    assert len(evaluated) > 0, "No evaluations found in judge results"
    
    # Check that each evaluation has required fields
    for eval_result in evaluated:
        assert 'question_number' in eval_result
        assert 'overall_score' in eval_result
        assert 0 <= eval_result['overall_score'] <= 1
        assert 'criteria' in eval_result
        assert len(eval_result['criteria']) > 0
        assert 'summary' in eval_result
        assert 'strengths' in eval_result
        assert 'weaknesses' in eval_result


@pytest.mark.asyncio
async def test_judge_identifies_data_source_violations(stress_test_results: Dict[str, Any]):
    """Test that judge identifies when agent uses general knowledge instead of SEC filings."""
    results = stress_test_results.get('results', [])
    successful = [r for r in results if r.get('status') == 'success' and r.get('response')]
    
    if not successful:
        pytest.skip("No successful stress test results to evaluate")
    
    judge = create_judge()
    
    # Check a few responses for data source adherence
    violations_found = []
    for result in successful[:3]:  # Check first 3 responses
        feedback = await evaluate_response(
            question=result,
            agent_response=result.get('response', ''),
            judge=judge
        )
        
        # Find data source adherence criterion
        data_source_criterion = next(
            (c for c in feedback.criteria if 'data source' in c.criterion_description.lower() or 
             'sec-only' in c.criterion_description.lower() or
             'general knowledge' in c.criterion_description.lower()),
            None
        )
        
        if data_source_criterion and not data_source_criterion.passed:
            violations_found.append({
                'question': result.get('question_number'),
                'judgement': data_source_criterion.judgement
            })
    
    # This test documents violations but doesn't fail - it's informational
    if violations_found:
        print("\n⚠️  Data source violations found:")
        for v in violations_found:
            print(f"  Q{v['question']}: {v['judgement']}")


@pytest.mark.asyncio
async def test_judge_evaluates_citation_quality(stress_test_results: Dict[str, Any]):
    """Test that judge evaluates citation quality in responses."""
    results = stress_test_results.get('results', [])
    successful = [r for r in results if r.get('status') == 'success' and r.get('response')]
    
    if not successful:
        pytest.skip("No successful stress test results to evaluate")
    
    judge = create_judge()
    
    # Evaluate citation quality for a sample response
    test_result = successful[0]
    feedback = await evaluate_response(
        question=test_result,
        agent_response=test_result.get('response', ''),
        judge=judge
    )
    
    # Find citation quality criterion
    citation_criterion = next(
        (c for c in feedback.criteria if 'citation' in c.criterion_description.lower()),
        None
    )
    
    assert citation_criterion is not None, "Citation quality criterion should be evaluated"
    assert isinstance(citation_criterion.passed, bool)
    assert len(citation_criterion.judgement) > 0


@pytest.mark.asyncio
async def test_judge_evaluation_average_score(judge_evaluation_results: Dict[str, Any]):
    """Test that judge evaluation provides meaningful average scores."""
    avg_score = judge_evaluation_results.get('average_score', 0)
    criteria_pass_rate = judge_evaluation_results.get('criteria_pass_rate', 0)
    
    # Scores should be between 0 and 1
    assert 0 <= avg_score <= 1, f"Average score should be between 0 and 1, got {avg_score}"
    assert 0 <= criteria_pass_rate <= 1, f"Criteria pass rate should be between 0 and 1, got {criteria_pass_rate}"
    
    # If we have evaluations, scores should be meaningful
    evaluated = judge_evaluation_results.get('evaluated', 0)
    if evaluated > 0:
        assert avg_score > 0, "Average score should be greater than 0 if evaluations exist"
        print(f"\n✓ Average score: {avg_score:.2%}")
        print(f"✓ Criteria pass rate: {criteria_pass_rate:.2%}")


@pytest.mark.asyncio
async def test_judge_evaluation_summary_statistics(judge_evaluation_results: Dict[str, Any]):
    """Test that judge evaluation provides complete summary statistics."""
    required_fields = [
        'evaluation_timestamp',
        'total_questions',
        'evaluated',
        'skipped',
        'errors',
        'average_score',
        'criteria_pass_rate',
        'evaluations'
    ]
    
    for field in required_fields:
        assert field in judge_evaluation_results, f"Missing required field: {field}"
    
    # Verify counts are consistent
    total = judge_evaluation_results['total_questions']
    evaluated = judge_evaluation_results['evaluated']
    skipped = judge_evaluation_results['skipped']
    errors = judge_evaluation_results['errors']
    
    assert evaluated + skipped + errors <= total, "Evaluation counts should not exceed total questions"
    
    print(f"\n✓ Evaluation Statistics:")
    print(f"  Total questions: {total}")
    print(f"  Evaluated: {evaluated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")


@pytest.mark.asyncio
async def test_judge_evaluates_missing_document_handling(stress_test_results: Dict[str, Any]):
    """Test that judge evaluates how well agent handles missing documents."""
    results = stress_test_results.get('results', [])
    
    # Find questions about missing documents (questions 11-20)
    missing_doc_questions = [
        r for r in results 
        if r.get('status') == 'success' and 
        r.get('response') and
        int(r.get('question_number', 0)) >= 11
    ]
    
    if not missing_doc_questions:
        pytest.skip("No missing document handling questions found in results")
    
    judge = create_judge()
    
    # Evaluate one missing document question
    test_result = missing_doc_questions[0]
    feedback = await evaluate_response(
        question=test_result,
        agent_response=test_result.get('response', ''),
        judge=judge
    )
    
    # Find missing document handling criterion
    missing_doc_criterion = next(
        (c for c in feedback.criteria if 'missing' in c.criterion_description.lower() or
         'document' in c.criterion_description.lower()),
        None
    )
    
    if missing_doc_criterion:
        assert isinstance(missing_doc_criterion.passed, bool)
        print(f"\n✓ Missing document handling evaluated: {missing_doc_criterion.passed}")
        print(f"  {missing_doc_criterion.judgement[:100]}...")

