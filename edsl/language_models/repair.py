import json


def repair(bad_json, error_message=""):
    from edsl.language_models import LanguageModelOpenAIFour

    m = LanguageModelOpenAIFour()
    results = m.execute_model_call(
        f"""Please repair this bad JSON: {bad_json}."""
        + (f"Parsing error message: {error_message}" if error_message else ""),
        system_prompt="You are a helpful agent. Only return the repaired JSON, nothing else.",
    )
    success = True
    try:
        valid_dict = json.loads(results["choices"][0]["message"]["content"])
    except json.JSONDecodeError:
        success = False
        valid_dict = {}
    return valid_dict, success


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
