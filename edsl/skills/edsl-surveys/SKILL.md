---
name: edsl-surveys
description: EDSL question types, survey composition, answer piping, memory, and implementation patterns.
tags: [edsl, surveys]
---

# Build an EDSL survey

For a questionnaire imported from a field manual, keep staff notes in an interviewer guide. `question_presentation` controls the prompt shown to the model. Extract approved wording into a JSON object keyed by question ID. For a response card, use an ordered list of the stem and approved option labels. Run `ep surveys check-wording survey.ep --expected stems.json --forbid-text "Read the response card."` with each distinctive staff phrase. Inspect failures with `ep surveys preview-prompt`. When a custom presentation contains staff directions, keep the directions in a guide and apply the reported `restore_default_presentation` command. Rerun the wording check on the saved file. Exercise both branches and the scored endpoints on the saved survey.

For a group discussion with private ballots, finish every baseline ballot before the first discussion turn. Maintain the analyst’s before/after ratings keyed by participant separately from the public transcript. Save or return both to the analyst. Construct each speaker’s prompt from their own persona and the public turns available at that point. Rehearse a single-person rating change and verify both the change report and the inputs seen by the other participants.

Use this skill for EDSL API questions about survey construction and for implementing survey objects. Check installed-version help and schemas when CLI details may differ.

When different participants own steps and one waits for another’s answer, use a respondent workflow. A Survey describes the questions one respondent answers. A `WorkflowExperiment` assigns each step to a participant, can release independent steps together and can skip optional steps. Read `ep skills show edsl-orchestration --reference SKILL.md`. Rehearse the saved definition with the supplied `step`, `participant`, and `answers` rows using `ep orchestration run --file experiment.json --responses responses.json --output rehearsal/`.

For TypeSafe judgments or option probabilities in a batched Evaluation, use `ep skills show edsl-judgment-evaluations --reference SKILL.md`. Verify the delivered workload with `ep validate --file review.ep --type evaluation`.

EDSL questions are stateless by default. When a later question depends on an earlier choice, pipe each relevant answer into its question text with `{{ question_name.answer }}` or use an appropriate memory mode. Do not add unrelated prior answers.

For a separate auditor or judge on one item, keep the original question type. Use `ep surveys set-question-model survey.ep audit --service openai --model gpt-4o-mini --system-prompt "Apply the eligibility criteria."`. Pipe the earlier choice into the audit question or configure targeted memory. Reopen the package with `ep surveys preview-prompt survey.ep audit --answers '{"application":"renewal"}'` and check the model, system prompt, and actual choice in the user prompt.

For directions on a grouped browser page, use `ep surveys add-instruction survey.ep --name directions --text "Count visits during the past month." --before clinic_visits`. Group the questions using their names. Inspect `item_order` in `ep surveys show survey.ep` to verify that the instruction precedes the first question on the intended page.

To extend an existing answer-order experiment, use `ep surveys set-option-randomization pilot.ep --add --question stall --pin-options '{"stall":["No preference"]}' --output updated.ep`. Check both `questions_to_randomize` and `options_to_pin` in the response. Each interview’s recorded options and prompt establish which label an answer code selected.

For branching surveys, **before building or editing**, write named cases in `paths.json` from the research brief. Include screen-outs, both sides of each cutoff, each branch and the join. Reopen the saved survey with `ep surveys check-paths survey.ep --cases paths.json`. If it fails on an existing rule, inspect `ep surveys show survey.ep`, then use `ep surveys replace-rule survey.ep --question NAME --expression EXPR --output revised.ep`. This changes the existing rule at its original priority. Rerun the same cases on the file you deliver. See [question path cases](references/question-path-cases.md) for the JSON format.

To combine existing questionnaires, run `ep surveys compose first.ep second.ep -o combined.ep`. Normal completion continues into the next module. Explicit stop rules end the whole survey. Resolve duplicate question names using `ep surveys rename-question first.ep old new -o revised.ep` before composing. Verify the join and early exits with `ep surveys check-paths`.

To restore selected fields from an approved draft, find the revision with `ep log survey.ep` and read its wording and choices with `ep surveys questions survey.ep --ref COMMIT`. Apply those fields to the current package with `ep surveys update-question`. This also updates the wording stored in its memory plan.

To change an existing question's type, use `ep surveys replace-question intake.ep rating --question-json '{"type":"linear_scale","options":[1,2,3,4,5]}'`. This keeps its name, position, routes and memory. The replacement inherits wording if omitted. Supply all settings for the new type, such as `interview_guide` for an AI interview. For browser follow-ups, pipe the earlier answer into that guide. Read back the saved survey and exercise each language and path.

For a survey with multiple versions, use `ep jobs variants` to find a representative interview index for each assignment group. On each version check a valid boundary with `ep jobs test-case --expect` and an invalid one with `--expect-rejection QUESTION`. For count-only questions use `ep jobs preview-prompt --expect-comments false` and inspect the rendered wording.

For an offline regression test of a saved job, run `ep jobs test-case study.ep --interview-index 0 --responses replies.json --expect answers.json -o checked.ep`. For a full rehearsal, use `ep jobs test-case study.ep --all -n 4 --responses replies.json -o rehearsal.ep` to run four iterations per assignment and save their prompts, raw test replies and decoded answers. For a saved treatment schedule, omit `-n` to use its planned iterations. `ep run --local` runs on this machine and still calls the provider for a hosted model. Both JSON objects map question names to values. Write each expected answer from the research brief before running the case. A budget reply can name the options directly, e.g. `{"bus":75,"rail":25}`. The corresponding final answer to check in `--expect` is `[{"bus":75},{"rail":25}]`. The command exercises the actual interview, returns a nonzero exit for a mismatch or validation error, and saves the completed case as Results on success.

For local edits, start with `ep surveys questions survey.ep`. Change wording or choices with `ep surveys update-question survey.ep NAME --question-text "..."` or repeated `--option` flags (the full ordered list). Use `--patch` for other fields, and `rename-question` for names used in piping, memory, or rules. Add `--output revised.ep` to keep the source. Use `ep surveys set-groups` to replace page boundaries, `ep humanize schema create --base-schema existing.json` to preserve browser settings, and `ep surveys check-paths --help` to verify grouped routes using sample answers.

To present a saved survey in a terminal, run `ep surveys show survey.ep --markdown`. Add `--with-question-names` or `--with-question-types` to label the headings. Add `--expand-options` to list every dropdown choice. On success, stdout is Markdown you can include directly in your reply. Use `ep surveys show survey.ep` for the JSON summary.

For detailed API behavior, use [survey reference](references/survey-reference.md), [full reference](references/full-reference.md), [composition contracts](references/composition-contracts.md), and [probabilistic responses](references/probabilistic-responses.md).

Related EDSL guidance: `edsl:edsl-quirks` and `edsl:edsl-study-files`.

Optional EP Agent cross-references may appear as `ep-agent:<skill-name>`. They describe research workflows or platform processes and are not part of the EDSL API.
