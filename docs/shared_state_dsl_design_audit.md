# Shared-State DSL Design and Security Audit

## Executive conclusion

The full-catalog experiment supports a small serialized state-machine language.
All 35 existing concrete shared-state primitives, plus the proposed
`SharedRegister`, can be represented by 36 recipes. The reference suite has 45
passing tests. Most domain behavior is visible in recipes rather than hidden in
Python classes.

The experiment is not ready to accept untrusted remote recipes. The expression
evaluator is closed—there is no `eval`, import, reflection, filesystem, or
network operator—but authoring validation, resource limits, context privacy,
and registered-algorithm isolation remain incomplete.

The recommended design is:

1. retain a small typed expression and effect kernel;
2. treat recipes as untrusted data;
3. treat registered algorithms as reviewed, versioned capabilities;
4. validate types, information flow, complexity, and output bounds before a
   recipe can run remotely;
5. resist arbitrary callbacks, general loops, attribute access, and dynamic
   function calls.

## What was audited

The implementation under `examples/shared_state_dsl/` contains:

- 36 independently serializable `Machine` recipes;
- a 263-line syntax and serialization kernel;
- a 530-line reference interpreter, including registered algorithms;
- five ordinary state-write forms: `set`, `set_once`, `put`, `append`, and a
  conditional `when(...)` wrapper;
- one explicit registered-algorithm effect;
- 16 named reducers;
- six registered algorithm entry points covering four mechanism families:
  LMSR, serial dictatorship, deferred acceptance, and the double auction.

The recipe files total approximately 950 lines. Most recipes are between 14 and
35 lines; the most involved declarative recipe, the sealed auction, is 50 lines.

## Kernel assessment

### Keep

The following constructs earn their place in the kernel because they recur
across unrelated targets and have straightforward, bounded semantics:

- typed constants, fields, command inputs, current context, and lexical locals;
- arithmetic, comparisons, equality, and lazy boolean operators;
- lazy `choose(condition, yes, no)`;
- map and sequence lookup, length, values, containment, and positional access;
- `record` and dynamic `map_of` construction;
- `filter_items`, `map_items`, and `map_sequence`;
- `set`, `set_once`, `put`, and `append` effects;
- conditional effects through `when`;
- close-time effects;
- `sum`, `mean`, `median`, `max`, `count_by`, `count_equal`, `tail`,
  `latest_by`, `argmax`, and stable multi-key record sorting.

Lazy conditionals and lazy `and`/`or` are part of the language contract. The
stress test found real guarded-lookup failures when these were evaluated
eagerly.

### Keep provisionally

These operations are useful but deserve a second design pass:

- `increment_keys` is concise for checkbox tallies, but may be expressible as a
  generic map-fold or an `increment` effect.
- `keys_min_distance` is a generic numerical selection operation, although its
  only current use is the beauty contest.
- `group_numeric_summary` and `series_converged` are independently meaningful,
  but they package several aggregations and convergence-policy choices.
- `weighted_matrix_tally` is convenient for agenda voting but is close to a
  domain helper.
- `ranked_ballot_results` combines three voting rules and is clearly a bundled
  domain reducer. It should become either composable voting reducers or a
  registered, versioned social-choice algorithm.

The criterion is not whether an operation has a domain-flavored name. It is
whether its semantics are independently useful, statically costable, and
clearer than the equivalent composition.

### Remove or avoid

Do not add:

- arbitrary Python callbacks;
- `eval`, imports, reflection, or unrestricted attribute access;
- user-defined loops or recursion;
- dynamic operator or function names;
- implicit access to the Python runtime, files, environment, or network;
- effects that target undeclared or cross-scope fields.

`minimum` and `concat` currently exist as raw expression names rather than
first-class helpers. Either expose and document them consistently or remove
them in favor of ordinary operators. A language should not have a shadow API
used only by hand-written recipes.

## Registered algorithms

Registered algorithms are the correct escape hatch for deterministic iterative
mechanisms that would make the expression language materially larger or less
auditable.

The experiment justifies four families:

| Family | Why it is registered |
|---|---|
| LMSR | Nontrivial pricing and atomic market settlement |
| Serial dictatorship | Iterative capacity-constrained assignment |
| Deferred acceptance | Proposal and rejection loop with institutional priorities |
| Double auction | Atomic order validation, matching, collateral, transfer, and status updates |

The six current entry points should be consolidated into four versioned
capabilities where practical. For example, double-auction submission and close
can be operations of one `double_auction@1` capability rather than unrelated
names.

Each registered algorithm must:

- be implemented and reviewed inside EDSL;
- declare an exact name and semantic version;
- accept and return plain typed data only;
- be deterministic for the same state and inputs;
- perform no filesystem, network, subprocess, environment, or credential I/O;
- run with time, memory, input-size, and output-size limits;
- validate its complete proposed state before atomic commit;
- have conformance and adversarial tests.

## Security findings

### Good existing boundary

Serialized expressions do not execute while parsing. Evaluation dispatches on
known operation names. Recipes cannot import modules, access object attributes,
call arbitrary functions, or initiate I/O. Commands evaluate against an
immutable pre-command snapshot and commit their effects to a copy, preventing
ordinary partial writes.

### Required before remote execution

1. **Operator allowlist validation.** Reject unknown expression, effect,
   reducer, type, and algorithm names during construction—not during execution.
2. **Recursive type checking.** Validate sequence elements, map keys and values,
   field initial values, effect results, views, and algorithm outputs. The
   prototype currently checks mostly top-level input shapes.
3. **Context capability checking.** Every `current` path must be declared and
   classified. Public views must not read private agent traits or internal
   interview metadata without an explicit disclosure permission.
4. **AST budgets.** Limit node count, nesting depth, string size, literal size,
   and repeated references.
5. **Execution budgets.** Bound input state size, collection lengths, generated
   collection sizes, sort sizes, evaluation steps, wall time, and serialized
   event/output size.
6. **Complexity analysis.** Assign conservative costs to collection operators.
   Reject or explicitly approve nested operations with quadratic or worse
   bounds.
7. **Numeric safety.** Reject NaN and infinity; define division-by-zero,
   overflow, empty-reduction, and out-of-range indexing behavior.
8. **Algorithm declaration checks.** A recipe may invoke only algorithms listed
   in its capability manifest, and the runtime must support the exact versions.
9. **Post-transition validation.** Validate the entire proposed state and its
   size before commit. The same applies to close-time effects.
10. **Version pinning.** Serialization must include a DSL version and exact
    operator/reducer/algorithm semantic versions. Unsupported semantics must be
    rejected, never silently reinterpreted.
11. **Idempotency contract.** Define whether close and advisory retry operations
    are idempotent. Remote retries must not duplicate non-idempotent writes.
12. **Audit events.** Record recipe ID, recipe version, command, read snapshot
    ID, algorithm capabilities, outcome, and resulting snapshot ID without
    leaking private command inputs into public results.

## Proposed validation phases

A recipe should pass these phases at creation and again on the remote server:

1. schema and version validation;
2. reference resolution and operator allowlisting;
3. type inference and assignment compatibility;
4. information-flow and context-capability validation;
5. static complexity and size-bound validation;
6. registered-capability resolution;
7. deterministic test-vector validation for published recipes.

No model inference or shared-state server should start for an invalid recipe.

## Readability findings

The DSL is most successful when a recipe reads as four adjacent declarations:

1. constants;
2. state fields;
3. commands and effects;
4. public views and completion conditions.

The least readable recipes define many module-level intermediate expressions or
repeat long `map_items` calls. A production authoring layer should add names
without adding semantics:

```python
with machine.expression("winner") as winner:
    ...
```

or simply allow ordinary Python variables, as the experiment does, while
ensuring only the resulting expression tree is serialized.

Recipe factories remain valuable for discoverability:

```python
poll = recipes.register(keys=activities, write="once")
auction = recipes.sealed_auction(mechanism="second_price", bidder_count=10)
```

They should return ordinary `Machine` data, not introduce new execution classes.

## Decision

Proceed with the DSL design, but do not move the prototype directly into core
EDSL. First produce a hardened `Machine` schema and validator, reduce or
reclassify the five questionable reducers, define the four registered
capability families, and test resource and privacy failures. The public manual
should teach recipes from the small kernel outward and introduce registered
algorithms only after ordinary state structures are understood.
