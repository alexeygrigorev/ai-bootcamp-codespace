import pytest
import scenario
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
import main


scenario.configure(default_model="openai/gpt-4o-mini")

class SearchAgentAdapter(scenario.AgentAdapter):

    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        user_prompt = input.last_new_user_message_str()
        result = await main.run_agent(user_prompt)
        new_messages = result.new_messages()
        return await self.convert_to_openai_format(new_messages)

    async def convert_to_openai_format(self, messages):
        openai_model = OpenAIChatModel("any")
        new_messages_openai_format = []
        for openai_message in await openai_model._map_messages(messages):
            new_messages_openai_format.append(openai_message)

        return new_messages_openai_format


@pytest.mark.asyncio
async def test_agent_code():
    
    user_prompt = "How do I implement LLM as a Judge eval?"

    result = await scenario.run(
        name="Evidently Search Agent Code Test",
        description="""
            User asks for help with implementing LLM as a Judge evaluation in Evidently.
        """,
        agents=[
            SearchAgentAdapter(),
            scenario.UserSimulatorAgent(),
            scenario.JudgeAgent(
                criteria=[
                    "Provides accurate and relevant code examples",
                    "Explains code implementation clearly",
                    "Contains at least one code python block in the article",
                    "Contains references"
                ],
            ),
        ],
        max_turns=2,
        set_id="python-examples",  # Add set_id parameter
    )

    assert result.success