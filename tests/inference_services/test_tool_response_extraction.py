from edsl.language_models.raw_response_handler import RawResponseHandler


def test_anthropic_tool_response_uses_text_after_tool_use():
    handler = RawResponseHandler(
        key_sequence=["content", 0, "text"], inference_service="anthropic"
    )
    response = {
        "content": [
            {"type": "text", "text": "I will search for that."},
            {"type": "server_tool_use", "id": "tool_1", "name": "web_search"},
            {"type": "web_search_tool_result", "content": []},
            {"type": "text", "text": "Here is the answer."},
        ]
    }

    assert handler.get_generated_token_string(response) == "Here is the answer."


def test_openai_responses_tool_call_uses_final_message():
    handler = RawResponseHandler(
        key_sequence=["output", 1, "content", 0, "text"],
        inference_service="openai_v2",
    )
    response = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "I will search for that."}],
            },
            {"type": "web_search_call", "id": "tool_1"},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Here is the answer."}],
            },
        ]
    }

    assert handler.get_generated_token_string(response) == "Here is the answer."
