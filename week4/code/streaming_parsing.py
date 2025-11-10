
import time
from typing import Any, Dict
from jaxn import JSONParserHandler, StreamingJSONParser


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


with open("message.json", "r", encoding="utf-8") as f:
    data = f.read()


handler = SearchResultArticleHandler()
parser = StreamingJSONParser(handler)

for i in range(0, len(data), 4):
    chunk = data[i:i+4]
    parser.parse_incremental(chunk)
    time.sleep(0.01)
