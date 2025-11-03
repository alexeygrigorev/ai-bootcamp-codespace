"""
Wikipedia Agent

Agent that uses Wikipedia API tools to answer questions.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_ai import Agent
from tools import search_wikipedia, get_wikipedia_page

# Load .env file if it exists
# Try loading from wikiagent directory, parent directory, or project root
env_paths = [
    Path(__file__).parent / '.env',                    # week3/wikiagent/.env
    Path(__file__).parent.parent / '.env',              # week3/.env
    Path(__file__).parent.parent.parent / '.env',       # project root/.env
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break
else:
    # If no .env found, try loading from default location (current directory)
    load_dotenv(override=True)


# Agent instructions
wikipedia_agent_instructions = """
You are a helpful Wikipedia research assistant.

Your workflow when answering questions:
1. FIRST, use search_wikipedia(query) to find relevant Wikipedia pages
2. Review the search results to identify the most relevant pages
3. Use get_wikipedia_page(title) to retrieve the content of the most relevant pages
4. Analyze the page content to answer the user's question
5. ALWAYS include references/citations in your answer

IMPORTANT GUIDELINES:
- Always start with a search - never try to answer without searching first
- Use specific search terms that match what the user is asking about
- Read multiple relevant pages if needed to provide a comprehensive answer
- When you get page content, look for specific information that answers the question
- MANDATORY: You MUST cite your sources by including references to the Wikipedia pages you used
- Format references as: [Page Title](https://en.wikipedia.org/wiki/Page_Title) or as a list at the end
- Always include at least one reference/citation in your answer
- If search returns no results, try alternative search terms
- If a page is not found, try variations of the title or search again
"""

# Create the agent
wikipedia_agent = Agent(
    name='wikipedia_agent',
    instructions=wikipedia_agent_instructions,
    tools=[search_wikipedia, get_wikipedia_page],
    model='openai:gpt-4o-mini'
)

