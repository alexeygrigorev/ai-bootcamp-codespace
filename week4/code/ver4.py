import asyncio
import json
import queue
import threading
import time
from typing import Any, Dict, List

import streamlit as st
from jaxn import JSONParserHandler, StreamingJSONParser

import search_agent
from pydantic_ai.messages import FunctionToolCallEvent


class StreamlitCallback(search_agent.NamedCallback):
    """A NamedCallback variant that pushes tool call lines to a queue.

    Mirrors search_agent.NamedCallback behavior but writes to a thread-safe
    queue instead of printing, so Streamlit can render them live.
    """

    def __init__(self, agent, tool_queue: "queue.Queue[str]"):
        super().__init__(agent)
        self._tool_queue = tool_queue

    async def print_function_calls(self, ctx, event):
        # Detect nested streams
        if hasattr(event, "__aiter__"):
            async for sub in event:
                await self.print_function_calls(ctx, sub)
            return

        if isinstance(event, FunctionToolCallEvent):
            tool_name = event.part.tool_name
            args = event.part.args
            try:
                args_str = json.dumps(args, ensure_ascii=False)
            except Exception:
                args_str = str(args)
            line = f"TOOL CALL ({self.agent_name}): {tool_name}({args_str})"
            self._tool_queue.put(line)


class StreamlitArticleHandler(JSONParserHandler):
    """Incrementally renders the SearchResultArticle JSON as Markdown in Streamlit."""

    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.buffer: List[str] = []

    def _flush(self):
        # Render the full buffer as markdown
        self.placeholder.markdown("".join(self.buffer))

    def on_field_start(self, path: str, field_name: str) -> None:
        if field_name == "references":
            header_level = path.count('/') + 2
            self.buffer.append(f"\n\n{'#' * header_level} References\n\n")
            self._flush()

    def on_field_end(self, path: str, field_name: str, value: str, parsed_value: Any = None) -> None:
        if field_name == "title" and path == "":
            self.buffer.append(f"# {value}\n\n")
            self._flush()
        if field_name == "heading":
            self.buffer.append(f"\n\n## {value}\n\n")
            self._flush()

    def on_value_chunk(self, path: str, field_name: str, chunk: str) -> None:
        if field_name == "content":
            self.buffer.append(chunk)
            self._flush()

    def on_array_item_end(self, path: str, field_name: str, item: Dict[str, Any] = None) -> None:
        if field_name == "references":
            # Expecting dict with 'title' and 'filename'
            title = item.get('title') if isinstance(item, dict) else None
            filename = item.get('filename') if isinstance(item, dict) else None
            if title and filename:
                self.buffer.append(f"- [{title}]({filename})\n")
                self._flush()


def _run_agent_stream(user_input: str, agent, tool_q: "queue.Queue[str]", text_q: "queue.Queue[str]"):
    async def _do():
        callback = StreamlitCallback(agent, tool_q)
        previous_text = ""

        async with agent.run_stream(user_input, event_stream_handler=callback) as result:
            async for item, last in result.stream_responses(debounce_by=0.01):
                for part in item.parts:
                    if not hasattr(part, "tool_name"):
                        continue
                    if part.tool_name != "final_result":
                        continue

                    current_text = part.args
                    delta = current_text[len(previous_text):]
                    if delta:
                        text_q.put(delta)
                    previous_text = current_text

        # Signal completion
        text_q.put(None)
        tool_q.put(None)

    asyncio.run(_do())


def _stream_to_ui(text_q: "queue.Queue[str]", tool_q: "queue.Queue[str]", tools_placeholder, output_placeholder) -> str:
    # Setup the streaming JSON parser for the final_result content
    handler = StreamlitArticleHandler(output_placeholder)
    parser = StreamingJSONParser(handler)

    tool_lines: List[str] = []
    tools_done = False

    while True:
        # Drain any available tool-call lines first so users see tools quickly
        while not tools_done:
            try:
                t = tool_q.get_nowait()
            except queue.Empty:
                break
            if t is None:
                tools_done = True
                break
            tool_lines.append(t)
            # Render tool calls as a bullet list
            if tool_lines:
                tools_placeholder.markdown("\n".join(f"- {line}" for line in tool_lines))

        # Then, try to read a chunk of the final_result JSON
        try:
            chunk = text_q.get(timeout=0.05)
        except queue.Empty:
            # No chunk yet; small wait keeps the loop cooperative
            time.sleep(0.01)
            continue

        if chunk is None:
            break

        parser.parse_incremental(chunk)

    # Return the full rendered markdown for history
    return "".join(handler.buffer)


def _get_agent():
    if "agent" not in st.session_state:
        st.session_state.agent = search_agent.create_agent()
    return st.session_state.agent


def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []  # {role: "user"|"assistant", content: str}


def main():
    st.set_page_config(page_title="Search Agent Chat", page_icon="🔎", layout="wide")
    st.title("🔎 Evidently Search Agent")
    st.caption("Ask about Evidently docs. Streams tool calls and results.")

    init_state()
    agent = _get_agent()

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])  # content already markdown-ready for assistant

    # Chat input
    prompt = st.chat_input("Type your question about Evidently…")
    if not prompt:
        return

    # Show user's message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant streaming container
    with st.chat_message("assistant"):
        st.markdown("**Tool Calls**")
        tools_placeholder = st.empty()
        st.markdown("---")
        st.markdown("**Answer**")
        output_placeholder = st.empty()

        # Queues for tool calls and output deltas
        tool_q: queue.Queue[str] = queue.Queue()
        text_q: queue.Queue[str] = queue.Queue()

        # Run the agent streaming in a background thread
        t = threading.Thread(
            target=_run_agent_stream,
            args=(prompt, agent, tool_q, text_q),
            daemon=True,
        )
        t.start()

        # Consume both streams and render incrementally
        assistant_markdown = _stream_to_ui(text_q, tool_q, tools_placeholder, output_placeholder)

    # Persist last assistant message as markdown rendered by the handler
    # We don't have direct access to handler buffer here, but output_placeholder
    # already rendered the full content. To keep history, fetch the element's
    # last value by re-parsing via queues isn't trivial, so we store a simple
    # note. For a full history, one could capture the handler buffer in state.
    # To keep it simple and reliable, we snapshot the page region using the
    # prompt as a divider; here we append a lightweight marker.
    st.session_state.messages.append({
        "role": "assistant",
        "content": assistant_markdown or "(No content returned)",
    })


if __name__ == "__main__":
    main()
