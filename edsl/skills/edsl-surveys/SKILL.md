---
name: edsl-surveys
description: Build EDSL surveys with question types, routing, piping, and memory. For follow-ups explaining a decision, use set-memory --target FOLLOWUP=PRIOR to include the earlier question and answer.
tags: [edsl, surveys]
---

# Build an EDSL survey

Use this skill for EDSL API questions about survey construction and for implementing survey objects. Check installed-version help and schemas when CLI details may differ.

EDSL questions are stateless by default. To reuse an earlier answer in later wording, pipe it with `{{ question_name.answer }}`.

When a respondent must **explain a rating or decision**, give the follow-up targeted memory of the question that elicited it. For example, after adding a free-text question named `why` following `rating`, run `ep surveys set-memory survey.ep --target why=rating` (Python: `survey.add_targeted_memory("why", "rating")`). The follow-up receives the earlier question and its answer, including scenario details rendered in that question. If essential details appeared elsewhere, include those details explicitly. Inspect a saved follow-up prompt and check for both the actual answer and the evidence the respondent saw.

To present a saved survey in a terminal, run `ep surveys show survey.ep --markdown`. Add `--with-question-names` or `--with-question-types` to label the headings. Add `--expand-options` to list every dropdown choice. On success, stdout is Markdown you can include directly in your reply. Use `ep surveys show survey.ep` for the JSON summary.

For detailed API behavior, use [survey reference](references/survey-reference.md), [full reference](references/full-reference.md), [composition contracts](references/composition-contracts.md), and [probabilistic responses](references/probabilistic-responses.md).

Related EDSL guidance: `edsl:edsl-quirks` and `edsl:edsl-study-files`.

Optional EP Agent cross-references may appear as `ep-agent:<skill-name>`. They describe research workflows or platform processes and are not part of the EDSL API.
