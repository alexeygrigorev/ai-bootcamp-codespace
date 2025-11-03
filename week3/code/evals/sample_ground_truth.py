"""
Ground truth sampler.

This script samples questions from the ground truth dataset and saves them
for reproducible evaluation runs.
"""

import argparse
from datetime import datetime
from typing import Optional

import pandas as pd


def sample_ground_truth(
    csv_path: str = './ground_truth_evidently.csv',
    sample_size: Optional[int] = None,
    random_state: int = 1,
    extra_indices: Optional[list[int]] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Sample questions from ground truth dataset and save to CSV.
    
    Args:
        csv_path: Path to the full ground truth CSV file
        sample_size: Number of samples to select (None = all)
        random_state: Random seed for reproducibility
        extra_indices: Additional specific indices to include
        output_path: Path to save sampled file (None = auto-generate)
        
    Returns:
        Path to the saved sample file
    """
    print(f"Loading ground truth from {csv_path}...")
    df_ground_truth = pd.read_csv(csv_path)
    total_questions = len(df_ground_truth)
    print(f"Total questions available: {total_questions}")
    
    if sample_size is None:
        print("Using all questions (no sampling)")
        df_sample = df_ground_truth
    else:
        print(f"Sampling {sample_size} questions with random_state={random_state}...")
        df_sample = df_ground_truth.sample(sample_size, random_state=random_state)
    
    # Add extra indices if specified
    if extra_indices:
        print(f"Adding extra indices: {extra_indices}")
        for idx in extra_indices:
            if 0 <= idx < total_questions:
                row = df_ground_truth.iloc[idx]
                # Check if already in sample
                if idx not in df_sample.index:
                    df_sample = pd.concat([df_sample, pd.DataFrame([row])], ignore_index=True)
                else:
                    print(f"  Index {idx} already in sample, skipping")
            else:
                print(f"  Warning: Index {idx} out of range (0-{total_questions-1}), skipping")
    
    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
        size_str = "all" if sample_size is None else f"{len(df_sample)}"
        output_path = f'ground_truth_sample_{size_str}_{timestamp}.csv'
    
    # Save sample
    df_sample.to_csv(output_path, index=False)
    
    print(f"\n✓ Sample saved to: {output_path}")
    print(f"  Total questions in sample: {len(df_sample)}")
    
    return output_path


def main_cli():
    """Command-line interface for sampling ground truth."""
    parser = argparse.ArgumentParser(
        description='Sample questions from ground truth dataset for evaluation'
    )
    parser.add_argument(
        '--input',
        default='./ground_truth_evidently.csv',
        help='Path to full ground truth CSV file'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=None,
        help='Number of questions to sample (default: all)'
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=1,
        help='Random seed for reproducibility (default: 1)'
    )
    parser.add_argument(
        '--extra-indices',
        type=int,
        nargs='+',
        help='Additional specific indices to include (e.g., --extra-indices 150 200)'
    )
    parser.add_argument(
        '--output',
        help='Output path for sample CSV (auto-generated if not specified)'
    )
    
    args = parser.parse_args()
    
    output_path = sample_ground_truth(
        csv_path=args.input,
        sample_size=args.sample_size,
        random_state=args.random_state,
        extra_indices=args.extra_indices,
        output_path=args.output
    )
    
    print("\n" + "=" * 70)
    print("USAGE IN EVALUATION:")
    print("=" * 70)
    print(f"python eval_orchestrator.py --csv {output_path}")
    print("\nOR run steps separately:")
    print(f"python eval_agent_run.py --csv {output_path}")


if __name__ == '__main__':
    main_cli()
