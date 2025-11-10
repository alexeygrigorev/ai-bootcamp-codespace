import asyncio

import search_agent


async def main():
    user_input = "How do I monitor data drift in production?"

    agent = search_agent.create_agent()
    callback = search_agent.NamedCallback(agent)

    result = await agent.run(user_input, event_stream_handler=callback)
    article = result.output

    print(article.format_article())


if __name__ == "__main__":
    asyncio.run(main())