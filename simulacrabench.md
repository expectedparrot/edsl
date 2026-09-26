# SimulacraBench and Expected Parrot

## Why this matters

SimulacraBench is a NeurIPS 2026 competition evaluating whether algorithms can augment sensitive survey data from UNHCR, UNICEF, and the World Bank. It is particularly relevant to Expected Parrot because many prospective customers possess respondent-level data that cannot be sent to external inference providers.

The strategic opportunity is broader than synthetic respondents:

> Expected Parrot can bring reproducible model experimentation to sensitive data without requiring the data to leave its owner's environment.

A strong competition result would provide independent evidence that Expected Parrot can build useful, calibrated human-behavior models under realistic privacy and deployment constraints.

## Competition structure

The benchmark is probabilistic completion of respondent-by-question matrices:

- Each row represents a respondent.
- `GIVEN` columns contain visible demographic, contextual, or prior-answer information.
- `PREDICT` columns contain categorical answers that must be predicted.
- The submission returns a probability distribution for every hidden cell, not a single answer.
- A normalized proper log score rewards calibrated probabilities. A uniform prediction scores 0 and a perfect prediction scores 1.
- Skip logic is part of the prediction target; the gated state is an additional answer option.
- Some completed respondents are visible, allowing adaptation to the evaluation population.

There are three instruments:

| Instrument | Population/task | Scored items |
| --- | --- | ---: |
| UNHCR ERPIS | Syrian refugee households in four countries of asylum | 213 |
| UNICEF Faith & Immunisation | Adults in ten countries; religion and vaccine uptake | 12 |
| World Bank Skills Assessment | Job seekers, primarily in South Africa, plus Lesotho and Nigeria | 73 |

The overall leaderboard score is the unweighted mean of the three instrument-level skills. Consequently, the 12-item UNICEF instrument is not commercially or competitively negligible: it contributes one-third of the final score.

## Closed-evaluation constraints

Evaluation follows a code-to-data model. Participants submit a ZIP containing `main.py`, optional dependencies and artifacts, and optionally a `models.txt` file listing public Hugging Face models. The organizers run `predict(frame, schema)` against unreleased microdata.

Important runtime constraints include:

- no network access during execution;
- no runtime sockets or child processes;
- one H100 GPU, with a 16 GB memory limit;
- 900 seconds for the complete development run and 3,600 seconds for the final run;
- a 1 GB submission archive, although public Hugging Face checkpoints can be downloaded during the image-build step;
- only aggregate scores and sanitized diagnostics are returned;
- external weights must be publicly downloadable, or bundled within the archive;
- attempts to reconstruct or identify hidden records are prohibited.

The private answer key never enters the participant container. The development and final respondent sets are distinct.

## Where EDSL fits

EDSL can serve as the research, orchestration, and auditing layer:

- an `AgentList` represents respondents, with `GIVEN` values as traits;
- a `ScenarioList` represents instruments, target items, answer options, and gates;
- a `Survey` requests categorical probability distributions;
- a `ModelList` represents base models, fine-tuned checkpoints, prompts, and ablations;
- `Results` stores predictions, raw outputs, costs, model metadata, and experiment provenance.

EDSL already contains probabilistic multiple-choice response machinery, which fits the benchmark better than repeatedly sampling a model for single answers.

### Meaning of local mode

For development, EDSL can call an open model through Ollama, vLLM, llama.cpp, or an OpenAI-compatible endpoint:

```bash
ep run \
  --survey survey.ep \
  --agent_list respondents.ep \
  --model my-finetuned-model \
  --service openai_compatible \
  --base-url http://localhost:8000/v1 \
  --local \
  --output predictions.ep
```

However, `--local` means that Expected Parrot remote inference is disabled. It does not necessarily mean that inference happens in the same Python process. A local HTTP endpoint still uses a socket, which the hosted competition runtime prohibits.

The final competition submission should therefore load its tokenizer and model directly with `transformers` and implement a standalone:

```python
def predict(frame, schema):
    ...
    return probability_vectors
```

The model-loading and probability-extraction code should be shared between an EDSL `LanguageModel` adapter used during development and the standalone submission implementation.

## A likely winning approach

Winning probably requires training on legally available, closely related survey microdata. The objective should be to learn transferable conditional distributions:

\[
P(\text{answer}_{ij} \mid \text{respondent GIVEN fields}, \text{question}_j)
\]

This is a better match for the benchmark than generic instruction tuning or role-playing.

### Candidate public training data

1. **World Bank STEP Skills Measurement surveys.** Public household surveys from many low- and middle-income countries cover personality, behavior, literacy, employment, social background, risk preferences, and job-related skills. These may contain identical or closely related questions and scales. African datasets should receive particular attention.

2. **UNICEF MICS surveys.** MICS datasets include vaccination, demographic, household, and sometimes faith-and-vaccination attitude questions. Some public instruments contain questions as close as whether religious or spiritual beliefs encourage vaccination.

3. **UNHCR and World Bank Syrian refugee surveys.** Public surveys from Jordan, Lebanon, Iraq, and the broader MENA region cover household composition, displacement, registration, housing, income, assistance, food security, health, education, employment, and migration intentions.

Question alignment should use identifiers where available, plus wording, option semantics, country, population, and instrument lineage. The three public competition schemas make systematic overlap discovery possible without accessing hidden answers.

### Training task

Construct a unified corpus containing:

```text
dataset
country and population
respondent attributes
visible answers
target question text
target answer options
target answer
gate state
```

Train using masked survey reconstruction:

1. Sample a respondent.
2. Preserve fields analogous to the benchmark's `GIVEN` block.
3. Mask one or more known answers.
4. Predict a probability vector for each masked question.
5. Optimize categorical log loss.
6. Vary the masks so the model learns conditional relationships rather than memorizing rows.

Evaluation should use leave-one-survey-out and leave-one-country-out splits. Random respondent splits would exaggerate transfer performance.

### Model progression

Start with several complementary systems rather than assuming a large generative model will win:

1. smoothed global, item, and subgroup marginals;
2. hierarchical multinomial regression or CatBoost;
3. low-rank matrix completion or an IRT-style latent-trait model;
4. a neural model combining question/option text embeddings with respondent features;
5. a compact fine-tuned encoder or decoder producing constrained option logits.

A 0.5B-3B model with a classification head is likely more practical than millions of autoregressive generations from a 7B model. Calibration and throughput must be measured under the actual 16 GB and 900-second limits.

The final system will likely be an ensemble:

\[
p = w_1p_{\text{public-data model}}
  + w_2p_{\text{visible-row model}}
  + w_3p_{\text{semantic prior}}
  + w_4p_{\text{marginal}}
\]

Weights, shrinkage, and temperatures should be selected on held-out surveys using the exact public grader.

### Runtime adaptation

Public data supplies a prior, while the complete `TRAIN` respondents supplied during evaluation reveal how the target population differs. During `predict()`, the system should:

- estimate observed item and subgroup marginals;
- fit lightweight population-specific corrections or latent traits;
- recalibrate the pretrained model to the visible population;
- handle deterministic gate relationships exactly;
- shrink uncertain estimates toward observed marginals;
- ensemble only after evaluating out-of-domain log loss.

This is necessary to address country, year, translation, sampling, and population shifts.

## Benefit to Expected Parrot

The principal benefit is credible validation, not the competition prize.

### Scientific credibility

A strong result on unreleased partner data is difficult to dismiss as contamination or cherry-picking. It directly addresses the objection that synthetic respondents may sound plausible without matching real human behavior.

The defensible claim would be:

> Expected Parrot provides an evidence-backed way to determine when model predictions can augment human survey samples—and when they cannot.

It would not justify claiming that synthetic respondents generally replace human subjects.

### Product positioning

Expected Parrot could expand from infrastructure for asking questions of agents into a platform for validated computational social science:

```text
Design a study in EDSL
        ↓
Collect a calibration sample with Humanize
        ↓
Train or adapt a population model
        ↓
Generate probabilistic synthetic responses
        ↓
Audit accuracy, calibration, uncertainty, and subgroup fidelity
```

This connects EDSL and Humanize into one coherent workflow.

### Institutional opportunities

The organizers and data partners—Stanford, UNHCR, UNICEF, the World Bank, and the UN network—are representative of organizations that need privacy-preserving survey augmentation. A strong result could support partnerships, pilots, publications, and enterprise credibility.

### Open-model differentiation

A fine-tuned open model that outperforms generic frontier-model prompting would demonstrate that Expected Parrot is more than a wrapper around commercial APIs. Durable assets would include:

- aligned public survey training data;
- the masked-response training recipe;
- EDSL benchmark adapters;
- calibration and evaluation tooling;
- a portable open checkpoint;
- a secure deployment pattern.

## Sensitive-data product opportunity

Many likely Expected Parrot customers hold health, financial, employment, government, humanitarian, or research data that cannot be uploaded to an external service. SimulacraBench resembles the deployment architecture these customers need:

```text
Expected Parrot supplies code, model, and study definition
                         ↓
Execution occurs in the customer's controlled environment
                         ↓
Sensitive records remain in that environment
                         ↓
Only approved aggregates, metrics, or artifacts leave
```

This suggests an **EDSL Private Data Plane** with three possible deployment modes:

- **Customer-hosted:** EDSL and open models run in the customer's VPC or on premises.
- **Confidential managed compute:** Expected Parrot operates isolated, short-lived, zero-egress workloads with strict controls.
- **Code-to-data:** customers run a signed EDSL job bundle and release only policy-approved outputs.

An `.ep` package could contain the survey and model specifications, transformation code, dependency manifest, provenance hashes, workflow gates, and output-disclosure policy—but no sensitive respondent records. Inputs would be injected only within the protected environment.

`--local` alone is not a sensitive-data security product. A credible offering would also need:

- enforced zero egress;
- pinned and scanned dependencies and models;
- signed execution bundles;
- secrets isolation;
- immutable audit logs;
- configurable retention and deletion;
- disclosure controls on outputs;
- subgroup privacy thresholds;
- defenses against reconstruction and memorization;
- a documented threat model and division of responsibilities.

## Recommended project outcome

The competition is strategically worthwhile if the work becomes a reusable EDSL capability rather than a specialized submission script. The desired outputs are:

1. a SimulacraBench-to-EDSL adapter;
2. an automated question-overlap pipeline for public surveys;
3. a calibrated population-model training and evaluation stack;
4. an offline, in-process model adapter shared with the competition submission;
5. an EDSL/Humanize workflow for human calibration and synthetic augmentation;
6. a prototype private-data execution bundle;
7. a research report describing performance, subgroup failures, and safe-use boundaries.

The immediate first step is to extract the three public schemas and measure question and construct overlap against STEP, MICS, and public UNHCR/World Bank refugee datasets.

## References

- [SimulacraBench competition site](https://simulacrabench.org/)
- [SimulacraBench public starter kit and submission specification](https://github.com/SituatedEvals/public)
- [World Bank STEP Skills Measurement collection](https://microdata.worldbank.org/catalog/step)
- [UNICEF immunization datasets](https://data.unicef.org/resources/dataset/immunization/)
- [UNHCR MENA microdata catalog](https://microdata.unhcr.org/index.php/catalog/MENA?view=v)
- [World Bank Survey of Syrian Refugees and Host Communities](https://microdata.worldbank.org/index.php/catalog/study/LBN_2015-2016_SRHCS_v01_M)
