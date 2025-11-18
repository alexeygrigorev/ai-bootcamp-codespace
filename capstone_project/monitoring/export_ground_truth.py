"""
Export ground truth dataset from monitoring database to CSV.
"""

import csv
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.db import Database


def export_ground_truth(output_file: str = None):
    """Export ground truth dataset to CSV."""
    db_url = os.environ.get("DATABASE_URL", "sqlite:///capstone_project/monitoring/monitoring.db")
    db = Database(db_url)
    db.ensure_schema()
    
    entries = db.get_ground_truth_entries(limit=10000)
    
    if not entries:
        print("No ground truth entries found in database.")
        return
    
    if output_file is None:
        output_file = Path(__file__).parent.parent / "eval" / "ground_truth_from_logs.csv"
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'id', 'log_id', 'question_text', 'expected_answer', 'company_name',
            'cik', 'form_type', 'filing_date', 'created_at'
        ])
        writer.writeheader()
        
        for entry in entries:
            writer.writerow({
                'id': entry.get('id'),
                'log_id': entry.get('log_id'),
                'question_text': entry.get('question_text', ''),
                'expected_answer': entry.get('expected_answer', ''),
                'company_name': entry.get('company_name', ''),
                'cik': entry.get('cik', ''),
                'form_type': entry.get('form_type', ''),
                'filing_date': entry.get('filing_date', ''),
                'created_at': str(entry.get('created_at', ''))
            })
    
    print(f"Exported {len(entries)} ground truth entries to {output_path}")


if __name__ == "__main__":
    output_file = sys.argv[1] if len(sys.argv) > 1 else None
    export_ground_truth(output_file)

