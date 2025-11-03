"""
Evaluation orchestrator.

This module orchestrates the complete evaluation pipeline:
1. Run the agent on ground truth questions
2. Evaluate results with the judge
3. Display comprehensive report with costs
"""
import argparse

import asyncio
from datetime import datetime
from typing import Optional
from pathlib import Path

from toyaikit.pricing import CostInfo
from pydantic_ai import Agent

from evals.eval_agent_run import run_agent_evaluation
from evals.eval_agent_judge import run_complete_judge_evaluation

import main


def format_cost_report(step_name: str, cost_info: CostInfo, indent: str = "") -> str:
    """
    Format cost information as a readable string.
    
    Args:
        step_name: Name of the evaluation step
        cost_info: Cost information
        indent: Indentation string
        
    Returns:
        Formatted cost report
    """
    lines = [
        f"{indent}{step_name} Costs:",
        f"{indent}  Input tokens cost:  ${cost_info.input_cost:>8.4f}",
        f"{indent}  Output tokens cost: ${cost_info.output_cost:>8.4f}",
        f"{indent}  Total cost:         ${cost_info.total_cost:>8.4f}",
    ]
    return "\n".join(lines)


def print_separator(title: str = "", width: int = 70, char: str = "="):
    """Print a formatted separator line."""
    if title:
        print(f"\n{char*3} {title} {char * (width - len(title) - 5)}")
    else:
        print(char * width)


async def run_full_evaluation(
    agent: Agent,
    csv_path: str = './ground_truth_evidently.csv',
    agent_model: str = 'gpt-4o-mini',
    judge_model: str = 'gpt-5-nano',
    max_concurrency: int = 10,
    output_path: Optional[str] = None
) -> dict:
    """
    Run complete evaluation pipeline: agent run + judge evaluation.
    
    Args:
        csv_path: Path to ground truth CSV (can be full set or pre-sampled)
        agent_model: Model for the agent
        judge_model: Model for the judge
        max_concurrency: Max concurrent operations
        output_path: Output file path for run results
        
    Returns:
        Dictionary with all results and metrics
    """
    start_time = datetime.now()
    
    print_separator("EVALUATION PIPELINE START")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Configuration:")
    print(f"  Ground truth: {csv_path}")
    print(f"  Agent model: {agent_model}")
    print(f"  Judge model: {judge_model}")
    print(f"  Max concurrency: {max_concurrency}")
    
    # Step 1: Run agent evaluation
    print_separator("STEP 1: AGENT EVALUATION")
    
    saved_path, run_cost, df_run = await run_agent_evaluation(
        csv_path=csv_path,
        max_concurrency=max_concurrency,
        model=agent_model,
        output_path=output_path
    )
    
    print("\n✓ Agent evaluation completed")
    print(f"  Evaluated: {len(df_run)} questions")
    print(f"  Results saved: {saved_path}")
    print(format_cost_report("Agent Run", run_cost, "  "))
    
    # Step 2: Run judge evaluation
    print_separator("STEP 2: JUDGE EVALUATION")
    
    # Generate judge output path with same timestamp as run results
    judge_output_path = saved_path.replace('eval-run-', 'eval-judge-')
    
    judge_cost, df_eval, metrics, judge_path = await run_complete_judge_evaluation(
        input_path=saved_path,
        model=judge_model,
        max_concurrency=max_concurrency,
        output_path=judge_output_path
    )
    
    print("\n✓ Judge evaluation completed")
    print(f"  Evaluated: {len(df_eval)} results")
    print(f"  Judge results saved: {judge_path}")
    print(format_cost_report("Judge Evaluation", judge_cost, "  "))
    
    # Calculate total cost
    total_cost = CostInfo(
        input_cost=run_cost.input_cost + judge_cost.input_cost,
        output_cost=run_cost.output_cost + judge_cost.output_cost,
        total_cost=run_cost.total_cost + judge_cost.total_cost
    )
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Print final report
    print_separator("EVALUATION SUMMARY")
    
    print("\nExecution Time:")
    print(f"  Duration: {duration.total_seconds():.1f} seconds")
    
    print("\nDataset:")
    print(f"  Questions evaluated: {len(df_run)}")
    
    print("\nEvaluation Metrics:")
    for check_name, score in metrics.items():
        status = "✓" if score >= 0.8 else "⚠" if score >= 0.6 else "✗"
        print(f"  {status} {check_name:<25} {score:>6.1%}")
    
    print(f"\nOverall Score: {metrics.mean():.1%}")
    
    print_separator("COST BREAKDOWN")
    print(format_cost_report("Agent Run", run_cost))
    print(format_cost_report("Judge Evaluation", judge_cost))
    print_separator()
    print(format_cost_report("TOTAL", total_cost))
    
    print_separator("EVALUATION COMPLETE")
    
    return {
        'run_results_path': saved_path,
        'judge_results_path': judge_path,
        'run_cost': run_cost,
        'judge_cost': judge_cost,
        'total_cost': total_cost,
        'df_run': df_run,
        'df_eval': df_eval,
        'metrics': metrics,
        'duration_seconds': duration.total_seconds(),
        'timestamp': start_time
    }


def main_cli():
    """Command-line interface for running full evaluation."""

    parser = argparse.ArgumentParser(
        description='Run complete agent evaluation pipeline (run + judge)'
    )
    parser.add_argument(
        '--csv',
        default='./ground_truth_evidently.csv',
        help='Path to ground truth CSV file (can be pre-sampled using sample_ground_truth.py)'
    )
    parser.add_argument(
        '--agent-model',
        default='gpt-4o-mini',
        help='Model to use for the agent'
    )
    parser.add_argument(
        '--judge-model',
        default='gpt-5-nano',
        help='Model to use for the judge'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=10,
        help='Maximum concurrent operations'
    )
    parser.add_argument(
        '--output',
        help='Output path for run results (auto-generated if not specified)'
    )
    
    args = parser.parse_args()

    agent = main.agent

    results = asyncio.run(run_full_evaluation(
        agent=agent,
        csv_path=args.csv,
        agent_model=args.agent_model,
        judge_model=args.judge_model,
        max_concurrency=args.concurrency,
        output_path=args.output
    ))
    
    # Create reports directory if it doesn't exist
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Save detailed report
    report_path = reports_dir / f"eval-report-{results['timestamp'].strftime('%Y-%m-%d-%H-%M')}.txt"
    with open(report_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("EVALUATION REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Timestamp: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {results['duration_seconds']:.1f} seconds\n")
        f.write(f"Questions: {len(results['df_run'])}\n\n")
        
        f.write("Evaluation Metrics:\n")
        for check_name, score in results['metrics'].items():
            f.write(f"  {check_name:<25} {score:>6.1%}\n")
        f.write(f"\nOverall Score: {results['metrics'].mean():.1%}\n\n")
        
        f.write("Cost Breakdown:\n")
        f.write("  Agent Run:\n")
        f.write(f"    Input:  ${results['run_cost'].input_cost:.4f}\n")
        f.write(f"    Output: ${results['run_cost'].output_cost:.4f}\n")
        f.write(f"    Total:  ${results['run_cost'].total_cost:.4f}\n\n")
        f.write("  Judge Evaluation:\n")
        f.write(f"    Input:  ${results['judge_cost'].input_cost:.4f}\n")
        f.write(f"    Output: ${results['judge_cost'].output_cost:.4f}\n")
        f.write(f"    Total:  ${results['judge_cost'].total_cost:.4f}\n\n")
        f.write("  TOTAL:\n")
        f.write(f"    Input:  ${results['total_cost'].input_cost:.4f}\n")
        f.write(f"    Output: ${results['total_cost'].output_cost:.4f}\n")
        f.write(f"    Total:  ${results['total_cost'].total_cost:.4f}\n\n")
        
        f.write(f"Results file: {results['run_results_path']}\n")
    
    print(f"\n📄 Detailed report saved to: {report_path}")


if __name__ == '__main__':
    main_cli()
