---
name: edsl-scenario-lists
description: Construct EDSL ScenarioLists from Python data, files, combinations, images, or other supported sources.
tags: [edsl, reference]
---

# EDSL ScenarioList

For a custom sampling or analysis script, export the records with `ep scenarios show frame.ep --limit 0 -o rows.json`. Work with the JSON array, then write the selected records through `ep scenarios create --from-json selected.json -o selected.ep`. Reopen the output with `ep validate --file selected.ep --type scenario_list`. In Python, use `ScenarioList.git.load(path, sync_coop=False)` and `ScenarioList(rows).git.save(output_path, sync_coop=False)` when the script needs native EDSL types.

To revise one item in a saved list, run `ep scenarios edit-item scenarios.ep --index 0 --patch '{"city":"Boston"}'`. Use `--insert` to append or insert an item and `--remove --index N` to delete one. Add `--output revised.ep` to keep the original.

To verify a saved dataset against arithmetic or eligibility rules, run `ep scenarios check-rows data.ep --require bounds "0 <= low <= high <= eligible"`. Repeat `--require NAME EXPRESSION` for each independent check. When a rule applies only to some records, use `--require-if NAME WHEN EXPRESSION`, for example `--require-if stock "active" "units > 0"`. The report counts skipped rows for each rule. Add `--id-field` when a reviewer needs record identifiers. The CLI checks every row. For a complete audit file, pass `--limit 0`. Otherwise the report lists up to 20 failed rows and sets `truncated` when there are more.

For an analyst handoff, select the fields to release with `ep scenarios transform source.ep --select participant_code --select score --fresh-package -o partner.ep`. This writes the selected rows with their original types into a single-revision file, excluding the codebook and earlier drafts. Inspect the rows and run `ep log partner.ep` before sharing.

Use `ScenarioList` to represent scenario variations for surveys and jobs. Construct from `Scenario` instances, dictionaries, supported CSV/Excel inputs, or combinations. For image scenarios, use `Scenario.from_image(...)` and reference the image field in every question that needs the image.

A scenario value must be used in question text where required by EDSL jobs compatibility checks. `ScenarioList` supports normal mutable-sequence operations, including `.append()`. Save durable artifacts with `.git.save(...)`.

See the [detailed construction patterns](references/detailed-guide.md). Related bundles: `edsl:edsl-file-store`, `edsl:edsl-study-files`.
