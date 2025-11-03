import pytest 

from pydantic_ai import Agent, AgentRunResult
from pydantic import BaseModel


from tests.utils import get_tool_calls
from search_agent import SearchResultArticle
import main


judge_instructions = """
you are an expert judge evaluating the performance of an AI search agent.
"""


class JudgeCriterion(BaseModel):
    criterion_description: str
    passed: bool
    judgement: str


class JudgeFeedback(BaseModel):
    criteria: list[JudgeCriterion]
    feedback: str


def create_judge():
    judge = Agent(
        name="judge",
        instructions=judge_instructions,
        model="openai:gpt-4o-mini",
        output_type=JudgeFeedback,
    )
    return judge


async def evaluate_agent_performance(
        criteria: list[str],
        result: AgentRunResult,
        output_transformer: callable = None) -> JudgeFeedback:
    
    
    tool_calls = get_tool_calls(result)
    tool_calls_str = [str(call) for call in tool_calls]

    output = result.output
    if output_transformer is not None:
        output = output_transformer(output)

    user_prompt = f"""
Evaluate the agent's performance based on the following criteria:
<CRITERIA>
{'\n'.join(criteria)}
</CRITERIA>

The agent's final output was:
<AGENT_OUTPUT>
{output}
</AGENT_OUTPUT>

Tool calls:
<TOOL_CALLS>
{'\n'.join([str(c) for c in tool_calls])}
</TOOL_CALLS>
    """

    print("Judge Prompt:", user_prompt)

    judge = create_judge()
    judge_result = await judge.run(user_prompt)
    return judge_result.output


@pytest.mark.asyncio
async def test_agent_no_legal_domain():
    user_prompt = "what is llm as a judge evaluation"

    result = await main.run_agent(user_prompt)

    print(result.output.format_article())
    
    criteria = [
        "agent made at least 3 tool calls",
        "article contains at least one section",
        "article contains at least one reference",
        "no legal terms are present in search queries (except the word 'judge')"
    ]

    judge_feedback = await evaluate_agent_performance(
        criteria,
        result,
        output_transformer=lambda output: output.format_article()
    )

    print(judge_feedback)

    for criterion in judge_feedback.criteria:
        assert criterion.passed, f"Criterion failed: {criterion.criterion_description}, {criterion.judgement}"


@pytest.mark.asyncio
async def test_agent_python_code():
    user_prompt = "how do I run llm as a judge"

    result = await main.run_agent(user_prompt)

    print(result.output.format_article())
    
    criteria = [
        "agent made at least 3 search calls",
        "agent made at least 1 read_file call",
        "there's python code in the results",
        "all the imports that are used in the code are defined",
        "all the variables and functions used in the code are defined or imported"
        "it describes how to create the evaluation dataset",
        "it describes how to configure the prompt template for the judge",
        "it describes how to run LLMEval",
        "it shows how to display the report",
        "LLMEval, Report and TextEvals are correctly imported",
    ]

    judge_feedback = await evaluate_agent_performance(
        criteria,
        result,
        output_transformer=lambda output: output.format_article()
    )

    print(judge_feedback)

    for criterion in judge_feedback.criteria:
        assert criterion.passed, f"Criterion failed: {criterion.criterion_description}, {criterion.judgement}"

