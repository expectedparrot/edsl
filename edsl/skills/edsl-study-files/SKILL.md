---
name: edsl-study-files
description: EDSL object source files and reproducible construction of Survey, ScenarioList, AgentList, ModelList, Jobs, and Results.
tags: [edsl, files, jobs]
---

# EDSL study files

Keep object construction in readable source files, export named EDSL objects, and save durable objects with their supported `.git.save(...)` interface. Build `Jobs` from the saved component objects with `ep jobs build`; run it with `ep run ... --output results.ep`. Do not run inference as an import-time side effect of a Python source file.

For balanced A/B studies, save one assignment per respondent. Build with `ep jobs build --expect-interviews N` using the intended count per iteration. If separate agent and scenario files have one matching row per respondent in the same order, add `--pair-agents-scenarios`. If a group should shape simulated judgments, include it in the persona or question. Use `ep jobs preview-prompt jobs.ep QUESTION --interview-index N` to check the actual prompts from each group and arm. For a saved job, run `ep jobs variants study.ep --group-by scenario.arm --unique-by agent.name --expect-interviews 16` with your own assignment fields and intended count. Use each returned interview index to rehearse its version, including a boundary reply that must be rejected. See [one assigned stimulus per respondent](references/assigned-stimuli.md) for both a joined scenario and a Jinja conditional.

Use `ep inspect agents.ep --markdown --page 1 --page-size 5` to present a page of agents with stacked traits and instructions. The same command previews saved scenarios, models, jobs, results, surveys, collections, and prompts. Check the exit code before presenting the Markdown.

Before reusing archived responses, run `ep results check-survey results.ep --against jobs.ep` to compare the saved survey definitions, then verify the expected respondent or scenario IDs and their counts in Results.

Common files include `study_survey.py`, `study_scenario_list.py`, `study_agent_list.py`, and optionally `study_model_list.py`. Use `ep models create` for ordinary model selections when it covers the needed configuration.

Use the installed CLI help and `edsl:edsl-surveys` for current APIs. A scenario field must be consumed by the survey where required by the installed EDSL validation rules. `Agent.name` is a distinct constructor field, not a trait.

This skill covers EDSL file and object conventions only. Study design choices, cost approval, remote execution policies, reporting workflows, and EP Agent scaffolds belong to the separately managed EP Agent environment (`ep-agent:workflow-file-layout`, `ep-agent:workflow-model-selection`).
