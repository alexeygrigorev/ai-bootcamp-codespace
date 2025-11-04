import asyncio
from typing import Any, Dict

import dotenv
import logfire

from jaxn import JSONParserHandler, StreamingJSONParser
import search_agent

from agent_logging import log_streamed_run, save_log

dotenv.load_dotenv()
logfire.configure()

logfire.instrument_pydantic_ai()


class SearchResultArticleHandler(JSONParserHandler):
    
    def on_field_start(self, path: str, field_name: str) -> None:
        if field_name == "references":
            header_level = path.count('/') + 2
            print(f"\n\n{'#' * header_level} References\n")
    
    def on_field_end(self, path: str, field_name: str, value: str, parsed_value: Any = None) -> None:
        if field_name == "title" and path == "":
            print(f"# {value}\n")
        
        if field_name == "heading":
            print(f"\n\n## {value}\n")
    
    def on_value_chunk(self, path: str, field_name: str, chunk: str) -> None:
        if field_name == "content":
            print(chunk, end="", flush=True)
    
    def on_array_item_end(self, path: str, field_name: str, item: Dict[str, Any] = None) -> None:
        if field_name == "references":
            print(f"- [{item['title']}]({item['filename']})")


async def main():
    user_input = "How do I monitor data drift in production?"

    agent = search_agent.create_agent()
    callback = search_agent.NamedCallback(agent)

    # result = await agent.run(user_input, event_stream_handler=callback)
    # article = result.output

    handler = SearchResultArticleHandler()
    parser = StreamingJSONParser(handler)

    previous_text = ""

    async with agent.run_stream(
        user_input, event_stream_handler=callback
    ) as result:
        async for item, last in result.stream_responses(debounce_by=0.01):
            for part in item.parts:
                if not hasattr(part, "tool_name"):
                    continue
                if part.tool_name != "final_result":
                    continue

                current_text = part.args
                delta = current_text[len(previous_text):]
                parser.parse_incremental(delta)
                previous_text = current_text

        log_entry = await log_streamed_run(agent, result)
        save_log(log_entry)


    # print(article.format_article())


if __name__ == "__main__":
    asyncio.run(main())