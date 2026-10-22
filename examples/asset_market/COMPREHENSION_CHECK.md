# Saved-state comprehension check

This is a bounded diagnostic, not another full market simulation. The user asked
whether EDSL asks the trading questions and whether a stronger model understands
the setup better. Preserve all original experiment code and run artifacts.

Before model calls, select four cases from seed 140926:

1. Original all-six Rational Arbitrageur, period 1 (explicit $14 valuation).
2. Speculative-v1 Rational Arbitrageur, period 1 (no supplied valuation).
3. Speculative-v1 Momentum Chaser, period 1.
4. Speculative-v1 Precommitter, period 20, after selling its inventory.

For each, run **three fresh responses per model**, comparing `gpt-4o-mini` with
the explicitly requested `gpt-5-mini`. Run two separate interview modes:

- **Exact trade replay:** reconstruct the saved QuestionDict and Agent from the
  actual original call. Verify both rendered prompt strings against the source.
  No comprehension answers precede these decisions, and no orders are settled.
- **Explicit comprehension:** retain the same rules, private state, history, and
  persona, but replace the trade task with 13 numerical factual questions and a
  brief explanation. Score against an independently computed answer key. Do not
  send that key or corrected historical rationales to either model.

Total: 48 model responses, 312 scored factual answers. The three speculative
cases give 9 comprehension responses per model without a supplied valuation.
The original anchored case is a reading/arithmetic check, not an independent
test of deriving fundamental value.

GPT-4o-mini retains temperature 0.7 and 650 tokens for trade replays; explicit
probes receive 1,800 tokens. GPT-5 mini uses medium reasoning and an 8,000-token
completion allowance (including reasoning), with its supported temperature of
1. This compares usable model configurations, not identical sampling settings.
Record actual finish reasons, model IDs, usage, prompts, and costs. Check for
truncation and missing results before interpreting scores. Expected cost is
under $1 for this small diagnostic, depending on reasoning usage.

Distinguish an affordable/allowed submitted order from an economically sensible
order. Buying four shares when more are affordable is permitted; claiming that
four is the maximum is an arithmetic error. A low limit bid alone is not proof
of confusion. Explicitly passing a quiz does not establish competent spontaneous
trading, faithful persona behavior, or a capacity to reproduce bubbles.

Numeric grading: exact integer counts/indicators; tolerance $0.011 for cash and
payment amounts and $0.02 for derived present value. Unknown or malformed
responses fail the relevant item. Treat explanations as visible evidence, not
access to a model's internal reasoning.

Official model documentation consulted:
https://developers.openai.com/api/docs/models/gpt-5-mini
https://developers.openai.com/api/docs/guides/reasoning
