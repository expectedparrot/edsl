# Persimmon and GPT on classic judgment tasks

## 1. What this study will produce

A reproducible comparison of Persimmon and GPT response distributions on three classic tasks, alongside published human results. The HTML report will show the item-level distributions, uncertainty intervals, source sample sizes, and exact differences in wording or administration. It will answer whether repeated responses from either model resemble the human distributions on these particular tasks.

This is a model-behavior benchmark, not a representative sample of people and not a general measure of whether a model is “behavioral.”

## 2. How it works

Run the same task wording, instructions, response formats, and answer order for both models. Compare the resulting proportions or numeric-response distributions with the published human samples. Report raw counts and denominators as well as intervals; do not treat model calls as independent human participants or use significance tests to claim human-population equivalence.

The primary comparisons are:

- **Linda conjunction choice:** share choosing “Linda is a bank teller and is active in the feminist movement,” compared with the transparent two-option result reported by Tversky and Kahneman (1983; 85% of 142 students). Counterbalance option order with exactly 100 interviews per order for each model, matching the original study’s equal split. This uses a fixed balanced schedule, not random shuffling.
- **Engineer–lawyer base-rate judgment:** partially reproduce the two prior-probability conditions (30 engineers/70 lawyers and 70 engineers/30 lawyers), using the three published profiles available in the source materials: Jack, Dick, and the no-information case. The original article used five profiles, so this is explicitly a partial replication. Run each model on 100 repetitions per prior condition, split equally between judging the probability that the person is an engineer and judging the probability that the person is a lawyer. Convert lawyer estimates to engineer estimates as 100 minus the response, matching the original pooling logic. Compare with the reported human summaries from Kahneman and Tversky (1973; 85 and 86 participants in the two groups). Preserve the between-subject prior conditions; do not show one simulated respondent both conditions.
- **Bat-and-ball problem:** use the original open numeric response format, not multiple-choice options. Compare exact-correct, intuitive `$0.10`, and other responses with Oechssler, Roider, and Schmitz (2009; 54.8% correct, 40.2% intuitive, 5.0% other among 564 participants).

Use 200 repeated interviews per model for Linda and bat-and-ball, and 100 per model in each engineer–lawyer prior condition. For Linda, the 200 interviews are split equally across the two option orders. For engineer–lawyer, each model has 200 interviews total across the two prior conditions, with 50 interviews in each prior-by-response-target cell. This yields 1,000 task responses per model: 200 Linda, 600 engineer–lawyer (three profiles by 200 total interviews), and 200 bat-and-ball. Across two models, the planned maximum is 2,000 task responses before retries or invalid answers. The same concise, neutral instruction will be used across models; no demographic personas will be added, because the published studies did not sample these fictional persona profiles.

Published human individual-response data are not available for every task. In particular, Kahneman and Tversky report group means and medians for the engineer–lawyer task rather than full individual distributions; their reported average across all five informative profiles is 50% in the low-engineer group and 55% in the high-engineer group, and the null description median is 30% versus 70%. For the partial replication, the report will compare the model distributions with the source’s published summary statistics where directly applicable, not present reconstructed human distributions or attribute the five-profile mean to Jack or Dick.

Sources: [Tversky & Kahneman (1983)](https://doi.org/10.1037/0033-295X.90.4.293); [Kahneman & Tversky (1973)](https://doi.org/10.1037/h0034747); [Frederick (2005)](https://doi.org/10.1257/089533005775196732); [Oechssler, Roider, & Schmitz (2009)](https://doi.org/10.1016/j.jebo.2009.04.018).

## 3. The agents

There will be no demographic persona list. Each repeated interview uses the same neutral respondent instructions and task text. `n` creates repeated model interviews; it does not create new human-like identities. We will interpret variation as variability in sampled model outputs under this prompt and setup. The per-condition sample counts are chosen to be comparable to or larger than the original human samples where practical, while keeping the multi-profile task manageable.

## 4. The survey or task

The study will use three separate task modules so that the response format stays faithful to each source:

1. **Linda:** the original profile and transparent two-option comparison; choose which statement is more probable. Use a fixed, evenly split option-order schedule. The original paper likewise inverted the order for half of participants and reported no order effect. The profile and question will be transcribed from the cited paper during build, with provenance recorded in the README.
2. **Engineer–lawyer:** the original set composition for one condition (30 engineers/70 lawyers) or the other (70 engineers/30 lawyers), followed by Jack, Dick, and the no-information baseline. Half of each prior-condition sample estimates engineer probability and half estimates lawyer probability; lawyer estimates will be reversed to engineer probability for comparison. The five-profile source design cannot be fully reproduced because only three of its profiles are available in the paper text. Each simulated interview receives only one prior condition and one response target. The source's performance-bonus language will be omitted because no monetary bonus is being offered to model responses.
3. **Bat-and-ball:** “A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?” Respond with a numeric amount in dollars, with no answer options.

No memory or answer piping is needed. Responses will be parsed without imputing missing or malformed outputs; valid-response denominators and exclusions will be reported per task.

## 5. Deliverables and preview

Deliverables: EDSL survey/jobs source, saved result packages, reproducible analysis code, source/provenance notes, and a concise HTML report (`report_detail: concise`). The report will include:

- aligned distribution plots for each task and published human benchmark;
- numeric summaries and uncertainty intervals;
- item wording, sample counts, missingness, and model configuration;
- interpretation of where each model matches or differs from human response patterns;
- limitations about repeated calls, prompt sensitivity, answer order, and cross-study differences.

Illustrative preview: the Linda panel will show the human benchmark at 85% conjunction responses (142 people) beside Persimmon and GPT bars based on 200 responses each. The engineer–lawyer panel will plot probability estimates by profile and prior condition, with the two original human conditions identified separately.

## 6. Model and cost

- **Persimmon:** `persimmon-v0.1`, the user-requested model used in the preceding pilot through the EDSL Persimmon service integration. Run with direct local inference from this machine, bypassing the Expected Parrot inference proxy and using the configured `PERSIMMON_API_KEY` from `.env`. The Expected Parrot catalog did not list Persimmon, and its API pricing is not exposed in the documentation, so the Persimmon charge remains unknown unless the account exposes usage pricing.
- **GPT comparison:** `gpt-6.2-sol` (OpenAI service), confirmed in the current model catalog at $2 per million input tokens and $10 per million output tokens. Run directly from this machine using the configured OpenAI key, with EDSL local mode, to match the execution path. It provides a same-task comparison with the earlier pilot.

Before any inference, build the jobs and calculate the GPT estimate using EDSL’s job-cost tooling. Confirm Persimmon billing/cost separately where possible. Present the resulting total and request explicit approval for paid inference. Local mode bypasses Expected Parrot’s inference service; it still makes paid provider API calls. The plan itself does not authorize model calls.

## 7. Decisions for you

- **Sample size and balance:** proceed with 200 repetitions for Linda and bat-and-ball, and 100 repetitions per model in each engineer–lawyer prior condition. Linda option order is balanced 100/100 per model. Engineer response target is balanced 50/50 within each prior condition. This produces 2,000 planned task responses across both models. Increasing the counts further will narrow model-response intervals but will not turn the calls into a representative human sample.
- **Engineer–lawyer scope:** use Jack, Dick, and the null case only, and label this as a partial replication because the full five profile texts are not available in the source materials.
- **Report detail:** concise, with item-level plots, methods, and limitations.

Choose **Looks good, proceed** to approve this design and authorize preparation of the study materials. Inference will stop until the jobs and cost estimate are ready and you separately approve the spend.
