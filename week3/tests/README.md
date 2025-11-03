# Wikipedia Agent Tests

Unit tests for the Wikipedia agent project.

## Test Coverage

The tests verify:

1. **Search tool is invoked** (`test_search_tool_is_invoked`)
   - Verifies that `search_wikipedia` is called when the agent runs
   - Checks that search queries include relevant terms

2. **Get page tool is invoked multiple times** (`test_get_page_tool_is_invoked_multiple_times`)
   - Verifies that `get_wikipedia_page` is called
   - Checks that it's called with titles from search results

3. **References are included** (`test_references_are_included`)
   - Verifies that the agent response includes citations/references
   - Checks for various reference indicators (Wikipedia links, citations, etc.)

4. **Full workflow** (`test_full_workflow`)
   - Tests the complete workflow: search → get pages → answer with references

5. **Tool functions** (`TestToolFunctions`)
   - Direct unit tests for `search_wikipedia` and `get_wikipedia_page` functions

## Running Tests

From the `week3/wikiagent` directory:

```bash
poetry run pytest ../tests/test_wikipedia_agent.py -v
```

To run a specific test:

```bash
poetry run pytest ../tests/test_wikipedia_agent.py::TestAgentToolInvocations::test_search_tool_is_invoked -v
```

## Test Structure

- `conftest.py` - Pytest fixtures and configuration
- `test_wikipedia_agent.py` - Main test file with all agent tests
- `pytest.ini` - Pytest configuration

## Test Strategy

The tests use mocking to:
- Replace Wikipedia API calls with mock data
- Track tool invocations via call logging
- Verify agent behavior without requiring actual API access
- Test agent instructions and prompt effectiveness

