One additional pattern worth considering: shared state updates do not have to be purely mechanical operations over raw respondent answers. We can use `QuestionThinking` or hidden analysis questions to derive structured updates, then write those derived values into shared state.

Pattern:

```text
respondent answer -> QuestionThinking analysis -> structured update -> shared state -> later interviews read updated state
```

Example:

```python
q_extract_themes = QuestionThinking(
    question_name="extract_themes",
    question_text="""
Given this interview answer:

{{ interview_response.answer }}

Existing themes:

{{ shared_state.themes.members }}

Return JSON with:
- new_themes
- existing_themes_mentioned
- representative_quote
""",
)
```

Then declared shared-state writes could use the thinking question's structured answer:

```python
survey.add_shared_state_write(
    after_question="extract_themes",
    target="themes",
    operation="add_many",
    values="{{ extract_themes.answer.new_themes }}",
)

survey.add_shared_state_write(
    after_question="extract_themes",
    target="theme_counts",
    operation="increment_many",
    values="{{ extract_themes.answer.existing_themes_mentioned }}",
)

survey.add_shared_state_write(
    after_question="extract_themes",
    target="theme_evidence",
    operation="append",
    value={
        "themes": "{{ extract_themes.answer.existing_themes_mentioned }}",
        "quote": "{{ extract_themes.answer.representative_quote }}",
        "respondent_id": "{{ agent.id }}",
    },
)
```

This would be especially useful for human surveys if hidden analysis questions can run after a human-visible answer. The human respondent answers normally; EDSL/Coop runs a hidden `QuestionThinking` step; the result updates shared state; later respondents or AI interviewers read the updated state.

Applications this unlocks:

- Adaptive interview theme tracking: extract themes after each interview and let later interviewers probe emerging or underexplored themes.
- Dynamic interview guides: update suggested follow-ups, saturated topics, and unresolved questions as interviews accumulate.
- Live qualitative codebook evolution: maintain codes, definitions, examples, merge suggestions, and deprecated codes.
- Product research memory: track pain points, feature requests, competitor mentions, objections, and representative quotes.
- Consensus/disagreement maps: extract claims and stances, then ask later experts about unresolved disagreements.
- Red-team finding trackers: identify vulnerability themes, severities, examples, and mitigations while avoiding duplicate probing.
- Research memo building: append structured takeaways, quotes, surprises, and recommended next questions after each interview.
- Respondent routing: classify respondents by persona/topics/expertise and route later follow-ups based on accumulated state.

Design implication: the shared-state write machinery should be able to write values derived from prior answers, including answers from hidden thinking/analysis questions. This keeps reads simple (`{{ shared_state... }}`), keeps writes explicit/auditable, and lets model-assisted analysis maintain high-level shared state without requiring arbitrary Python callbacks.
