from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Union, Dict
from typing import Optional

from .token_bucket import TokenBucket  # Original implementation
from .exceptions import BucketNotFoundError, InvalidBucketParameterError

def safe_float_for_json(value: float) -> Union[float, str]:
    """Convert float('inf') to 'infinity' for JSON serialization.

    Args:
        value: The float value to convert

    Returns:
        Either the original float or the string 'infinity' if the value is infinite
    """
    if value == float("inf"):
        return "infinity"
    return value


app = FastAPI()

# In-memory storage for TokenBucket instances
buckets: Dict[str, TokenBucket] = {}

@app.exception_handler(BucketNotFoundError)
async def bucket_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )

@app.exception_handler(InvalidBucketParameterError)
async def invalid_parameter_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


class TokenBucketCreate(BaseModel):
    bucket_name: str
    bucket_type: str
    capacity: Union[int, float]
    refill_rate: Union[int, float]


@app.get("/buckets")
async def list_buckets(
    bucket_type: Optional[str] = None,
    bucket_name: Optional[str] = None,
    include_logs: bool = False,
):
    """List all buckets and their current status.

    Args:
        bucket_type: Optional filter by bucket type
        bucket_name: Optional filter by bucket name
        include_logs: Whether to include the full logs in the response
    """
    result = {}

    for bucket_id, bucket in buckets.items():
        # Apply filters if specified
        if bucket_type and bucket.bucket_type != bucket_type:
            continue
        if bucket_name and bucket.bucket_name != bucket_name:
            continue

        # Get basic bucket info
        bucket_info = {
            "bucket_name": bucket.bucket_name,
            "bucket_type": bucket.bucket_type,
            "tokens": bucket.tokens,
            "capacity": bucket.capacity,
            "refill_rate": bucket.refill_rate,
            "turbo_mode": bucket.turbo_mode,
            "num_requests": bucket.num_requests,
            "num_released": bucket.num_released,
            "tokens_returned": bucket.tokens_returned,
        }
        for k, v in bucket_info.items():
            if isinstance(v, float):
                bucket_info[k] = safe_float_for_json(v)

        # Only include logs if requested
        if include_logs:
            bucket_info["log"] = bucket.log

        result[bucket_id] = bucket_info

    return result


@app.post("/bucket/{bucket_id}/add_tokens")
async def add_tokens(bucket_id: str, amount: float):
    """Add tokens to an existing bucket."""
    if bucket_id not in buckets:
        raise BucketNotFoundError(f"Bucket with ID '{bucket_id}' not found")

    if not isinstance(amount, (int, float)) or amount != amount:  # Check for NaN
        raise InvalidBucketParameterError("Invalid amount specified")

    if amount == float("inf") or amount == float("-inf"):
        raise InvalidBucketParameterError("Amount cannot be infinite")

    bucket = buckets[bucket_id]
    bucket.add_tokens(amount)

    # Ensure we return a JSON-serializable float
    current_tokens = float(bucket.tokens)
    if not -1e308 <= current_tokens <= 1e308:  # Check if within JSON float bounds
        current_tokens = 0.0  # or some other reasonable default

    return {"status": "success", "current_tokens": safe_float_for_json(current_tokens)}


# @app.post("/bucket")
# async def create_bucket(bucket: TokenBucketCreate):
#     bucket_id = f"{bucket.bucket_name}_{bucket.bucket_type}"
#     if bucket_id in buckets:
#         raise HTTPException(status_code=400, detail="Bucket already exists")

#     # Create an actual TokenBucket instance
#     buckets[bucket_id] = TokenBucket(
#         bucket_name=bucket.bucket_name,
#         bucket_type=bucket.bucket_type,
#         capacity=bucket.capacity,
#         refill_rate=bucket.refill_rate,
#     )
#     return {"status": "created"}


@app.post("/bucket")
async def create_bucket(bucket: TokenBucketCreate):
    if (
        not isinstance(bucket.capacity, (int, float))
        or bucket.capacity != bucket.capacity
    ):  # Check for NaN
        raise InvalidBucketParameterError("Invalid capacity value")
    if (
        not isinstance(bucket.refill_rate, (int, float))
        or bucket.refill_rate != bucket.refill_rate
    ):  # Check for NaN
        raise InvalidBucketParameterError("Invalid refill rate value")
    if bucket.capacity == float("inf") or bucket.refill_rate == float("inf"):
        raise InvalidBucketParameterError("Values cannot be infinite")
    bucket_id = f"{bucket.bucket_name}_{bucket.bucket_type}"
    if bucket_id in buckets:
        # Instead of error, return success with "existing" status
        return {
            "status": "existing",
            "bucket": {
                "capacity": safe_float_for_json(buckets[bucket_id].capacity),
                "refill_rate": safe_float_for_json(buckets[bucket_id].refill_rate),
            },
        }

    # Create a new bucket
    buckets[bucket_id] = TokenBucket(
        bucket_name=bucket.bucket_name,
        bucket_type=bucket.bucket_type,
        capacity=bucket.capacity,
        refill_rate=bucket.refill_rate,
    )
    return {"status": "created"}


@app.post("/bucket/{bucket_id}/get_tokens")
async def get_tokens(bucket_id: str, amount: float, cheat_bucket_capacity: bool = True):
    if bucket_id not in buckets:
        raise BucketNotFoundError(f"Bucket with ID '{bucket_id}' not found")

    bucket = buckets[bucket_id]
    await bucket.get_tokens(amount, cheat_bucket_capacity)
    return {"status": "success"}


@app.post("/bucket/{bucket_id}/turbo_mode/{state}")
async def set_turbo_mode(bucket_id: str, state: bool):
    if bucket_id not in buckets:
        raise BucketNotFoundError(f"Bucket with ID '{bucket_id}' not found")

    bucket = buckets[bucket_id]
    if state:
        bucket.turbo_mode_on()
    else:
        bucket.turbo_mode_off()
    return {"status": "success"}


@app.get("/bucket/{bucket_id}/status")
async def get_bucket_status(bucket_id: str):
    if bucket_id not in buckets:
        raise BucketNotFoundError(f"Bucket with ID '{bucket_id}' not found")

    bucket = buckets[bucket_id]
    status = {
        "tokens": bucket.tokens,
        "capacity": bucket.capacity,
        "refill_rate": bucket.refill_rate,
        "turbo_mode": bucket.turbo_mode,
        "num_requests": bucket.num_requests,
        "num_released": bucket.num_released,
        "tokens_returned": bucket.tokens_returned,
        "log": bucket.log,
    }
    for k, v in status.items():
        if isinstance(v, float):
            status[k] = safe_float_for_json(v)

    for index, entry in enumerate(status["log"]):
        ts, value = entry
        status["log"][index] = (ts, safe_float_for_json(value))

    # print(status)
    return status


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
