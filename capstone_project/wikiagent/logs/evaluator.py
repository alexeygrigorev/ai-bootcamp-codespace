"""
Evaluator for Wikipedia Agent Logs

Reads logs from the logs/ directory and evaluates them using:
- follow_instruction: Did the agent follow its instructions?
- answer_relevant: Is the answer relevant to the question?
- context_appropriate: Were the tools used appropriately?
"""

import json
import re
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def _tokenize(text: str) -> List[str]:
    """Tokenize text into words."""
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _get_user_prompt(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Extract the first user prompt from messages."""
    for msg in messages:
        # Handle pydantic_ai message format with "kind" and "parts"
        # User messages can have kind "request" or "user"
        if msg.get("kind") in ("user", "request"):
            parts = msg.get("parts", [])
            for part in parts:
                if part.get("part_kind") == "user-prompt":
                    content = part.get("content")
                    if isinstance(content, str):
                        return content
        # Handle standard format with "role"
        elif msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Handle list of content parts
                for part in content:
                    if isinstance(part, str):
                        return part
                    elif isinstance(part, dict) and "text" in part:
                        return part["text"]
    return None


def _count_tool_calls(messages: List[Dict[str, Any]], tool_name: str) -> int:
    """Count how many times a specific tool was called."""
    count = 0
    for msg in messages:
        # Handle pydantic_ai message format with "kind" and "parts"
        # Tool calls can be in messages with kind "response" or "assistant"
        if msg.get("kind") in ("assistant", "response"):
            parts = msg.get("parts", [])
            for part in parts:
                if part.get("part_kind") == "tool-call":
                    tool_name_in_part = part.get("tool_name") or part.get("tool")
                    if tool_name_in_part == tool_name:
                        count += 1
        # Handle standard format with "role"
        elif msg.get("role") == "assistant":
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        # Check for tool calls in various formats
                        if part.get("type") == "tool_call" and part.get("tool_name") == tool_name:
                            count += 1
                        elif part.get("tool") == tool_name:
                            count += 1
            # Also check message-level tool calls
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict) and (tc.get("name") == tool_name or tc.get("tool_name") == tool_name):
                        count += 1
    return count


def evaluate_follow_instruction(
    instructions: str,
    answer: str,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluate if the agent followed its instructions.
    
    Checks:
    - Did it use search_wikipedia tool?
    - Did it include citations/references as required?
    - Did it follow the workflow described in instructions?
    """
    instructions_lower = instructions.lower() if instructions else ""
    answer_lower = answer.lower() if answer else ""
    
    # Check if instructions require citations/references
    requires_citations = (
        "citation" in instructions_lower or
        "reference" in instructions_lower or
        "cite" in instructions_lower
    )
    
    # Check if answer has citations
    has_citations = (
        "http://" in answer or
        "https://" in answer or
        "wikipedia.org" in answer_lower or
        "reference" in answer_lower or
        "citation" in answer_lower
    )
    
    # Check if search_wikipedia tool was used
    search_calls = _count_tool_calls(messages, "search_wikipedia")
    used_search = search_calls > 0
    
    # Check if get_wikipedia_page tool was used
    page_calls = _count_tool_calls(messages, "get_wikipedia_page")
    used_page = page_calls > 0
    
    # Determine if instructions were followed
    passed = True
    details = []
    
    if requires_citations:
        if has_citations:
            details.append("Citations included as required")
        else:
            details.append("Citations missing (required by instructions)")
            passed = False
    
    # Instructions typically require using search first
    if "search" in instructions_lower and not used_search:
        details.append("Search tool not used (instructions require search)")
        passed = False
    elif used_search:
        details.append(f"Search tool used {search_calls} time(s)")
    
    if used_page:
        details.append(f"Page retrieval tool used {page_calls} time(s)")
    
    if not answer:
        passed = False
        details.append("No answer provided")
    
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": "; ".join(details) if details else "No specific checks performed"
    }


def evaluate_answer_relevant(
    question: str,
    answer: str
) -> Dict[str, Any]:
    """
    Evaluate if the answer is relevant to the question.
    
    Checks:
    - Token overlap between question and answer
    - Answer length (should be substantial)
    - Semantic relevance (basic heuristic)
    """
    if not question or not answer:
        return {
            "passed": False,
            "score": 0.0,
            "details": "Missing question or answer"
        }
    
    # Tokenize and calculate overlap
    q_tokens = set(_tokenize(question))
    a_tokens = set(_tokenize(answer))
    
    overlap = len(q_tokens & a_tokens)
    union = len(q_tokens | a_tokens)
    jaccard = overlap / max(1, union)
    
    # Check answer length
    words = _tokenize(answer)
    word_count = len(words)
    
    # Basic relevance checks
    has_substantial_content = word_count >= 20
    has_overlap = jaccard >= 0.1 or overlap >= 3
    
    passed = has_substantial_content and has_overlap
    score = min(1.0, jaccard * 2)  # Scale jaccard to 0-1 range
    
    details = f"Token overlap: {overlap}, Jaccard: {jaccard:.3f}, Words: {word_count}"
    
    return {
        "passed": passed,
        "score": score,
        "details": details
    }


def evaluate_context_appropriate(
    question: str,
    answer: str,
    messages: List[Dict[str, Any]],
    tools_available: List[str]
) -> Dict[str, Any]:
    """
    Evaluate if the context/tools used were appropriate.
    
    Checks:
    - Were Wikipedia tools used when needed?
    - Was the workflow appropriate (search then retrieve)?
    - Were tools used efficiently?
    """
    if not question or not answer:
        return {
            "passed": False,
            "score": 0.0,
            "details": "Missing question or answer"
        }
    
    # Check tool usage
    search_calls = _count_tool_calls(messages, "search_wikipedia")
    page_calls = _count_tool_calls(messages, "get_wikipedia_page")
    
    # Determine if tools were used appropriately
    details = []
    passed = True
    score = 1.0
    
    # Wikipedia agent should use search for most questions
    question_lower = question.lower()
    needs_search = any(
        word in question_lower for word in ["what", "where", "when", "who", "how", "why", "which"]
    ) or len(question.split()) > 3
    
    if needs_search:
        if search_calls == 0:
            details.append("Search tool not used but question requires it")
            passed = False
            score = 0.3
        elif search_calls > 0:
            details.append(f"Search tool used appropriately ({search_calls} call(s))")
    
    # If search was used, page retrieval should typically follow
    if search_calls > 0 and page_calls == 0:
        details.append("Search used but no pages retrieved")
        score = min(score, 0.7)
    
    if page_calls > 0:
        details.append(f"Page retrieval used ({page_calls} call(s))")
    
    # Check for excessive tool calls (might indicate inefficiency)
    total_calls = search_calls + page_calls
    if total_calls > 10:
        details.append(f"High number of tool calls ({total_calls}) - may be inefficient")
        score = min(score, 0.8)
    
    if not details:
        details.append("Tool usage appears appropriate")
    
    return {
        "passed": passed,
        "score": score,
        "details": "; ".join(details)
    }


def parse_log_file(log_path: Path) -> Dict[str, Any]:
    """Parse a single log file and extract relevant information."""
    try:
        with log_path.open("r", encoding="utf-8") as f:
            log_data = json.load(f)
        
        messages = log_data.get("messages", [])
        user_prompt = _get_user_prompt(messages)
        
        # Handle system_prompt which can be a string or list
        system_prompt = log_data.get("system_prompt", "")
        if isinstance(system_prompt, list):
            # Join list items into a single string
            system_prompt = "\n".join(str(item) for item in system_prompt if item)
        elif not isinstance(system_prompt, str):
            system_prompt = str(system_prompt) if system_prompt else ""
        
        return {
            "filepath": str(log_path),
            "agent_name": log_data.get("agent_name", "unknown"),
            "model": log_data.get("model", "unknown"),
            "user_prompt": user_prompt or "",
            "instructions": system_prompt,
            "output": log_data.get("output", ""),
            "messages": messages,
            "tools": log_data.get("tools", []),
            "usage": log_data.get("usage", {}),
        }
    except Exception as e:
        print(f"Error parsing {log_path}: {e}")
        return None


def get_evaluated_logs(csv_path: Path) -> set[str]:
    """Get the set of log files that have already been evaluated."""
    if not csv_path.exists():
        return set()
    
    evaluated = set()
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                log_file = row.get("log_file", "")
                if log_file:
                    evaluated.add(log_file)
    except Exception as e:
        print(f"Warning: Could not read existing evaluation results: {e}")
    
    return evaluated


def evaluate_logs(logs_dir: Path = Path("logs"), csv_path: Path = None) -> List[Dict[str, Any]]:
    """
    Read log files from the logs directory and evaluate only new ones.
    
    Args:
        logs_dir: Directory containing log files
        csv_path: Path to existing evaluation CSV (to check for already-evaluated logs)
    
    Returns a list of evaluation results for new logs only.
    """
    if not logs_dir.exists():
        print(f"Logs directory {logs_dir} does not exist")
        return []
    
    log_files = list(logs_dir.glob("*.json"))
    if not log_files:
        print(f"No log files found in {logs_dir}")
        return []
    
    # Get already-evaluated logs if CSV exists
    evaluated_logs = set()
    if csv_path and csv_path.exists():
        evaluated_logs = get_evaluated_logs(csv_path)
        print(f"Found {len(evaluated_logs)} already-evaluated log(s)")
    
    # Filter to only new logs
    new_log_files = [f for f in log_files if f.name not in evaluated_logs]
    
    if not new_log_files:
        print(f"No new log files to evaluate (all {len(log_files)} logs already evaluated)")
        return []
    
    print(f"Found {len(new_log_files)} new log file(s) to evaluate (out of {len(log_files)} total)")
    
    results = []
    
    for log_file in new_log_files:
        print(f"Evaluating {log_file.name}...")
        
        log_data = parse_log_file(log_file)
        if not log_data:
            continue
        
        # Evaluate using the three criteria
        follow_instruction = evaluate_follow_instruction(
            instructions=log_data["instructions"],
            answer=log_data["output"],
            messages=log_data["messages"]
        )
        
        answer_relevant = evaluate_answer_relevant(
            question=log_data["user_prompt"],
            answer=log_data["output"]
        )
        
        context_appropriate = evaluate_context_appropriate(
            question=log_data["user_prompt"],
            answer=log_data["output"],
            messages=log_data["messages"],
            tools_available=log_data["tools"]
        )
        
        results.append({
            "log_file": log_file.name,
            "agent_name": log_data["agent_name"],
            "model": log_data["model"],
            "user_prompt": log_data["user_prompt"][:200] + "..." if len(log_data["user_prompt"]) > 200 else log_data["user_prompt"],
            "follow_instruction_passed": follow_instruction["passed"],
            "follow_instruction_score": follow_instruction["score"],
            "follow_instruction_details": follow_instruction["details"],
            "answer_relevant_passed": answer_relevant["passed"],
            "answer_relevant_score": answer_relevant["score"],
            "answer_relevant_details": answer_relevant["details"],
            "context_appropriate_passed": context_appropriate["passed"],
            "context_appropriate_score": context_appropriate["score"],
            "context_appropriate_details": context_appropriate["details"],
            "timestamp": datetime.now().isoformat()
        })
    
    return results


def save_eval_results(results: List[Dict[str, Any]], output_path: Path, append: bool = False):
    """
    Save evaluation results to a CSV file.
    
    Args:
        results: List of evaluation results to save
        output_path: Path to CSV file
        append: If True, append to existing file; if False, overwrite
    """
    if not results:
        print("No results to save")
        return
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define CSV columns
    fieldnames = [
        "log_file",
        "agent_name",
        "model",
        "user_prompt",
        "follow_instruction_passed",
        "follow_instruction_score",
        "follow_instruction_details",
        "answer_relevant_passed",
        "answer_relevant_score",
        "answer_relevant_details",
        "context_appropriate_passed",
        "context_appropriate_score",
        "context_appropriate_details",
        "timestamp"
    ]
    
    # Determine if we need to write header
    write_header = not (append and output_path.exists())
    
    mode = "a" if append else "w"
    with output_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(results)
    
    action = "Appended" if append else "Saved"
    print(f"\n✓ {action} evaluation results to {output_path}")
    print(f"  New logs evaluated: {len(results)}")


def load_all_eval_results(csv_path: Path) -> List[Dict[str, Any]]:
    """Load all evaluation results from CSV file."""
    if not csv_path.exists():
        return []
    
    results = []
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert string booleans back to booleans
                for key in row:
                    if key.endswith("_passed"):
                        row[key] = row[key].lower() == "true" if row[key] else None
                    elif key.endswith("_score"):
                        try:
                            row[key] = float(row[key]) if row[key] else None
                        except (ValueError, TypeError):
                            row[key] = None
                results.append(row)
    except Exception as e:
        print(f"Warning: Could not load existing evaluation results: {e}")
    
    return results


def main():
    """Main function to run the evaluator."""
    # Since this file is now in logs/, use current directory for logs
    logs_dir = Path(__file__).parent
    output_path = logs_dir / "evaluation_results.csv"
    
    # Evaluate only new logs
    results = evaluate_logs(logs_dir, csv_path=output_path)
    
    if not results:
        print("No new logs to evaluate")
        # Still show summary of all existing results
        all_results = load_all_eval_results(output_path)
        if all_results:
            print(f"\nTotal logs already evaluated: {len(all_results)}")
        return
    
    # Append new results to CSV (or create if it doesn't exist)
    append = output_path.exists()
    save_eval_results(results, output_path, append=append)
    
    # Load all results (existing + new) for summary
    all_results = load_all_eval_results(output_path)
    
    # Print summary
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    total = len(all_results)
    new_count = len(results)
    
    if new_count > 0:
        print(f"New logs evaluated in this run: {new_count}")
    print(f"Total logs evaluated: {total}")
    
    if total > 0:
        follow_passed = sum(1 for r in all_results if r.get("follow_instruction_passed"))
        relevant_passed = sum(1 for r in all_results if r.get("answer_relevant_passed"))
        context_passed = sum(1 for r in all_results if r.get("context_appropriate_passed"))
        
        print(f"\nFollow Instruction: {follow_passed}/{total} passed ({follow_passed/total*100:.1f}%)")
        print(f"Answer Relevant: {relevant_passed}/{total} passed ({relevant_passed/total*100:.1f}%)")
        print(f"Context Appropriate: {context_passed}/{total} passed ({context_passed/total*100:.1f}%)")
        
        # Average scores
        scores_follow = [r.get("follow_instruction_score") for r in all_results if r.get("follow_instruction_score") is not None]
        scores_relevant = [r.get("answer_relevant_score") for r in all_results if r.get("answer_relevant_score") is not None]
        scores_context = [r.get("context_appropriate_score") for r in all_results if r.get("context_appropriate_score") is not None]
        
        if scores_follow:
            avg_follow = sum(scores_follow) / len(scores_follow)
            print(f"\nAverage Scores:")
            print(f"  Follow Instruction: {avg_follow:.3f}")
        if scores_relevant:
            avg_relevant = sum(scores_relevant) / len(scores_relevant)
            if not scores_follow:
                print(f"\nAverage Scores:")
            print(f"  Answer Relevant: {avg_relevant:.3f}")
        if scores_context:
            avg_context = sum(scores_context) / len(scores_context)
            if not scores_follow and not scores_relevant:
                print(f"\nAverage Scores:")
            print(f"  Context Appropriate: {avg_context:.3f}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()

