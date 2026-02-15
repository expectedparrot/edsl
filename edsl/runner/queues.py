"""
Queue System for Rate-Limited LLM Execution

Components:
- TokenBucket: Rate limiting with RPM and TPM
- Queue: Task queue with token buckets
- DispatchHeap: Priority queue ordered by availability time
- QueueRegistry: Manages all queues, routes tasks
"""

from dataclasses import dataclass, field
from typing import Any
import time
import heapq
import threading
import logging

from .models import generate_id

# Configure logging for queue operations
logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Tokens refill continuously at `rate` tokens/second up to `capacity`.
    Can go negative after reconciliation if actual usage exceeded estimate.
    """

    capacity: float
    rate: float  # tokens per second
    tokens: float = field(default=None)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.tokens is None:
            self.tokens = self.capacity

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def try_acquire(self, amount: float) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        self.refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def time_until_available(self, amount: float) -> float:
        """Calculate seconds until `amount` tokens are available."""
        self.refill()
        if self.tokens >= amount:
            return 0.0
        return (amount - self.tokens) / self.rate

    def reconcile(self, estimated: float, actual: float) -> None:
        """Adjust tokens after actual usage is known."""
        delta = estimated - actual
        self.tokens = min(self.capacity, self.tokens + delta)


@dataclass
class QueueMeta:
    """Metadata for a queue."""

    queue_id: str
    service: str
    model: str
    api_key: str
    rpm_limit: int
    tpm_limit: int


class Queue:
    """
    A rate-limited queue for a specific (service, model, api_key) combination.

    Maintains:
    - RPM bucket (requests per minute)
    - TPM bucket (tokens per minute)
    - FIFO task list
    - Depth counter
    """

    def __init__(
        self,
        queue_id: str,
        service: str,
        model: str,
        api_key: str,
        rpm_limit: int = 60,
        tpm_limit: int = 100000,
    ):
        self.queue_id = queue_id
        self.service = service
        self.model = model
        self.api_key = api_key

        # Token buckets
        self.rpm_bucket = TokenBucket(
            capacity=float(rpm_limit), rate=rpm_limit / 60.0  # per second
        )
        self.tpm_bucket = TokenBucket(
            capacity=float(tpm_limit), rate=tpm_limit / 60.0  # per second
        )

        # Task queue (FIFO)
        self._tasks: list[dict] = []
        self._lock = threading.Lock()

        # Throughput tracking
        self._request_count = 0
        self._token_count = 0
        self._start_time: float | None = None
        self._end_time: float | None = None  # Frozen when queue becomes idle
        self._stats_lock = threading.Lock()  # Thread-safe stats updates

    @property
    def depth(self) -> int:
        return len(self._tasks)

    @property
    def meta(self) -> QueueMeta:
        return QueueMeta(
            queue_id=self.queue_id,
            service=self.service,
            model=self.model,
            api_key=self.api_key,
            rpm_limit=int(self.rpm_bucket.capacity),
            tpm_limit=int(self.tpm_bucket.capacity),
        )

    def enqueue(self, task: dict) -> None:
        """Add a task to the queue."""
        with self._lock:
            self._tasks.append(task)
            logger.info(
                f"[QUEUE ENQUEUE] queue={self.queue_id[:8]}... service={self.service} "
                f"model={self.model} task={task.get('task_id', 'unknown')[:8]}... "
                f"depth_after={len(self._tasks)}"
            )

    def peek(self) -> dict | None:
        """Look at the next task without removing it."""
        with self._lock:
            return self._tasks[0] if self._tasks else None

    def dequeue(self) -> dict | None:
        """Remove and return the next task."""
        with self._lock:
            if self._tasks:
                task = self._tasks.pop(0)
                logger.info(
                    f"[QUEUE DEQUEUE] queue={self.queue_id[:8]}... service={self.service} "
                    f"model={self.model} task={task.get('task_id', 'unknown')[:8]}... "
                    f"depth_after={len(self._tasks)}"
                )
                # Freeze stats when queue becomes empty
                if len(self._tasks) == 0 and self._start_time is not None:
                    with self._stats_lock:
                        if self._end_time is None:
                            self._end_time = time.time()
                return task
            return None

    def try_acquire(self, estimated_tokens: int) -> bool:
        """Try to acquire capacity for a request (thread-safe)."""
        with self._stats_lock:
            # Need 1 RPM token and estimated_tokens TPM tokens
            if not self.rpm_bucket.try_acquire(1):
                return False
            if not self.tpm_bucket.try_acquire(estimated_tokens):
                # Return the RPM token
                self.rpm_bucket.tokens += 1
                return False

            # Track throughput (start timer on first request)
            if self._start_time is None:
                self._start_time = time.time()
            # Clear end time since we're active again
            self._end_time = None
            self._request_count += 1
            self._token_count += estimated_tokens

            return True

    def time_until_available(self, estimated_tokens: int) -> float:
        """Calculate when the next task can execute (thread-safe)."""
        with self._stats_lock:
            rpm_wait = self.rpm_bucket.time_until_available(1)
            tpm_wait = self.tpm_bucket.time_until_available(estimated_tokens)
            return max(rpm_wait, tpm_wait)

    def reconcile(self, estimated_tokens: int, actual_tokens: int) -> None:
        """Adjust TPM bucket after actual usage is known (thread-safe)."""
        with self._stats_lock:
            self.tpm_bucket.reconcile(estimated_tokens, actual_tokens)
            # Update token count with actual (adjust for estimate difference)
            self._token_count += actual_tokens - estimated_tokens

    def get_throughput_stats(self) -> dict:
        """
        Get current throughput statistics.

        Returns dict with:
        - request_count: Total requests processed
        - token_count: Total tokens processed
        - elapsed_seconds: Time since first request
        - avg_rpm: Average requests per minute
        - avg_tpm: Average tokens per minute
        - rpm_utilization: Percentage of RPM limit being used
        - tpm_utilization: Percentage of TPM limit being used
        - is_frozen: True if stats are frozen (queue emptied)
        """
        with self._stats_lock:
            if self._start_time is None:
                return {
                    "request_count": 0,
                    "token_count": 0,
                    "elapsed_seconds": 0,
                    "avg_rpm": 0,
                    "avg_tpm": 0,
                    "rpm_utilization": 0,
                    "tpm_utilization": 0,
                    "is_frozen": False,
                }

            # Use frozen end time if queue has emptied, otherwise current time
            end_time = self._end_time if self._end_time is not None else time.time()
            elapsed = end_time - self._start_time
            if elapsed < 1:
                elapsed = 1  # Avoid division by very small numbers

            # Calculate average rates (per minute)
            avg_rpm = (self._request_count / elapsed) * 60
            avg_tpm = (self._token_count / elapsed) * 60

            # Calculate utilization percentages
            rpm_limit = self.rpm_bucket.capacity
            tpm_limit = self.tpm_bucket.capacity
            rpm_util = (avg_rpm / rpm_limit * 100) if rpm_limit > 0 else 0
            tpm_util = (avg_tpm / tpm_limit * 100) if tpm_limit > 0 else 0

            return {
                "request_count": self._request_count,
                "token_count": self._token_count,
                "elapsed_seconds": elapsed,
                "avg_rpm": avg_rpm,
                "avg_tpm": avg_tpm,
                "rpm_utilization": rpm_util,
                "tpm_utilization": tpm_util,
                "is_frozen": self._end_time is not None,
            }


class DispatchHeap:
    """
    Priority queue of queues, ordered by availability time.

    Used to efficiently find which queue can execute next.
    Queues are identified by (availability_time, queue_id).
    """

    def __init__(self):
        self._heap: list[tuple[float, str]] = []  # (availability_time, queue_id)
        self._queue_times: dict[str, float] = {}  # queue_id -> availability_time
        self._lock = threading.Lock()

    def push(self, queue_id: str, availability_time: float) -> None:
        """Add or update a queue's availability time."""
        with self._lock:
            self._queue_times[queue_id] = availability_time
            heapq.heappush(self._heap, (availability_time, queue_id))

    def pop(self) -> tuple[str, float] | None:
        """Remove and return the queue with earliest availability."""
        with self._lock:
            while self._heap:
                avail_time, queue_id = heapq.heappop(self._heap)
                # Check if this entry is current (not stale)
                if (
                    queue_id in self._queue_times
                    and self._queue_times[queue_id] == avail_time
                ):
                    del self._queue_times[queue_id]
                    return queue_id, avail_time
            return None

    def peek(self) -> tuple[str, float] | None:
        """Look at the earliest queue without removing."""
        with self._lock:
            while self._heap:
                avail_time, queue_id = self._heap[0]
                if (
                    queue_id in self._queue_times
                    and self._queue_times[queue_id] == avail_time
                ):
                    return queue_id, avail_time
                heapq.heappop(self._heap)  # Remove stale entry
            return None

    def update(self, queue_id: str, availability_time: float) -> None:
        """Update a queue's availability time."""
        self.push(queue_id, availability_time)  # Lazy update

    def remove(self, queue_id: str) -> None:
        """Remove a queue from the heap."""
        with self._lock:
            self._queue_times.pop(queue_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue_times)


# Default rate limits by service
# High defaults (TPM=1M, RPM=10K) to avoid artificial bottlenecks
DEFAULT_RATE_LIMITS = {
    "openai": {"rpm": 10_000, "tpm": 1_000_000},
    "openai_v2": {"rpm": 10_000, "tpm": 1_000_000},  # Same as openai
    "anthropic": {"rpm": 10_000, "tpm": 1_000_000},
    "google": {"rpm": 10_000, "tpm": 1_000_000},
    "groq": {"rpm": 10_000, "tpm": 1_000_000},
    "mistral": {"rpm": 10_000, "tpm": 1_000_000},
    "deep_infra": {"rpm": 10_000, "tpm": 1_000_000},
    "deepseek": {"rpm": 10_000, "tpm": 1_000_000},
    "xai": {"rpm": 10_000, "tpm": 1_000_000},
    "together": {"rpm": 10_000, "tpm": 1_000_000},
    "perplexity": {"rpm": 10_000, "tpm": 1_000_000},
    "bedrock": {"rpm": 10_000, "tpm": 1_000_000},
    "azure": {"rpm": 10_000, "tpm": 1_000_000},
    "test": {"rpm": 10_000, "tpm": 1_000_000},
}


class QueueRegistry:
    """
    Manages all queues and routes tasks to appropriate queues.

    Queues are indexed by:
    - queue_id for direct lookup
    - (service, model) for routing

    Supports dynamic queue creation when auto_register_api_keys is set.
    """

    def __init__(self, auto_register: bool = True):
        """
        Initialize the queue registry.

        Args:
            auto_register: If True, automatically create queues for new
                          (service, model) combinations when API keys are available.
        """
        self._queues: dict[str, Queue] = {}
        self._service_model_index: dict[tuple[str, str], list[str]] = {}
        self._dispatch_heap = DispatchHeap()
        self._lock = threading.Lock()
        self._auto_register = auto_register
        self._service_api_keys: dict[
            str, str
        ] = {}  # service -> api_key for auto-registration

    @property
    def dispatch_heap(self) -> DispatchHeap:
        return self._dispatch_heap

    def set_service_api_key(self, service: str, api_key: str) -> None:
        """
        Store an API key for a service to enable auto-registration.

        When auto_register is True and a task is routed to a (service, model)
        without a queue, a new queue will be created using this API key.
        """
        self._service_api_keys[service] = api_key
        logger.debug(f"[REGISTRY] Stored API key for service={service}")

    def get_service_api_key(self, service: str) -> str | None:
        """Get the stored API key for a service."""
        return self._service_api_keys.get(service)

    def register_queue(
        self,
        service: str,
        model: str,
        api_key: str,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
    ) -> str:
        """Register a new queue. Returns queue_id."""
        # Get default limits if not specified
        defaults = DEFAULT_RATE_LIMITS.get(service, {"rpm": 60, "tpm": 100000})
        rpm = rpm_limit or defaults["rpm"]
        tpm = tpm_limit or defaults["tpm"]

        queue_id = generate_id()
        queue = Queue(
            queue_id=queue_id,
            service=service,
            model=model,
            api_key=api_key,
            rpm_limit=rpm,
            tpm_limit=tpm,
        )

        with self._lock:
            self._queues[queue_id] = queue

            key = (service, model)
            if key not in self._service_model_index:
                self._service_model_index[key] = []
            self._service_model_index[key].append(queue_id)

        logger.info(
            f"[QUEUE REGISTERED] queue={queue_id[:8]}... service={service} "
            f"model={model} rpm={rpm} tpm={tpm} api_key={api_key[:8]}..."
        )

        return queue_id

    def get_queue(self, queue_id: str) -> Queue:
        """Get a queue by ID."""
        return self._queues[queue_id]

    def find_queues(self, service: str, model: str) -> list[str]:
        """Find all queue IDs matching (service, model)."""
        with self._lock:
            return list(self._service_model_index.get((service, model), []))

    def route_task(self, service: str, model: str) -> str:
        """Select the best queue for a task (shortest depth).

        If no queue exists and auto_register is enabled with an API key
        for this service, a new queue will be automatically created.
        """
        queue_ids = self.find_queues(service, model)

        # Auto-register if no queue exists and we have an API key
        if not queue_ids and self._auto_register:
            api_key = self._service_api_keys.get(service)
            if api_key:
                logger.info(
                    f"[QUEUE AUTO-REGISTER] Creating queue for service={service} model={model}"
                )
                queue_id = self.register_queue(
                    service=service,
                    model=model,
                    api_key=api_key,
                )
                queue_ids = [queue_id]

        if not queue_ids:
            logger.debug(
                f"[QUEUE ROUTING FAILED] No queue found for service={service} model={model}"
            )
            raise ValueError(f"No queue for {service}/{model}")

        # Pick queue with lowest depth
        selected = min(queue_ids, key=lambda qid: self._queues[qid].depth)
        logger.debug(
            f"[QUEUE ROUTING] service={service} model={model} "
            f"candidates={len(queue_ids)} selected={selected[:8]}..."
        )
        return selected

    def enqueue_task(self, task: dict, service: str, model: str) -> str:
        """Route and enqueue a task. Returns queue_id."""
        queue_id = self.route_task(service, model)
        queue = self._queues[queue_id]

        was_empty = queue.depth == 0
        queue.enqueue(task)

        # Add to dispatch heap if queue was empty
        if was_empty:
            estimated_tokens = task.get("estimated_tokens", 500)
            avail_time = time.time() + queue.time_until_available(estimated_tokens)
            self._dispatch_heap.push(queue_id, avail_time)

        return queue_id

    def list_queues(self) -> list[QueueMeta]:
        """List all registered queues."""
        return [q.meta for q in self._queues.values()]


def load_queues_from_env(
    registry: QueueRegistry, env_path: str = None
) -> dict[str, str]:
    """
    Load API keys from .env file and register queues.

    Also stores API keys in the registry for auto-registration of new models.

    Returns mapping of service -> queue_id for the primary queue.
    """
    import os
    from pathlib import Path

    if env_path:
        # Load from specific file
        from dotenv import load_dotenv

        load_dotenv(env_path)

    # Map of env var -> (service, model patterns)
    key_mappings = {
        "OPENAI_API_KEY": (
            "openai",
            ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        ),
        "ANTHROPIC_API_KEY": (
            "anthropic",
            [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ],
        ),
        "GOOGLE_API_KEY": (
            "google",
            ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"],
        ),
        "GROQ_API_KEY": ("groq", ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]),
        "MISTRAL_API_KEY": (
            "mistral",
            ["mistral-large-latest", "mistral-small-latest"],
        ),
        "DEEP_INFRA_API_KEY": (
            "deep_infra",
            ["meta-llama/Meta-Llama-3.1-70B-Instruct"],
        ),
        "DEEPSEEK_API_KEY": ("deepseek", ["deepseek-chat", "deepseek-reasoner"]),
        "XAI_API_KEY": ("xai", ["grok-2-latest"]),
        "TOGETHER_API_KEY": ("together", ["meta-llama/Llama-3.3-70B-Instruct-Turbo"]),
        "PERPLEXITY_API_KEY": ("perplexity", ["llama-3.1-sonar-large-128k-online"]),
        "AWS_ACCESS_KEY_ID": (
            "bedrock",
            [],
        ),  # No default models, just enable auto-registration
        "AZURE_OPENAI_KEY": (
            "azure",
            [],
        ),  # No default models, just enable auto-registration
    }

    # Also map additional service variations to their keys
    service_key_aliases = {
        "openai_v2": "OPENAI_API_KEY",  # openai_v2 uses same key as openai
    }

    registered = {}

    for env_var, (service, models) in key_mappings.items():
        api_key = os.environ.get(env_var)
        if api_key:
            # Store API key for auto-registration
            registry.set_service_api_key(service, api_key)

            # Register default queues for common models
            for model in models:
                queue_id = registry.register_queue(
                    service=service,
                    model=model,
                    api_key=api_key,
                )
                if service not in registered:
                    registered[service] = queue_id

    # Handle service aliases
    for alias_service, env_var in service_key_aliases.items():
        api_key = os.environ.get(env_var)
        if api_key:
            registry.set_service_api_key(alias_service, api_key)
            logger.info(
                f"[REGISTRY] Enabled auto-registration for {alias_service} (via {env_var})"
            )

    return registered
