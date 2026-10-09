More stress-testing examples suggest a few additions/refinements to the shared-state design.

## 1. Live qualitative theme saturation

Pattern: human-visible interview answer -> hidden `QuestionThinking` extracts themes -> writes update shared theme state.

```python
survey = (
    Survey([q_experience, q_extract_themes])
    .with_shared_state(
        scope="{{ scenario.study_id }}",
        primitives={
            "themes": SharedSet(),
            "theme_counts": SharedCounterMap(),
            "theme_evidence": SharedLog(),
        },
    )
    .add_shared_state_write(
        after_question="extract_themes",
        target="themes",
        operation="add_many",
        values="{{ extract_themes.answer.new_themes }}",
    )
    .add_shared_state_write(
        after_question="extract_themes",
        target="theme_counts",
        operation="increment_many",
        values="{{ extract_themes.answer.mentioned_themes }}",
    )
    .add_shared_state_write(
        after_question="extract_themes",
        target="theme_evidence",
        operation="append_many",
        values="{{ extract_themes.answer.quotes }}",
    )
)
```

This points to `append_many`, low-count views such as `CounterMap.bottom_k`, and hidden analysis questions for human surveys.

## 2. Dynamic qualitative codebook

Shared primitives:

```python
primitives={
    "codes": SharedSet(),
    "codebook": SharedMap(),
    "coded_items": SharedLog(),
}
```

Annotators see `{{ shared_state.codes.members }}` and `{{ shared_state.codebook.values }}`. A hidden thinking question can propose missing codes, then writes can add the code and update the codebook:

```python
survey.add_shared_state_write(
    after_question="suggest_code",
    condition="{{ suggest_code.answer.new_code is not none }}",
    target="codebook",
    operation="put",
    key="{{ suggest_code.answer.new_code }}",
    value={
        "definition": "{{ suggest_code.answer.definition }}",
        "example_quote": "{{ suggest_code.answer.example_quote }}",
    },
)
```

This highlights that `SharedMap.put` needs separate templated `key` and `value`, and that collision/review semantics may matter for AI-suggested updates.

## 3. Peer review / annotation assignment

This example made `SharedQueue` or `SharedWorkPool` look more central than optional.

```python
primitives={
    "submissions": SharedMap(),
    "review_queue": SharedQueue(),
    "reviews": SharedLog(),
}
```

Submissions are enqueued for review; later respondents need to claim tasks atomically. Doing this through a `QuestionThinking` that selects from stale queue state is awkward. It would be better to support a pre-question shared-state action:

```python
survey.add_shared_state_action(
    before_question="review",
    target="review_queue",
    operation="claim",
    as_="claimed_submission",
    claimant_id="{{ agent.id }}",
)
```

Then the review question can reference:

```jinja2
{{ shared_state.claimed_submission.item_id }}
```

This suggests the design needs **before-question actions**, not only after-question writes.

## 4. Limited-capacity booking

Shared primitives:

```python
primitives={
    "slots": SharedCapacityPool(
        capacities={
            "Mon 9am": 3,
            "Mon 2pm": 2,
            "Tue 9am": 1,
        }
    ),
    "reservations": SharedLog(),
}
```

Question options can be current availability:

```python
QuestionMultipleChoice(
    question_name="slot",
    question_text="Choose one available slot.",
    question_options="{{ shared_state.slots.available }}",
)
```

Write:

```python
survey.add_shared_state_write(
    after_question="slot",
    target="slots",
    operation="reserve",
    resource="{{ slot.answer }}",
    quantity=1,
    holder_id="{{ agent.id }}",
    on_failure="retry_question",
)
```

This points to write-failure policies beyond just `error`/`warn`, especially for human UI:

- `error`
- `warn`
- `retry_question`
- possibly `skip_to`

## 5. Public goods / behavioral game

Shared primitives:

```python
primitives={
    "public_good": SharedRegister(initial_value=0),
    "contributions": SharedLog(),
    "contribution_by_player": SharedMap(),
}
```

This raises a small modeling question: should numeric `SharedRegister` support `increment`, or should we use a one-key `SharedCounterMap`? Either can work, but the primitive operation set should be clear.

## 6. Rumor / information diffusion

Shared primitive:

```python
primitives={
    "messages": SharedLog(),
}
```

Agents read recent visible messages and append new messages:

```jinja2
Recent public messages:
{{ shared_state.messages.tail }}
```

For network simulations, respondents may only see messages from neighbors. That suggests we may need shared-state **views**, not only raw primitive reads:

```python
views={
    "visible_messages": SharedLogView(
        target="messages",
        filter="{{ entry.sender_id in agent.neighbors }}",
        tail=10,
    )
}
```

## Design implications from these examples

1. We likely need both `after_question` writes and `before_question` actions.

2. Some shared-state operations need return values that later questions can reference, e.g. queue `claim`, capacity `reserve`, compare-and-set success/failure.

3. Write failures need control-flow semantics, especially in human surveys where stale state is normal.

4. Views are probably important:
   - `CounterMap.top_k`
   - `CounterMap.bottom_k`
   - `Log.tail`
   - filtered logs
   - capacity availability
   - claimed task views

5. `SharedQueue`/`SharedWorkPool` and `SharedCapacityPool` seem important for genuinely live coordination, not just aggregation.

6. Hidden analysis questions using `QuestionThinking` are a major use case: they let EDSL update semantic shared state such as themes, codebooks, claims, risks, or research memos.

7. Execution mode remains important:
   - sequential for deterministic LLM simulations
   - live for human surveys
   - snapshot for reproducible non-interdependent batches

Tentative refinement: the core API may want:

```python
.with_shared_state(scope=..., primitives={...}, views={...})
.add_shared_state_action(before_question=..., target=..., operation=..., as_=...)
.add_shared_state_write(after_question=..., target=..., operation=..., ...)
```

That still preserves the key split: reads are template context, while writes/actions are explicit, validated side effects.
