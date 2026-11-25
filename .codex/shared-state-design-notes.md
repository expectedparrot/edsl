# Shared State Design Notes

## Core Idea

Shared state lets otherwise separate survey instances read and write a scoped common state during collection.

Reads should be simple and template-like:

```jinja2
{{ shared_state.slot_counts }}
{{ shared_state.topics }}
```

Writes need explicit declarations because they are side effects that can influence other respondents.

## Design Split

- Reads: load configured keys before rendering each question and expose them as `shared_state`.
- Writes: execute after a validated answer, using declared operations.
- Results: normal answers remain in `answer.*`; shared-state reads/writes go in metadata.

## Example API Shape

```python
survey = survey.with_shared_state(
    scope="{{ scenario.meeting_id }}",
    store="coop",
    read_keys=["slot_counts", "best_slots"],
)

survey = survey.add_shared_state_write(
    after_question="availability",
    operation="append",
    key="availability_submissions",
    value={
        "respondent_id": "{{ agent.id }}",
        "slots": "{{ availability.answer }}",
    },
)
```

## Useful Operations

Likely v1 operations:

- `set`
- `merge`
- `append`
- `append_unique`
- `increment`
- `increment_many`

Maybe later:

- `compare_and_set`
- `claim`
- `release`
- transactional/server-defined operations

## Examples Discussed

### Availability Poll

- Shared reads: `slot_counts`, `best_slots`.
- Writes:
  - append availability submission
  - increment counts for selected slots
- Important operation: `increment_many`.

### Collaborative Agenda Builder

- Shared reads: `topics`, `topic_vote_counts`.
- Writes:
  - append or append_unique proposed topic
  - append proposal metadata
  - increment_many vote counts
- Important operations:
  - `append_unique`
  - `increment_many`
- Reads should happen before each question render so dynamic options can use current shared state.

## Safety / Semantics

- Writes happen only after answer validation.
- Writes execute in declaration order.
- Default `on_write_error` should be `error`.
- Read/write metadata should include scope, keys, versions/timestamps when available.
- Stores should be pluggable: local memory for testing, Coop for live shared state.

