from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Union, Dict
import time
from typing import Union, List, Any, Optional
import asyncio
from threading import RLock
from edsl.jobs.buckets.TokenBucket import TokenBucket  # Original implementation

app = FastAPI()

# In-memory storage for TokenBucket instances
buckets: Dict[str, TokenBucket] = {}


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

        # Only include logs if requested
        if include_logs:
            bucket_info["log"] = bucket.log

        result[bucket_id] = bucket_info

    return result


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
    bucket_id = f"{bucket.bucket_name}_{bucket.bucket_type}"
    if bucket_id in buckets:
        # Instead of error, return success with "existing" status
        return {
            "status": "existing",
            "bucket": {
                "capacity": buckets[bucket_id].capacity,
                "refill_rate": buckets[bucket_id].refill_rate,
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
        raise HTTPException(status_code=404, detail="Bucket not found")

    bucket = buckets[bucket_id]
    await bucket.get_tokens(amount, cheat_bucket_capacity)
    return {"status": "success"}


@app.post("/bucket/{bucket_id}/turbo_mode/{state}")
async def set_turbo_mode(bucket_id: str, state: bool):
    if bucket_id not in buckets:
        raise HTTPException(status_code=404, detail="Bucket not found")

    bucket = buckets[bucket_id]
    if state:
        bucket.turbo_mode_on()
    else:
        bucket.turbo_mode_off()
    return {"status": "success"}


@app.get("/bucket/{bucket_id}/status")
async def get_bucket_status(bucket_id: str):
    if bucket_id not in buckets:
        raise HTTPException(status_code=404, detail="Bucket not found")

    bucket = buckets[bucket_id]
    return {
        "tokens": bucket.tokens,
        "capacity": bucket.capacity,
        "refill_rate": bucket.refill_rate,
        "turbo_mode": bucket.turbo_mode,
        "num_requests": bucket.num_requests,
        "num_released": bucket.num_released,
        "tokens_returned": bucket.tokens_returned,
        "log": bucket.log,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
