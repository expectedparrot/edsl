import pytest
import boto3
from botocore.exceptions import ClientError


@pytest.fixture(scope="module")
def bedrock_client():
    return boto3.client("bedrock", region_name="us-west-2")


@pytest.fixture(scope="module")
def bedrock_runtime_client():
    return boto3.client("bedrock-runtime", region_name="us-west-2")


@pytest.fixture(scope="module")
def all_model_ids(bedrock_client):
    return [
        x["modelId"] for x in bedrock_client.list_foundation_models()["modelSummaries"]
    ]


# TODO: this test is uninformative, because it can't fail
def test_converse_with_models(bedrock_runtime_client, all_model_ids):
    user_message = """[INST]You are a a very intelligent bot with exceptional critical thinking[/INST]
    I went to the market and bought 10 apples. I gave 2 apples to your friend and 2 to the helper. I then went and bought 5 more apples and ate 1. How many apples did I remain with?

    Let's think step by step."""

    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]

    for model_id in all_model_ids:
        try:
            response = bedrock_runtime_client.converse(
                modelId=model_id,
                messages=conversation,
                inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
                additionalModelRequestFields={},
            )
            response_text = response["output"]["message"]["content"][0]["text"]
            print(f"############ {model_id} ###########")
            print(response_text)
        except (ClientError, Exception) as e:
            print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
            continue
