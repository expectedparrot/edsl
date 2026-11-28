---
name: edsl-human-survey
description: Create, configure, inspect, and retrieve EDSL humanized surveys.
tags: [edsl, reference]
---

# EDSL humanized surveys

`Survey.humanize()` configures an EDSL survey for browser-based respondents. EDSL's `ep humanize` commands create and manage deployed surveys, previews, schemas, responses, respondents, schedules, deliveries, and callbacks, and pause or resume response collection. Discover exact flags with `ep humanize --help` and the relevant subcommand help.

Memory modes for simulated `.run()` jobs do not apply to humanized surveys. Pipe earlier answers into later question text with `{{ question_name.answer }}`. For API details, consult [schema](references/humanize-schema.md), [grouped pages](references/grouped-pages-and-messages.md), [background questions](references/background-questions.md), [interviews](references/question-interview.md), [in-progress responses](references/in-progress-responses.md), [live editing](references/editing-live-surveys.md), and [interview languages](references/interview-languages.md).

For an AI follow-up, create a question of type `interview`. Put `{{ rating.answer }}` directly in its interview guide when the interviewer needs the earlier rating. For wording that changes with a language selection, use a Jinja `{% if %}` in the structured question text so responses stay in one column. With `ep humanize schema validate --survey survey.ep --schema browser.json --answers '{"rating":2}'`, supply each example language and inspect `rendered_question_texts`, the rendered guide, and the language assigned to each active mode. When the participant chooses the language for the opening turn, route to an interview configured for that language and check both paths with `ep surveys check-paths`.

Related EDSL bundles: `edsl:edsl-human-survey-agent-access`, `edsl:edsl-human-survey-assistant`, `edsl:edsl-human-survey-css`, `edsl:edsl-human-survey-javascript`, `edsl:edsl-human-survey-notifications`, `edsl:edsl-human-survey-preview`, and `edsl:edsl-prolific`.
