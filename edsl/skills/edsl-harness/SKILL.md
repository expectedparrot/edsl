---
name: edsl-harness
description: Use EDSL's installed, version-matched skills and Expected Parrot package guidance when creating, running, or debugging EDSL work.
tags: [edsl, harness, routing]
---

# EDSL harness guide

Use this skill when the task involves EDSL APIs, EDSL CLI commands, or an
Expected Parrot research package.

## Find the right EDSL guidance

Use the installed `ep` CLI. For a simple survey, start with
`ep skills show edsl-surveys --reference SKILL.md`. When the right skill is
unclear, use `ep skills search "<task topic>" --snippets` and retrieve the
matching skill's `SKILL.md`. Read additional references by relative path
when the task calls for them. Parse the JSON status, data, and warnings.

Do not locate skill files by resolving `edsl.__file__` or constructing paths
under `site-packages`. Those paths are package internals and can bypass the
catalog for the active `ep` environment. The CLI returns the skills bundled
with that installed EDSL version. If a relevant skill is missing, check the
installed version and use that version's CLI help and documentation rather
than guessing command flags.

For durable EDSL objects and source conventions, use `edsl:edsl-study-files`.
For question construction, use `edsl:edsl-surveys`; for a CLI or API edge case,
use `edsl:edsl-quirks`. Search the catalog for other topics instead of loading
every skill into the conversation.

## Expected Parrot authentication

Before an operation that needs Expected Parrot cloud access, run
`ep auth status` and inspect `data.authenticated`. If no key is configured,
run `ep auth login`, complete its browser flow, then check the status again.
Do not print, copy into prompts, or expose API keys. Local EDSL work does not
require cloud authentication.

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
