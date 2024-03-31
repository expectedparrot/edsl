import sqlite3
import json
from edsl.data.CacheEntry import CacheEntry

class SQLiteDict:
    def __init__(self, db_path = None):
        self.db_path = db_path or "./edsl_cache/data.db"
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()
        
    def __setitem__(self, key, value):
        value_json = json.dumps(value.to_dict())
        self.cursor.execute("INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)", (key, value_json))
        self.conn.commit()
        
    def __getitem__(self, key):
        self.cursor.execute("SELECT value FROM data WHERE key = ?", (key,))
        result = self.cursor.fetchone()
        if result:
            return CacheEntry.from_dict(json.loads(result[0]))
        raise KeyError(f"Key '{key}' not found.")
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
        
    def update(self, new_d):
        for key, value in new_d.items():
            if key in self:
                pass
            else:
                self[key] = value    

    def values(self):
        self.cursor.execute("SELECT value from data")
        for value in self.cursor.fetchall():
            yield CacheEntry(**json.loads(value[0]))

    def items(self):
        self.cursor.execute("SELECT key, value FROM data")
        for key, value in self.cursor.fetchall():
            yield key, CacheEntry(**json.loads(value))
        
    def __delitem__(self, key):
        if key in self:
            self.cursor.execute("DELETE FROM data WHERE key = ?", (key,))
            self.conn.commit()
        else:
            raise KeyError(f"Key '{key}' not found.")
            
    def __contains__(self, key):
        self.cursor.execute("SELECT 1 FROM data WHERE key = ?", (key,))
        return self.cursor.fetchone() is not None
    
    def __iter__(self):
        self.cursor.execute("SELECT key FROM data")
        for row in self.cursor.fetchall():
            yield row[0]
            
    def __len__(self):
        self.cursor.execute("SELECT COUNT(*) FROM data")
        return self.cursor.fetchone()[0]
    
    def keys(self):
        return set(iter(self))
    
    def close(self):
        self.conn.close()

