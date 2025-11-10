import pickle

from pathlib import Path
from typing import Any, Dict, List

from minsearch import Index

import docs


class SearchTools:
    def __init__(self, index: Index, file_index: dict[str, Any], top_k: int):
        self.index = index
        self.file_index = file_index
        self.top_k = top_k

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the index for documents matching the given query.

        Args:
            query (str): The search query string.

        Returns:
            A list of search results
        """
        return self.index.search(
            query=query,
            num_results=5,
        )

    def read_file(self, filename: str) -> str:
        """
        Retrieve the contents of a file from the file index if it exists.

        Args:
            filename (str): The name of the file to read.

        Returns:
            str: The file's contents if found, otherwise an error message
            indicating that the file does not exist.
        """
        if filename in self.file_index:
            return self.file_index[filename]
        return "File doesn't exist"


def load_data():
    github_data = docs.read_github_data()
    parsed_data = docs.parse_data(github_data)
    return parsed_data


def prepare_search_index(parsed_data, chunk_size: int, chunk_step: int):
    chunks = docs.chunk_documents(parsed_data, size=chunk_size, step=chunk_step)

    index = Index(text_fields=["title", "description", "content"])

    index.fit(chunks)
    return index


def prepare_file_index(parsed_data):
    file_index = {}

    for item in parsed_data:
        filename = item["filename"]
        content = item["content"]
        file_index[filename] = content

    return file_index


def _prepare_search_tools(chunk_size: int, chunk_step: int, top_k: int):
    parsed_data = load_data()

    search_index = prepare_search_index(
        parsed_data=parsed_data,
        chunk_size=chunk_size,
        chunk_step=chunk_step
    )

    file_index = prepare_file_index(parsed_data=parsed_data)

    return SearchTools(
        index=search_index,
        file_index=file_index,
        top_k=top_k
    )


def prepare_search_tools(chunk_size: int, chunk_step: int, top_k: int):
    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)

    cache_file = cache_dir / f"search_tools_{chunk_size}_{chunk_step}_{top_k}.bin"

    if cache_file.exists():
        with open(cache_file, "rb") as f:
            search_tools = pickle.load(f)
            return search_tools

    search_tools = _prepare_search_tools(
        chunk_size=chunk_size, chunk_step=chunk_step, top_k=top_k
    )

    with open(cache_file, "wb") as f:
        pickle.dump(search_tools, f)

    return search_tools


if __name__ == "__main__":
    search_tools = prepare_search_tools()
    results = search_tools.search("data drift")
    for r in results:
        print(r)
