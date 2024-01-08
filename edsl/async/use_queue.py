import asyncio
import random


async def get_data():
    time_delay = random.randint(1, 10)
    # print(f"start fetching; wait {time_delay} seconds")
    await asyncio.sleep(time_delay)
    # print(f"done fetching; waited {time_delay} seconds")
    return {"data": time_delay}


async def process_data(queue):
    while True:
        data = await queue.get()
        if data is None:  # Sentinel value to indicate completion
            break
        # print(f"Processed data: {data}")


async def get_multiple_data(queue):
    tasks = [get_data() for _ in range(10)]
    for task in asyncio.as_completed(tasks):
        result = await task
        await queue.put(result)
    await queue.put(None)  # Add sentinel value to indicate all tasks are done


if __name__ == "__main__":

    def main():
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        # Run data fetching and processing coroutines
        loop.run_until_complete(
            asyncio.gather(get_multiple_data(queue), process_data(queue))
        )

        loop.close()
