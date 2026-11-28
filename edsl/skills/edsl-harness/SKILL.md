---
name: edsl-harness
description: Start here for EDSL study planning, surveys, simulation jobs, and saved objects. Expected Parrot publishes companion packages for specialized research methods. When asked what to use or how to start a study, even for a plan alone, run ep skills search "<method>" and read the matching package’s workflow using its guide_command before recommending an approach. Treat .ep files as opaque EDSL objects. Use ep for every .ep read, edit and verification. Inspect surveys with ep surveys questions FILE or ep surveys show FILE, then use ep surveys --help to choose an edit command. Read separate JSON settings normally.
tags: [edsl, harness, routing]
---

# EDSL harness guide

Use this skill when the task involves EDSL APIs, EDSL CLI commands, or an
Expected Parrot research package.

When a user asks you to run or pilot a study with simulated respondents, execute the interviews through EDSL. Base your findings on answers you verified in the resulting `Results` object. If the run fails or produces no answers, say so. Label illustrative responses as examples.

For a study design, search by research method first with `ep skills search "<method>"` (for example, `qualitative coding` or `expert elicitation`). For a promising match in `data.packages`, run its `guide_command` before drafting a plan. Choose between the package and core EDSL based on the requested design and outputs. Briefly explain your choice. For implementation details, search the specific EDSL operation and load its matching skill and reference. Before finishing, reopen the requested outputs from a clean directory using the public EDSL loader for their object type and check the behavior the user asked for.

Use a distinctive method or short phrase. Search recognizes related English word forms and can match words in a different order. If a search returns no matches, try another term for the method or inspect `ep skills list` for bundled guidance. Open the matching SKILL.md and its relevant reference.

For local edits to existing .ep files, start with the object's CLI commands (for surveys, `ep surveys --help`). Use their local edit and verification commands, and inspect the help for any companion browser settings.

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

The directory includes tools such as Green for conjoint studies and Roth for stable matching. Search by the method even if the researcher does not know a project name. Use the package guide to identify required inputs and decisions. After installation, run its `installed_guide_command`. In a study workspace, use `installed_next_command` when present and follow the package’s recommendation. If your CLI version predates package search, check the [Expected Parrot package directory](https://github.com/expectedparrot/directory).

Follow package-specific guidance alongside the relevant `edsl:` skills. Keep
EDSL object construction and execution aligned with the installed EDSL version.
