# Survey composition contracts

Use these supported relationships when designing a survey that combines human
answers, background AI inference, dynamic options, or an adaptive interview.
The linked references contain implementation details.

| Relationship | Contract | Implementation reference |
|---|---|---|
| Questions → grouped page | Define question groups and enable group presentation; keep same-page questions independent and interviews on their own pages. | `edsl:edsl-human-survey` (optional cross-reference: Grouped pages) |
| Notice → routing step | `SurveyMessage` is a display-only routable node; `Instruction` supplies later model context. | `edsl:edsl-human-survey` (optional cross-reference: Informational steps) |
| Question → thinking step | `thinking_question(q, ...)` preserves the wrapped question's answer type and validation, using its own model and system prompt. Wrap `QuestionList` when later questions need a list. | [Thinking wrapper](full-reference.md#per-question-model--system-prompt-thinking_question) |
| Thinking step → human question | In a humanized survey, thinking steps run invisibly on the server, store their answers, and auto-advance to the next visible question. | `edsl:edsl-human-survey` (optional cross-reference: Background questions) |
| Prior answer → later content | Pipe `{{ question_name.answer }}` into later question text or an `interview_guide`. In human surveys, explicitly pipe the answers the next question needs; simulation memory settings do not supply this context. | `edsl:edsl-human-survey` (optional cross-reference: Human answer piping) |
| List answer → choice options | A list-valued answer can supply `question_options="{{ items.answer }}"` for a later checkbox or multiple-choice question. Pass the whole template string, not a one-element list containing it. | [Dynamic options](survey-reference.md#using-prior-answers-as-question-options) |
| Structured questions → adaptive interview | A `QuestionInterview` can follow structured questions in the same human survey. Pipe the relevant prior answers into its guide so it can probe them without re-asking. | `ep-agent:methods-ai-interview` |

These contracts support a human free-text answer → thinking-wrapped list →
human checkbox → adaptive interview in one humanized survey. Choosing this
composition does not require a separate custom application or a second survey.

## Boundaries that affect design

- A free-text answer containing JSON-looking text is not a typed list. Choose
  the wrapped question type to match what the next question consumes.
- Piping supplies prior answers; it does not grant access to future answers or
  automatically give a human interview all earlier survey context.
- Background thinking and AI interviews consume inference credits. They are
  not free merely because a human is answering the visible questions.
- Before deployment, render a runway preview for wording, order, and layout
  (`edsl:edsl-human-survey-preview`). It does not run the dynamic flow (piping,
  background steps, the interview itself), so in a deployed survey use the
  returned `preview_url` for those. See `edsl:edsl-human-survey`.

These are composition facts for design. Construct and validate the actual
artifact during implementation, including requested fixed options, write-ins,
interview mode, and schema settings.
