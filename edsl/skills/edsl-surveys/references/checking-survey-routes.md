# Checking survey routes

For rules on the same question in the same phase, the most recently added matching rule wins. For cutoffs, make the conditions mutually exclusive. For example, given consent, a 0–10 rating, and three possible destinations:

```python
survey.add_stop_rule("consent", "{{ consent.answer }} == 'No'")
survey.add_rule("rating", "{{ rating.answer }} <= 3", "urgent")
survey.add_rule("rating", "3 < {{ rating.answer }} and {{ rating.answer }} <= 6", "routine")
survey.add_rule("rating", "{{ rating.answer }} > 6", "closing")
survey.add_rule("urgent", "True", "closing")
```

Reopen the saved instrument and walk each expected path. Include declined consent, both sides of every cutoff (including fractional scores for a continuous scale), and the destination after each branch rejoins.

```python
from edsl import Survey
from edsl.surveys.base import EndOfSurvey

saved = Survey.git.load("triage.ep", sync_coop=False)
assert saved.next_question("consent", {"consent.answer": "No"}) == EndOfSurvey
for score, expected in [(0, "urgent"), (3, "urgent"), (3.5, "routine"), (4, "routine"),
                        (6, "routine"), (7, "closing")]:
    assert saved.next_question("rating", {"rating.answer": score}).question_name == expected
assert saved.next_question("urgent", {"urgent.answer": "example"}).question_name == "closing"
```

If a threshold depends on a previous answer, define the full predicate once. Use its negation in the other branch so a broad fallback cannot also match. For example, given two account tiers and a usage measure:

```python
needs_help = "({{ tier.answer }} == 'Basic' and {{ usage.answer }} <= 2) or ({{ tier.answer }} == 'Plus' and {{ usage.answer }} <= 4)"
survey.add_skip_rule("help_details", f"not ({needs_help})")
survey.add_skip_rule("regular_review", "(" + needs_help + ") or {{ usage.answer }} > 8")
```

Run a path for each tier at its threshold and just above it, even if the survey declares whole-number minimum and maximum bounds. A numerical question can still return a fractional answer.
