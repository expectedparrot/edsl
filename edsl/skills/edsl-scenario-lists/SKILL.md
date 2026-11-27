---
name: edsl-scenario-lists
description: Construct EDSL ScenarioLists from Python data, files, combinations, images, or other supported sources.
tags: [edsl, reference]
---

# EDSL ScenarioList

To revise one item in a saved list, run `ep scenarios edit-item scenarios.ep --index 0 --patch '{"city":"Boston"}'`. Use `--insert` to append or insert an item and `--remove --index N` to delete one. Add `--output revised.ep` to keep the original.

Use `ScenarioList` to represent scenario variations for surveys and jobs. Construct from `Scenario` instances, dictionaries, supported CSV/Excel inputs, or combinations. For image scenarios, use `Scenario.from_image(...)` and reference the image field in every question that needs the image.

A scenario value must be used in question text where required by EDSL jobs compatibility checks. `ScenarioList` supports normal mutable-sequence operations, including `.append()`. Save durable artifacts with `.git.save(...)`.

See the [detailed construction patterns](references/detailed-guide.md). Related bundles: `edsl:edsl-file-store`, `edsl:edsl-study-files`.
