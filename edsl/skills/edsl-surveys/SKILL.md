---
name: edsl-surveys
description: EDSL question types, survey composition, answer piping, memory, and implementation patterns.
tags: [edsl, surveys]
---

# Build an EDSL survey

Use this skill for EDSL API questions about survey construction and for implementing survey objects. Check installed-version help and schemas when CLI details may differ.

EDSL questions are stateless by default. When a later question depends on an earlier choice, pipe each relevant answer into its question text with `{{ question_name.answer }}` or use an appropriate memory mode. Do not add unrelated prior answers. For a simulated follow-up such as “Why did you give that rating?”, inspect a saved interview prompt to verify that the model received the earlier rating and the stimulus it refers to.

To present a saved survey in a terminal, run `ep surveys show survey.ep --markdown`. Add `--with-question-names` or `--with-question-types` to label the headings. Add `--expand-options` to list every dropdown choice. On success, stdout is Markdown you can include directly in your reply. Use `ep surveys show survey.ep` for the JSON summary.

For detailed API behavior, use [survey reference](references/survey-reference.md), [full reference](references/full-reference.md), [composition contracts](references/composition-contracts.md), and [probabilistic responses](references/probabilistic-responses.md).

Related EDSL guidance: `edsl:edsl-quirks` and `edsl:edsl-study-files`.

Optional EP Agent cross-references may appear as `ep-agent:<skill-name>`. They describe research workflows or platform processes and are not part of the EDSL API.
