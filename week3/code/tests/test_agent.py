
from tests.utils import get_tool_calls
from search_agent import SearchResultArticle
import main


def test_agent_makes_3_search_calls():
    user_prompt = "What is LLM evaluation?"
    result = main.run_agent_sync(user_prompt)

    print(result.output.format_article())

    tool_calls = get_tool_calls(result)
    assert len(tool_calls) >= 3, f"Expected at least 3 tool calls, got {len(tool_calls)}"

    article: SearchResultArticle = result.output
    assert len(article.sections) > 0, "Expected at least one section in the article"


def test_agent_adds_references():
    user_prompt = "What is LLM evaluation?"
    result = main.run_agent_sync(user_prompt)

    article: SearchResultArticle = result.output
    print(article.format_article())

    tool_calls = get_tool_calls(result)
    assert len(tool_calls) >= 3, f"Expected at least 3 tool calls, got {len(tool_calls)}"

    assert len(article.sections) > 0, "Expected at least one section in the article"
    assert len(article.references) > 0, "Expected at least one reference in the article"


def test_agent_code():
    user_prompt = "How do I implement LLM as a Judge eval?"
    result = main.run_agent_sync(user_prompt)

    article: SearchResultArticle = result.output
    print(article.format_article())

    assert len(article.sections) > 0, "Expected at least one section in the article"

    found_code = False

    for section in article.sections:
        if "```python" in section.content:
            found_code = True

    assert found_code, "Expected at least one code block in the article"


def test_agent_no_legal_domain():
    user_prompt = "what is llm as a judge evaluation"
    result = main.run_agent_sync(user_prompt)

    print(result.output.format_article())

    tool_calls = get_tool_calls(result)
    assert len(tool_calls) >= 3, f"Expected at least 3 tool calls, got {len(tool_calls)}"

    legal_terms = ["legal", "law", "court", "litigation"]

    for call in tool_calls:
        query = call.args.get("query", "").lower()
        for term in legal_terms:
            assert term not in query, "Did not expect legal domain in tool calls"


def test_agent_no_evidently_in_search_queries():
    user_prompt = "what is llm as a judge evaluation"
    result = main.run_agent_sync(user_prompt)

    print(result.output.format_article())

    tool_calls = get_tool_calls(result)
    assert len(tool_calls) >= 3, f"Expected at least 3 tool calls, got {len(tool_calls)}"

    for call in tool_calls:
        query = call.args.get("query", "").lower()
        assert "evidently" not in query, "Did not expect 'evidently' in search queries"


def test_agent_not_more_than_10_searches():
    user_prompt = "examples of incorrect LLM responses"
    result = main.run_agent_sync(user_prompt)

    print(result.output.found_answer)
    print(result.output.format_article())

    tool_calls = get_tool_calls(result)
    assert len(tool_calls) >= 3, f"Expected at least 3 tool calls, got {len(tool_calls)}"
    assert len(tool_calls) <= 10, f"Expected at most 10 tool calls, got {len(tool_calls)}"