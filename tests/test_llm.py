
import asyncio
from dotenv import load_dotenv
from llm_client import LLMClient

load_dotenv()


async def main():
    client = LLMClient()

    response = await client.chat(
        system="You are a helpful assistant.",
        user="Which number is larger, 9.11 or 9.8?",
    )

    print("Response:", response.content)
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Input tokens:", response.tokens_in)
    print("Output tokens:", response.tokens_out)
    print("Estimated cost:", response.cost_usd)
    print("Latency:", response.latency_ms, "ms")


if __name__ == "__main__":
    asyncio.run(main())
