from edsl.inference_services.services.aws_bedrock import AwsBedrockService


def test_manual_claude_thinking_budget_respects_output_limit():
    model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    assert AwsBedrockService._thinking_request_fields(model_id, 5000) == {
        "thinking": {"type": "enabled", "budget_tokens": 4999}
    }
    assert AwsBedrockService._thinking_request_fields(model_id, 1024) == {}


def test_manual_claude_thinking_uses_temperature_one():
    config = AwsBedrockService._build_inference_config(
        "anthropic.claude-3-7-sonnet-20250219-v1:0",
        max_tokens=16000,
        temperature=0.5,
        top_p=0.9,
    )
    assert config["temperature"] == 1.0
