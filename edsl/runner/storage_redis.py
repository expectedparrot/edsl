"""
Redis Storage Implementation

Provides a Redis-backed implementation of StorageProtocol for distributed
multi-node execution.

Features:
- Connection pooling for performance
- Atomic operations using Redis commands
- Key prefixing for namespace isolation
- Optional TTL support for volatile data
- Pub/sub support for worker coordination
"""

import json
import fnmatch
from typing import Any

try:
    import redis
    from redis import Redis, ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None
    ConnectionPool = None


class RedisStorage:
    """
    Redis implementation of StorageProtocol.

    Suitable for:
    - Multi-node distributed deployment
    - High-throughput workloads
    - Real-time coordination between workers

    Key Mappings:
    - Persistent: {prefix}:persistent:{key} -> JSON string
    - Volatile: {prefix}:volatile:{key} -> JSON string with type tag
    - Sets: {prefix}:set:{key} -> Redis SET
    - Blobs: {prefix}:blob:{blob_id} -> binary data
    - Blob metadata: {prefix}:blob_meta:{blob_id} -> JSON string

    Usage:
        # Local Redis
        storage = RedisStorage("redis://localhost:6379")

        # Remote Redis with auth
        storage = RedisStorage("redis://:password@host:6379/0")

        # With custom prefix
        storage = RedisStorage("redis://localhost:6379", prefix="myapp")
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "runner",
        connection_pool_size: int = 50,
        decode_responses: bool = False,
    ):
        """
        Initialize Redis storage.

        Args:
            redis_url: Redis connection URL
            prefix: Key prefix for namespace isolation
            connection_pool_size: Maximum number of connections in pool
            decode_responses: If True, decode byte responses to strings
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for RedisStorage. "
                "Install with: pip install redis"
            )

        self._prefix = prefix
        self._pool = ConnectionPool.from_url(
            redis_url,
            max_connections=connection_pool_size,
            decode_responses=False,  # We handle encoding ourselves
        )
        self._client: Redis = Redis(connection_pool=self._pool)

        # Test connection
        try:
            self._client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def _key(self, namespace: str, key: str) -> str:
        """Build a prefixed key."""
        return f"{self._prefix}:{namespace}:{key}"

    def _persistent_key(self, key: str) -> str:
        return self._key("persistent", key)

    def _volatile_key(self, key: str) -> str:
        return self._key("volatile", key)

    def _set_key(self, key: str) -> str:
        return self._key("set", key)

    def _blob_key(self, blob_id: str) -> str:
        return self._key("blob", blob_id)

    def _blob_meta_key(self, blob_id: str) -> str:
        return self._key("blob_meta", blob_id)

    # -------------------------------------------------------------------------
    # Blob operations
    # -------------------------------------------------------------------------

    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        """Write binary blob data to blob storage."""
        pipe = self._client.pipeline()
        pipe.set(self._blob_key(blob_id), data)
        if metadata:
            pipe.set(self._blob_meta_key(blob_id), json.dumps(metadata))
        else:
            pipe.delete(self._blob_meta_key(blob_id))
        pipe.execute()

    def read_blob(self, blob_id: str) -> bytes | None:
        """Read binary blob data. Returns None if blob doesn't exist."""
        result = self._client.get(self._blob_key(blob_id))
        return result  # Already bytes

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        """Read blob metadata without reading the blob data."""
        result = self._client.get(self._blob_meta_key(blob_id))
        if result:
            return json.loads(result.decode("utf-8"))
        return None

    def delete_blob(self, blob_id: str) -> None:
        """Delete a blob from storage."""
        pipe = self._client.pipeline()
        pipe.delete(self._blob_key(blob_id))
        pipe.delete(self._blob_meta_key(blob_id))
        pipe.execute()

    def blob_exists(self, blob_id: str) -> bool:
        """Check if a blob exists in storage."""
        return bool(self._client.exists(self._blob_key(blob_id)))

    # -------------------------------------------------------------------------
    # Persistent operations
    # -------------------------------------------------------------------------

    def write_persistent(self, key: str, value: dict) -> None:
        """Write immutable data to persistent storage."""
        self._client.set(self._persistent_key(key), json.dumps(value))

    def read_persistent(self, key: str) -> dict | None:
        """Read from persistent storage. Returns None if key doesn't exist."""
        result = self._client.get(self._persistent_key(key))
        if result:
            return json.loads(result.decode("utf-8"))
        return None

    def batch_write_persistent(self, items: dict[str, dict]) -> None:
        """Write multiple items to persistent storage atomically."""
        if not items:
            return
        pipe = self._client.pipeline()
        for key, value in items.items():
            pipe.set(self._persistent_key(key), json.dumps(value))
        pipe.execute()

    def delete_persistent(self, key: str) -> None:
        """Delete a key from persistent storage."""
        self._client.delete(self._persistent_key(key))

    def scan_keys_persistent(self, pattern: str) -> list[str]:
        """Scan persistent storage for keys matching pattern (glob-style)."""
        # Convert glob pattern to Redis pattern
        redis_pattern = self._persistent_key(pattern)
        keys = []
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor, match=redis_pattern, count=1000)
            keys.extend(batch)
            if cursor == 0:
                break

        # Strip prefix and return
        prefix_len = len(self._prefix) + len(":persistent:")
        return [k.decode("utf-8")[prefix_len:] for k in keys]

    # -------------------------------------------------------------------------
    # Volatile operations
    # -------------------------------------------------------------------------

    def _encode_volatile(self, value: Any) -> bytes:
        """Encode a volatile value with type information."""
        if isinstance(value, int):
            return json.dumps({"_type": "int", "_value": value}).encode("utf-8")
        elif isinstance(value, float):
            return json.dumps({"_type": "float", "_value": value}).encode("utf-8")
        elif isinstance(value, str):
            return json.dumps({"_type": "str", "_value": value}).encode("utf-8")
        elif isinstance(value, dict):
            return json.dumps({"_type": "dict", "_value": value}).encode("utf-8")
        elif isinstance(value, list):
            return json.dumps({"_type": "list", "_value": value}).encode("utf-8")
        else:
            return json.dumps({"_type": "unknown", "_value": value}).encode("utf-8")

    def _decode_volatile(self, data: bytes) -> Any:
        """Decode a volatile value from Redis."""
        obj = json.loads(data.decode("utf-8"))
        value_type = obj.get("_type", "unknown")
        value = obj.get("_value")

        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        return value

    def write_volatile(self, key: str, value: str | int | float | dict | list) -> None:
        """Write mutable data to volatile storage."""
        self._client.set(self._volatile_key(key), self._encode_volatile(value))

    def read_volatile(self, key: str) -> str | int | float | dict | list | None:
        """Read from volatile storage. Returns None if key doesn't exist."""
        result = self._client.get(self._volatile_key(key))
        if result:
            return self._decode_volatile(result)
        return None

    def delete_volatile(self, key: str) -> None:
        """Delete a key from volatile storage."""
        self._client.delete(self._volatile_key(key))

    def batch_delete_volatile(self, keys: list[str]) -> int:
        """
        Delete multiple keys from volatile storage in a single operation.

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys successfully deleted
        """
        if not keys:
            return 0

        # Build prefixed keys
        redis_keys = [self._volatile_key(k) for k in keys]

        # Use DELETE with multiple keys (Redis supports this natively)
        return self._client.delete(*redis_keys)

    def increment_volatile(self, key: str, amount: int = 1) -> int:
        """
        Atomically increment a counter.

        Uses a Lua script to handle the type-tagged format atomically.
        """
        lua_script = """
        local key = KEYS[1]
        local amount = tonumber(ARGV[1])

        local current = redis.call('GET', key)
        local new_value

        if current then
            local obj = cjson.decode(current)
            if obj._type ~= 'int' and obj._type ~= 'float' then
                return redis.error_reply('Cannot increment non-numeric value')
            end
            new_value = obj._value + amount
        else
            new_value = amount
        end

        local new_obj = cjson.encode({_type = 'int', _value = new_value})
        redis.call('SET', key, new_obj)
        return new_value
        """

        # Register and execute the script
        script = self._client.register_script(lua_script)
        result = script(keys=[self._volatile_key(key)], args=[amount])
        return int(result)

    def scan_keys_volatile(self, pattern: str) -> list[str]:
        """Scan volatile storage for keys matching pattern (glob-style)."""
        redis_pattern = self._volatile_key(pattern)
        keys = []
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor, match=redis_pattern, count=1000)
            keys.extend(batch)
            if cursor == 0:
                break

        prefix_len = len(self._prefix) + len(":volatile:")
        return [k.decode("utf-8")[prefix_len:] for k in keys]

    def batch_read_volatile(self, keys: list[str]) -> dict[str, Any]:
        """
        Read multiple keys from volatile storage in a single operation using MGET.
        Returns a dict mapping key to value (or None if key doesn't exist).
        """
        if not keys:
            return {}

        # Build prefixed keys
        redis_keys = [self._volatile_key(k) for k in keys]

        # Use MGET to fetch all values in one round-trip
        values = self._client.mget(redis_keys)

        # Build result dict, decoding values
        result = {}
        for key, value in zip(keys, values):
            if value is not None:
                result[key] = self._decode_volatile(value)
            else:
                result[key] = None
        return result

    def batch_write_volatile(self, items: dict[str, Any]) -> None:
        """
        Write multiple keys to volatile storage in a single operation using pipeline.
        """
        if not items:
            return

        pipe = self._client.pipeline()
        for key, value in items.items():
            pipe.set(self._volatile_key(key), self._encode_volatile(value))
        pipe.execute()

    def batch_read_persistent(self, keys: list[str]) -> dict[str, dict | None]:
        """
        Read multiple keys from persistent storage in a single operation using MGET.
        Returns a dict mapping key to value (or None if key doesn't exist).
        """
        if not keys:
            return {}

        # Build prefixed keys
        redis_keys = [self._persistent_key(k) for k in keys]

        # Use MGET to fetch all values in one round-trip
        values = self._client.mget(redis_keys)

        # Build result dict, decoding JSON
        result = {}
        for key, value in zip(keys, values):
            if value is not None:
                result[key] = json.loads(value.decode("utf-8"))
            else:
                result[key] = None
        return result

    def pop_multiple_from_set(self, key: str, count: int) -> list[str]:
        """
        Atomically remove and return up to count elements from a set using SPOP.
        Returns empty list if set is empty or doesn't exist.
        """
        if count <= 0:
            return []

        result = self._client.spop(self._set_key(key), count)
        if result:
            return [r.decode("utf-8") if isinstance(r, bytes) else r for r in result]
        return []

    def batch_get_with_set_sizes(
        self, value_keys: list[str], set_keys: list[str]
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Read multiple volatile values AND set sizes in a single pipeline call.

        Args:
            value_keys: Keys to GET (volatile storage)
            set_keys: Keys to get SCARD for (set storage)

        Returns:
            Tuple of (values_dict, sizes_dict)
            - values_dict: {key: decoded_value or None}
            - sizes_dict: {key: set_size}
        """
        if not value_keys and not set_keys:
            return {}, {}

        pipe = self._client.pipeline()

        # Queue GET commands for values
        for key in value_keys:
            pipe.get(self._volatile_key(key))

        # Queue SCARD commands for set sizes
        for key in set_keys:
            pipe.scard(self._set_key(key))

        # Execute all in one round-trip
        results = pipe.execute()

        # Split results
        values_dict = {}
        sizes_dict = {}

        for i, key in enumerate(value_keys):
            value = results[i]
            if value is not None:
                values_dict[key] = self._decode_volatile(value)
            else:
                values_dict[key] = None

        offset = len(value_keys)
        for i, key in enumerate(set_keys):
            sizes_dict[key] = results[offset + i] or 0

        return values_dict, sizes_dict

    # -------------------------------------------------------------------------
    # Set operations
    # -------------------------------------------------------------------------

    def add_to_set(self, key: str, value: str) -> bool:
        """Add value to a set. Returns True if value was added, False if already present."""
        result = self._client.sadd(self._set_key(key), value)
        return result > 0

    def add_multiple_to_set(self, key: str, values: list[str]) -> int:
        """Add multiple values to a set in a single operation using SADD."""
        if not values:
            return 0
        return self._client.sadd(self._set_key(key), *values)

    def remove_from_set(self, key: str, value: str) -> bool:
        """Remove value from a set. Returns True if value was removed."""
        result = self._client.srem(self._set_key(key), value)
        return result > 0

    def pop_from_set(self, key: str) -> str | None:
        """Atomically remove and return an arbitrary element from a set."""
        result = self._client.spop(self._set_key(key))
        if result:
            return result.decode("utf-8")
        return None

    def get_set_members(self, key: str) -> set[str]:
        """Get all members of a set."""
        result = self._client.smembers(self._set_key(key))
        return {m.decode("utf-8") for m in result}

    def set_size(self, key: str) -> int:
        """Get the number of elements in a set."""
        return self._client.scard(self._set_key(key))

    def check_set_membership(self, key: str, values: list[str]) -> list[bool]:
        """Check which values are members of a set using SMISMEMBER (Redis 6.2+).

        Returns a list of booleans, one per input value, indicating membership.
        """
        if not values:
            return []
        result = self._client.smismember(self._set_key(key), values)
        return [bool(r) for r in result]

    # -------------------------------------------------------------------------
    # Pub/Sub operations (for distributed coordination)
    # -------------------------------------------------------------------------

    def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel. Returns number of subscribers that received it."""
        return self._client.publish(f"{self._prefix}:{channel}", message)

    def pubsub(self):
        """Get a pubsub object for subscribing to channels."""
        return self._client.pubsub()

    def subscribe(self, channel: str, callback):
        """Subscribe to a channel with a callback function."""
        ps = self.pubsub()
        ps.subscribe(**{f"{self._prefix}:{channel}": callback})
        return ps

    # -------------------------------------------------------------------------
    # Distributed locking (for leader election, etc.)
    # -------------------------------------------------------------------------

    def acquire_lock(self, name: str, timeout: int = 10, blocking: bool = True) -> bool:
        """
        Acquire a distributed lock.

        Args:
            name: Lock name
            timeout: Lock timeout in seconds (auto-release after this time)
            blocking: If True, wait for lock; if False, return immediately

        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = self._key("lock", name)
        if blocking:
            # Try to acquire with blocking
            return bool(self._client.set(lock_key, "1", nx=True, ex=timeout))
        else:
            return bool(self._client.set(lock_key, "1", nx=True, ex=timeout))

    def release_lock(self, name: str) -> bool:
        """Release a distributed lock."""
        lock_key = self._key("lock", name)
        return bool(self._client.delete(lock_key))

    def extend_lock(self, name: str, timeout: int = 10) -> bool:
        """Extend the timeout of an existing lock."""
        lock_key = self._key("lock", name)
        return bool(self._client.expire(lock_key, timeout))

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data with this prefix from storage."""
        pattern = f"{self._prefix}:*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=1000)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def stats(self) -> dict:
        """Return storage statistics."""
        persistent_count = 0
        volatile_count = 0
        set_count = 0
        blob_count = 0

        # Count persistent keys
        cursor = 0
        while True:
            cursor, keys = self._client.scan(
                cursor, match=f"{self._prefix}:persistent:*", count=1000
            )
            persistent_count += len(keys)
            if cursor == 0:
                break

        # Count volatile keys
        cursor = 0
        while True:
            cursor, keys = self._client.scan(
                cursor, match=f"{self._prefix}:volatile:*", count=1000
            )
            volatile_count += len(keys)
            if cursor == 0:
                break

        # Count sets
        cursor = 0
        while True:
            cursor, keys = self._client.scan(
                cursor, match=f"{self._prefix}:set:*", count=1000
            )
            set_count += len(keys)
            if cursor == 0:
                break

        # Count blobs
        cursor = 0
        while True:
            cursor, keys = self._client.scan(
                cursor, match=f"{self._prefix}:blob:*", count=1000
            )
            # Exclude metadata keys
            blob_keys = [k for k in keys if b":blob_meta:" not in k]
            blob_count += len(blob_keys)
            if cursor == 0:
                break

        return {
            "persistent_keys": persistent_count,
            "volatile_keys": volatile_count,
            "sets": set_count,
            "blobs": blob_count,
        }

    def close(self) -> None:
        """Close the Redis connection pool."""
        self._client.close()
        self._pool.disconnect()

    # -------------------------------------------------------------------------
    # Redis Streams operations (for distributed task queues)
    # -------------------------------------------------------------------------

    def _stream_key(self, stream: str) -> str:
        """Build a stream key with prefix."""
        return f"{self._prefix}:stream:{stream}"

    def stream_add(
        self,
        stream: str,
        data: dict,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        """
        Add a message to a Redis Stream.

        Args:
            stream: Stream name
            data: Message data as dict (values will be JSON encoded if not strings)
            maxlen: Optional max length for stream trimming
            approximate: If True, use approximate trimming (~) for better performance

        Returns:
            Message ID
        """
        # Encode data for Redis stream (all values must be strings/bytes)
        encoded = {}
        for key, value in data.items():
            if isinstance(value, (str, bytes)):
                encoded[key] = value
            else:
                encoded[key] = json.dumps(value)

        result = self._client.xadd(
            self._stream_key(stream),
            encoded,
            maxlen=maxlen,
            approximate=approximate,
        )
        return result.decode("utf-8") if isinstance(result, bytes) else result

    def stream_read(
        self,
        stream: str,
        count: int = 10,
        block: int | None = None,
        last_id: str = "0",
    ) -> list[tuple[str, dict]]:
        """
        Read messages from a stream.

        Args:
            stream: Stream name
            count: Maximum number of messages to return
            block: Milliseconds to block waiting for new messages (None = don't block)
            last_id: Read messages after this ID ("0" = from beginning, "$" = only new)

        Returns:
            List of (message_id, data) tuples
        """
        result = self._client.xread(
            {self._stream_key(stream): last_id},
            count=count,
            block=block,
        )

        messages = []
        if result:
            for stream_name, stream_messages in result:
                for msg_id, msg_data in stream_messages:
                    # Decode message ID and data
                    msg_id_str = (
                        msg_id.decode("utf-8") if isinstance(msg_id, bytes) else msg_id
                    )
                    decoded_data = {}
                    for k, v in msg_data.items():
                        key = k.decode("utf-8") if isinstance(k, bytes) else k
                        val = v.decode("utf-8") if isinstance(v, bytes) else v
                        # Try to JSON decode
                        try:
                            decoded_data[key] = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            decoded_data[key] = val
                    messages.append((msg_id_str, decoded_data))
        return messages

    def stream_create_group(
        self,
        stream: str,
        group: str,
        start_id: str = "0",
        mkstream: bool = True,
    ) -> bool:
        """
        Create a consumer group for a stream.

        Args:
            stream: Stream name
            group: Consumer group name
            start_id: Starting message ID ("0" = from beginning, "$" = only new)
            mkstream: Create stream if it doesn't exist

        Returns:
            True if group created, False if already exists
        """
        try:
            self._client.xgroup_create(
                self._stream_key(stream),
                group,
                id=start_id,
                mkstream=mkstream,
            )
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                return False  # Group already exists
            raise

    def stream_read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block: int | None = None,
        pending: bool = False,
    ) -> list[tuple[str, dict]]:
        """
        Read messages from a stream using a consumer group.

        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Consumer name (unique per consumer in the group)
            count: Maximum number of messages to return
            block: Milliseconds to block waiting for new messages
            pending: If True, read pending messages (">"), otherwise start from last

        Returns:
            List of (message_id, data) tuples
        """
        stream_id = ">" if not pending else "0"

        result = self._client.xreadgroup(
            group,
            consumer,
            {self._stream_key(stream): stream_id},
            count=count,
            block=block,
        )

        messages = []
        if result:
            for stream_name, stream_messages in result:
                for msg_id, msg_data in stream_messages:
                    # Decode message ID and data
                    msg_id_str = (
                        msg_id.decode("utf-8") if isinstance(msg_id, bytes) else msg_id
                    )
                    decoded_data = {}
                    for k, v in msg_data.items():
                        key = k.decode("utf-8") if isinstance(k, bytes) else k
                        val = v.decode("utf-8") if isinstance(v, bytes) else v
                        # Try to JSON decode
                        try:
                            decoded_data[key] = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            decoded_data[key] = val
                    messages.append((msg_id_str, decoded_data))
        return messages

    def stream_ack(self, stream: str, group: str, *message_ids: str) -> int:
        """
        Acknowledge messages as processed.

        Args:
            stream: Stream name
            group: Consumer group name
            message_ids: One or more message IDs to acknowledge

        Returns:
            Number of messages acknowledged
        """
        return self._client.xack(self._stream_key(stream), group, *message_ids)

    def stream_pending(
        self,
        stream: str,
        group: str,
        count: int = 10,
        consumer: str | None = None,
    ) -> list[dict]:
        """
        Get pending (unacknowledged) messages for a consumer group.

        Args:
            stream: Stream name
            group: Consumer group name
            count: Maximum number of messages to return
            consumer: Optional consumer name to filter by

        Returns:
            List of pending message info dicts
        """
        if consumer:
            result = self._client.xpending_range(
                self._stream_key(stream),
                group,
                min="-",
                max="+",
                count=count,
                consumername=consumer,
            )
        else:
            result = self._client.xpending_range(
                self._stream_key(stream),
                group,
                min="-",
                max="+",
                count=count,
            )

        pending = []
        for item in result:
            msg_id = item["message_id"]
            if isinstance(msg_id, bytes):
                msg_id = msg_id.decode("utf-8")
            consumer_name = item["consumer"]
            if isinstance(consumer_name, bytes):
                consumer_name = consumer_name.decode("utf-8")
            pending.append(
                {
                    "message_id": msg_id,
                    "consumer": consumer_name,
                    "time_since_delivered": item["time_since_delivered"],
                    "times_delivered": item["times_delivered"],
                }
            )
        return pending

    def stream_claim(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time: int,
        *message_ids: str,
    ) -> list[tuple[str, dict]]:
        """
        Claim pending messages that have been idle for too long.

        This is useful for handling messages from dead consumers.

        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Consumer claiming the messages
            min_idle_time: Minimum idle time in milliseconds
            message_ids: Message IDs to claim

        Returns:
            List of (message_id, data) tuples for claimed messages
        """
        result = self._client.xclaim(
            self._stream_key(stream),
            group,
            consumer,
            min_idle_time,
            message_ids,
        )

        messages = []
        for msg_id, msg_data in result:
            msg_id_str = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else msg_id
            decoded_data = {}
            for k, v in msg_data.items():
                key = k.decode("utf-8") if isinstance(k, bytes) else k
                val = v.decode("utf-8") if isinstance(v, bytes) else v
                try:
                    decoded_data[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    decoded_data[key] = val
            messages.append((msg_id_str, decoded_data))
        return messages

    def stream_len(self, stream: str) -> int:
        """Get the length of a stream."""
        return self._client.xlen(self._stream_key(stream))

    def stream_delete(self, stream: str, *message_ids: str) -> int:
        """
        Delete messages from a stream.

        Args:
            stream: Stream name
            message_ids: Message IDs to delete

        Returns:
            Number of messages deleted
        """
        return self._client.xdel(self._stream_key(stream), *message_ids)

    def stream_trim(self, stream: str, maxlen: int, approximate: bool = True) -> int:
        """
        Trim a stream to a maximum length.

        Args:
            stream: Stream name
            maxlen: Maximum number of messages to keep
            approximate: If True, use approximate trimming for better performance

        Returns:
            Number of messages trimmed
        """
        return self._client.xtrim(
            self._stream_key(stream),
            maxlen=maxlen,
            approximate=approximate,
        )

    def stream_info(self, stream: str) -> dict:
        """
        Get information about a stream.

        Returns dict with:
        - length: Number of messages
        - first-entry: First message ID and data
        - last-entry: Last message ID and data
        - groups: Number of consumer groups
        """
        try:
            result = self._client.xinfo_stream(self._stream_key(stream))
            # Decode bytes
            info = {}
            for k, v in result.items():
                key = k.decode("utf-8") if isinstance(k, bytes) else k
                if isinstance(v, bytes):
                    info[key] = v.decode("utf-8")
                else:
                    info[key] = v
            return info
        except redis.ResponseError:
            return {"error": "Stream does not exist"}

    def stream_groups(self, stream: str) -> list[dict]:
        """
        Get information about consumer groups for a stream.

        Returns list of group info dicts.
        """
        try:
            result = self._client.xinfo_groups(self._stream_key(stream))
            groups = []
            for group in result:
                info = {}
                for k, v in group.items():
                    key = k.decode("utf-8") if isinstance(k, bytes) else k
                    if isinstance(v, bytes):
                        info[key] = v.decode("utf-8")
                    else:
                        info[key] = v
                groups.append(info)
            return groups
        except redis.ResponseError:
            return []

    # -------------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------------

    def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self._client.ping()
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Timing events storage
    # -------------------------------------------------------------------------

    def _timing_key(self, job_id: str) -> str:
        """Get the Redis key for job timing events."""
        return f"{self._prefix}:timing:{job_id}"

    def add_timing_event(
        self,
        job_id: str,
        phase: str,
        component: str,
        timestamp: float,
        duration_ms: float | None = None,
        details: dict | None = None,
    ) -> None:
        """
        Add a timing event for a job.

        Args:
            job_id: The job identifier
            phase: Phase name (e.g., 'api_receive', 'dispatcher_start')
            component: Component name (api, dispatcher, worker)
            timestamp: Unix timestamp
            duration_ms: Duration in milliseconds (optional)
            details: Additional details (optional)
        """
        import json

        event = {
            "phase": phase,
            "component": component,
            "timestamp": timestamp,
            "duration_ms": duration_ms,
            "details": details,
        }
        # Use a list to preserve order, with score as timestamp for ordering
        key = self._timing_key(job_id)
        self._client.rpush(key, json.dumps(event))
        # Set expiration (24 hours)
        self._client.expire(key, 86400)

    def get_timing_events(self, job_id: str) -> list[dict]:
        """
        Get all timing events for a job.

        Args:
            job_id: The job identifier

        Returns:
            List of timing event dicts, ordered by insertion time
        """
        import json

        key = self._timing_key(job_id)
        events = self._client.lrange(key, 0, -1)
        result = []
        for event_json in events:
            try:
                if isinstance(event_json, bytes):
                    event_json = event_json.decode("utf-8")
                result.append(json.loads(event_json))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        return result

    def clear_timing_events(self, job_id: str) -> None:
        """Clear all timing events for a job."""
        key = self._timing_key(job_id)
        self._client.delete(key)

    def add_timing_events_batch(
        self,
        job_id: str,
        events: list[dict],
    ) -> None:
        """
        Add multiple timing events for a job in a single pipeline call.

        This is much more efficient than calling add_timing_event() multiple times.

        Args:
            job_id: The job identifier
            events: List of event dicts, each containing:
                - phase: Phase name
                - component: Component name
                - timestamp: Unix timestamp
                - duration_ms: Duration in milliseconds (optional)
                - details: Additional details (optional)
        """
        import json

        if not events:
            return

        key = self._timing_key(job_id)
        pipe = self._client.pipeline()
        for event in events:
            pipe.rpush(key, json.dumps(event))
        # Set expiration (24 hours)
        pipe.expire(key, 86400)
        pipe.execute()

    # -------------------------------------------------------------------------
    # API request counter (for tracking requests across scaled instances)
    # -------------------------------------------------------------------------

    def _api_endpoint_stats_key(self, job_id: str) -> str:
        """Get the Redis key for API endpoint stats (Hash)."""
        return f"{self._prefix}:stats:{job_id}:api_endpoints"

    def increment_api_endpoint_count(self, job_id: str, endpoint: str) -> int:
        """
        Increment the counter for a specific API endpoint.

        This is called by each API instance on every request,
        allowing accurate counting across scaled instances.

        Args:
            job_id: The job identifier
            endpoint: The endpoint name (submit, status, progress, results, cancel, errors, timing)

        Returns:
            The new count after incrementing.
        """
        key = self._api_endpoint_stats_key(job_id)
        count = self._client.hincrby(key, endpoint, 1)
        # Track Redis calls (1 for hincrby, +1 if expire needed)
        # Set expiration (24 hours) on first operation
        if count == 1:
            self._client.expire(key, 86400)
        return count

    def get_api_endpoint_counts(self, job_id: str) -> dict[str, int]:
        """
        Get all API endpoint counts for a job.

        Returns:
            Dict mapping endpoint name to count.
        """
        key = self._api_endpoint_stats_key(job_id)
        counts = self._client.hgetall(key)
        result = {}
        for k, v in counts.items():
            # Handle bytes from Redis
            key_str = k.decode("utf-8") if isinstance(k, bytes) else k
            val_int = int(v.decode("utf-8") if isinstance(v, bytes) else v)
            result[key_str] = val_int
        return result

    def get_api_request_count(self, job_id: str) -> int:
        """
        Get the total API request count for a job (sum of all endpoints).

        Returns:
            The total count across all API instances and endpoints.
        """
        counts = self.get_api_endpoint_counts(job_id)
        return sum(counts.values())

    # -------------------------------------------------------------------------
    # Dispatcher stats (flush count tracking)
    # -------------------------------------------------------------------------

    def _dispatcher_stats_key(self, job_id: str) -> str:
        """Get the Redis key for dispatcher stats."""
        return f"{self._prefix}:stats:{job_id}:dispatcher"

    def increment_dispatcher_flush_count(self, job_id: str, events_flushed: int) -> int:
        """
        Increment the dispatcher flush counter.

        Args:
            job_id: The job identifier
            events_flushed: Number of events in this flush

        Returns:
            The new flush count.
        """
        key = self._dispatcher_stats_key(job_id)
        pipe = self._client.pipeline()
        pipe.hincrby(key, "flush_count", 1)
        pipe.hincrby(key, "events_flushed", events_flushed)
        pipe.expire(key, 86400)
        results = pipe.execute()
        return results[0]  # Return flush count

    def get_dispatcher_stats(self, job_id: str) -> dict[str, int]:
        """
        Get dispatcher stats for a job.

        Returns:
            Dict with flush_count, events_flushed, and redis_calls.
        """
        key = self._dispatcher_stats_key(job_id)
        stats = self._client.hgetall(key)
        result = {"flush_count": 0, "events_flushed": 0, "redis_calls": 0}
        for k, v in stats.items():
            key_str = k.decode("utf-8") if isinstance(k, bytes) else k
            val_int = int(v.decode("utf-8") if isinstance(v, bytes) else v)
            result[key_str] = val_int
        return result

    # -------------------------------------------------------------------------
    # Redis call tracking (actual network round-trips)
    # -------------------------------------------------------------------------

    def _redis_calls_key(self, job_id: str) -> str:
        """Get the Redis key for tracking Redis round-trips."""
        return f"{self._prefix}:stats:{job_id}:redis_calls"

    def increment_redis_calls(self, job_id: str, count: int = 1) -> int:
        """
        Increment the Redis call counter for a job.

        Args:
            job_id: The job identifier
            count: Number of calls to add (default 1)

        Returns:
            The new count after incrementing.
        """
        key = self._redis_calls_key(job_id)
        new_count = self._client.incrby(key, count)
        if new_count == count:
            self._client.expire(key, 86400)
        return new_count

    def get_redis_calls(self, job_id: str) -> int:
        """
        Get the Redis call count for a job.

        Returns:
            Total Redis network round-trips for this job.
        """
        key = self._redis_calls_key(job_id)
        result = self._client.get(key)
        if result:
            return int(result.decode("utf-8") if isinstance(result, bytes) else result)
        return 0
