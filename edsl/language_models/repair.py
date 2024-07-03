import json
import asyncio

from rich import print
from rich.console import Console
from rich.syntax import Syntax

from edsl.utilities.utilities import clean_json

from edsl.utilities.repair_functions import extract_json_from_string

async def async_repair(bad_json, error_message="", user_prompt=None, system_prompt=None):
    s = clean_json(bad_json)

    try:
        # this is the OpenAI version, but that's fine
        valid_dict = json.loads(s)
        success = True
    except json.JSONDecodeError:
        valid_dict = {}
        success = False
        #print("Replacing control characters didn't work. Trying extracting the sub-string.")
    else:
        return valid_dict, success

    try:
        valid_dict = extract_json_from_string(s)
        success = True
        #print("Extracting the sub-string worked!")
    except ValueError:
        valid_dict = {}
        success = False
        #print("Extracting JSON didn't work. Trying with a LM model.")
        # console = Console()
        # error_message = f"[red]{str(bad_json)}[/red]"
        # console.print("    " + error_message)
    else:
        return valid_dict, success

    from edsl import Model
    m = Model()

    prompt = """
    A language model was supposed to respond to a question. 
    The response should have been JSON object with an answer to a question and some commentary.
    
    It should have retured a string like this: 
    
    '{'answer': 'The answer to the question.', 'comment': 'Some commentary.'}'
    
    or:

    '{'answer': 'The answer to the question.'}'

    The answer field is very like an integer number. The comment field is always string.

    You job is to return just the repaired JSON object that the model should have returned, properly formatted.

        - It might have included some preliminary comments.
        - It might have included some control characters.
        - It might have included some extraneous text.

    DO NOT include any extraneous text in your response. Just return the repaired JSON object.
    Do not preface the JSON object with any text. Just return the JSON object.

    Please repair this bad JSON: """ + str(bad_json)

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
        # this is the OpenAI version, but that's fine
        valid_dict = json.loads(results["choices"][0]["message"]["content"])
        success = True
    except json.JSONDecodeError:
        valid_dict = {}
        success = False
        console = Console()
        error_message = f"All repairs. failed. LLM Model given [red]{str(bad_json)}[/red]"
        console.print("    " + error_message)
        model_returned = results["choices"][0]["message"]["content"]
        console.print(f"LLM Model returned: [blue]{model_returned}[/blue]")


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
