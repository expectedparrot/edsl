import threading
import os
from edsl.caching.sql_dict import SQLiteDict
from edsl.caching.cache_entry import CacheEntry

def test_sql_dict_concurrency():
    """Stress test SQLiteDict with concurrent writes and reads."""
    db_path = "test_concurrency.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    sql_dict = SQLiteDict(db_path)
    num_threads = 10
    num_items_per_thread = 50
    
    def worker(thread_id):
        for i in range(num_items_per_thread):
            key = f"key_{thread_id}_{i}"
            entry = CacheEntry.example()
            # Test write
            sql_dict[key] = entry
            # Test read
            assert sql_dict[key] == entry
            # Test contains
            assert key in sql_dict

    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verify total count
    assert len(list(sql_dict.keys())) == num_threads * num_items_per_thread
    
    # Test concurrent update
    def updater(thread_id):
        new_data = {f"update_{thread_id}_{i}": CacheEntry.example() for i in range(10)}
        sql_dict.update(new_data)

    update_threads = []
    for i in range(num_threads):
        t = threading.Thread(target=updater, args=(i,))
        update_threads.append(t)
        t.start()

    for t in update_threads:
        t.join()

    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    test_sql_dict_concurrency()
