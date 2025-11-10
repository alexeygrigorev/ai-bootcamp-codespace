
import search_agent
import asyncio

agent = search_agent.create_agent()
agent_callback = search_agent.NamedCallback(agent)


async def run_agent(user_prompt: str):
    results = await agent.run(
        user_prompt=user_prompt,
        event_stream_handler=agent_callback
    )

    return results


def run_agent_sync(user_prompt: str):
    return asyncio.run(run_agent(user_prompt))