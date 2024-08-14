# Use the Converse API to send a text message to Llama 2 Chat 70B.
import edsl
import boto3
from botocore.exceptions import ClientError

# Create a Bedrock Runtime client in the AWS Region you want to use.
all_models_ids = []
client = boto3.client('bedrock',region_name="us-west-2")
for  x in client.list_foundation_models()['modelSummaries']:
    all_models_ids.append(x['modelId'])

client = boto3.client("bedrock-runtime", region_name="us-west-2")

for model_id in all_models_ids:
    # Set the model ID, e.g., Titan Text Premier.

    # Start a conversation with the user message.
    user_message = """[INST]You are a a very intelligent bot with exceptional critical thinking[/INST]
    I went to the market and bought 10 apples. I gave 2 apples to your friend and 2 to the helper. I then went and bought 5 more apples and ate 1. How many apples did I remain with?

    Let's think step by step."""
    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]

    try:
        # Send the message to the model, using a basic inference configuration.
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens":512,"temperature":0.5,"topP":0.9},
            additionalModelRequestFields={}
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
        print("############",model_id,"###########")
        print(response_text)

    except (ClientError, Exception) as e:
        
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
