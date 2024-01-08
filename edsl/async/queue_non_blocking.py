import asyncio
import random


async def get_data(queue):
    time_delay = random.randint(1, 10)
    # print(f"start fetching; wait {time_delay} seconds")
    await asyncio.sleep(time_delay)
    # print(f"done fetching; waited {time_delay} seconds")
    await queue.put({"data": time_delay})


async def process_data(queue):
    while True:
        data = await queue.get()
        if data is None:  # Sentinel value to indicate completion
            break
        # print(f"Processed data: {data}")
    # print("All data processed.")


async def get_multiple_data(queue, num_tasks):
    tasks = [asyncio.create_task(get_data(queue)) for _ in range(num_tasks)]
    await asyncio.gather(*tasks)
    await queue.put(None)  # Add sentinel value to indicate all tasks are done


def main():
    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    # Run data fetching and processing coroutines
    loop.run_until_complete(
        asyncio.gather(get_multiple_data(queue, 10), process_data(queue))
    )

    loop.close()


if __name__ == "__main__":
    # main()
    pass
