from openai import AsyncOpenAI
import asyncio

client = AsyncOpenAI(base_url="http://127.0.0.1:8000/v1", api_key="fake_key")


async def main():
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Question XX42"}]
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
