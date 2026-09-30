# Shared-state DSL stress test

## Purpose

The current shared-state experiment contains 35 concrete `SharedPrimitive`
classes. Many are shallow: they declare a state dictionary, expose one or two
write methods, enforce answer constraints, and calculate a view or settlement.

This stress test asks whether those classes can instead be serialized recipes
over a small state-machine language. It is intentionally separate from the core
EDSL implementation. The executable catalog is
`examples/shared_state_dsl_experiment.py`.

The second-pass workbench lives in `examples/shared_state_dsl/`. It has one
module per target and a shared `kernel.py`. Each target module exports one
`SPEC`, can be read without navigating a monolithic catalog, and is discovered
by `python -m examples.shared_state_dsl.validate`. The validator checks each
target independently before serializing the collection.

The first migrated cross-section is:

- `shared_register.py` and `shared_log.py`, exercising generic storage;
- `shared_voting_game.py`, exercising choice contracts and reducers;
- `shared_ultimatum_game.py`, exercising multi-stage commands and explicit
  payoff expressions;
- `shared_budget_pool.py`, exercising atomic arithmetic and map updates;
- `shared_binary_market.py`, exercising the registered-algorithm boundary.

This per-target layout is now the development path. A target is not considered
migrated if its file simply delegates to the old primitive or hides its behavior
behind a target-specific pure function.

The workbench also contains a reference interpreter in `runtime.py`. It executes
generic expressions and effects, validates command inputs, records advisory
outcomes, and reconstructs machines from serialized JSON. All right-hand
expressions in one command are evaluated against the same pre-command snapshot;
their effects then commit atomically. The initial tests caught and corrected an
implementation that accidentally let later effects observe earlier effects from
the same command.

The first executable test suite covers first-write-wins conflicts, append-only
views, voting reducers, staged ultimatum payoffs, atomic partial funding, and the
versioned LMSR boundary. It also round-trips every migrated specification through
JSON reconstruction.

The next stress batch adds work claiming, capacity-constrained coalition moves,
capability-constrained resource allocation, generated agenda identifiers,
nested repeated-game rounds, and Delphi convergence. These targets introduced
only two general ideas: immutable collection expressions and conditional
effects. They did not require new target-specific pure functions.

Direct comparison with the existing `SharedVotingGame` exposed an incorrect
first-pass assumption that voting was a simple candidate register. The existing
primitive actually collects complete rankings, hides ballots until close, and
then calculates plurality, Borda, and Condorcet results. The corrected DSL
recipe required general close-time effects and closed-state-dependent views.
Its ballots and all three result calculations now match the existing primitive
on the conformance trace.

## First complete result

Every current concrete primitive, plus the proposed `SharedRegister`, has been
rewritten as a serializable `Machine` recipe. The prototype validates that:

- every current class has exactly one recipe;
- every effect targets a declared field;
- every input reference is declared by its command;
- the entire 36-recipe catalog serializes to JSON.

The first pass uses nine structural node kinds:

```text
type       ref        record
set        set_once   put
append     call       algorithm
```

That result is promising but not sufficient. The recipes also name 16
transition algorithms and 36 pure helper functions. Some of these names merely
hide behavior that should be expressed using general collection and arithmetic
expressions. Counting only the nine outer node kinds would therefore overstate
the simplification.

## Proposed minimal kernel

The second-pass target has four parts.

### Types

```text
Boolean  Number  Text  Choice
Optional  Sequence  Map  Record
```

Types carry serializable constraints such as numerical bounds, allowed choices,
record fields, and collection item types.

### References

```text
constant.<name>
state.<name>
input.<name>
current.<path>
```

`current` paths are checked references to agent, assignment, run, and other
execution context. They are data in the serialized recipe, not arbitrary Python
attribute access on a worker.

### Atomic effects

```text
set(field, expression)
set_once(field, expression)
put(map_field, key, expression, once=False)
append(sequence_field, expression)
```

A command applies all its effects atomically against one state version. Counter
updates, removals, and nested updates should first be attempted as expressions
that produce a new collection value rather than added as new top-level effect
types.

### Pure expressions

The expression algebra needs literals and records; Boolean and arithmetic
operators; conditionals; collection lookup and replacement; and a small set of
reducers such as length, sum, mean, median, minimum, maximum, and count-by.

Named payoff functions such as `dictator_payoffs` should not become registered
runtime functions. A named recipe should contain the serialized arithmetic
formula directly. Otherwise shallow primitive classes have merely become
shallow function registrations.

## Full catalog rewrite

The table records what each existing class becomes in the first-pass catalog.
“Generic” means its state transition can be represented with ordinary typed
fields and effects. “Expand” means the first pass used a named helper that the
second pass should replace with general expressions. “Built-in” means a
substantial, named scientific algorithm may justify a versioned implementation.

| Current class | Recipe structure | Second-pass status |
|---|---|---|
| `SharedLog` | Sequence plus `append` | Generic |
| `SharedWorkPool` | Available sequence, claims map, completed map | Expand queue claim |
| `SharedSignalSchedule` | Signal constants, revealed map, event sequence | Expand indexed reveal |
| `SharedBinaryMarket` | Quantities, portfolios, trades, settlement | Built-in LMSR calculation |
| `SharedUltimatumGame` | Four optional fields and two `set_once` commands | Generic |
| `SharedMoneyRequestGame` | Player-to-request map and payoff formula | Generic |
| `SharedMatrixGame` | Seat-to-action map and payoff-table lookup | Generic |
| `SharedRepeatedMatrixGame` | Round-to-action maps and repeated lookup | Expand nested map update |
| `SharedDictatorGame` | Actor fields, bounded transfer, arithmetic payoff | Generic |
| `SharedTrustGame` | Two bounded transfers and arithmetic payoff | Generic |
| `SharedBeautyContest` | Player-to-number map and aggregate formula | Generic |
| `SharedCommonPoolGame` | Player-to-request map and aggregate formula | Generic |
| `SharedCentipedeGame` | History sequence, terminal predicate, configured payoff lookup | Expand configured transition table |
| `SharedMarketEntryGame` | Player-to-Boolean map and congestion formula | Generic |
| `SharedSealedAuction` | Bid map, hidden view, close-time mechanism | Built-in auction settlement family |
| `SharedBilateralTrade` | Offer fields, decision field, arithmetic payoff | Generic |
| `SharedSignalingGame` | Signal fields, decision field, arithmetic payoff | Generic |
| `SharedNashDemandGame` | Seat-to-demand map and arithmetic payoff | Generic |
| `SharedVotingGame` | Voter-to-candidate map and count-by view | Generic |
| `SharedCheapTalkGame` | Message fields, action field, outcome formula | Generic |
| `SharedPrincipalAgentGame` | Contract fields, effort field, expected-payoff formula | Generic |
| `SharedCoalitionPool` | Membership maps, capacities, request history | Expand conditional collection update |
| `SharedBudgetPool` | Remaining amount, funded map, allocation history | Expand bounded atomic arithmetic |
| `SharedDocument` | Text field and revision sequence | Generic |
| `SharedCounterMap` | Key-to-count map | Expand collection-wide increment |
| `SharedMatchPool` | Ranked requests and close-time matches | Built-in matching mechanism family |
| `SharedDeferredAcceptance` | Ranked requests, capacities, priorities, matches | Built-in deferred acceptance |
| `SharedDoubleAuction` | Accounts, orders, trades, clearing | Built-in auction clearing family |
| `SharedResourceBoard` | Assignment maps, capability constraints, attempts | Expand conditional collection update |
| `SharedAuction` | Bid sequence, maximum, winning index | Generic |
| `SharedMessageBoard` | Message-record sequence | Generic |
| `SharedNegotiation` | Turn-record sequence and terminal predicate | Generic |
| `SharedAgenda` | Proposal sequence, ballot sequence, weighted count-by | Expand generated identifiers |
| `SharedDelphiPanel` | Response sequence, grouped summaries, convergence predicate | Generic reducers plus formulas |
| `SharedForecast` | Forecast sequence and weighted mean | Generic reducers plus formulas |
| proposed `SharedRegister` | Typed map and `put`/`put_once` | Generic foundation |

## Question composition

Commands declare typed inputs independently of questions:

```python
vote = Command(
    inputs={
        "voter": Text(),
        "candidate": Choice(CANDIDATES),
    },
    effects=(
        put(
            state.ballots,
            key=input.voter,
            value=input.candidate,
            once=True,
        ),
    ),
)
```

A recipe factory exposes that command as a method. Binding a question checks its
answer contract at construction:

```python
survey = Survey([
    candidate,
    election.vote(
        voter=current.agent.name,
        candidate=candidate.answer,
    ),
])
```

The question remains responsible for elicitation and answer validation. The
command remains responsible for atomic state transition constraints. Compatible
answer shapes can therefore be reused across recipes without making the DSL
depend on every concrete EDSL question class.

## Named recipes remain useful

Removing concrete primitive classes does not require removing domain names:

```python
game = games.ultimatum(stake=100)
market = markets.binary(contract="Event occurs", liquidity=50)
mechanism = matching.deferred_acceptance(capacities, priorities)
```

These factories return ordinary `Machine` recipes. They provide discoverability,
domain-specific documentation, and good defaults without creating new execution
types.

## Boundary for registered algorithms

The DSL should not grow loops, arbitrary callbacks, imports, or unrestricted
Python merely to eliminate every built-in. A registered algorithm is justified
when it is:

- scientifically named and independently testable;
- deterministic and atomic;
- expensive or obscure to express with collection reducers;
- explicitly versioned in serialization.

The likely irreducible families after a second pass are:

1. LMSR pricing and settlement;
2. matching mechanisms such as deferred acceptance and serial dictatorship;
3. auction clearing and mechanism-specific settlement.

Centipede transitions, capacity checks, work claiming, counter updates, and
payoff formulas should first be expressed with the generic language. If they
cannot be represented clearly, that is evidence for one missing general
construct—not automatically evidence for another domain class.

## Evaluation

The completed per-target experiment contains 36 independently serialized
recipes. The arithmetic batch—dictator, trust, beauty contest, common pool,
market entry, and Nash demand—required one additional generic expression:
`map_of((key_expr, value_expr), ...)`. This permits result dictionaries whose
keys are participant names computed at runtime. It replaces a potentially large
family of role-specific payoff helpers with one ordinary map constructor. A
second batch—document, counter map, money request, and matrix game—added only
three general facilities: bounded integer types, positional sequence lookup,
and incrementing a selected set of map keys. Matrix-game conformance also
showed that public collection shapes (list versus tuple) belong in the recipe's
observable contract, even when both are serialized as JSON arrays.

The signaling, cheap-talk, and principal-agent recipes then composed without
adding any kernel feature. Their staged behavior uses command requirements;
private or delayed disclosure uses conditional views; and settlement uses the
same dynamic map constructor introduced by the arithmetic games. This is
positive evidence that these are configurations of a common state-machine
model rather than distinct execution primitives.

The bilateral-trade, centipede, and ascending-auction recipes added generic
sequence filtering and mapping, plus ordinary comparison operators. They also
exposed and corrected an interpreter-semantic issue: conditional expressions
must evaluate only the selected branch. Without lazy conditionals, a guarded
lookup such as “read the winning bid if a positive bid exists” can fail while
evaluating the branch that should have been skipped.

The sealed-bid auction did not require a registered settlement algorithm. A
stable, multi-key record sort plus ordinary map expressions made winner
selection, first- or second-price payment, all-pay revenue, and utilities
inspectable in the recipe. The message board then reused sequence projection
to retain interview metadata internally while omitting it from the public view;
only generic string trimming and case folding were added.

Signal schedules and forecast histories share the same collection vocabulary:
filtering prevents duplicate releases, participant context selects private
history, `latest_by` produces one current forecast per forecaster, and ordinary
maps compute consensus statistics. This batch also established that boolean
`and` and `or`, like conditional expressions, require short-circuit evaluation
so a validation guard can safely precede a lookup.

The final four existing targets clarify the extension boundary. Negotiation is
fully declarative. Preference collection and summary views for match pools and
deferred acceptance are declarative, while their iterative settlement rules are
registered as `serial_dictatorship@1` and `deferred_acceptance@1`. The double
auction similarly uses registered atomic transitions for order validation,
price-time matching, collateral checks, account transfers, order-status
changes, and trade creation. Its order-book view remains ordinary DSL.

The executable checks now cover each new recipe's behavior, JSON round trips,
and direct happy-path conformance between the DSL and the existing dictator,
matrix-game, signaling-game, ascending-auction, sealed-auction, forecast,
double-auction, and voting primitives. The 36 recipes comprise all 35 concrete
primitives in the experimental source catalog plus the proposed
`SharedRegister`; the reference suite currently has 45 passing tests.

The experiment supports the refactor, with a warning. Typed fields, four atomic
effects, pure expressions, and a few registered algorithm families appear able
to replace all 35 concrete classes. The first-pass helper count shows
that the expression algebra must be designed and measured carefully. A DSL is
smaller only if domain behavior is visible in serialized recipes rather than
hidden behind differently named runtime functions.

The catalog migration is complete. The next step is not to add more operators,
but to audit the resulting language: remove redundancies, classify registered
algorithms as trusted capabilities, impose static complexity and state-size
limits, and compare recipe readability with the original classes.
> Historical design audit. The implemented API is documented in
> [shared_state.md](shared_state.md).
