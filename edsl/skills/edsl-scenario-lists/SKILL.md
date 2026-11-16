---
name: edsl-scenario-lists
description: Construct EDSL ScenarioLists from Python data, files, combinations, images, or other supported sources.
tags: [edsl, reference]
---

# EDSL ScenarioList

Use `ScenarioList` to represent scenario variations for surveys and jobs. Construct from `Scenario` instances, dictionaries, supported CSV/Excel inputs, or combinations. For image scenarios, use `Scenario.from_image(...)` and reference the image field in every question that needs the image.

A scenario value must be used in question text where required by EDSL jobs compatibility checks. `ScenarioList.append()` is not a mutating operation; create a Python list and construct a new `ScenarioList`. Save durable artifacts with `.git.save(...)`.

See the [detailed construction patterns](references/detailed-guide.md). Related bundles: `edsl:edsl-file-store`, `edsl:edsl-study-files`.
