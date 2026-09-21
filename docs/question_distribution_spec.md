# QuestionDistribution

Status: local v1 implemented, including validation, both local execution paths,
CLI schema discovery/validation, and package round trips. Remote worker transport
is tested locally; deployed remote inference has not been verified. Hosted
Humanize remains unsupported and is rejected before remote creation.

## Purpose and answer contract

Add `QuestionDistribution`, registered as `question_type="distribution"`, to
elicit a probability distribution over researcher-supplied objects/categories
or intervals of a numerical variable. Like `QuestionBudget`, the respondent
allocates a fixed total across supplied choices. Here the total is always 1 and
the public answer is one dictionary mapping each supplied label to its probability.

```python
{"a": 0.2, "b": 0.2, "c": 0.6}
{"[0,10)": 0.2, "[10,Inf)": 0.8}
```

These values are **probability masses**: for a numerical bin, its value is the
probability that the variable falls anywhere inside that interval. They need
not come from observed data, so the API should call this an elicited distribution
rather than an empirical PDF. It is a categorical PMF or a binned numerical
distribution. Density heights would be mass divided by bin width; bin masses
alone do not specify how probability is distributed within a bin.

The feature returns the distribution itself in `answer.<question_name>`.
Sampling a single answer, fitting a continuous family, and directly eliciting
quantiles are separate possible extensions.

## Proposed construction API

```python
QuestionDistribution(
    question_name: str,
    question_text: str,
    *,
    question_options: list[str] | None = None,
    bins: list[str] | None = None,
    min_value: int | float | str | None = None,
    max_value: int | float | str | None = None,
    bucket_size: int | float | None = None,
    tolerance: float = 1e-6,
    include_comment: bool = True,
    question_presentation: str | None = None,
    answering_instructions: str | None = None,
)
```

Exactly one construction form is required:

| Form | Required fields | Optional fields | Conflicts |
| --- | --- | --- | --- |
| Categories/objects | `question_options` | Common question fields, `tolerance` | All numerical fields |
| Explicit numerical bins | `bins` | `min_value`, `max_value`, common fields, `tolerance` | `question_options`, `bucket_size` |
| Generated numerical bins | `min_value`, `max_value`, `bucket_size` | Common fields, `tolerance` | `question_options`, `bins` |

### Named objects or categories

```python
from edsl import QuestionDistribution

q = QuestionDistribution(
    question_name="winner",
    question_text="What is the probability that each candidate wins?",
    question_options=["a", "b", "c"],
)
# Example answer: {"a": 0.2, "b": 0.2, "c": 0.6}
```

An object is identified by a nonempty string label or stable string ID in v1.
Descriptions can be supplied in the question text. Arbitrary Python objects as
dictionary keys and automatic conversion of objects to strings are outside v1.
Labels must be unique exactly as supplied; reject whitespace-only labels and
leading/trailing whitespace rather than silently changing keys. A one-option
distribution is allowed and must assign that option probability 1 within tolerance.

The prompt states that the options must describe mutually exclusive,
collectively exhaustive outcomes. EDSL can check label uniqueness, but cannot
establish semantic exclusivity or completeness. An author can supply an explicit
"Other" category; the system does not invent it or fill in its probability.

### Explicit intervals

```python
q = QuestionDistribution(
    question_name="waiting_time",
    question_text="How many minutes will the wait be?",
    bins=["[0,10)", "[10, Inf]"],
    min_value=0,
)
# Canonical bins: ["[0,10)", "[10,Inf)"]
# Example answer: {"[0,10)": 0.2, "[10,Inf)": 0.8}
```

`min_value` and `max_value`, when omitted, are inferred from the outer bin
boundaries. Supplied bounds assert the intended support and must match those
boundaries exactly; they do not clip or extend supplied bins. Bounds delimit
the variable's full support, not a display window. No probability is allocated
outside them. A question about a conditional distribution should explicitly
state the conditioning event in its text.

Explicit intervals support unequal widths and unbounded tails:

```python
bins=["(-Inf,0)", "[0,10)", "[10,100)", "[100,Inf)"]
```

### Generated intervals

```python
q = QuestionDistribution(
    question_name="duration",
    question_text="How long will the task take, in minutes (0 through 25)?",
    min_value=0,
    max_value=25,
    bucket_size=10,
)
# Canonical bins: ["[0,10)", "[10,20)", "[20,25]"]
# Example answer: {"[0,10)": 0.2, "[10,20)": 0.5, "[20,25]": 0.3}
```

Generated bins start at `min_value`. Their width is `bucket_size`, except that
the final bin is shortened to end at `max_value` if necessary. Intermediate
bins are left-closed/right-open; the last bin includes the finite maximum.
Thus every value in the inclusive support belongs to exactly one bin.

Require finite numeric bounds with `min_value < max_value` and a finite,
strictly positive numeric `bucket_size`. Reject booleans. A bucket size greater
than or equal to the range produces one bin. Generation across an infinite
range is invalid; use explicit bins to specify unbounded tails.

Compute edges from the starting value and integer multiples of the size using
decimal arithmetic based on each input's decimal spelling. Do not repeatedly
add binary floats. For example, 0 to 0.3 with size 0.1 produces exactly three
bins, with no tiny trailing interval. Explicitly supplied values such as
`0.30000000000000004` retain their meaning; do not silently round user inputs.

Proposed v1 limit: at most 1,000 categories or bins. Check the generated bin
count before allocating the list and report the count and limit on failure.

## Interval parsing and construction validation

Parse intervals into structured endpoints and closure flags using a restricted
parser, never expression evaluation. Support decimal/scientific numeric literals,
`Inf`, `+Inf`, `-Inf`, and case-insensitive `Infinity` spellings. Permit surrounding
whitespace in interval notation. Reject NaN, expressions, units, and malformed
brackets. Infinity is a boundary, not an observable outcome.

Canonical labels remove whitespace, normalize equivalent number spellings
(`10.0` becomes `10`, negative zero becomes `0`), use `Inf`/`-Inf`, and always
use open brackets at infinite boundaries. For compatibility with the motivating
example, accept `[10, Inf]` at construction and canonicalize it to `[10,Inf)`.
Show canonical labels in prompts and use those exact labels in answers.

Validate the entire partition at construction:

1. The list is nonempty and within the category/bin limit.
2. Each interval has a strictly smaller lower than upper endpoint. Zero-width
   intervals and singleton point masses are not supported in numerical mode.
3. Bins are supplied in ascending order; reject out-of-order inputs rather than
   silently sorting them.
4. Adjacent bins have equal shared boundary values. A positive gap or overlap
   is invalid. Infinity can appear only at the outside edges of the partition.
5. Exactly one of the two adjacent intervals includes a shared boundary.
   `[0,10)` followed by `[10,20]` is valid; `[0,10]` followed by `[10,20]`
   double-counts 10; `[0,10)` followed by `(10,20]` omits it. Both invalid
   partitions are rejected even if the intended variable is continuous.
6. Finite outside boundaries must be included. For example, `[0,10]` is a
   valid one-bin support; `(0,10]` is rejected in v1. Infinite boundaries
   are always open after canonicalization.
7. Optional declared support bounds equal the outer endpoints and satisfy
   `min_value < max_value`. In explicit-bin mode, numeric infinities or the
   corresponding infinity strings are permitted as outer bound assertions.
   Finite bounds must be numeric; arbitrary numeric strings are not accepted.
8. Canonical labels are unique. No separate endpoint epsilon is applied:
   probability `tolerance` is unrelated to interval geometry.

Allow either left- or right-ownership of interior boundaries when explicitly
specified, provided the partition rules hold. Generated bins always use the
single convention described above.

Errors identify the offending bin or adjacent pair and the reason, e.g.,
`Bins 0 and 1 overlap at 10; exactly one interval must include this boundary.`
Use the project's question-creation exception conventions. Invalid static
definitions must fail before an inference call or job submission.

## Response validation and prompting

The model-facing answer is a JSON object whose keys are the canonical category
or bin labels. The question's validator receives the usual EDSL response
envelope, for example:

```json
{
  "answer": {"a": 0.2, "b": 0.2, "c": 0.6},
  "comment": "Candidate c appears most likely."
}
```

The standard parser may attach generated-token metadata as it does for other
question types. The answer stored in Results remains the single inner mapping.

Validation requirements:

- Require exactly one entry for every expected key, including zero-probability
  entries. Reject missing and unknown keys. Key order in the incoming object
  does not matter; store the validated mapping in declared category/bin order.
- Reject duplicate keys while decoding raw JSON rather than accepting the last
  occurrence. A direct Python dictionary already has unique keys.
- Require numeric values in `[0,1]`, inclusive. Reject booleans, numeric strings,
  percentages, nulls, NaN, and infinities. Integers 0 and 1 are valid.
- Require `abs(math.fsum(probabilities) - 1) <= tolerance`; no relative tolerance.
  The default is `1e-6`. Proposed configurable range: finite `0 <= tolerance <=
  1e-3`, excluding booleans, to keep this a rounding allowance.
- Preserve accepted values, including a within-tolerance residual. Do not
  normalize, clip, fill missing values, assign a remainder, or round values.
  An out-of-tolerance sum is a validation failure with the observed total.
- Lists and lists of singleton dictionaries are not valid public answers.
  A provider adapter may use an internal schema representation only if it
  preserves exact label-to-probability identity and applies this same validator.
- Ordinary retry/repair machinery may request a corrected response, but it must
  not invent a distribution through Budget's numerical repair policy. Any
  formatting recovery must preserve all original keys and numerical values.

Prompt instructions show every canonical label and specify: assign probabilities
from 0 to 1, include every label, and make the total 1. For bins, explicitly
request probability *inside the whole interval*, not a density height, and
explain the bracket convention. Describe the support and include a valid example
using the actual labels. Comments follow the existing `include_comment` contract.

## Relationship to existing questions

`QuestionBudget` supplies useful allocation presentation patterns, but currently
validates a list and translates its public answer to a list of singleton
dictionaries. It also supports underallocation/remainder repair policies that
do not belong in this distribution contract. Implement `QuestionDistribution`
with its own response model and validator; reuse small helpers only where
semantics agree. Do not change Budget behavior as part of this feature.

`ProbabilisticResponse` on multiple choice already supports categorical vectors
and optional host-side resolution. `QuestionDistribution` has a labelled mapping
as its answer and adds an explicit numerical partition. Common probability
validation can be factored out if existing behavior remains unchanged. There
is no `resolution`, `permissive`, `budget_sum`, or implicit remainder in this API.

## Serialization and execution integration

- Export `QuestionDistribution` through the standard EDSL imports and register
  `distribution` for question construction, deserialization, and schema discovery.
- Preserve the chosen authoring form in `to_dict()`/`from_dict()`: categories,
  canonical explicit intervals with optional bound assertions, or generation
  parameters. Do not serialize both explicit bins and generation parameters as
  constructor inputs. Always serialize the response tolerance.
- Expose the resolved canonical labels as a read-only `answer_keys` property.
  Expose resolved numerical intervals as a read-only `resolved_bins` property
  (`None` in category mode). Derive them from validated configuration; invalidate
  cached response schemas if a supported edit changes the definition.
- Serialize infinite bounds using JSON strings `"-Inf"` and `"Inf"`, never
  nonstandard JSON Infinity/NaN literals. Explicit interval strings already
  encode their boundary values portably.
- JSON, Survey/Jobs/Results `.ep` packages, and survey JSONL round trips preserve
  configuration, resolved meaning, and answer dictionaries. Results carry the
  associated question definition so bin widths and boundaries remain recoverable.
- Local execution, Runner, direct agent answers, and supported remote execution
  validate and return the same answer mapping. Answer translation is idempotent;
  it never wraps the mapping in a list or replaces labels with numeric indices.
- `ep schema list`, `ep schema show --question_type distribution`, and `ep validate`
  expose the type and its constraints. CLI construction should use existing
  schema-driven input paths; add dedicated convenience flags only where needed.
- Question text may use ordinary EDSL templates. V1 category labels, intervals,
  bounds, and bucket sizes are static: explicitly reject template expressions
  in structural fields. Scenario-dependent partitions require a later contract
  for validation after rendering and preservation of each realized partition.
- Reject option randomization for this type in v1. Category order is declared;
  numerical bin order is ascending. Do not let generic option-randomization
  machinery rearrange intervals or change label/value associations.
- Provide a local HTML representation showing each label and its allocation,
  a total, and validation feedback. Hosted Humanize support requires a matching
  server/client implementation; until available, surface an unsupported-type
  error instead of converting this to Budget and changing its contract.
- Remote workers must recognize the type and validate its contract before
  claiming execution support. Old installations may reject the new type; they
  must not reinterpret it as another question type.

## Acceptance criteria

1. The three examples above construct successfully and produce the stated
   canonical keys and public dictionary shape.
2. Conflicting/absent construction forms, empty or duplicate category labels,
   unsupported structural templates, and limits violations fail at construction.
3. Tests cover finite, one-sided infinite, fully unbounded, unequal-width, and
   one-bin partitions; alternate valid boundary ownership; and normalization
   of `[10, Inf]`. Invalid gaps, overlaps, omitted/doubled endpoints, NaN,
   reversed/zero-width bins, unsorted bins, and mismatched support bounds fail.
4. Generated bins cover the exact range once, include its finite maximum, and
   handle negative minima, decimal sizes, exact division, a shortened last bin,
   and bucket sizes larger than the range. Invalid and unbounded generation
   fails without allocating an unbounded list.
5. Response tests cover valid zero probabilities, one-option answers, reordered
   keys, sum tolerance boundaries, and each invalid key/value case. Raw duplicate
   JSON keys fail before they can be discarded. Accepted residuals are preserved.
6. Prompt tests verify the actual canonical labels, bracket/support explanation,
   mass wording, and comment behavior. HTML rendering escapes arbitrary labels.
7. A deterministic test-model run and a direct-answer run store the same single
   dictionary in `answer.<question_name>` through both supported local execution
   paths. Later questions can access a probability with dictionary indexing.
8. Serialization and package round trips preserve all forms and unbounded
   intervals using strict JSON. `ep results select` returns the mapping; standard
   export behavior preserves every key/value without flattening ambiguities.
9. The supported remote worker passes an end-to-end round trip; unsupported
   runtimes and Humanize deployments report a clear unsupported-type failure.
10. Existing Budget and probabilistic-choice regression tests continue to pass.

## Recommended scope decisions

Humanize's planned painting widget has a per-question setting:
`{"questions": {"forecast": {"initial_distribution": "empty"}}}`.
The accepted values are `"uniform"` (default) and `"empty"`. Uniform means equal
probability per supplied bucket or outcome, even for unequal-width intervals.
Empty means unanswered until the respondent allocates probability. A saved
response takes precedence over either initial state. This setting belongs to
Humanize configuration, not the question constructor, and does not affect LLM
answers. Schema validation is available; hosted elicitation still requires the
coordinated coopr widget release described above.

An optional `show_moments: true` in that per-question Humanize schema shows the
implied mean and variance for finite numeric bins; it defaults to false. This
assumes probability is uniform within each bin, an assumption labelled in the UI.
For midpoint `m_i`, width `w_i` and bin probability `p_i`, the mean is
`sum(p_i * m_i)` and variance is `sum(p_i * ((m_i - mean)^2 + w_i^2 / 12))`.
Categories and unbounded intervals do not receive moment summaries. This display
setting does not change the answer or add assumptions to LLM elicitation.

The proposal above chooses string-labelled objects, explicit interval strings,
inclusive finite support, shortened final buckets, strict probability validation,
and preservation of answers within tolerance. These are the implemented v1 choices.

Defer arbitrary object payloads, dynamic partitions, generated overflow bins,
mixed point masses and intervals, percentage response modes, and distribution
sampling. A later numerical analysis API can compute cumulative mass at bin
boundaries directly. It must require an explicit within-bin assumption to
calculate a density, mean, or interpolated quantile; unbounded tails need an
additional tail model. None of those assumptions should be silently attached to
the distribution answer.
