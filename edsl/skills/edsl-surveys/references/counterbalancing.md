# Counterbalance a four-period concept test

When four forms must balance both period and immediate predecessor effects, one valid set of orders is ABDC, BCAD, CDBA, DACB. Each concept appears once per period. Across the forms, each of the twelve possible ordered pairs of different concepts occurs once. A simple cyclic rotation satisfies the period check but repeats the same four transitions.

For a saved ScenarioList with four concept descriptions in `p1` through `p4` and a Survey with questions `score1` through `score4`, check both packages before running interviews.

```python
from collections import Counter
from itertools import permutations
from edsl import ScenarioList, Survey

forms = ScenarioList.git.load("forms.ep", sync_coop=False)
survey = Survey.git.load("test.ep", sync_coop=False)
periods = ["p1", "p2", "p3", "p4"]
orders = [[form[key] for key in periods] for form in forms]
concepts = set(orders[0])
assert len(forms) == len(concepts) == 4
assert all(set(order) == concepts for order in orders)
assert all(set(period) == concepts for period in zip(*orders))
pairs = Counter(pair for order in orders for pair in zip(order, order[1:]))
assert pairs == Counter(permutations(concepts, 2))

assert survey.question_names == ["score1", "score2", "score3", "score4"]
for form, order in zip(forms, orders):
    for question, expected in zip(survey.questions, order):
        text = question.render({**form, "scenario": dict(form)}).question_text
        assert {concept for concept in concepts if concept in text} == {expected}
```
