---
name: edsl-harness
description: Use EDSL's installed, version-matched skills and Expected Parrot package guidance when creating, running, or debugging EDSL work.
tags: [edsl, harness, routing]
---

# EDSL harness guide

Use this skill when the task involves EDSL APIs, EDSL CLI commands, or an
Expected Parrot research package.

## Find the right EDSL guidance

Use the `ep` executable from the active EDSL environment. If it is unavailable,
try `python -m edsl` in that environment. Check the installed version and the
skill catalog before relying on remembered APIs:

```bash
ep info
ep skills list --routing
ep skills search "<task topic>" --snippets
ep skills show <skill-name>
```

These commands return JSON. Parse stdout as JSON and inspect `status`, `data`,
and `warnings`. Search for the concrete task, then load only the matching skill
and any references it links. The installed package's skills match its EDSL
version. If a relevant skill is missing, check the installed version and use
that version's CLI help and documentation rather than guessing command flags.

For durable EDSL objects and source conventions, use `edsl:edsl-study-files`.
For question construction, use `edsl:edsl-surveys`; for a CLI or API edge case,
use `edsl:edsl-quirks`. Search the catalog for other topics instead of loading
every skill into the conversation.

## Organize new EDSL work

First inspect the current project and follow its existing structure. Do not
move or replace existing files just to match a template. For a new, small EDSL
study, keep object construction in separate readable files, for example:

```text
study/
  study_survey.py
  study_agent_list.py       # when the study needs agents
  study_scenario_list.py    # when the study needs scenarios
  study_model_list.py       # when a reusable model panel is useful
  results/
  analysis/
  writeup/
```

Use only the components the study needs. Keep model execution out of module
import side effects, validate inputs before running, and save durable objects
in supported `.ep` packages. Load `edsl:edsl-study-files` for the exact source
and CLI conventions.

## Find an Expected Parrot package

For work that appears to need a specialized Expected Parrot package beyond
EDSL's core capabilities, consult the [Expected Parrot package directory](https://github.com/expectedparrot/directory).
Choose a package that matches the user's task, then read its own repository
README and agent guidance before installing or using it. The directory is a
catalog, not an installer or a guarantee that a package is already present.
Install only the package needed for the requested work, using its documented
instructions; do not guess its CLI, dependencies, or file layout.

Follow package-specific guidance alongside the relevant `edsl:` skills. Keep
EDSL object construction and execution aligned with the installed EDSL version.
