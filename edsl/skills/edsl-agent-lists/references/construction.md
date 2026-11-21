# AgentList construction

## Python

```python
from edsl import Agent, AgentList

agents = AgentList([
    Agent(name="Alice", traits={"age": 25, "occupation": "teacher"}),
    Agent(name="Bob", traits={"age": 35, "occupation": "doctor"}),
])
agents.git.save("agents.ep")
```

`name` is a reserved `Agent` constructor argument. Do not put it in `traits`.
Agent lists can also carry shared instructions; keep per-agent variation in
traits.

## CLI import

```bash
ep agents create --from-csv people.csv --output agents.ep
ep agents create --from-csv people.csv --name-field name --output agents.ep
ep agents create --from-xlsx people.xlsx --sheet Sheet1 --name-field respondent_id --output agents.ep
```

Use `ep agents create --help` for supported sources and transformations. Check
the output with `ep inspect agents.ep` or `AgentList.git.load("agents.ep")`.
