# Checked question stems

`Stem` builds question text from static prose and explicit EDSL references. It
checks placeholders and bindings while the survey is authored, then lowers the
result to a string containing ordinary Jinja expressions. Existing renderers
and serialized surveys continue to consume `question_text` as a string.

```python
from edsl import QuestionFreeText, QuestionMultipleChoice, Stem
from edsl.sharedstate import current

q_name = QuestionFreeText(question_name="name", question_text="What is your name?")
q_time = QuestionMultipleChoice(
    question_name="time", question_text="Which time works?",
    question_options=["Morning", "Afternoon"],
)
q_followup = QuestionFreeText(
    question_name="followup",
    question_text=Stem(
        "Thanks, {name}. You chose {time}. Your participant group is {group}.",
        name=q_name.answer,
        time=q_time.answer,
        group=current.agent.group,
    ),
)
```

Question answers use `question.answer`; context fields use `current.agent.*`,
`current.scenario.*`, or `current.run.*`. Each `{placeholder}` must have exactly
one binding. Placeholders are simple identifiers; attribute access, format
specifiers, and conversions belong on the reference object or in application
logic, not in the template.

Static braces are escaped with Python formatting syntax (`{{` and `}}`). Static
text is safely quoted when lowered, so Jinja-looking content in that text stays
literal. Use `literal(value)` to opt in to rendering a string, number, or
boolean value; arbitrary objects are rejected.

```python
from edsl import Stem, literal

Stem("Show the code {{name}}; target: {target}", target=literal("{{ not a variable }}"))
```

The result is a `str` subclass and can be passed directly as `question_text`.
Calling `.compile()` returns a plain string. The serialized survey stores only
the lowered Jinja text, so no `Stem` runtime or wire-format dependency is added.
