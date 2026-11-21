---
name: edsl-agent-lists
description: Build, import, validate, and save EDSL AgentLists from Python data or tabular files.
tags: [edsl, reference]
---

# EDSL AgentList

Use `AgentList` to represent respondent personas or other agents in EDSL. Construct from `Agent` instances or use `ep agents create` for CSV and Excel inputs. Keep shared instructions on the list or agents as supported by the current API; represent per-agent differences as traits. See the [construction guide](references/construction.md).

`name` is reserved by `Agent`: pass it as `Agent(name=..., traits={...})`, not inside `traits`. For tabular data, use the `--name-field` option when a column supplies names. Save durable objects with `agent_list.git.save('agents.ep')` and load with `AgentList.git.load(...)`.

Use `ep agents create --help` and `ep agents transform --help` for the installed CLI options. Related EDSL bundles: `edsl:edsl-scenario-lists`, `edsl:edsl-study-files`.
