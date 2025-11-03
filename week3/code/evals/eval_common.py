"""
Common utilities for evaluation scripts.

This module provides shared functionality used by both eval_agent_run.py
and eval_agent_judge.py, including async helpers, cost calculation,
and message simplification.
"""

import asyncio
import json
from tqdm.auto import tqdm
from toyaikit.pricing import PricingConfig, CostInfo


async def map_progress(seq, f, max_concurrency=6):
    """
    Asynchronously map async function f over seq with progress bar.
    
    Args:
        seq: Sequence of items to process
        f: Async function to apply to each item
        max_concurrency: Maximum number of concurrent tasks
        
    Returns:
        List of results in the same order as input sequence
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run(el):
        async with semaphore:
            return await f(el)

    # create one coroutine per element
    coros = [run(el) for el in seq]

    # turn them into tasks that complete as they finish
    completed = asyncio.as_completed(coros)

    results = []

    for coro in tqdm(completed, total=len(seq)):
        result = await coro
        results.append(result)

    return results


def calculate_cost(model: str, all_results: list) -> CostInfo:
    """
    Calculate total cost for a list of LLM results.
    
    Args:
        model: Model name (e.g., 'gpt-4o-mini')
        all_results: List of tuples containing (original_item, result)
        
    Returns:
        CostInfo object with input, output, and total costs
    """
    pricing = PricingConfig()
    
    input_tokens = 0
    output_tokens = 0

    for _, r in all_results:
        usage = r.usage()
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens

    cost = pricing.calculate_cost(model, input_tokens, output_tokens)
    
    return cost


def simplify_messages(messages):
    """
    Simplify message history for logging and analysis.
    
    Extracts key information from message parts, excluding unnecessary
    details like tool returns and final_result tool calls.
    
    Args:
        messages: List of message objects with parts
        
    Returns:
        List of simplified message dictionaries
    """
    messages_simplified = []

    for m in messages:
        parts = []

        for original_part in m.parts:
            kind = original_part.part_kind
            part = {
                'kind': kind
            }
            
            if kind == 'user-prompt':
                part['content'] = original_part.content
            elif kind == 'tool-call':
                if original_part.tool_name == 'final_result':
                    continue
                part['tool_name'] = original_part.tool_name
                part['args'] = json.loads(original_part.args)
            elif kind == 'tool-return':
                continue
            elif kind == 'text':
                part['content'] = original_part.content

            parts.append(part)

        if len(parts) > 0:
            messages_simplified.extend(parts)

    return messages_simplified
