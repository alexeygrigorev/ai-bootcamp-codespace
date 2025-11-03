"""
Judge evaluation for agent outputs.

This module loads agent run results and evaluates them using a judge LLM
to assess answer quality, relevance, and completeness.
"""

import sys
import json
import pickle
import asyncio

from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from toyaikit.pricing import CostInfo

import docs
import search_agent
from evals.eval_common import map_progress, calculate_cost


# Define evaluation criteria
class CheckName(str, Enum):
    """Types of evaluation checks."""
    instructions_follow = "instructions_follow"
    instructions_avoid = "instructions_avoid" 
    answer_relevant = "answer_relevant"
    answer_clear = "answer_clear"
    answer_match = "answer_match"
    answer_citations = "answer_citations"
    completeness = "completeness"
    tool_call_search = "tool_call_search"


CHECK_DESCRIPTIONS = {
    CheckName.instructions_follow: "The agent followed the user's instructions (in <INSTRUCTIONS>)",
    CheckName.instructions_avoid: "The agent avoided doing things it was told not to do",
    CheckName.answer_relevant: "The response directly addresses the user's question",
    CheckName.answer_clear: "The answer is clear and correct",
    CheckName.answer_match: "The ANSWER is similar to the REFERENCE",
    CheckName.answer_citations: "The response includes proper citations or sources when required",
    CheckName.completeness: "The response is complete and covers all key aspects of the request",
    CheckName.tool_call_search: "Is the search tool invoked?"
}


class EvaluationCheck(BaseModel):
    """Single evaluation check result."""
    check_name: CheckName = Field(description="The type of evaluation check")
    reasoning: str = Field(description="The reasoning behind the check result")
    check_pass: bool = Field(description="Whether the check passed (True) or failed (False)")


class EvaluationChecklist(BaseModel):
    """Complete evaluation checklist with all checks."""
    checklist: list[EvaluationCheck] = Field(description="List of all evaluation checks")
    summary: str = Field(description="Evaluation summary")


def generate_checklist_text() -> str:
    """
    Generate formatted checklist text from CHECK_DESCRIPTIONS.
    
    Returns:
        Formatted checklist string
    """
    checklist_items = []
    for check_name in CheckName:
        description = CHECK_DESCRIPTIONS[check_name]
        checklist_items.append(f"- {check_name.value}: {description}")
    return "\n".join(checklist_items)


def create_judge_instructions() -> str:
    """
    Create judge instructions with checklist.
    
    Returns:
        Complete judge instructions
    """
    return f"""
Use this checklist to evaluate the quality of an AI agent's answer (<ANSWER>) to a user question (<QUESTION>).
We also include the entire log (<LOG>) for analysis. In <REFERENCE> you will see
the file, from which the user question was generated.

For each item of the checklist, check if the condition is met. 

Checklist:

{generate_checklist_text()}

Output true/false for each check and provide a short explanation for your judgment.
""".strip()


def create_judge_agent(model: str = "gpt-5-nano") -> Agent:
    """
    Create judge agent for evaluation.
    
    Args:
        model: Model name to use for judge
        
    Returns:
        Configured Agent instance
    """
    judge_instructions = create_judge_instructions()
    
    judge = Agent(
        name="judge",
        instructions=judge_instructions,
        model=model,
        output_type=EvaluationChecklist
    )
    
    return judge


def load_eval_results(input_path: str) -> list[dict]:
    """
    Load evaluation results from pickle file.
    
    Args:
        input_path: Path to pickle file with eval results
        
    Returns:
        List of evaluation result dictionaries
    """
    with open(input_path, 'rb') as f_in:
        rows = pickle.load(f_in)
    
    return rows


def load_reference_documents() -> dict[str, str]:
    """
    Load and parse reference documents.
    
    Returns:
        Dictionary mapping filename to content
    """
    github_data = docs.read_github_data()
    parsed_data = docs.parse_data(github_data)
    file_index = {d['filename']: d['content'] for d in parsed_data}
    
    return file_index


async def evaluate_single_result(row: dict, 
                                 judge: Agent,
                                 file_index: dict[str, str],
                                 instructions: str) -> tuple[dict, any]:
    """
    Evaluate a single agent result with the judge.
    
    Args:
        row: Result row to evaluate
        judge: Judge agent
        file_index: Reference documents
        instructions: Agent instructions for context
        
    Returns:
        Tuple of (original_row, judge_output)
    """
    original_filename = row['original_question']['filename']
    reference = file_index[original_filename]
    
    user_prompt = f"""
<INSTRUCTIONS>{instructions}</INSTRUCTIONS>
<QUESTION>{row['question']}</QUESTION>
<ANSWER>{row['answer']}</ANSWER>
<REFERENCE>{reference}</REFERENCE>
<LOG>{json.dumps(row['messages'])}</LOG>
""".strip()
    
    output = await judge.run(user_prompt=user_prompt)
    return row, output


async def run_judge_evaluation(rows: list[dict],
                               judge: Agent,
                               file_index: dict[str, str],
                               instructions: str,
                               max_concurrency: int = 10) -> list[tuple]:
    """
    Run judge evaluation on all results.
    
    Args:
        rows: List of result rows to evaluate
        judge: Judge agent
        file_index: Reference documents
        instructions: Agent instructions
        max_concurrency: Maximum concurrent evaluations
        
    Returns:
        List of (original_row, judge_result) tuples
    """
    async def evaluate_row(row):
        return await evaluate_single_result(row, judge, file_index, instructions)
    
    results = await map_progress(rows, evaluate_row, max_concurrency=max_concurrency)
    
    return results


def format_judge_results(results: list[tuple]) -> pd.DataFrame:
    """
    Format judge results into a DataFrame.
    
    Args:
        results: List of (original_row, judge_result) tuples
        
    Returns:
        DataFrame with evaluation results
    """
    all_checks = []

    for original_row, result in results:
        checks = result.output.checklist
        checks_formatted = {
            'question': original_row['question']
        }
        for check in checks:
            checks_formatted[check.check_name] = check.check_pass
        all_checks.append(checks_formatted)

    df_eval = pd.DataFrame(all_checks)
    return df_eval


def calculate_metrics(df_eval: pd.DataFrame) -> pd.Series:
    """
    Calculate average scores for each check.
    
    Args:
        df_eval: DataFrame with evaluation results
        
    Returns:
        Series with average scores
    """
    # Skip the question column
    check_columns = [col for col in df_eval.columns if col != 'question']
    return df_eval[check_columns].mean()


def save_judge_results(results: list[tuple], output_path: str):
    """
    Save judge results to pickle file.
    
    Args:
        results: List of (original_row, judge_result) tuples
        output_path: Path to save results
    """
    import pickle
    from pathlib import Path
    
    # Ensure reports directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'wb') as f_out:
        pickle.dump(results, f_out)
    
    print(f"Judge results saved to: {output_path}")


async def run_complete_judge_evaluation(input_path: str,
                                       model: str = "gpt-5-nano",
                                       max_concurrency: int = 10,
                                       output_path: str = None) -> tuple[CostInfo, pd.DataFrame, pd.Series, str]:
    """
    Run complete judge evaluation pipeline.
    
    Args:
        input_path: Path to evaluation results file
        model: Judge model name
        max_concurrency: Maximum concurrent evaluations
        output_path: Path to save judge results (auto-generated if not specified)
        
    Returns:
        Tuple of (cost_info, results_df, metrics, saved_path)
    """
    # Load evaluation results
    print(f"Loading evaluation results from {input_path}...")
    rows = load_eval_results(input_path)
    print(f"Loaded {len(rows)} evaluation results")
    
    # Load reference documents
    print("Loading reference documents...")
    file_index = load_reference_documents()
    
    # Create judge
    print("Creating judge agent...")
    judge = create_judge_agent(model)
    
    # Run evaluation
    print("Running judge evaluation...")
    results = await run_judge_evaluation(
        rows,
        judge,
        file_index,
        search_agent.search_instructions,
        max_concurrency
    )
    
    # Calculate cost
    cost_info = calculate_cost(model, results)
    print(f"Total cost: ${cost_info.total_cost:.4f}")
    
    # Format results
    df_eval = format_judge_results(results)
    metrics = calculate_metrics(df_eval)
    
    # Save results
    if output_path is None:
        # Generate output path from input path
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        output_path = f"reports/eval-judge-{timestamp}.bin"
    
    save_judge_results(results, output_path)
    
    return cost_info, df_eval, metrics, output_path


def main_cli():
    """Command-line interface for running judge evaluation."""
    
    if len(sys.argv) < 2:
        print("Usage: python eval_agent_judge.py <eval_results_file.bin>")
        print("Example: python eval_agent_judge.py eval-run-2025-10-23-12-00.bin")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    cost_info, df_eval, metrics, saved_path = asyncio.run(
        run_complete_judge_evaluation(input_path)
    )
    
    print("\n=== Judge Evaluation Summary ===")
    print(f"Evaluated {len(df_eval)} results")
    print(f"Results saved: {saved_path}")
    print(f"\nInput cost: ${cost_info.input_cost:.4f}")
    print(f"Output cost: ${cost_info.output_cost:.4f}")
    print(f"Total cost: ${cost_info.total_cost:.4f}")
    
    print("\n=== Evaluation Metrics ===")
    for check_name, score in metrics.items():
        print(f"{check_name}: {score:.2%}")


if __name__ == '__main__':
    main_cli()
