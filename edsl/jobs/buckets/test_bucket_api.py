from edsl.jobs.buckets.BucketCollectionAPI import BucketAPI, ModelRequest


api = BucketAPI()
api.register_model(
    ModelRequest(model="gpt-4", tpm=90000, rpm=3500, inference_service="openai")
)

# Try to consume tokens
success = api.consume("gpt-4", tokens=100)
if success:
    print("Tokens consumed successfully")

# Get current status
status = api.get_status("gpt-4")
print(f"Tokens remaining: {status.tokens_remaining}")
