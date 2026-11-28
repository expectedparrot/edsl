---
name: edsl-study-files
description: EDSL object source files and reproducible construction of Survey, ScenarioList, AgentList, ModelList, Jobs, and Results.
tags: [edsl, files, jobs]
---

# EDSL study files

Choose the input object by what one row represents:

- **A simulated respondent.** Import profiles with `ep agents create --from-csv people.csv --name-field name --output people.ep` and pass `--agents people.ep` to `ep jobs build` or `--agent_list people.ep` to `ep run`. Use the actual name column, or omit `--name-field` when there is none. The other columns become traits that an ordinary simulated respondent receives in its persona prompt.
- **A situation or stimulus.** Import it as a `ScenarioList`. Pipe each relevant field into the question that needs it, e.g. `{{ product_description }}`. Identifiers can stay in Results for matching records.

For a pilot, inspect a saved decision prompt for one respondent. Check the system and user prompts for the profile details or stimulus that should influence that decision. A name or a Results column alone only identifies the row.

Keep object construction in readable source files, export named EDSL objects, and save durable objects with their supported `.git.save(...)` interface. Build `Jobs` from the saved component objects with `ep jobs build`; run it with `ep run ... --output results.ep`. Do not run inference as an import-time side effect of a Python source file.

Before writing a study-specific builder or analyzer, search for the research method with `ep skills search "<method>"`. Run a matching entry’s `guide_command` to read its package workflow before installation. Its README in the [Expected Parrot package directory](https://github.com/expectedparrot/directory) covers setup. For example, Green builds discrete-choice studies, Conversation manages multi-agent discussions, and Umriss calibrates synthetic populations against survey marginals. When a package fits the brief, follow its installation instructions, including any EDSL version pin. Run its `installed_guide_command` and use `installed_next_command` when present to resume the project. Check which files it exports or imports when handing work between the package and `ep`.

Use `ep inspect agents.ep --markdown --page 1 --page-size 5` to present a page of agents with stacked traits and instructions. The same command previews saved scenarios, models, jobs, results, surveys, collections, and prompts. Check the exit code before presenting the Markdown.

Common files include `study_survey.py`, `study_scenario_list.py`, `study_agent_list.py`, and optionally `study_model_list.py`. Use `ep models create` for ordinary model selections when it covers the needed configuration.

Use the installed CLI help and `edsl:edsl-surveys` for current APIs. `Agent.name` is a distinct constructor field, not a trait.

This skill covers EDSL file and object conventions only. Study design choices, cost approval, remote execution policies, reporting workflows, and EP Agent scaffolds belong to the separately managed EP Agent environment (`ep-agent:workflow-file-layout`, `ep-agent:workflow-model-selection`).
