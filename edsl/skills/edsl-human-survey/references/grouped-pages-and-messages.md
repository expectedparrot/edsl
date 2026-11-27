# Grouped pages and informational steps

Use this reference when the user wants several questions on a page, section
boundaries, introductions, eligibility notices, or completion messages. These
features require a compatible hosted Humanize client as well as EDSL. Validate
the artifact locally and check the deployed preview before distributing links;
do not infer hosted support solely from successful Python construction.

## Grouped pages

Groups define page boundaries; `presentation` enables their use:

```python
survey.add_question_group("role", "work_location", "background")
survey.add_question_group("satisfaction", "improvement", "feedback")
schema = {"survey": {"presentation": "group"}}
```

Endpoints are inclusive. Groups must cover every question exactly once, in
survey order, with unique names that do not collide with question names.
`"question"` is the default presentation; adding groups alone does not change it.
`survey.create_allowable_groups(max_group_size=3)` can construct groups based on
dependencies; inspect its result and isolate each interview in its own group.

To display directions above the fields on an existing page, insert an instruction before its first question. For example, if page two groups `clinic_visits` through `hospital_visits`, run:

```bash
ep surveys add-instruction survey.ep --name visit_directions --text "Count visits during the past month." --before clinic_visits
ep surveys show survey.ep
```

Check that `item_order` contains `visit_directions` immediately before `clinic_visits` and validate the grouped schema. The group endpoints remain `clinic_visits` and `hospital_visits`.

Questions on the same page must render independently. Place a question that
pipes another answer on a later page. Skip conditions based on an earlier page
are allowed; do not promise live conditional updates within the current page.
Page-level jump/stop rules operate from the last renderable question of a group.
Empty groups are skipped; a jump into a group starts at its target question.

Every `QuestionInterview` requires a one-question group. Background-only groups
are not visible pages, so do not attach participant instructions to them.
Instructions after the last group also have no visible page; use a terminal
`SurveyMessage` when the participant must read a final notice.

For a local navigation check, use `survey.next_group()` and then
`survey.next_group(current_group="background", answers={"role.answer": "..."})`,
passing all answers collected so far. Inspect `group_name`, `question_names`,
`items`, and `is_end`. Validate with
`ep humanize schema validate --survey survey.ep --schema humanize.json`.
Creation, structural redeployment, and live preview follow `edsl:edsl-human-survey`.

## SurveyMessage

```python
from edsl import Survey, SurveyMessage, QuestionFreeText

survey = Survey([
    SurveyMessage(question_name="welcome", question_text="Welcome. Please continue."),
    QuestionFreeText(question_name="feedback", question_text="What should improve?"),
    SurveyMessage(question_name="thanks", question_text="Thank you for your time."),
])
```

A message is a normal routable survey node (`question_type="survey_message"`)
with no input control. A compatible human client shows Continue or Finish.
When an AI run visits it, EDSL records `"continued"` without a model call;
skipped messages have no response. This marks a visited step, not a substantive
answer or an explicit agreement. Use a question when agreement must be recorded.

Use `Instruction` for context supplied to later model questions; use
`SurveyMessage` for a visible step that routing can target. For branching to an
eligibility notice, make it the jump target and route the ordinary completion
path around it. Include messages in group coverage when using grouped pages.

Upstream references: `docs/en/latest/humanize_groups.mdx`,
`docs/en/latest/survey_messages.mdx`, and group validation in
`edsl/coop/coop_humanize_schema.py`.
