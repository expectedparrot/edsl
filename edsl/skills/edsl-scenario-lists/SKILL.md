---
name: edsl-scenario-lists
description: Construct EDSL ScenarioLists from Python data, files, combinations, images, or other supported sources.
tags: [edsl, reference]
---

# EDSL ScenarioList

Use `ScenarioList` to represent scenario variations for surveys and jobs. Construct from `Scenario` instances, dictionaries, supported CSV/Excel inputs, or combinations. For image scenarios, use `Scenario.from_image(...)` and reference the image field in every question that needs the image.

Use scenario rows for the situations respondents evaluate. Pipe each detail needed for a decision into the corresponding question; other columns can serve as identifiers or analysis metadata. When a row describes the simulated respondent making the decision, import it as an `AgentList` (see `edsl:edsl-agent-lists`). `ScenarioList` supports normal mutable-sequence operations, including `.append()`. Save durable artifacts with `.git.save(...)`.

See the [detailed construction patterns](references/detailed-guide.md). Related bundles: `edsl:edsl-file-store`, `edsl:edsl-study-files`.
