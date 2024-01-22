import json
import asyncio


async def async_repair(bad_json, error_message=""):
    from edsl.language_models import LanguageModelOpenAIFour

    m = LanguageModelOpenAIFour()

    prompt = f"""This is the output from a less capable language model.  
    It was supposed to respond with just a JSON object with an answer to a question and some commentary, 
    in a field called "comment" next to "answer".
    Please repair this bad JSON: {bad_json}."""

    if error_message:
        prompt += f" Parsing error message: {error_message}"

    try:
        results = await m.async_execute_model_call(
            prompt,
            system_prompt="You are a helpful agent. Only return the repaired JSON, nothing else.",
        )
    except Exception as e:
        return {}, False

    try:
        valid_dict = json.loads(results["choices"][0]["message"]["content"])
        success = True
    except json.JSONDecodeError:
        valid_dict = {}
        success = False

    return valid_dict, success


def repair_wrapper(bad_json, error_message=""):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Add repair as a task to the running loop
            task = loop.create_task(async_repair(bad_json, error_message))
            return task
        else:
            # Run a new event loop for repair
            return loop.run_until_complete(async_repair(bad_json, error_message))
    except RuntimeError:
        # Create a new event loop if one is not already available
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(async_repair(bad_json, error_message))


def repair(bad_json, error_message=""):
    return repair_wrapper(bad_json, error_message)


# Example usage:
# result, success = repair_wrapper('{"name": "John Doe", "age": 30,}')  # example bad JSON


# def repair_wrapper(bad_json, error_message=""):
#     loop = asyncio.get_event_loop()
#     if loop.is_running():
#         # Add repair as a task to the running loop
#         task = loop.create_task(repair(bad_json, error_message))
#         return task
#     else:
#         # Run a new event loop for repair
#         return loop.run_until_complete(repair(bad_json, error_message))


# Example usage:
# result, success = repair_wrapper('{"name": "John Doe", "age": 30,}')  # example bad JSON


if __name__ == "__main__":
    bad_json = """
    {
      'answer': "The problematic phrase in the excerpt is \'typically\'. This word is vague and can lead to different interpretations. An alternative phrasing that would be less problematic is: 
      'On average, how long do you cook scrambled eggs?}
    """
    try:
        json.loads(bad_json)
        print("Loaded")
    except json.JSONDecodeError as e:
        error_message = str(e)
        repaired, success = repair(bad_json, error_message)
        print(f"Repaired: {repaired}")
