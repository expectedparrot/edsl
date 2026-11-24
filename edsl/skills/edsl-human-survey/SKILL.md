---
name: edsl-human-survey
description: Create, configure, inspect, and retrieve EDSL humanized surveys.
tags: [edsl, reference]
---

# EDSL humanized surveys

`Survey.humanize()` configures an EDSL survey for browser-based respondents. EDSL's `ep humanize` commands create and manage deployed surveys, previews, schemas, responses, respondents, schedules, deliveries, and callbacks, and pause or resume response collection. Discover exact flags with `ep humanize --help` and the relevant subcommand help.

Memory modes for simulated `.run()` jobs do not apply to humanized surveys. Pipe earlier answers into later question text with `{{ question_name.answer }}`. For API details, consult [schema](references/humanize-schema.md), [grouped pages](references/grouped-pages-and-messages.md), [background questions](references/background-questions.md), [interviews](references/question-interview.md), [in-progress responses](references/in-progress-responses.md), [live editing](references/editing-live-surveys.md), and [interview languages](references/interview-languages.md).

Related EDSL bundles: `edsl:edsl-human-survey-agent-access`, `edsl:edsl-human-survey-assistant`, `edsl:edsl-human-survey-css`, `edsl:edsl-human-survey-javascript`, `edsl:edsl-human-survey-notifications`, `edsl:edsl-human-survey-preview`, and `edsl:edsl-prolific`.
