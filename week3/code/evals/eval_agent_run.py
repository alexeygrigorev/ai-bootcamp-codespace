"""
Agent evaluation runner.

This module runs the search agent against a ground truth dataset and saves
the results for later analysis by the judge.
"""

import pickle
import traceback

from datetime import datetime
from typing import Optional

import pandas as pd
from toyaikit.pricing import CostInfo

from evals.eval_common import map_progress, calculate_cost, simplify_messages

import main


def load_ground_truth(csv_path: str = "./ground_truth_evidently.csv") -> list[dict]:
    """
    Load ground truth data from CSV file.
    
    Args:
        csv_path: Path to the ground truth CSV file
        
    Returns:
        List of ground truth records as dictionaries
    """
    df_ground_truth = pd.read_csv(csv_path)
    return df_ground_truth.to_dict(orient="records")
async def run_agent_on_question(question_record: dict, agent):
    """
    Run the agent on a single question.

    Args:
        question_record: Dictionary containing the question
        agent: The agent to run

    Returns:
        Tuple of (question_record, result) or (None, None) on error
    """
    try:
        result = await agent.run(question_record["question"])
        return (question_record, result)
    except Exception as e:
        print(f"Error processing {question_record}: {e}")
        traceback.print_exc()
        return (None, None)


async def run_evaluation(
    ground_truth: list[dict], agent, max_concurrency: int = 10
) -> list[tuple]:
    """
    Run evaluation on all ground truth questions.

    Args:
        ground_truth: List of ground truth records
        agent: The agent to evaluate
        max_concurrency: Maximum concurrent agent runs

    Returns:
        List of (question, result) tuples
    """

    async def run_on_question(q):
        return await run_agent_on_question(q, agent)

    all_results = await map_progress(
        ground_truth, run_on_question, max_concurrency=max_concurrency
    )

    return all_results


def prepare_results_for_judge(all_results: list[tuple]) -> list[dict]:
    """
    Prepare evaluation results for judge analysis.

    Args:
        all_results: List of (question, result) tuples

    Returns:
        List of row dictionaries containing questions, answers, and metadata
    """
    rows = []

    for q, r in all_results:
        if q is None or r is None:
            continue

        usage = r.usage()
        row = {
            "question": q["question"],
            "answer": r.output.format_article(),
            "messages": simplify_messages(r.new_messages()),
            "tool_call_number": usage.tool_calls,
            "requests": usage.requests,
            "original_question": q,
            "original_result": r,
        }
        rows.append(row)

    return rows


def save_results(rows: list[dict], output_path: Optional[str] = None) -> str:
    """
    Save evaluation results to a pickle file.

    Args:
        rows: List of result dictionaries
        output_path: Path to save file (None = auto-generate)

    Returns:
        Path to the saved file
    """
    if output_path is None:
        from pathlib import Path
        
        # Create reports directory if it doesn't exist
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        output_path = f"reports/eval-run-{timestamp}.bin"

    with open(output_path, "wb") as f_out:
        pickle.dump(rows, f_out)

    return output_path


async def run_agent_evaluation(
    csv_path: str = "./ground_truth_evidently.csv",
    max_concurrency: int = 10,
    model: str = "gpt-4o-mini",
    output_path: Optional[str] = None,
) -> tuple[str, CostInfo, pd.DataFrame]:
    """
    Run complete agent evaluation pipeline.
    
    Args:
        csv_path: Path to ground truth CSV (can be full set or pre-sampled)
        max_concurrency: Max concurrent runs
        model: Model name for cost calculation
        output_path: Output file path
        
    Returns:
        Tuple of (output_path, cost_info, results_df)
    """
    # Load ground truth
    ground_truth = load_ground_truth(csv_path=csv_path)
    print(f"Loaded {len(ground_truth)} ground truth questions")

    # Get agent
    agent = main.agent

    # Run evaluation
    print("Running agent evaluation...")
    all_results = await run_evaluation(ground_truth, agent, max_concurrency)

    # Calculate cost
    valid_results = [(q, r) for q, r in all_results if q is not None and r is not None]
    cost_info = calculate_cost(model, valid_results)
    print(f"Total cost: ${cost_info.total_cost:.4f}")

    # Prepare results
    rows = prepare_results_for_judge(all_results)
    df_run = pd.DataFrame(rows)

    # Save results
    saved_path = save_results(rows, output_path)
    print(f"Results saved to {saved_path}")

    return saved_path, cost_info, df_run


def main_cli():
    """Command-line interface for running agent evaluation."""
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(
        description='Run agent evaluation on ground truth dataset'
    )
    parser.add_argument(
        '--csv',
        default='./ground_truth_evidently.csv',
        help='Path to ground truth CSV file (can be pre-sampled)'
    )
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='Model to use for the agent'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=10,
        help='Maximum concurrent operations'
    )
    parser.add_argument(
        '--output',
        help='Output path for results (auto-generated if not specified)'
    )

    args = parser.parse_args()

    saved_path, cost_info, df_run = asyncio.run(
        run_agent_evaluation(
            csv_path=args.csv,
            max_concurrency=args.concurrency,
            model=args.model,
            output_path=args.output
        )
    )

    print("\n=== Evaluation Summary ===")
    print(f"Total questions: {len(df_run)}")
    print(f"Input cost: ${cost_info.input_cost:.4f}")
    print(f"Output cost: ${cost_info.output_cost:.4f}")
    print(f"Total cost: ${cost_info.total_cost:.4f}")
    print(f"Results saved: {saved_path}")


if __name__ == "__main__":
    main_cli()
