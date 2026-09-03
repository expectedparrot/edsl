# Recreating the mug-bargaining experiment with EDSL

## Executive summary

We recreated the published **405-cell factorial design** using **gemini-2.5-flash-lite** through the EDSL causal/conversation adapter. The agents reached a deal in **197 of 405 conversations (48.6%)**, compared with **50%** in Manning, Zhu, and Horton (2024).

This is a **design replication with a contemporary model**, not an exact computational reproduction: the paper used GPT-4 in April 2024, and its historical model snapshot and complete prompt stack are not pinned here.

## Experimental design

- 9 buyer budgets: $3, $6, $7, $8, $10, $13, $18, $20, $25
- 9 seller minimum acceptable prices: $3, $5, $7, $8, $10, $13, $18, $20, $25
- 5 seller-attachment levels, from none to extreme
- One negotiation per treatment combination; buyer and seller alternate
- A hidden model judge checks for a natural endpoint after every utterance; hard cap of 20
- A measurement-only coordinator codes whether the transcript contains explicit price agreement
- Prespecified linear-probability SCM with HC3 standard errors

## Main estimates

| Cause | EDSL estimate | HC3 SE | Approx. p | Paper estimate | Difference |
|---|---:|---:|---:|---:|---:|
| `buyer_budget` | 0.034 | 0.003 | 0.000 | 0.037 | -0.003 |
| `seller_minimum_price` | -0.030 | 0.003 | 0.000 | -0.035 | 0.005 |
| `seller_attachment` | -0.020 | 0.013 | 0.140 | -0.025 | 0.005 |

Coefficients are percentage-point changes in deal probability per one-unit increase when multiplied by 100. Attachment is encoded 0–4 in its declared ordinal order.

## Deal rates by seller attachment

| Attachment | Deal rate | N |
|---|---:|---:|
| no emotional attachment | 46.9% | 81 |
| slight emotional attachment | 55.6% | 81 |
| moderate emotional attachment | 54.3% | 81 |
| high emotional attachment | 43.2% | 81 |
| extreme emotional attachment | 43.2% | 81 |

## Conversation diagnostics

Conversations averaged **7.82 utterances** (range 3–20).

## What this exercise established

The experiment can be represented end-to-end as serializable research objects: SCM, treatment design, participant assignments, conversation protocol, measurement manifest, transcript state, and frozen estimator. Private treatment information remained role-scoped, while the coordinator received the completed transcript only for measurement.

The replication also exposed a useful execution distinction: measurement-only roles must belong to the compiled experiment without being inserted into the speaking protocol. The general runner now supports that distinction.

## Limitations

- A single negotiation was run per cell, matching the published 405-run design but leaving cell-level model randomness unaveraged.
- Provider/model version, prompts, and inference defaults differ from the historical experiment.
- The binary outcome is itself model-coded; future robustness checks should add deterministic transcript coding and multiple judges.
- Statistical significance describes this simulated population and does not establish transportability to human bargaining.

## Example transcripts

### Representative deal

Treatments: buyer budget $20; seller minimum $3; attachment: high emotional attachment. Outcome: 1.

```text
Buyer: Hi there! I'm interested in the mug. What's your asking price?
Seller: Hello! I'm so glad you're interested in this mug. It's truly a special piece. I'm asking $7 for it.
Buyer: That sounds like a great price! I'll take it.
```

### Representative no-deal

Treatments: buyer budget $3; seller minimum $20; attachment: high emotional attachment. Outcome: 0.

```text
Buyer: Hello! I'm interested in the mug. What's your asking price?
Seller: Hello! I'm so glad you're interested in this mug. It's truly a special piece. I'm asking $35 for it.
Buyer: That's a bit more than I was hoping to spend. Would you consider $2?
Seller: Oh, $2 is much too low for this mug. I couldn't possibly let it go for that. It has so much sentimental value to me.
```

## Reproducibility artifacts

The run directory contains the serialized experiment, conversation, analysis plan, benchmark, one SQLite transcript store and provenance record per cell, the fitted SCM, and a flat analysis CSV.
