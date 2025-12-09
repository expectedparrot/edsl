import json
import asyncio
import warnings


async def async_repair(
    bad_json, error_message="", user_prompt=None, system_prompt=None, cache=None
):
    from ..utilities import clean_json

    s = clean_json(bad_json)

    try:
        # this is the OpenAI version, but that's fine
        valid_dict = json.loads(s)
        success = True
    except json.JSONDecodeError:
        valid_dict = {}
        success = False
        # print("Replacing control characters didn't work. Trying extracting the sub-string.")
    else:
        return valid_dict, success

    try:
        from ..utilities.repair_functions import extract_json_from_string

        valid_dict = extract_json_from_string(s)
        success = True
    except ValueError:
        valid_dict = {}
        success = False
    else:
        return valid_dict, success

    from ..questions.QuestionExtract import QuestionExtract

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)

        q = QuestionExtract(
            question_text="""
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

        Bad answer: """
            + str(bad_json)
            + "The model received a user prompt of: '"
            + str(user_prompt)
            + """'
        The model received a system prompt of: ' """
            + str(system_prompt)
            + """
        '
        Please return the repaired JSON object, following the instructions the original model should have followed, though 
        using 'new_answer' a nd 'new_comment' as the keys.""",
            answer_template={
                "new_answer": "<number, string, list, etc.>",
                "new_comment": "Model's comments",
            },
            question_name="model_repair",
        )

    results = await q.run_async(cache=cache)

    try:
        # this is the OpenAI version, but that's fine
        valid_dict = json.loads(json.dumps(results))
        success = True
        # this is to deal with the fact that the model returns the answer and comment as new_answer and new_comment
        valid_dict["answer"] = valid_dict.pop("new_answer")
        valid_dict["comment"] = valid_dict.pop("new_comment")
    except json.JSONDecodeError:
        valid_dict = {}
        success = False
        from rich.console import Console

        console = Console()
        error_message = (
            f"All repairs. failed. LLM Model given [red]{str(bad_json)}[/red]"
        )
        console.print("    " + error_message)
        model_returned = results["choices"][0]["message"]["content"]
        console.print(f"LLM Model returned: [blue]{model_returned}[/blue]")

    return valid_dict, success


def repair_wrapper(
    bad_json, error_message="", user_prompt=None, system_prompt=None, cache=None
):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Add repair as a task to the running loop
            task = loop.create_task(
                async_repair(bad_json, error_message, user_prompt, system_prompt, cache)
            )
            return task
        else:
            # Run a new event loop for repair
            return loop.run_until_complete(
                async_repair(bad_json, error_message, user_prompt, system_prompt, cache)
            )
    except RuntimeError:
        # Create a new event loop if one is not already available
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            async_repair(bad_json, error_message, user_prompt, system_prompt, cache)
        )


def repair(
    bad_json, error_message="", user_prompt=None, system_prompt=None, cache=None
):
    return repair_wrapper(bad_json, error_message, user_prompt, system_prompt, cache)


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
