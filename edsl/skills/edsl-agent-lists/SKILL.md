---
name: edsl-agent-lists
description: Build, import, validate, and save EDSL AgentLists from Python data or tabular files.
tags: [edsl, reference]
---

# EDSL AgentList

For a synthetic panel built from separate category totals, use `ep agents from-margins margins.csv --seed 43 --id-field person_id -o agents.ep`. The CSV columns are `field,category,count`. Each trait must total the same population size. Rebuild from the supplied file for each seed. Read joint counts from the saved package with `ep agents tally agents.ep --trait age_group --trait commute_mode`, substituting the actual trait names. Verify the total before reporting any zero. A cross-tabulation in this panel describes one possible assignment of traits. Population associations require joint data.

To revise one item in a saved list, run `ep agents edit-item agents.ep --index 0 --patch '{"traits":{"city":"Boston"}}'`. Use `--insert` to append or insert an item and `--remove --index N` to delete one. Add `--output revised.ep` to keep the original.

Use `AgentList` to represent respondent personas or other agents in EDSL. Construct from `Agent` instances or use `ep agents create` for CSV and Excel inputs. Keep shared instructions on the list or agents as supported by the current API; represent per-agent differences as traits. See the [construction guide](references/construction.md).

`name` is reserved by `Agent`: pass it as `Agent(name=..., traits={...})`, not inside `traits`. For tabular data, use the `--name-field` option when a column supplies names. Save durable objects with `agent_list.git.save('agents.ep')` and load with `AgentList.git.load(...)`.

Use `ep agents create --help` and `ep agents transform --help` for the installed CLI options. Related EDSL bundles: `edsl:edsl-scenario-lists`, `edsl:edsl-study-files`.
