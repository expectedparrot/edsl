# Typed market configuration

Start with [typed_market_experiment.py](typed_market_experiment.py). It contains
the entire experiment and persona prompts; it does not import another experiment.
The previously published report and its bundled source describe the historical
run. This authoring layer is a subsequent refactor.

## Economic and mechanism settings

```python
from edsl.sharedstate import (
    CallMarketRules, CashInterest, DiscreteDistribution, Endowment,
    PricingRule, Redemption, ShareDividend, call_market,
)

rules = CallMarketRules(
    periods=30,
    endowment=Endowment(cash_cents=10_000, shares=4),
    pricing=PricingRule.MARGINAL_MIDPOINT,
    income=(
        CashInterest(rate=0.05),
        ShareDividend(distribution=DiscreteDistribution(
            values_cents=(40, 100), probabilities=(0.5, 0.5),
        )),
    ),
    redemption=Redemption(value_cents=1_400),
)
market = call_market(["alice", "bob"], rules=rules, seed=140926)
```

Objects validate on construction, reject unknown fields, and are immutable.
`rules.with_changes(periods=15)` creates a **validated** alternative. Nested
objects also support `with_changes`; do not use Pydantic's unchecked
`model_copy(update=...)` or `model_construct` for experiment authoring.
Money in rule parameters is integer cents; quoted and forecast prices are dollars.
Booleans are not accepted as numeric parameters. Negative values, nonfinite
numbers, missing wire fields, duplicate forecast names, and unsupported policies
produce field-specific validation errors.

For example, this fails immediately, before building a workflow or making calls:

```python
rules = CallMarketRules(income=(
    {"kind": "cash_interest", "rate": 0.05},
    {"kind": "share_dividend", "distribution": {
        "values_cents": [40, 100], "probabilities": [1.0],
    }},
))
# income.1.share_dividend.distribution.probabilities:
# expected 2 probabilities matching values_cents; received 1
```

### What can vary between sessions

| Setting | Location | Supported variations |
|---|---|---|
| Horizon | `rules.periods` | Positive integer; updates workflow and prompts. |
| Uniform initial portfolios | `rules.endowment` | Nonnegative integer cash cents and shares. |
| Cash return | `CashInterest.rate` | Finite nonnegative rate, including zero. |
| Common dividend | `ShareDividend.distribution` | Nonempty discrete nonnegative cent values and probabilities summing to one. |
| Income order | `rules.income` | Exactly one interest and one dividend rule, in either order. |
| Terminal payoff | `rules.redemption.value_cents` | Nonnegative integer cents; paid after final income. |
| Uniform clearing price | `rules.pricing` | Marginal midpoint, marginal bid, marginal ask. |
| Buy-order quantity cap | `rules.maximum_buy_quantity` | Positive integer; default resolves to total shares, or one if supply is zero. |
| Internal initial reference | `rules.initial_reference_price` | Nonnegative finite dollars or `None`; the speculative example does not display it. |
| Population | `TraderTreatment.composition` | Nonempty sequence of RA, MC, BT, PC, NT, OC. |
| Seat assignment | `TraderTreatment.assignment_seed` | Separate seed for shuffling the population. |
| LLM execution | Treatment model, service, temperature, reasoning effort, max tokens | Changes execution plan; provider-specific model availability is checked during execution. |
| Forecast elicitation | Treatment `forecast_horizons` and matching rule `forecast_keys` | Horizons start at zero and strictly increase; mismatch fails before execution. |
| Market replication | `build(seed=...)` | Changes the v1 dividend and tie streams; they are separated by purpose within this seed. |

Persona prose and the common speculative framing are explicit templates in the
example. Editing those is a prompt treatment. They are not settlement rules.
Borrowing, short selling, persistent orders, heterogeneous endowments, alternate
information disclosure, and independent dividend/tie seed overrides are not
implemented as configurable treatments. Version 1 fixes cent rounding, price
priority with seeded ties, sealed orders, and redemption timing. Unsupported
configuration is rejected rather than silently ignored.

## One source for execution, instructions, and benchmarks

`rules.instructions(trader_count)` renders economic facts from the actual rules.
The example uses it in every question and inserts the configured cash return in
the rational-arbitrageur persona. Forecast labels, history fields, and question
answer keys are generated from the declared horizons.

`rules.fundamental_value(period)` calculates the pre-trade risk-neutral value
by backward induction with the configured payment order, horizon, and terminal
payoff. It ignores cent rounding and does not assume a constant $14 benchmark.
Changing interest or dividends can change the entire benchmark path. The
historical report's fixed benchmark remains appropriate to its original rules;
use this method for reports on new configurations.

## Records and QuestionDict

`DecisionSchema.question(...)` creates the EDSL `QuestionDict` from shared field
definitions. `validate_decision(...)` applies the complete decision contract:
forecast ranges, order side, integer quantity, and positive active-order prices.
QuestionDict currently expresses primitive value types, so its schema alone
does not enforce all these constraints.

The market runtime validates forecasts and order intent separately to preserve
v1 behavior: a malformed forecast fails submission; an invalid order is recorded
with a reason and zero admitted quantity. Rejected payloads are retained exactly.
`AcceptedOrder`, `TradeFill`, `Account`, and `RoundOutcome` validate the generated
records. Finite forecasts are not necessarily economically sensible; terminal
horizon instruction compliance remains an analysis diagnostic.

## Serialization and replay

`rules.to_dict()` and `CallMarketRules.from_dict(data)` round-trip the authoring
configuration. `CallMarketRules.model_json_schema()` exposes its nested schema,
allowed alternatives, and bounds. TraderTreatment has the same methods.
The market factory emits the existing version-1 Machine format. The original
keyword API still works, with the same validation; mixing legacy overrides with
`rules=` is rejected. The runtime validates loaded constants before starting an
experiment backend. Loading data never imports experiment-specific code.

Prepare the default specification without calls:

```sh
python -m examples.asset_market.typed_market_experiment \
  --prepare-only --output /private/tmp/typed-market-prepared
```

Pass `--rules rules.json --treatment treatment.json` to author a variant from
saved configuration. These files are optional. Use a fresh output directory for
a changed experiment; a resumed run uses its pinned specification.

Replay all 360 archived decisions without calls:

```sh
python -m examples.asset_market.typed_market_experiment \
  --responses examples/asset_market/runs/gpt5-full-30-native/responses.json \
  --output /private/tmp/typed-market-replay-new
```

Omitting both `--responses` and `--prepare-only` runs a new hosted-model session.
Saved answers apply only to a matching participant/step layout. Reusing them
under changed economics is a mechanical counterfactual, not fresh LLM behavior.

The default specification and all 30 question templates match the archived
experiment, apart from regenerated identifiers and creation time. The report's
code snapshots stay frozen; its builder verifies their recorded hashes instead
of attributing later library changes to the old run.

The [verification record](typed-market-verification.json) records exact equality
of the full final state after replaying 360 decisions and 30 settlements, with
zero new model calls. It also identifies the source and input hashes. The local
checks passed 221 broader regression tests and 27 targeted tests after the final
validation edits (the groups overlap).
