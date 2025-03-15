import threading
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import json

app = FastAPI()


async def generate_response(question_number: int) -> dict:
    # Simulate some asynchronous work
    await asyncio.sleep(1)
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo-0613",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"answer": f"SPAM for question {question_number}!"}
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    user_prompt = body["messages"][-1]["content"]
    question_number = int(user_prompt.split("XX")[1])

    response = await generate_response(question_number)
    return JSONResponse(content=response)


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    # Start the server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

# Your main code here
# ...

# To use this with the OpenAI SDK:
# from openai import AsyncOpenAI
# client = AsyncOpenAI(base_url="http://127.0.0.1:8000/v1", api_key="fake_key")
# response = await client.chat.completions.create(model="gpt-3.5-turbo", messages=[...])
