# Probability responses for AI surveys

Use only when the research design calls for elicited distributions rather than
ordinary categorical responses. These are model-elicited probabilities, not
validated population frequencies. Humanize widget support is not implied.

When the distribution itself is the answer, for AI or human respondents,
especially over numerical intervals, use `QuestionDistribution` instead (see
[survey-reference.md](survey-reference.md#questiondistribution)).

```python
from edsl import QuestionMultipleChoice

choice = QuestionMultipleChoice(
    question_name="choice", question_text="Which option would you choose?",
    question_options=["A", "B", "C"],
    probabilistic_response={"representation": "categorical", "resolution": "mode"},
)
```

`categorical` requires one finite nonnegative probability per option, summing
to one within tolerance. `resolution="none"` retains the distribution without
choosing a categorical answer; `"mode"` resolves to the highest probability;
`"sample"` requires an explicit integer `seed` and samples in EDSL after
validation. Do not ask the answering model to generate its own random draw.
Select a resolution that supplies the answer type downstream piping requires.

Checkbox responses instead require
`{"representation": "inclusion_probabilities", "joint_model": "independent",
"resolution": "sample", "seed": 42}`. Each option probability lies in [0, 1];
they need not sum to one. This explicitly assumes independent inclusion, not a
joint distribution over subsets. Do not use it to claim correlated selections
or guaranteed selection counts. Preserve distributions and resolution metadata
alongside resolved answers. Nontrivial `min_selections` / `max_selections` are
rejected for probabilistic checkboxes because they change the supplied marginals.

For calibrated synthetic populations, follow `ep-agent:research-marginal-twins`;
do not replace its calibration protocol with raw model probabilities.

Source: EDSL `edsl/questions/probabilistic_response.py` and its question/Runner
regression tests (July 2026). No separate public guide was found in the audit.
