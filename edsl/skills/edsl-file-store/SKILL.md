---
name: edsl-file-store
description: Use EDSL FileStore and FileStoreList objects for files in scenarios and survey answers.
tags: [edsl, reference]
---

# EDSL FileStore

`FileStore(path=...)` wraps a local image, document, data file, or other supported file for use as an EDSL value. Place it in a `Scenario`, then reference the scenario field in question text, for example `{{ scenario.file_path }}`. Reference the FileStore field in **each question** that needs the file. Saying “see the attached image” alone leaves the model without the artwork. Reopen the saved job with `ep jobs preview-prompt signs.ep direction --interview-index 0 --expect-files 1`. The attachment list includes the MIME type, byte count, and SHA-256 so you can verify the input even when two files have the same name.

`FileStore` also provides helpers such as `extract_text()`, `mime_type`, `is_image()`, and `to_scenario_list()` for supported formats. File upload answers can be converted with `FileStore.from_file_upload_answer`; generated image answers can be passed to later image-generation questions. See the [detailed FileStore guide](references/detailed-guide.md).

Related bundles: `edsl:edsl-scenario-lists`, `edsl:edsl-surveys`.
