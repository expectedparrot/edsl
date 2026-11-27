---
name: edsl-surveys
description: EDSL question types, survey composition, answer piping, memory, and implementation patterns.
tags: [edsl, surveys]
---

# Build an EDSL survey

Use this skill for EDSL API questions about survey construction and for implementing survey objects. Check installed-version help and schemas when CLI details may differ.

For TypeSafe judgments or option probabilities in a batched Evaluation, use `ep skills show edsl-judgment-evaluations --reference SKILL.md`. Verify the delivered workload with `ep validate --file review.ep --type evaluation`.

EDSL questions are stateless by default. When a later question depends on an earlier choice, pipe each relevant answer into its question text with `{{ question_name.answer }}` or use an appropriate memory mode. Do not add unrelated prior answers.

For a separate auditor or judge on one item, keep the original question type. Use `ep surveys set-question-model survey.ep audit --service openai --model gpt-4o-mini --system-prompt "Apply the eligibility criteria."`. Pipe the earlier choice into the audit question or configure targeted memory. Reopen the package with `ep surveys preview-prompt survey.ep audit --answers '{"application":"renewal"}'` and check the model, system prompt, and actual choice in the user prompt.

For directions on a grouped browser page, use `ep surveys add-instruction survey.ep --name directions --text "Count visits during the past month." --before clinic_visits`. Group the questions using their names. Inspect `item_order` in `ep surveys show survey.ep` to verify that the instruction precedes the first question on the intended page.

For branching surveys, **before building or editing**, write named cases in `paths.json` from the research brief. Include screen-outs, both sides of each cutoff, each branch and the join. Reopen the saved survey with `ep surveys check-paths survey.ep --cases paths.json`. If it fails on an existing rule, inspect `ep surveys show survey.ep`, then use `ep surveys replace-rule survey.ep --question NAME --expression EXPR --output revised.ep`. This changes the existing rule at its original priority. Rerun the same cases on the file you deliver. See [question path cases](references/question-path-cases.md) for the JSON format.

To combine existing questionnaires, run `ep surveys compose first.ep second.ep -o combined.ep`. Normal completion continues into the next module. Explicit stop rules end the whole survey. Resolve duplicate question names using `ep surveys rename-question first.ep old new -o revised.ep` before composing. Verify the join and early exits with `ep surveys check-paths`.

To restore selected fields from an approved draft, find the revision with `ep log survey.ep` and read its wording and choices with `ep surveys questions survey.ep --ref COMMIT`. Apply those fields to the current package with `ep surveys update-question`. This also updates the wording stored in its memory plan.

For local edits, start with `ep surveys questions survey.ep`. Change wording or choices with `ep surveys update-question survey.ep NAME --question-text "..."` or repeated `--option` flags (the full ordered list). Use `--patch` for other fields, and `rename-question` for names used in piping, memory, or rules. Add `--output revised.ep` to keep the source. Use `ep surveys set-groups` to replace page boundaries, `ep humanize schema create --base-schema existing.json` to preserve browser settings, and `ep surveys check-paths --help` to verify grouped routes using sample answers.

To present a saved survey in a terminal, run `ep surveys show survey.ep --markdown`. Add `--with-question-names` or `--with-question-types` to label the headings. Add `--expand-options` to list every dropdown choice. On success, stdout is Markdown you can include directly in your reply. Use `ep surveys show survey.ep` for the JSON summary.

For detailed API behavior, use [survey reference](references/survey-reference.md), [full reference](references/full-reference.md), [composition contracts](references/composition-contracts.md), and [probabilistic responses](references/probabilistic-responses.md).

Related EDSL guidance: `edsl:edsl-quirks` and `edsl:edsl-study-files`.

Optional EP Agent cross-references may appear as `ep-agent:<skill-name>`. They describe research workflows or platform processes and are not part of the EDSL API.
