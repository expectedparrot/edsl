# demo.py
import sqlite3

from .plan import (build_append_plan, build_rename_plan, build_drop_key_plan, build_add_values_plan)
from .memory_backend import MemoryState
from .sqlite_backend import SQLiteState

from typing import List, Any, Dict

backend = MemoryState()

conn = sqlite3.connect(":memory:")
with open("backend/schema.sql", "r", encoding="utf-8") as f:
    conn.executescript(f.read())

backend = SQLiteState(conn, 0)

class ScenarioList:

    def __init__(self, data: List[Any]):
        self.backend = backend

        for entry in data: 
            plan = build_append_plan(entry)
            plan.execute(self.backend, {"payload": entry})

    def get_scenario(self, position: int) -> Any:
        return self.backend.get_materialized_scenario(position)

    def get_all_scenarios(self) -> List[Any]:
        return self.backend.get_all_materialized_scenarios()

    def __str__(self) -> str:
        return str(self.get_all_scenarios())

    def append(self, entry: Any) -> None:
        plan = build_append_plan(entry)
        plan.execute(self.backend, {"payload": entry})
        return None

    def rename(self, old_key: str, new_key: str) -> None:
        plan = build_rename_plan(old_key, new_key)
        plan.execute(self.backend, {})
        return None

    def drop_key(self, key: str) -> None:
        plan = build_drop_key_plan(key)
        plan.execute(self.backend, {})
        return None

    def add_values(self, key: str, values: List[Any]) -> None:
        plan = build_add_values_plan(key, values)
        plan.execute(self.backend, {})
        return None



def run_demo():
    # ----- memory state -----
    mem = MemoryState()
    mem.meta = {"rename": {"persona": "personas"}, "drop": ["age"]}

    # ----- sqlite state -----
    conn = sqlite3.connect("demo.db")
    with open("backend/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute("INSERT INTO scenario_lists (id, meta) VALUES (?, ?)", (1, '{"rename":{"persona":"personas"},"drop":["age"]}'))
    db = SQLiteState(conn, 1)

    # ----- build ONE plan and execute it on both backends -----
    payloads = [
        {"persona": "Alice", "likes": "sailing"},
        {"persona": "Bob", "likes": "chickens"},
    ]

    for p in payloads:
        plan = build_append_plan(p)
        plan.execute(mem, {"payload": p})
        plan.execute(db, {"payload": p})

    # prove both produced same derived fields + normalization
    print("MEM:", mem.scenarios)

    rows = conn.execute("SELECT payload FROM scenarios WHERE list_id=1 ORDER BY position").fetchall()
    db_scenarios = [eval(row[0].replace("true","True").replace("false","False")) if row[0].startswith("{'") else __import__("json").loads(row[0]) for row in rows]
    print("DB :", db_scenarios)

    assert mem.scenarios == db_scenarios
    print("\n✅ Same ops, same normalization, same derived digest, same result.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    #run_demo()
    data = [
        {"persona": "Alice", "likes": "sailing"},
        {"persona": "Bob", "likes": "chickens"},
    ]
    scenario_list = ScenarioList(data)
    print(scenario_list)

    print("After rename:")

    scenario_list.rename("persona", "first_name")

    print("After drop:")
    scenario_list.drop_key("likes")
    print(scenario_list)

    print("After an override:")
    scenario_list.add_values("likes", ["sailing", "chickens"])
    print(scenario_list)
