#!/usr/bin/env python
"""
Generate evaluation questions from documentation using LLM.
"""

import json
import argparse

from dataclasses import dataclass
from typing import List, Literal, Tuple
from concurrent.futures import ThreadPoolExecutor
from toyaikit.pricing import PricingConfig

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel, Field
from tqdm import tqdm

import docs


@dataclass
class Config:
    """Configuration for question generation."""

    model: str = "gpt-4o-mini"
    max_workers: int = 6
    min_content_length: int = 1000
    chars_per_question: int = 1000
    output_file: str = "ground_truth_evidently.csv"
    exclude_keywords: List[str] = None

    def __post_init__(self):
        if self.exclude_keywords is None:
            self.exclude_keywords = ["unpublished", "legacy", "leftovers", "updates"]


class Question(BaseModel):
    """
    Represents a realistic search-engine-style query a user might type before finding the article.
    """

    question: str = Field(
        ...,
        description="A natural, short search query — not a full-sentence question — phrased like something typed into Google.",
    )
    summary_answer: str = Field(
        ...,
        description="A concise 1–2 sentence summary of how the article addresses the query.",
    )
    difficulty: Literal["beginner", "intermediate", "advanced"] = Field(
        ..., description="The assumed knowledge level of the user making the query."
    )
    intent: Literal["text", "code"] = Field(
        ...,
        description="Specifies if the user's intent is to get a theoretical explanation ('text') or an implementation example ('code').",
    )
    relevant_lines: str = Field(
        ...,
        description="The specific line numbers or range from the source document that are most relevant to answering this question (e.g., 'lines 45-67' or 'line 23').",
    )


class GeneratedQuestions(BaseModel):
    """
    A structured collection of human-like search queries derived from a given article.
    """

    description: str = Field(
        ...,
        description="A summary of the article or topic these search-style questions were generated for.",
    )
    questions: List[Question] = Field(
        ...,
        description="A list of realistic search queries with short summaries, difficulty levels, and user intent.",
    )


def get_instructions() -> str:
    """Return the system instructions for the LLM."""
    return """
You are given a technical article. Your task is to imagine what a person might type into a search engine 
before finding and reading this article.

Generate realistic, human-like search queries — not formal questions. 
They should sound like what people actually type into Google or Stack Overflow 
when trying to solve a problem, learn a concept, or find code examples.

Guidelines:
- Avoid full-sentence questions with punctuation like "What is..." or "How do I...".
- Use short, natural search phrases instead, such as:
  - "evidently data definition example"
  - "map target and prediction columns evidently"
  - "difference between timestamp and datetime evidently"
- Make queries varied and spontaneous, not repetitive or over-polished.
- Assume users of different knowledge levels:
  - beginner: broad or basic understanding
  - intermediate: knows basic terms but seeks clarification or examples
  - advanced: familiar with the tool, looking for details, edge cases, or integration options

Distribution rules:
- 60% of the queries should target beginner-level users
- 30% should target intermediate-level users
- 10% should target advanced-level users
- 75% of queries should have an intent of "code" (looking for examples or implementation)
- 25% should have an intent of "text" (looking for conceptual or theoretical explanations)

For each generated query, include:
- question: the natural, human-style search phrase
- summary_answer: a short 1–2 sentence summary of how the article addresses it
- difficulty: one of ["beginner", "intermediate", "advanced"]
- intent: one of ["text", "code"]
- relevant_lines: the specific line numbers or range from the source document that contain the information to answer this query (e.g., "lines 45-67" or "line 23")

Also include a description summarizing what kind of article the questions are about.

Note: The document content will be provided with line numbers at the start of each line to help you identify relevant sections.
""".strip()


def filter_documents(documents: List[dict], config: Config) -> Tuple[List[dict], int]:
    """
    Filter documents based on length and excluded keywords.

    Returns:
        Tuple of (selected_docs, total_questions)
    """
    selected_docs = []
    total_questions = 0

    for doc in documents:
        if "title" not in doc:
            continue

        title = doc["title"].lower()
        content = doc.get("content", "")

        if len(content) < config.min_content_length:
            continue

        if any(keyword in title for keyword in config.exclude_keywords):
            continue

        num_questions = len(content) // config.chars_per_question
        total_questions += num_questions
        print(f"{title}: {num_questions} questions")
        selected_docs.append(doc)

    return selected_docs, total_questions


def llm_structured(
    client: OpenAI, instructions: str, user_prompt: str, output_format: type, model: str
):
    """
    Call LLM with structured output.

    Returns:
        Tuple of (parsed_output, usage)
    """
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": user_prompt},
    ]

    response = client.responses.parse(
        model=model, input=messages, text_format=output_format
    )

    return (response.output_parsed, response.usage)


def add_line_numbers(content: str) -> str:
    """Add line numbers to content for LLM reference."""
    lines = content.split('\n')
    numbered_lines = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
    return '\n'.join(numbered_lines)


def process_document(
    doc: dict, client: OpenAI, instructions: str, config: Config
) -> dict:
    """Process a single document to generate questions."""
    content = doc["content"]
    num_questions = len(content) // config.chars_per_question

    # Add line numbers to content for LLM
    content_with_lines = add_line_numbers(content)
    
    # Create doc copy with numbered content
    doc_for_llm = doc.copy()
    doc_for_llm["content"] = content_with_lines

    user_prompt = f"""
generate {num_questions} questions for this document:
{json.dumps(doc_for_llm)}
""".strip()

    output, usage = llm_structured(
        client=client,
        instructions=instructions,
        user_prompt=user_prompt,
        output_format=GeneratedQuestions,
        model=config.model,
    )

    return {"doc": doc, "questions": output, "usage": usage}


def map_progress(pool: ThreadPoolExecutor, seq: List, f) -> List:
    """
    Map function f over seq using the provided executor pool while
    displaying a tqdm progress bar.
    """
    results = []

    with tqdm(total=len(seq)) as progress:
        futures = []

        for el in seq:
            future = pool.submit(f, el)
            future.add_done_callback(lambda p: progress.update())
            futures.append(future)

        for future in futures:
            result = future.result()
            results.append(result)

    return results


def calculate_cost(results: List[dict], model: str) -> float:
    """Calculate the total cost of API calls."""

    pricing = PricingConfig()
    input_tokens = sum(r["usage"].input_tokens for r in results)
    output_tokens = sum(r["usage"].output_tokens for r in results)

    cost = pricing.calculate_cost(model, input_tokens, output_tokens)
    print(f"Total tokens - Input: {input_tokens}, Output: {output_tokens}")
    print(f"Estimated cost: ${cost}")

    return cost


def flatten_results(results: List[dict]) -> List[dict]:
    """Flatten results into a list of questions with metadata."""
    final_questions = []

    for r in results:
        doc = r["doc"]
        questions = r["questions"]

        for q in questions.questions:
            final_question = q.model_dump()
            final_question["filename"] = doc["filename"]
            final_questions.append(final_question)

    return final_questions


def save_questions(questions: List[dict], output_file: str):
    """Save questions to CSV file."""
    df_questions = pd.DataFrame(questions)
    df_questions.to_csv(output_file, index=False)
    print(f"\nSaved {len(questions)} questions to {output_file}")


def main(config: Config):
    """Main processing function."""
    print("Loading documents...")
    raw_documents = docs.read_github_data()
    documents = docs.parse_data(raw_documents)
    print(f"Loaded {len(documents)} documents")

    print("\nFiltering documents...")
    selected_docs, total_questions = filter_documents(documents, config)
    print(f"Selected {len(selected_docs)} documents")
    print(f"Expected ~{total_questions} questions\n")

    print("Generating questions...")
    client = OpenAI()
    instructions = get_instructions()

    def process_fn(doc):
        return process_document(doc, client, instructions, config)

    with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
        results = map_progress(pool, selected_docs, process_fn)

    print(f"\nProcessed {len(results)} documents")

    print("\nCalculating cost...")
    calculate_cost(results, config.model)

    print("\nFlattening results...")
    final_questions = flatten_results(results)

    save_questions(final_questions, config.output_file)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate evaluation questions from documentation"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=6,
        help="Maximum number of parallel workers (default: 6)",
    )
    parser.add_argument(
        "--min-content-length",
        type=int,
        default=1000,
        help="Minimum content length for document selection (default: 1000)",
    )
    parser.add_argument(
        "--chars-per-question",
        type=int,
        default=1000,
        help="Number of characters per question (default: 1000)",
    )
    parser.add_argument(
        "--output",
        default="ground_truth_evidently.csv",
        help="Output CSV file (default: ground_truth_evidently.csv)",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=["unpublished", "legacy", "leftovers", "updates"],
        help="Keywords to exclude from document titles",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    config = Config(
        model=args.model,
        max_workers=args.max_workers,
        min_content_length=args.min_content_length,
        chars_per_question=args.chars_per_question,
        output_file=args.output,
        exclude_keywords=args.exclude,
    )

    main(config)
