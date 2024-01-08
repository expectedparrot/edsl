import asyncio
import random

###############
## Base Example
###############


async def get_data():
    time_delay = random.randint(1, 10)
    print(f"start fetching; wait {time_delay}")
    await asyncio.sleep(time_delay)
    print(f"done fetching; wait {time_delay}")
    return {"data": time_delay}


async def get_multiple_data():
    tasks = [get_data() for _ in range(10)]
    result = await asyncio.gather(*tasks)
    #    print(result)
    return result


async def get_multiple_data_stream():
    tasks = [get_data() for _ in range(10)]
    for task in asyncio.as_completed(tasks):
        result = await task
        print(f"Task completed with result: {result}")


def sim_stream():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_multiple_data_stream())
    loop.close()


if __name__ == "__main__":
    if False:
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(get_multiple_data())
        loop.close()


####################
## Streaming Example
####################
