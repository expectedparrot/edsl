# Human Survey Back Navigation Spec

## Summary

Add support for a Back button in human survey navigation.

The feature should allow a human respondent to return to prior questions, revise answers, and continue through the survey using the existing skip-rule and piping semantics. The implementation should be locally testable in EDSL, even though the primary user-facing surface is humanize.

The core design principle is:

> `Survey` defines possible forward flow. `humanize_schema` defines human navigation policy. A local `SurveySession` applies both.

## Motivation

EDSL surveys currently support forward navigation through rules, skip logic, stop rules, memory, and piping. That is appropriate for model execution and for simple human collection, but real human survey UX often needs correction:

- Respondents make mistakes and need to revise a prior answer.
- Branching surveys should recompute the next path after an answer changes.
- Human survey UI should behave like a stateful respondent session, not only a one-pass generator.
- Local tests should be able to validate human navigation behavior without requiring Coop, a browser, or remote services.

This is especially important for humanize workflows where survey authors want a normal survey experience but still need EDSL's deterministic survey semantics.

## Current Implementation Context

Relevant current code:

- `edsl/surveys/survey_navigator.py`
  - `SurveyNavigator.next_question(current_question, answers)` computes the next forward question from the current question and an answers dict.
  - It applies after-rules and then before-rules/skip-rules for candidate next questions.
- `edsl/surveys/survey_navigator.py`
  - `SurveyNavigator.gen_path_through_survey()` is a forward-only coroutine that mutates `survey.answers`.
- `edsl/surveys/rules/rule.py`
  - `Rule` rejects backward jumps. This is good and should remain true.
- `edsl/surveys/dag/construct_dag.py`
  - `survey.dag()` combines memory dependencies, rule dependencies, and piping dependencies.
- `edsl/coop/coop_humanize_schema.py`
  - Humanize schema is already the convention for human-specific survey behavior.
  - Top-level `survey` options currently include `custom_css`.
  - Per-question humanize schema classes already hold controls like `optional`, `format`, `comment`, and interview-specific configuration.

Back navigation should not require changing the acyclic rule model. It should be modeled as respondent session history layered on top of existing forward navigation.

## Non-Goals

- Do not add backward edges to `Rule`.
- Do not make `Survey.next_question()` compute a previous question.
- Do not make model/agent execution use a Back button.
- Do not expose invalidated branch answers as ordinary `answer.<question>` values in `Results`.
- Do not implement a random-access "jump to any previous question" UI in v1.

## Humanize Schema Design

Back navigation is human-specific, so settings should live in `humanize_schema`.

### Survey-Level Navigation

Add a survey-level navigation config:

```json
{
  "survey": {
    "navigation": {
      "back_button": true
    }
  },
  "questions": {}
}
```

Proposed Pydantic model:

```python
class SurveyNavigationConfig(HumanizeSchemaBase):
    back_button: bool = False


class SurveyHumanizeSchema(HumanizeSchemaBase):
    custom_css: Optional[str] = None
    navigation: Optional[SurveyNavigationConfig] = None
```

Default behavior:

- Missing `survey.navigation` means no Back button.
- Missing `survey.navigation.back_button` means `False`.

### Question-Level Navigation

Some questions should act as navigation boundaries. Examples:

- consent
- treatment/randomization assignment
- payment or external side-effect confirmations
- screeners where going back after termination should be disallowed

Add explicit question-level navigation config to every supported humanize question schema class.

Proposed model:

```python
class QuestionNavigationConfig(HumanizeSchemaBase):
    allow_back_past: bool = True
```

Each humanize question schema gets:

```python
navigation: Optional[QuestionNavigationConfig] = None
```

Example:

```json
{
  "survey": {
    "navigation": {
      "back_button": true
    }
  },
  "questions": {
    "consent": {
      "navigation": {
        "allow_back_past": false
      }
    },
    "assignment": {
      "navigation": {
        "allow_back_past": false
      }
    },
    "feedback": {
      "optional": true
    }
  }
}
```

Semantics:

- `allow_back_past: false` means the respondent cannot navigate backward from a later visited question to a point before this question once this question has been completed and the respondent has moved forward.
- The respondent may still edit the current question before moving forward.
- Missing `navigation` means defaults.
- Missing `allow_back_past` means `True`.
- Question-level navigation settings only matter when the survey-level Back button is enabled.

This requires altering each supported humanize question schema class. That is acceptable and keeps the schema explicit, consistent with the current code style.

## Metadata History

Always retain navigation metadata. This should not be a user-configurable control.

The session should preserve enough history to audit what happened:

```json
[
  {
    "event": "answer",
    "question": "owns_car",
    "answer": "no",
    "revision": 1
  },
  {
    "event": "forward",
    "from": "owns_car",
    "to": "transit_mode"
  },
  {
    "event": "answer",
    "question": "transit_mode",
    "answer": "bus",
    "revision": 1
  },
  {
    "event": "back",
    "from": "transit_mode",
    "to": "owns_car"
  },
  {
    "event": "answer",
    "question": "owns_car",
    "answer": "yes",
    "revision": 2
  },
  {
    "event": "invalidate",
    "question": "transit_mode",
    "reason": "path_truncated"
  }
]
```

Open implementation detail: exact metadata namespace in final `Results`.

Recommended default:

- Active answers appear in normal `answer.<question>` fields.
- Inactive/invalidated answers do not appear as active answer values.
- Inactive answers and navigation events are retained in metadata.

Possible metadata shape:

```json
{
  "humanize_navigation": {
    "events": [],
    "inactive_answers": {
      "transit_mode": {
        "answer": "bus",
        "reason": "path_truncated",
        "revision": 1
      }
    }
  }
}
```

## Local Survey Session Design

Add a local session/state-machine layer, probably:

```text
edsl/surveys/survey_session.py
```

Possible API:

```python
session = SurveySession(
    survey,
    humanize_schema=humanize_schema,
)
```

or:

```python
session = survey.start_session(humanize_schema=humanize_schema)
```

Core methods/properties:

```python
session.current()
session.current_name
session.answer(question_name, value)
session.forward()
session.back()
session.can_back()
session.final_answers()
session.navigation_history()
session.inactive_answers()
```

Internal state:

```python
current_item
active_path
current_index
active_rule_answers
answer_records
navigation_events
```

`active_rule_answers` should use the same key convention as rules:

```python
{
  "q0.answer": "yes"
}
```

The session should call existing survey navigation methods for forward movement:

```python
survey.next_question_with_instructions(current_item, active_rule_answers)
```

Back movement should use session history:

- Back decrements through the actual visited path.
- Back does not ask the rule system for a prior question.
- Back is blocked if it would cross a completed question with `allow_back_past: false`.

## Forward Navigation Semantics

Forward navigation should always recompute from the current answer state.

Example:

```text
q0: Do you own a car?
  yes -> q_car
  no  -> q_transit
```

Flow:

1. respondent answers `q0 = no`
2. forward goes to `q_transit`
3. respondent answers `q_transit = bus`
4. respondent goes back to `q0`
5. respondent changes `q0 = yes`
6. forward recomputes and goes to `q_car`

The old `q_transit` answer becomes inactive and is retained only in metadata.

## Answer Change Semantics

When an answer changes at the current question:

- Record a new answer revision.
- Truncate the active path after the current item.
- Mark downstream answers inactive.
- Continue forward using the current answer state.

For v1, this path truncation rule is simpler and safer than trying to preserve downstream answers that may or may not still be semantically valid.

Later optimization:

- Use `survey.dag(textify=True)` to invalidate only dependent downstream answers.
- Preserve still-valid downstream answers when the path remains unchanged.

V1 should prefer correctness and clear semantics.

## Back Boundary Semantics

Given:

```text
consent -> q1 -> q2
```

Schema:

```json
{
  "survey": {
    "navigation": {
      "back_button": true
    }
  },
  "questions": {
    "consent": {
      "navigation": {
        "allow_back_past": false
      }
    }
  }
}
```

Expected behavior:

- At `q2`, Back to `q1` is allowed.
- At `q1`, Back to `consent` or before consent is blocked if that would cross the consent boundary.

Question to settle during implementation:

- Should Back from `q1` to `consent` be allowed, while Back from `consent` to any earlier item is blocked?
- Or should completing consent prevent returning to consent at all?

Recommended interpretation:

> `allow_back_past: false` blocks crossing from after the question to before the question. It does not necessarily block returning to the boundary question itself.

If we need the stricter behavior later, add a second field:

```json
{
  "navigation": {
    "allow_back_to": false,
    "allow_back_past": false
  }
}
```

Do not add this stricter setting in v1 unless required.

## Instructions And Question Groups

The session should support instructions because human survey navigation already includes them through `next_question_with_instructions`.

Initial behavior:

- Instructions can be part of `active_path`.
- Back can return to an instruction unless blocked by a question boundary.
- Instructions do not have question-level humanize schema entries.

Question groups:

- v1 may operate item-by-item even if the UI displays grouped questions.
- If humanize renders groups as pages, `SurveySession` may eventually need page-level path entries.
- For local v1, test item-level semantics first.

## Stop Rules

Stop rules should be handled by existing forward navigation returning `EndOfSurvey`.

Back after stop:

- If Back button is enabled and the stop boundary is not otherwise blocked, a respondent may go back from an end state to revise an answer.
- If a screener or terminal question should prevent this, set `allow_back_past: false` on the appropriate boundary question.

This keeps stop-rule behavior configurable through question-level navigation boundaries.

## Randomization

Randomization needs special care.

Principles:

- Randomized assignments should be sticky within a respondent session.
- Going back should not re-randomize treatment.
- If a randomization/assignment question is represented as a question in the survey, authors can set `allow_back_past: false`.
- If randomization happens outside ordinary questions, the session/backend should still record the assignment in metadata and treat it as sticky.

Open question:

- Are all humanize randomization points represented in the EDSL survey object, or can Coop/backend add assignment state externally?

## Results Semantics

Default `Results` should show final active answers only.

Invalidated path answers should not appear as ordinary answer values:

```python
results.select("answer.*")
```

should mean final completed path answers, not every answer a respondent ever entered.

Recommended behavior:

- Active answers: normal `answer.<question>` fields.
- Skipped/inactive questions: absent or `None`, consistent with existing EDSL convention.
- Navigation history: metadata.
- Invalidated answers: metadata.

## CLI Support

Extend humanize schema CLI controls.

Survey-level:

```bash
ep humanize schema create --survey survey.ep --back-button --output humanize.json
ep humanize schema set <uuid> --back-button
```

Question-level:

```bash
ep humanize schema create --survey survey.ep --back-button --no-back-past consent
ep humanize schema set <uuid> --survey survey.ep --no-back-past consent
```

Alternative flag names:

```bash
--back-boundary consent
--disallow-back-past consent
```

Recommended CLI name:

```bash
--no-back-past QUESTION
```

because it maps directly to:

```json
{
  "navigation": {
    "allow_back_past": false
  }
}
```

## Testing Plan

### Schema Tests

Add tests in:

```text
tests/coop/test_coop_humanize_schema.py
```

Cases:

- Survey-level `navigation.back_button: true` validates.
- Survey-level `navigation.back_button: false` validates.
- Unknown survey navigation key fails.
- Question-level `navigation.allow_back_past: false` validates for each supported question type or at least representative types.
- Unknown question navigation key fails.
- Non-boolean `allow_back_past` fails.

### CLI Tests

Add tests in:

```text
tests/test_cli.py
```

Cases:

- `ep humanize schema create --back-button` writes `survey.navigation.back_button`.
- `ep humanize schema create --no-back-past consent` writes question-level navigation.
- `ep humanize schema set --back-button --no-back-past consent` patches expected schema.

### Local Navigation Tests

Add tests in:

```text
tests/surveys/test_survey_session_navigation.py
```

Cases:

- Back disabled by default.
- Back enabled by `humanize_schema.survey.navigation.back_button`.
- Linear survey back/forward.
- Branch change invalidates old branch answer.
- Invalidated answers do not appear in `final_answers()`.
- Invalidated answers appear in metadata/history.
- Back blocked by `allow_back_past: false`.
- Stop rule can be reversed by Back unless blocked.
- Instructions work in active path.

## Suggested Implementation Phases

### Phase 1: Schema

- Add `SurveyNavigationConfig`.
- Add `QuestionNavigationConfig`.
- Add `navigation` field to `SurveyHumanizeSchema`.
- Add `navigation` field to all supported question-level humanize schema classes.
- Add validation tests.

### Phase 2: CLI

- Add `--back-button`.
- Add `--no-back-past QUESTION`.
- Update schema builder.
- Add CLI tests.

### Phase 3: Local Session Engine

- Add `SurveySession`.
- Add `Survey.start_session(humanize_schema=None)`.
- Implement forward/back/path truncation/history.
- Add local navigation tests.

### Phase 4: Humanize Integration

- Make human survey UI/backend consume the same navigation semantics.
- Ensure final Results include only active answers.
- Persist navigation metadata.

## Open Questions

- Should `allow_back_past: false` allow returning to the boundary question itself?
- What exact metadata namespace should navigation history use in `Results`?
- Should inactive answers be included in local `SurveySession.final_result_metadata()` even before Results integration?
- How should grouped-page UIs map to item-level session history?
- Are randomization boundaries always represented as EDSL questions?

