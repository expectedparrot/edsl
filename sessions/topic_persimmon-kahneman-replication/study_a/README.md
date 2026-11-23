# Study log

## Purpose

Compare repeated Persimmon and GPT responses on classic cognitive judgment tasks with published human summaries using EDSL.

Author: Codex with John Horton
Created: 2026-11-21

## Decisions and log

- The user approved the literature-matched study design and preparation, with paid inference reserved for a separate approval after cost estimation.
- Persimmon must run through direct local inference from the user's configured `.env`, bypassing Expected Parrot inference. GPT will use the same local execution path.
- Linda option order will be fixed-balanced: 100 interviews per model for each option order, matching the source's half-and-half counterbalance without random shuffling.
- The engineer–lawyer module is a partial replication using the published Jack and Dick profiles plus the null case. It uses 100 interviews per model in each prior condition, split 50/50 between engineer and lawyer probability prompts. The original paper's full five-profile stimulus set is not reproduced in the available text.
- No demographic personas are used. EDSL `n` repetitions are interpreted as repeated model outputs under fixed prompts, not as a human population sample.
- The original engineer–lawyer instruction's monetary-bonus statement is omitted because model responses receive no monetary incentive.
- Published benchmarks: Tversky & Kahneman (1983), DOI 10.1037/0033-295X.90.4.293; Kahneman & Tversky (1973), DOI 10.1037/h0034747; Frederick (2005), DOI 10.1257/089533005775196732; Oechssler, Roider, & Schmitz (2009), DOI 10.1016/j.jebo.2009.04.018.

## Execution status

Study plan approved for preparation. Survey, scenario, AgentList, ModelList, and four Jobs packages have been built and saved. EDSL model inference is configured for direct local calls, bypassing the Expected Parrot inference proxy.

The generated template initially invoked `uv run --frozen`, but this repository has no `uv.lock`; the study Makefile therefore uses the already-installed repository `.venv` executables. The scaffold's combined-provider cost request was rejected because Expected Parrot's cost service could not parse the custom Persimmon model. A GPT-only estimate using the supported `--model gpt-6.2-sol` override succeeded: **$1.3598 point estimate** for the full GPT arm. Persimmon's direct API charge is unknown from public documentation and must be checked in the user's account before running.

No model calls have been made. Do not execute `make data` until the user approves the itemized cost and addresses the unknown Persimmon charge.
