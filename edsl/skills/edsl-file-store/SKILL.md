---
name: edsl-file-store
description: Use EDSL FileStore and FileStoreList objects for files in scenarios and survey answers.
tags: [edsl, reference]
---

# EDSL FileStore

`FileStore(path=...)` wraps a local image, document, data file, or other supported file for use as an EDSL value. Place it in a `Scenario`, then reference the scenario field in question text, for example `{{ scenario.file_path }}`. EDSL resolves the stored content when constructing the model input.

`FileStore` also provides helpers such as `extract_text()`, `mime_type`, `is_image()`, and `to_scenario_list()` for supported formats. File upload answers can be converted with `FileStore.from_file_upload_answer`; generated image answers can be passed to later image-generation questions. See the [detailed FileStore guide](references/detailed-guide.md).

Related bundles: `edsl:edsl-scenario-lists`, `edsl:edsl-surveys`.
