from dataclasses import dataclass

from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent
from pydantic_ai.messages import ModelMessage, UserPromptPart

import search_tools


@dataclass
class AgentConfig:
    chunk_size: int = 2000
    chunk_step: int = 1000
    top_k: int = 5

    model: str = "openai:gpt-4o-mini"


class NamedCallback:

    def __init__(self, agent):
        self.agent_name = agent.name

    async def print_function_calls(self, ctx, event):
        # Detect nested streams
        if hasattr(event, "__aiter__"):
            async for sub in event:
                await self.print_function_calls(ctx, sub)
            return

        if isinstance(event, FunctionToolCallEvent):
            tool_name = event.part.tool_name
            args = event.part.args
            print(f"TOOL CALL ({self.agent_name}): {tool_name}({args})")

    async def __call__(self, ctx, event):
        return await self.print_function_calls(ctx, event)


search_instructions = """
You are a search assistant for the Evidently documentation.

Evidently is an open-source Python library and cloud platform for evaluating, testing, and monitoring data and AI systems.
It provides evaluation metrics, testing APIs, and visual reports for model and data quality.

Your task is to help users find accurate, relevant information about Evidently's features, usage, and integrations.

You have access to the following tools:

- search — Use this to explore the topic and retrieve relevant snippets or documentation.
- read_file — Use this to retrieve or verify the complete content of a file when:
    * A code snippet is incomplete, truncated, or missing definitions.
    * You need to check that all variables, imports, and functions referenced in code are defined.
    * You must ensure the code example is syntactically correct and runnable.

If `read_file` cannot be used or the file content is unavailable, clearly state:
> "Unable to verify with read_file."

Search Strategy

- For every user query:
    * Perform at least 3 and at most 6 distinct searches to gather enough context.
    * Each search must use a different phrasing or keyword variation of the user's question.
    * Keep all searches relevant to Evidently (no need to include "Evidently" in the search text).

- After collecting search results:
    1. Synthesize the information into a concise, accurate answer.
    2. If your answer includes code, always validate it with `read_file` before finalizing.
    3. If a code snippet or reference is incomplete, explicitly mention it.

Important:
- The 6-search limit applies only to `search` calls.
- You may call `read_file` at any time, even after the search limit is reached.
- `read_file` calls are verification steps and do not count toward the 6-search limit.

Code Verification and Completeness Rules

- All variables, functions, and imports in your final code examples must be defined or imported.
- Never shorten, simplify, or truncate code examples. Always present the full, verified version.
- When something is missing or undefined in the search results:
    * Call `read_file` with the likely filename to retrieve the complete file content.
    * Replace any partial code with the full verified version.
- If the file is not available or cannot be verified:
    * Include a clear note: "Unable to verify this code."
- Do not reformat, rename variables, or omit lines from the verified code.

Output Format

- Write your answer clearly and accurately.
- Include a "References" section listing the search queries or file names you used.
- If you couldn’t find a complete answer after 6 searches, set found_answer = False.
"""


class Reference(BaseModel):
    title: str
    filename: str

class Section(BaseModel):
    heading: str
    content: str
    references: list[Reference]


class SearchResultArticle(BaseModel):
    found_answer: bool
    title: str
    sections: list[Section]
    references: list[Reference]

    def format_article(self, base_url: str = "https://github.com/evidentlyai/docs/blob/main"):
        output = f"# {self.title}\n\n"

        for section in self.sections:
            output += f"## {section.heading}\n\n"
            output += f"{section.content}\n\n"
            output += "### References\n"
            for ref in section.references:
                output += f"- [{ref.title}]({base_url}/{ref.filename})\n"

        output += "## References\n"
        for ref in self.references:
            output += f"- [{ref.title}]({base_url}/{ref.filename})\n"

        return output




def force_answer_after_6_searches(messages: list[ModelMessage]) -> list[ModelMessage]: 
    num_tool_calls = 0

    for m in messages:
        for p in m.parts:
            if p.part_kind == 'tool-call' and p.tool_name == 'search':
                num_tool_calls = num_tool_calls + 1

    if num_tool_calls >= 6:
        print('forcing output')
        last_message = messages[-1]
        finish_prompt = 'System message: The maximal number of searches has exceeded 6. Proceed to finishing the writeup'
        finish_prompt_part = UserPromptPart(finish_prompt)
        last_message.parts.append(finish_prompt_part)

    return messages


def create_agent(config: AgentConfig = None) -> Agent:
    if config is None:
        config = AgentConfig()

    tools = search_tools.prepare_search_tools(
        config.chunk_size,
        config.chunk_step,
        config.top_k
    )

    agent = Agent(
        name="search",
        instructions=search_instructions,
        tools=[tools.search, tools.read_file],
        model=config.model,
        output_type=SearchResultArticle,
        history_processors=[force_answer_after_6_searches]
    )

    # print(agent.toolsets[0].tools.keys())

    return agent