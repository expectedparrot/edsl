---
name: edsl-scenario-lists
description: Construct EDSL ScenarioLists from Python data, files, combinations, images, or other supported sources.
tags: [edsl, reference]
---

# EDSL ScenarioList

Use `ScenarioList` to represent scenario variations for surveys and jobs. Construct from `Scenario` instances, dictionaries, supported CSV/Excel inputs, or combinations. For image scenarios, use `Scenario.from_image(...)` and reference the image field in every question that needs the image.

CSV imports preserve text, including leading zeroes in IDs. To import numeric fields, use the original CSV headers, for example `ep scenarios create --from-csv catalog.csv --column-type price=float --column-type seats=int --output catalog.ep`. Empty numeric cells and invalid numbers produce a validation error with the CSV record number, column and value.

A scenario value must be used in question text where required by EDSL jobs compatibility checks. `ScenarioList` supports normal mutable-sequence operations, including `.append()`. Save durable artifacts with `.git.save(...)`.

See the [detailed construction patterns](references/detailed-guide.md). Related bundles: `edsl:edsl-file-store`, `edsl:edsl-study-files`.
