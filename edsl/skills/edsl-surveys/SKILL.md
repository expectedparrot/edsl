---
name: edsl-surveys
description: EDSL question types, survey composition, answer piping, memory, and implementation patterns.
tags: [edsl, surveys]
---

# Build an EDSL survey

Use this skill for EDSL API questions about survey construction and for implementing survey objects. Check installed-version help and schemas when CLI details may differ.

EDSL questions are stateless by default. When a later question depends on an earlier choice, pipe each relevant answer into its question text with `{{ question_name.answer }}` or use an appropriate memory mode. Do not add unrelated prior answers.

To offer only the respondent's selected choices in a follow-up, pass the earlier checkbox answer as the entire `question_options` string. This example asks for two priorities, then one favorite.

```bash
ep surveys create --question-type checkbox --question-name priorities --question-text "Which two matter most?" --option Lighting --option Signage --option Cleanliness --min-selections 2 --max-selections 2 --output priorities.ep
ep surveys add-question priorities.ep --question-type multiple_choice --question-name favorite --question-text "Which is your favorite?" --question-json '{"question_options":"{{ priorities.answer }}"}'
```

Reopen the survey and render the follow-up with two known selections. Lighting and Signage should be the only available choices.

```bash
python -c "from edsl import Survey; q = Survey.git.load('priorities.ep', sync_coop=False).get('favorite'); selected = ['Lighting', 'Signage']; assert q.render({'priorities': {'answer': selected}}).question_options == selected"
```

To present a saved survey in a terminal, run `ep surveys show survey.ep --markdown`. Add `--with-question-names` or `--with-question-types` to label the headings. Add `--expand-options` to list every dropdown choice. On success, stdout is Markdown you can include directly in your reply. Use `ep surveys show survey.ep` for the JSON summary.

For detailed API behavior, use [survey reference](references/survey-reference.md), [full reference](references/full-reference.md), [composition contracts](references/composition-contracts.md), and [probabilistic responses](references/probabilistic-responses.md).

Related EDSL guidance: `edsl:edsl-quirks` and `edsl:edsl-study-files`.

Optional EP Agent cross-references may appear as `ep-agent:<skill-name>`. They describe research workflows or platform processes and are not part of the EDSL API.
