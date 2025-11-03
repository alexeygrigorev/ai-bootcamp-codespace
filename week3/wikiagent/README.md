# WikiAgent

A simple Wikipedia agent that can search and retrieve information from Wikipedia.

## Setup

1. Install dependencies using Poetry:

```bash
poetry install
```

2. Set up your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```
OPENAI_API_KEY=your-api-key-here
```

## Usage

Run the main script:

```bash
poetry run python main.py
```

This will ask the question "where do capybaras live?" and print the answer.

## Project Structure

- `__init__.py` - Package initialization
- `tools.py` - Wikipedia API tools (search and get_page)
- `wikipedia_agent.py` - Agent definition using Pydantic AI
- `main.py` - Main entry point that runs the agent

## Tools

- `search_wikipedia(query)` - Searches Wikipedia for pages matching the query
- `get_wikipedia_page(title)` - Retrieves raw content of a Wikipedia page

