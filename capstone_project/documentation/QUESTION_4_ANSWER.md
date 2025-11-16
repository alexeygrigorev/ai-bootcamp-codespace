## Question 4: Framework and LLM Provider

### Answer

**Framework:** Pydantic AI (for POC) → LangChain (for production)

**LLM Provider:** OpenAI GPT-4o-mini (for POC) → AWS Bedrock with Claude Sonnet (for production)

### Rationale

For the proof-of-concept phase, we're using **Pydantic AI with OpenAI GPT-4o-mini** for rapid development and validation. Pydantic AI provides a clean, Pythonic API with built-in structured outputs (perfect for SEC filing metadata), and GPT-4o-mini offers cost-effective testing at $0.15/1M tokens with fast iteration cycles.

For production deployment, we'll migrate to **LangChain with AWS Bedrock** using Claude Sonnet models. This shift is driven by enterprise requirements: Bedrock provides SOC2/HIPAA compliance critical for financial data, multi-model flexibility (Claude for complex analysis, Llama for routine queries), and cost optimization through the right tool for the right task. LangChain's mature ecosystem, LangSmith observability, and provider-agnostic architecture support scalable deployment.

See `README_llm_framework.md` for detailed comparison, migration strategy, and implementation examples.

