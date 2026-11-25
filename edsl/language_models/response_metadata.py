"""Normalize provider termination and token-usage evidence without parsing answers."""


def _text_present(content):
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(part, dict)
            and not part.get("thought", False)
            and part.get("type") not in ("thinking", "reasoning")
            and bool(str(part.get("text") or "").strip())
            for part in content
        )
    return False


def response_metadata(response) -> dict:
    """Keep absent usage as None; reasoning is a subset of completion tokens.

    Google reports visible candidate and thought tokens separately; OpenAI and
    Anthropic include reasoning in their output/completion total.
    """
    if not isinstance(response, dict):
        return {}
    finish = response.get("stop_reason") or response.get("stopReason")
    incomplete = (response.get("incomplete_details") or {}).get("reason")
    visible = None
    usage = response.get("usage") or {}
    input_tokens = usage.get(
        "prompt_tokens", usage.get("input_tokens", usage.get("inputTokens"))
    )
    completion = usage.get(
        "completion_tokens", usage.get("output_tokens", usage.get("outputTokens"))
    )
    details = (
        usage.get("completion_tokens_details")
        or usage.get("output_tokens_details")
        or {}
    )
    reasoning = details.get("reasoning_tokens", usage.get("reasoning_tokens"))
    total = usage.get("total_tokens", usage.get("totalTokens"))
    if response.get("choices"):
        choice = response["choices"][0]
        finish = choice.get("finish_reason")
        visible = _text_present(
            (choice.get("message") or {}).get("content", choice.get("text"))
        )
    elif "output" in response and isinstance(response["output"], list):
        visible = any(
            item.get("type") == "message" and _text_present(item.get("content"))
            for item in response["output"]
            if isinstance(item, dict)
        )
    elif "content" in response:
        visible = _text_present(response["content"])
    elif response.get("candidates"):
        candidate = response["candidates"][0]
        finish = candidate.get("finish_reason", candidate.get("finishReason"))
        visible = _text_present((candidate.get("content") or {}).get("parts"))
    elif isinstance(response.get("output"), dict):
        visible = _text_present(
            (response["output"].get("message") or {}).get("content")
        )

    google_usage = response.get("usage_metadata") or response.get("usageMetadata")
    if google_usage:
        input_tokens = google_usage.get(
            "prompt_token_count", google_usage.get("promptTokenCount")
        )
        reasoning = google_usage.get(
            "thoughts_token_count", google_usage.get("thoughtsTokenCount")
        )
        output = google_usage.get(
            "candidates_token_count", google_usage.get("candidatesTokenCount")
        )
        completion = (
            (output or 0) + (reasoning or 0)
            if output is not None or reasoning is not None
            else None
        )
        total = google_usage.get(
            "total_token_count", google_usage.get("totalTokenCount")
        )
    else:
        output = (
            max(0, completion - reasoning)
            if isinstance(completion, int) and isinstance(reasoning, int)
            else None
        )

    if (
        finish is None
        and incomplete is None
        and visible is None
        and not usage
        and not google_usage
    ):
        return {}
    truncated = str(finish or incomplete or "").lower() in {
        "length",
        "max_tokens",
        "max_output_tokens",
        "model_length",
    }
    return {
        "finish_reason": finish,
        "incomplete_reason": incomplete,
        "truncated": truncated,
        "visible_answer_present": visible,
        "input_tokens": input_tokens,
        "reasoning_tokens": reasoning,
        "visible_output_tokens": output,
        "completion_tokens": completion,
        "total_tokens": total,
    }
