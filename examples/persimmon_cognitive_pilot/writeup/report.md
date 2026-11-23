---
title: "Persimmon and GPT-6.2-Sol on Classic Judgment Problems"
date: 2026-11-21
---

## Summary

I used EDSL to run four multiple-choice judgment problems with 12 fictional personas on Persimmon v0.1 and GPT-6.2-Sol. The follow-up counterbalanced the normative answer's position, used the same question wording and option schedule for both models, and recorded one response per persona and item. GPT-6.2-Sol returned a valid answer for all 12 personas on three items and 11 on the occupation base-rate item; one blank response remained after retries.

GPT-6.2-Sol selected the normative answer on every valid response in this small run. Persimmon did so on 4/12 Linda responses, 5/12 occupation responses, 5/12 taxi responses, and 10/12 bat-and-ball responses. These are descriptive counts from 12 hand-written synthetic personas, not estimates of human performance or evidence that one model is generally better.

## Results

| Item | Normative answer | Persimmon v0.1 | GPT-6.2-Sol | Same answer on shared valid personas |
|---|---|---:|---:|---:|
| Linda conjunction | Bank teller alone | 4/12 | 12/12 | 4/12 |
| Occupation base rate | Lawyer, if the description has no specified diagnostic likelihood | 5/12 | 11/11 valid (one blank) | 5/11 |
| Taxi base rate | Blue taxi | 5/12 | 12/12 | 5/12 |
| Bat and ball | $0.05 | 10/12 | 12/12 | 10/12 |

Persimmon's full answer counts in the counterbalanced run were 8 conjunction / 4 bank-teller-alone for Linda; 5 lawyer / 7 engineer for occupation; 5 blue / 6 green / 1 equally likely for taxi; and 10 at $0.05 / 2 at $0.10 for bat-and-ball. GPT-6.2-Sol selected bank teller alone 12 times, lawyer 11 times with one blank, blue taxi 12 times, and $0.05 12 times.

![Four-panel horizontal bar chart comparing Persimmon and GPT-6.2-Sol answer counts for the Linda, occupation, taxi, and bat-and-ball questions.](plots/answer_distributions.png)

Figure 1: Multiple-choice answer counts by item and model. Bars show valid responses; GPT-6.2-Sol returned 11 valid occupation answers out of 12.

![Grouped horizontal bars showing the percentage of shared valid personas choosing the normative answer for each item and model.](plots/normative_answer_share.png)

Figure 2: Normative-answer selections among personas with valid answers from both models. Counts beside bars give correct responses over shared valid responses.

The correct answer was assigned to each option position equally often: six times per position for Linda, four times for each of three positions on occupation and taxi, and three times for each of four positions on bat-and-ball. GPT-6.2-Sol's selected positions followed those correct positions because every valid answer was normative. The one missing occupation answer was assigned to the third position, leaving 11 valid GPT-6.2-Sol responses for that item. The occupation comparison therefore uses the 11 personas with valid answers from both models; the other items have 12 shared responses.

Persimmon's initial fixed-order run put the normative answer first on every item. Its counterbalanced follow-up differed from that initial run on three items, but those are separate stochastic draws; the changes cannot be attributed to answer position alone. The balanced follow-up fixed the option-position confound in the design by distributing the normative answer evenly across positions.

## Method

The 12 fictional personas had varied ages, occupations, and response styles. Each item was run as a separate EDSL `QuestionMultipleChoice`, with one persona and one model per interview. Both models received the same prompt wording, response options, persona instructions, and deterministic option-position schedule. GPT-6.2-Sol used EDSL's OpenAI service; Persimmon used the new EDSL Persimmon service adapter, `persimmon-v0.1`, on its standard tier. Both were limited to 128 output tokens, and responses were constrained to the exact option text.

The comparison uses the valid-response intersection for each item. A GPT-6.2-Sol blank on the occupation item remained after three attempts for that response; two other blank occupation responses were recovered on retry. We retain the original missing response in the artifact and report 11/12 coverage rather than imputing an answer.

The questions are adaptations of established judgment tasks: a Linda-style conjunction choice, representativeness/base-rate judgment, Bayesian base-rate updating, and the bat-and-ball cognitive reflection problem. The conjunction task follows the probability constraint studied by [Tversky and Kahneman (1983)](https://doi.org/10.1037/0033-295X.90.4.293); the representativeness and base-rate items draw on their heuristics-and-biases work ([1974](https://doi.org/10.1126/science.185.4157.1124)); the bat-and-ball item is associated with the Cognitive Reflection Test ([Frederick, 2005](https://doi.org/10.1257/089533005775196732)). These prompts are adaptations, not exact replications.

## EDSL implementation

The comparison uses EDSL's standard `QuestionMultipleChoice`, `Survey`, `AgentList`, and `Model` objects. The core position assignment and run pattern from the study code is:

```python
from edsl import Model, QuestionMultipleChoice, Survey
from edsl.caching import Cache

def options_with_correct_position(item, position):
    distractors = [option for option in item["options"] if option != item["correct"]]
    distractors.insert(position, item["correct"])
    return distractors

for index, agent in enumerate(agents):
    position = index % len(item["options"])
    options = options_with_correct_position(item, position)
    question = QuestionMultipleChoice(
        question_name=item["name"],
        question_text=item["text"],
        question_options=options,
        include_comment=False,
        answering_instructions=(
            "Choose exactly one option. Return only the exact option text, "
            "with no explanation."
        ),
    )
    results = Survey([question]).by(agent).by(model).run(
        cache=Cache(),
        disable_remote_inference=True,
        disable_remote_cache=True,
        max_concurrency=1,
    )
```

EDSL also supports built-in per-interview option shuffling with `Survey(..., questions_to_randomize=["question_name"])`. That feature randomizes order but does not guarantee equal counts at each position in a small sample. This run used the explicit rotation above to guarantee balance and preserve the same option order across model arms. The full scripts are linked below.

The Persimmon integration is implemented in EDSL's `PersimmonService`. It uses `PERSIMMON_API_KEY` and the Persimmon conversations and turns endpoints. For a standard EDSL question, the adapter packages the question as a short questioner/respondent exchange; `QuestionInterview` uses the same conversation API for multi-turn interviewing. See the [service implementation](../../../edsl/inference_services/services/persimmon_service.py) and the [EDSL language-model documentation](../../../docs/en/latest/language_models.mdx) for the adapter and registration details.

## Interpretation: is Persimmon more behavioral?

In this narrow battery, Persimmon produced more responses that resemble familiar heuristic or bias patterns: 8/12 chose the Linda conjunction; 7/12 chose engineer over lawyer despite the 70/30 base rates; 6/12 chose green taxi despite blue being more likely under the stated witness accuracy; and 2/12 gave the intuitive $0.10 bat-and-ball answer. GPT-6.2-Sol selected the designated normative answer on every valid response. The chart shows that contrast clearly.

So, if “more behavioral” means “more likely to show these classic departures from the problem's designated normative answer,” Persimmon was more behavioral in these observations. That does not establish that it is more human-like overall. We did not collect human responses, explanations, or confidence, and the questions are adapted rather than exact replications. A model can reproduce a named bias without matching the distribution, reasoning, or individual differences found among people.

There is also a design qualification for the occupation item: the prompt gives a 70/30 prior and a personality description, but no likelihoods for that description by occupation. “Lawyer” is the base-rate answer if the description supplies no diagnostic information; a fully specified Bayesian posterior cannot be calculated from the prompt as written. This makes the occupation result less decisive than Linda, taxi, and bat-and-ball.

## Comparison with published human results

Published findings offer useful context, but only some are close enough for a direct rate comparison.

| Task | Published human result | Persimmon / GPT-6.2-Sol | How close is the comparison? |
|---|---|---|---|
| Linda conjunction | In a direct two-option test, 85% of 142 undergraduates chose the conjunction. In a later sample, the conjunction response was 62.6% for the lower-CRT group and 38.3% for the higher-CRT group. | Persimmon: 8/12 (67%); GPT-6.2-Sol: 0/12. | Close wording and same two choices, though our description is adapted and n=12. Persimmon's rate is near the human lower-CRT result; GPT's is below both human-group rates. |
| Occupation / base rates | In Kahneman and Tversky's study, 85 low-engineer-prior and 86 high-engineer-prior participants estimated probabilities across five descriptions. Mean probability estimates were 50% and 55%; stereotyped descriptions drew judgments toward representativeness, with only a slight effect of the manipulated prior. | Persimmon selected Engineer 7/12; GPT-6.2-Sol selected Lawyer in 11/11 valid answers. | Not a direct rate comparison: the published task elicited numerical judgments under two prior conditions, while our adapted task is one forced choice and has no quantified likelihood for its personality description. |
| Taxi / witness evidence | In Bar-Hillel's published study, 36% of 52 participants gave the witness's 80% reliability as their answer; the median was 80%, while about 10% gave an estimate near the Bayesian answer of 41%. | Persimmon selected the witness-identified Green taxi in 6/12; GPT-6.2-Sol did so in 0/12. | Directional context only. Our task reverses the color labels and asks for one of three categories, not a numeric probability. |
| Bat and ball | In an online experiment with 564 participants, 54.8% answered correctly, 40.2% gave the intuitive $0.10 answer, and 5.0% gave another answer. | Persimmon: 2/12 intuitive answers (17%); GPT-6.2-Sol: 0/12. | Same problem, but our models received forced-choice options while the human study used a written answer. |

The contrast on Linda is consistent with Persimmon reproducing a response pattern found in both the original and later human samples. But the bat-and-ball result points the other way: in this pilot Persimmon produced fewer intuitive errors than one published human sample, and GPT-6.2-Sol produced none. The taxi result points in the human-like direction for Persimmon, although the response formats differ. Together, these results do not support a single ranking of “behavioralness.” They suggest that model similarity to human responses depends on the task and response format.

![Published human response rates on the Linda and bat-and-ball items shown beside model response rates. The gray bars are separate human samples; blue and orange bars show the synthetic model runs.](plots/published_human_benchmarks.png)

Figure 3: Human benchmark context for two items with published response rates. The source samples, response modes, and model sample sizes differ; the bars are descriptive comparisons, not a pooled estimate.

The original Linda result is from [Tversky and Kahneman (1983)](https://doi.org/10.1037/0033-295X.90.4.293); the CRT-stratified Linda and bat-and-ball figures are from [Oechssler, Roider, and Schmitz (2009)](https://doi.org/10.1016/j.jebo.2009.04.018). The classic occupation task is from [Kahneman and Tversky (1973)](https://doi.org/10.1037/h0034747), and the taxi results are from [Bar-Hillel (1980)](https://doi.org/10.1016/0010-6918(80)90046-3).

## Interpretation and limitations

The forced-choice results do not reveal whether an answer came from calculation, learned test-taking conventions, or another process. No explanations or confidence judgments were collected.

The comparison contains only 12 fictional personas, one response per persona per item and model, and four adapted tasks. It has no human comparison group and cannot establish population-level rates, stable model differences, or persona-specific effects. GPT-6.2-Sol's one missing answer also reduces occupation-item common support to 11 personas. Treat all differences as exploratory behavior under these exact prompts and settings.

## Reproducibility

- [Initial Persimmon run](../run_pilot.py)
- [Counterbalanced Persimmon run](../run_counterbalanced.py)
- [GPT-6.2-Sol comparison run](../run_gpt6_comparison.py)
- [Retry for missing GPT-6.2-Sol response](../retry_gpt6_missing.py)
- [Model comparison analysis](../analyze_model_comparison.py)
- [Comparison plot builder](../analysis/build_model_comparison_plots.py)
- [Plot quality checker](../analysis/check_plots.py)
- [Persimmon counterbalanced summary](../analysis/summary_counterbalanced.json)
- [Model comparison summary](../analysis/summary_model_comparison.json)
- Results packages are under `../results/counterbalanced/`; GPT-6.2-Sol results and the occupation retry are under `../results/counterbalanced/gpt-6.2-sol/`.
- CSV exports from the earlier Persimmon analysis are in `../analysis/`.
