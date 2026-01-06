import hashlib
import json
from edsl.caching.cache_entry import CacheEntry
from edsl.caching.cache import Cache

def test_gen_key_backward_compatibility():
    """Verify that gen_key without salt produces the same key as before."""
    data = {
        "model": "gpt-3.5-turbo",
        "parameters": {"temperature": 0.5},
        "system_prompt": "Hello",
        "user_prompt": "Hi",
        "iteration": 1
    }
    # Current implementation (salted with None/empty string)
    key = CacheEntry.gen_key(**data)
    
    # Expected legacy key (unsalted)
    long_key = f"{data['model']}{json.dumps(data['parameters'], sort_keys=True)}{data['system_prompt']}{data['user_prompt']}{data['iteration']}"
    expected_legacy = hashlib.md5(long_key.encode()).hexdigest()
    
    print(f"Key: {key}")
    print(f"Legacy: {expected_legacy}")
    assert key == expected_legacy
    print("Backward compatibility test passed.")

def test_gen_key_with_salt():
    """Verify that salt actually changes the key."""
    data = {
        "model": "gpt-3.5-turbo",
        "parameters": {"temperature": 0.5},
        "system_prompt": "Hello",
        "user_prompt": "Hi",
        "iteration": 1
    }
    key1 = CacheEntry.gen_key(**data, salt="user1")
    key2 = CacheEntry.gen_key(**data, salt="user2")
    key_no_salt = CacheEntry.gen_key(**data)
    
    assert key1 != key2
    assert key1 != key_no_salt
    assert key2 != key_no_salt
    print("Salting test passed: keys are partitioned by salt.")

def test_cache_fetch_salting_logic():
    """Verify Cache.fetch uses separate keys for local vs remote."""
    class FakeCoop:
        def __init__(self, api_key):
            self.api_key = api_key
            self.api_url = "http://fake"
            self.headers = {}

    cache = Cache()
    cache.coop = FakeCoop(api_key="secret_key")
    
    # Mock _fetch_from_remote_cache to avoid actual network calls
    requested_remote_keys = []
    def mock_fetch_remote(key):
        requested_remote_keys.append(key)
        return None
    
    cache._fetch_from_remote_cache = mock_fetch_remote
    
    data = {
        "model": "gpt-3.5-turbo",
        "parameters": {"temperature": 0.5},
        "system_prompt": "Hello",
        "user_prompt": "Hi",
        "iteration": 1
    }
    
    # Compute the expected keys
    local_key = CacheEntry.gen_key(**data)
    expected_salt = hashlib.sha256(b"secret_key").hexdigest()
    remote_key = CacheEntry.gen_key(**data, salt=expected_salt)
    
    # Trigger fetch with remote_fetch=True
    cache.fetch(**data, remote_fetch=True)
    
    print(f"Expected Local Key: {local_key}")
    print(f"Expected Remote Key: {remote_key}")
    print(f"Requested Remote Keys: {requested_remote_keys}")
    
    assert remote_key in requested_remote_keys
    assert local_key not in requested_remote_keys
    print("Cache fetch salting logic test passed.")

if __name__ == "__main__":
    test_gen_key_backward_compatibility()
    test_gen_key_with_salt()
    test_cache_fetch_salting_logic()
