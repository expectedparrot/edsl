## Summary

Add a new question type, `QuestionAnnotate`, for tasks where the response consists of selecting sections of presented text and applying structured labels, comments, or edits.

Unlike scalar question types such as free text, multiple choice, or linear scale, this question type would produce a structured set of annotations over source text. It should support both model respondents and human respondents.

## Motivation

Many EDSL use cases involve reviewing text rather than answering a single prompt:

- Mark claims, evidence, counterarguments, or assumptions in a passage.
- Identify confusing, misleading, unsupported, or persuasive sections.
- Apply qualitative coding labels to interview transcripts.
- Highlight factual errors and suggest corrections.
- Review policy/legal/academic text with span-level comments.
- Label sections of generated output for evaluation, grading, or red-teaming.
- Ask humans or agents to edit only selected sections rather than rewrite an entire document.

Today these tasks can be approximated by asking for JSON in a free-text answer, but that loses schema-level validation, UI affordances, result consistency, and downstream analysis support.

## Proposed Mental Model

`QuestionAnnotate` should model structured markup over a source document:

1. What text is presented.
2. What portions of the text can be selected.
3. What metadata can be attached to each selection.

Example:

```python
QuestionAnnotate(
    question_name="annotate_argument",
    text="The policy would reduce emissions, but it may increase costs...",
    labels=["claim", "evidence", "counterargument"],
    instructions="Highlight spans and label each one.",
)
```

The answer would be a collection of annotations, not a single scalar value:

```json
{
  "annotations": [
    {
      "start": 0,
      "end": 39,
      "selected_text": "The policy would reduce emissions",
      "label": "claim"
    },
    {
      "start": 48,
      "end": 69,
      "selected_text": "it may increase costs",
      "label": "counterargument"
    }
  ]
}
```

For edit-oriented annotation:

```json
{
  "annotations": [
    {
      "start": 48,
      "end": 69,
      "selected_text": "it may increase costs",
      "label": "revise",
      "edit": {
        "operation": "replace",
        "text": "it could increase short-term costs"
      }
    }
  ]
}
```

## Core Affordances

Initial affordances worth considering:

- Span selection over source text.
- One or more labels per span.
- Optional free-form notes or rationale per annotation.
- Optional edit operation per annotation.
- Multiple annotations per response.
- Validation that offsets match the presented text.
- Validation that labels come from the allowed schema.
- Configurable overlap policy.
- Configurable cardinality constraints.
- Configurable required coverage, such as "mark at least one span" or "label every sentence."
- Configurable selection granularity, such as character span, token span, sentence, or paragraph.

## Span-Based vs Unit-Based Annotation

There are two natural modes.

### Span-based

The respondent selects arbitrary text ranges:

```json
{
  "start": 15,
  "end": 42,
  "label": "confusing",
  "selected_text": "..."
}
```

This is flexible and works well for:

- Named entities.
- Claims and evidence.
- Phrase-level sentiment or toxicity.
- Factual errors.
- Local edits.
- Fine-grained review.

### Unit-based

The question pre-segments text into units and respondents label units:

```json
{
  "unit_id": "sent_3",
  "label": "evidence"
}
```

This is useful for:

- Sentence classification.
- Paragraph-level coding.
- Rubric grading.
- Easier human UI.
- Easier validation and aggregation.

One possible design is to make spans the normalized internal representation, while allowing sentence/paragraph convenience modes that compile to spans with stable `unit_id` metadata.

## Possible Answer Schema

A flexible answer shape:

```json
{
  "annotations": [
    {
      "id": "a1",
      "start": 120,
      "end": 154,
      "selected_text": "increase administrative burden",
      "labels": ["cost"],
      "note": "This is a downside.",
      "edit": {
        "operation": "replace",
        "text": "increase administrative complexity"
      },
      "confidence": 0.82,
      "metadata": {}
    }
  ]
}
```

Notes:

- `selected_text` is redundant with offsets, but useful for inspection and drift detection.
- `labels` could be a list for multi-label annotation, or `label` could be singular for a simpler v1.
- `confidence` may be useful for model respondents, but should probably be optional.
- `metadata` provides an extension point without expanding the core schema too quickly.

## Possible Constructor Surface

A narrow v1:

```python
QuestionAnnotate(
    question_name="q",
    text=article_text,
    labels=["claim", "evidence", "unclear"],
    allow_overlaps=False,
    require_nonempty=True,
    selection_mode="span",
    annotation_mode="label",
    max_annotations=None,
)
```

A richer label schema could allow per-label behavior:

```python
QuestionAnnotate(
    question_name="q",
    text=article_text,
    labels=[
        {
            "name": "factual_error",
            "description": "A statement that appears factually incorrect.",
            "requires_note": True,
            "allows_edit": True
        },
        {
            "name": "strong_claim",
            "description": "A central assertion in the text.",
            "requires_note": False,
            "allows_edit": False
        }
    ]
)
```

## Validation Rules To Consider

Potential validation:

- `start` and `end` are integers within the text bounds.
- `start < end`.
- `selected_text == text[start:end]`, possibly after a configurable whitespace normalization.
- Labels must be declared in the question schema.
- Annotation count respects `min_annotations` and `max_annotations`.
- Overlapping spans are rejected unless `allow_overlaps=True`.
- Required labels are present if configured.
- `note` is present for labels that require notes.
- `edit` is present for labels that require edits.
- Edit operations are drawn from an allowed set: `replace`, `delete`, `insert_before`, `insert_after`.
- Unit ids are valid if using sentence/paragraph/unit mode.

## Human UI Considerations

For human respondents, the question needs a real annotation interface:

- Select text and choose a label.
- Show labels with stable colors.
- Allow editing or deleting existing annotations.
- Optionally add a note or replacement text.
- Show a side panel/list of annotations.
- Prevent invalid overlaps when configured.
- Support keyboard-friendly workflows for repeated labeling.
- Support sentence/paragraph click-to-label mode.
- Preserve annotation order or display by document order.

This would fit especially well with `humanize`, where a structured annotation UI would be much better than asking humans to return JSON.

## Model Prompting Considerations

For model respondents, rendering should make the structured output contract explicit:

- Present the source text.
- Tell the model to return JSON only.
- Require each annotation to include offsets, selected text, and label.
- Explain whether overlaps are allowed.
- Explain label definitions.
- For edits, require an edit operation and replacement text where appropriate.

The model side should probably validate and repair/retry malformed responses the same way other structured question types do, if that fits the existing architecture.

## Result Analysis Considerations

Downstream results tooling could benefit from annotation-specific helpers:

- Select all annotations for a question.
- Explode annotations into one row per annotation.
- Filter by label.
- Export annotated spans with scenario/agent/model metadata.
- Compute label counts.
- Compute coverage of the source text.
- Compare annotator agreement by span overlap or unit label.

Even if these helpers come later, the initial answer schema should make them possible.

## Open Design Questions

- Should v1 allow overlapping annotations?
- Should v1 support multiple labels per span, or exactly one label?
- Should edits be first-class in v1, or deferred?
- Should annotation order be preserved as respondent-created order, document order, or both?
- Should `selected_text` be required?
- Should offsets be character offsets, token offsets, or both?
- Should selection be limited to plain text in v1?
- Should this eventually support HTML, Markdown, PDFs, or images?
- Should the same question type support both arbitrary spans and sentence/paragraph units?
- How should annotations interact with survey memory and piping?
- How should invalid model outputs be repaired?

## Suggested V1

Start narrow:

- Plain text only.
- Character offsets only.
- Required `selected_text`.
- One label per annotation.
- Optional `note`.
- Optional `edit` with `replace` only, or defer edits entirely.
- Configurable `allow_overlaps`.
- Configurable `min_annotations` and `max_annotations`.
- Result shape: `{ "annotations": [...] }`.

This gives EDSL a stable annotation primitive without committing immediately to complex document annotation, multi-modal markup, or full editing workflows.

