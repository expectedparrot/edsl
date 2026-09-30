# Thirty-six shared-state case studies with Gemini

## Method

Each retained shared-state machine was embedded in a concrete EDSL Survey and run
with `gemini-2.5-flash` using local inference. Sequential mechanisms used live
reads; simultaneous decisions used common snapshot rounds; repeated processes used
round barriers; and terminal mechanisms used typed completion and finalization.

These are case studies, not estimates of average model behavior. Each run is one
realization intended to test whether the example is understandable, executable,
and analytically useful. The runnable source is
`examples/shared_state_gemini_game_smoke.py`. Results come from
`examples/shared_state_gemini_complete_audit.json`, with simplified reruns for four
slow cases in `examples/shared_state_gemini_case_study_reruns.json`.

## Economic games

### 1. Dictator allocation

**Scenario.** A dictator divides a $100 endowment with an anonymous recipient.

**Result.** Gemini transferred $25 and retained $75.

**What it showed.** A single terminal decision maps cleanly to one command and one
typed completion predicate. The raw exit state is easy to interpret.

### 2. Ultimatum bargaining

**Scenario.** A proposer divides $100; a responder can accept or destroy the pie.

**Result.** The proposer offered $50 and the responder accepted.

**What it showed.** Ordered roles and just-in-time state refresh worked: the
responder read version 1 containing the actual offer.

### 3. Trust and reciprocity

**Scenario.** A sender may transfer up to $100, which is tripled; the receiver may
return any amount.

**Result.** The sender transferred all $100 and the receiver returned $150, leaving
an equal $150/$150 division.

**What it showed.** The state machine correctly constrained the return by available
funds and captured an unusually trusting behavioral outcome.

### 4. Bilateral trade

**Scenario.** A buyer values an object at $90; a seller privately incurs cost $30.

**Result.** The buyer offered exactly $30 and the seller rejected.

**What it showed.** Indifference at the participation constraint needs an explicit
behavioral convention. A mechanically feasible trade need not be behaviorally
accepted.

### 5. Bilateral negotiation

**Scenario.** The same buyer and seller negotiate the price of a used sailboat
through an append-only turn record.

**Result.** The buyer offered $40 and the seller accepted.

**What it showed.** Framing and a visible transcript changed behavior relative to
the one-shot trade. The agreement field correctly copied the preceding offer.

### 6. One-shot matrix game

**Scenario.** Two players simultaneously choose cooperate or defect under standard
prisoner's-dilemma payoffs.

**Result.** Both defected and earned 1 each.

**What it showed.** Both decisions read version 0, confirming genuinely sealed
simultaneous play.

### 7. Repeated matrix game

**Scenario.** The same two players repeat the dilemma for three observable rounds.

**Result.** Both defected in all three rounds. Read versions were `[0,0]`, `[2,2]`,
and `[4,4]`.

**What it showed.** Round snapshots worked exactly. The example also forced round
keys to be explicitly JSON-stable rather than relying on numeric dictionary keys.

### 8. Centipede game

**Scenario.** Players alternate take/pass decisions along a three-node payoff tree.

**Result.** The first player took immediately for payoffs `[2,0]`; later interviews
were skipped.

**What it showed.** Early terminal state correctly propagates into schedule-level
stopping.

### 9. Nash demand

**Scenario.** Two players independently demand shares of a $100 pie; incompatible
demands pay zero.

**Result.** Both demanded $50, producing a feasible equal split.

**What it showed.** Settlement from two sealed numeric answers is concise and
unambiguous.

### 10. The 11–20 money-request game

**Scenario.** Each player requests 11–20; asking exactly one less than the other
earns a $20 bonus.

**Result.** Requests were 12 and 15, so neither earned the bonus.

**What it showed.** Gemini did not coordinate on adjacent requests in this single
realization. Repetition is needed before drawing a behavioral conclusion.

### 11. Beauty contest

**Scenario.** Three players choose 0–100; the winner is closest to two-thirds of the
mean.

**Result.** Choices were 19, 14.28, and 19; the target was 11.62 and the 14.28
player won.

**What it showed.** Derived close-time statistics and deterministic winner selection
worked with non-integer answers.

### 12. Market entry

**Scenario.** Three firms choose whether to enter a market with congestion costs.

**Result.** One entered and earned 7; two stayed out and earned 2.

**What it showed.** The simultaneous outcome was economically coherent, unlike an
earlier realization in which every firm stayed out.

### 13. Common-pool extraction

**Scenario.** Three users extract up to 20 units from a stock of 60.

**Result.** Extractions were 20, 15, and 15; total demand was 50 and payoffs were
23.33, 18.33, and 18.33.

**What it showed.** Nested payoff construction and floating-point serialization
were stable.

### 14. Cheap talk

**Scenario.** An aligned sender privately observes state L or R and sends a
costless message; a receiver then acts.

**Result.** The sender truthfully sent L and the receiver chose L.

**What it showed.** Private information can enter a write without leaking through
the public view; the receiver sees only the message.

### 15. Labor-market signaling

**Scenario.** A productive worker chooses costly education before an employer's
hiring decision.

**Result.** The worker chose zero education and the employer did not hire.

**What it showed.** Information design matters: the employer observed the signal,
not the hidden productivity input. The result is not a runtime error, but the
scenario should state what beliefs education is meant to convey.

### 16. Principal–agent contracting

**Scenario.** A firm offers a success bonus; a worker privately chooses costly high
or free low effort.

**Result.** The firm offered 34 and the worker chose high effort.

**What it showed.** The public view can conceal effort until closure while still
computing expected payoffs.

## Auctions, markets, and matching

### 17. Sealed second-price auction

**Scenario.** Three bidders have private values 80, 70, and 40.

**Result.** Gemini bid exactly those values; the value-80 bidder won and paid 70.

**What it showed.** Private traits, snapshot bidding, deterministic tie-breaking,
and close-time utilities composed cleanly.

### 18. Ascending auction

**Scenario.** Three bidders with values 45, 65, and 55 bid sequentially for a
sailboat lesson.

**Result.** Bids were only 1, 2, and 3; the last bidder won at 3.

**What it showed.** The state machine worked, but the mechanism is not behaviorally
complete: it lacks repeated bidding, dropout, and a stopping rule. One bid per
bidder turns “ascending auction” into a misleading label.

### 19. Continuous double auction

**Scenario.** A buyer worth 70 and seller costing 30 submit simultaneous limit
orders.

**Result.** A bid of 69 crossed an ask of 31 and traded at 31.

**What it showed.** The registered matching algorithm atomically updated orders,
accounts, inventory, and the trade record regardless of arrival order.

### 20. Binary prediction market

**Scenario.** An optimist with belief 75% and pessimist with belief 25% trade an
LMSR contract before an external resolution.

**Result.** They bought 8 YES and 2 NO shares. The event resolved false; settled
wealth was 95.84 for the optimist and 101.07 for the pessimist.

**What it showed.** The exercise discovered that portfolios were originally inert.
The algorithm now records LMSR costs, cash, positions, and settlement wealth.

### 21. Deferred acceptance

**Scenario.** Students A and B rank North and South under institution priorities
and one seat per institution.

**Result.** A matched North and B matched South.

**What it showed.** Typed participant-count completion eliminated a synthetic
“market closer” respondent.

### 22. Serial-dictatorship activity matching

**Scenario.** Three people rank four scarce group activities in priority order.

**Result.** A received hike, B bike ride, and C sailing.

**What it showed.** Preference collection, interview audit IDs, algorithmic close,
and public assignment release worked together.

## Collective choice and resource allocation

### 23. Ranked voting

**Scenario.** Three voters rank candidates A, B, and C according to stated ideals.

**Result.** First-place votes tied 1–1–1; A won Borda and Condorcet comparisons and
was also reported as plurality winner.

**What it showed.** The plurality tie-break silently used candidate declaration
order. That rule should be explicit in configuration and output.

### 24. Coalition formation

**Scenario.** Five members request entry into red or blue coalitions with capacity
two each.

**Result.** Four members filled the coalitions; the fifth request was recorded but
rejected as capacity-full.

**What it showed.** Conditional writes preserve an audit trail of unsuccessful
attempts. A typed advisory reason would make the rejection easier to analyze.

### 25. Emergency-resource allocation

**Scenario.** An engine crew and ambulance crew select incidents from a shared
board containing a fire and injury.

**Result.** E1 was assigned to fire and A1 to injury; both attempts were accepted.

**What it showed.** Live sequential visibility prevented duplicate incident claims.
Giving agents fixed capabilities reduced inference calls and made the substantive
decision clearer.

### 26. Civic budget allocation

**Scenario.** Park and library advocates sequentially request shares of a $100
municipal fund.

**Result.** Each requested and received $50; the budget reached zero and the chair's
later interview was skipped.

**What it showed.** Finite-resource clamping and schedule stopping work. The first
version used two model questions per agent and timed out; a better Survey asks only
the decision not already fixed by role.

### 27. Activity preference register

**Scenario.** Three residents privately register one weekend-activity preference.

**Result.** All registered hike.

**What it showed.** Concurrent snapshot writes were isolated and successful. The
homogeneous result reflects under-specified personas, not shared-state visibility.

### 28. Activity counter

**Scenario.** Four residents choose an activity and increment a shared tally.

**Result.** All four chose beach day.

**What it showed.** Atomic commutative updates work, but the case needs heterogeneous
resident traits to be a meaningful behavioral simulation.

## Deliberation, information, and collaborative work

### 29. Delphi forecasting

**Scenario.** Three experts with initial estimates 45, 55, and 65 revise after a
common first-round summary.

**Result.** Six responses committed in two complete rounds before closure. Round
reads were `[0,0,0]` and `[3,3,3]`.

**What it showed.** The first implementation could converge after only one response
in round two. Completion now requires a full panel in both compared rounds.

### 30. Forecast revision

**Scenario.** Three forecasters begin at 30%, 50%, and 70%, then see consensus and
revise once.

**Result.** In the prompt-capture run, second-round estimates were 45%, 50%, and
54%, showing convergence from initial beliefs of 30%, 50%, and 70%.

**What it showed.** Fixing confidence as part of the persona made the Survey both
clearer and faster than asking Gemini for two answers per round.

### 31. Private-signal schedule

**Scenario.** Amina and Boris receive different private weather signals in two
rounds and interpret each one.

**Result.** Amina saw sunny then windy; Boris saw cloudy then calm. Read versions
were 1, 2, 3, and 4.

**What it showed.** This required true before-question writes. It also revealed
that they do not yet safely compose with concurrent common snapshots; the example
uses a private live view, and unsafe snapshot construction is rejected.

### 32. Committee agenda

**Scenario.** Two members propose weekend projects; two later members vote on the
generated agenda.

**Result.** Every participant first contributes an activity and then votes on the
complete agenda. The matrix rows are resolved from the committed proposal list,
and positional matrix answers are decoded into semantic activity-to-vote mappings.

**What it showed.** A Survey can express distinct proposal and voting phases with
sequential visibility. Raw Results snapshots omit the derived score view, which is
an analysis limitation.

### 33. Collaborative document

**Scenario.** Three editors sequentially improve a one-sentence activity plan.

**Result.** The text evolved through three versions and ended as “The plan is to
decide on an activity.”

**What it showed.** Versioning worked, but the final text was still not actionable.
The prompt needs an explicit acceptance criterion, and the machine may need a
review/approval primitive rather than unconditional whole-document replacement.

### 34. Field-observation log

**Scenario.** Three observers independently record concise evidence about group
cooperation.

**Result.** Three entries committed atomically; one response ignored the requested
format and supplied several alternatives.

**What it showed.** `T.any()` is convenient but too weak for research data. A typed
record schema would catch malformed or overly broad observations at creation.

### 35. Family message board

**Scenario.** Three members sequentially discuss how to choose a restorative
weekend activity.

**Result.** Later messages explicitly incorporated earlier contributions, producing
a coherent thread.

**What it showed.** The content behaved like replies, but every `reply_to` remained
null because the Survey did not ask agents to select message IDs. The machine
supports threading; the example did not expose it ergonomically.

### 36. Atomic work pool

**Scenario.** Two workers concurrently claim two queued work items before seeing
their question, then submit completion notes.

**Result.** Worker A received W2 and Worker B W1; both completed distinct items.

**What it showed.** Before-question assignment is atomic, while the command outcome
remains advisory. A subsequent persistent read exposes a viewer-specific `my_claim`
as the authoritative assignment without disclosing other workers' claims. Assignment
order remains completion-dependent and should be explicit when reproducibility matters.

### 37. Meeting availability poll

**Scenario.** Four professors with different preferred slots and different degrees
of flexibility serially mark every meeting time they would accept while seeing
earlier responses.

**Result.** Wednesday at 2:00 PM became acceptable to all four professors even
though it was nobody's first choice. It appeared in the first response and every
later respondent retained it. Tuesday at 10:00 AM reached three acceptances; all
other slots reached two. Reads advanced through versions `[0,1,2,3]`.

**What it showed.** A checkbox answer composes naturally with a typed sequence in
shared state. Keeping both the per-person acceptability map and atomically updated
slot counts makes the state useful for prompts and later analysis. Serial visibility
allows later participants to trade off convenience against coordination, making the
path of earlier responses behaviorally consequential.

## What these case studies suggest changing

The examples point to five priorities:

1. Store canonical derived exit views alongside raw exit state in Results.
2. Add first-class round setup and finalization barriers.
3. Support serializable machine parameter binding for participant counts and rules.
4. Preserve question/provider/attempt details for bounded inference failures.
5. Encourage typed record schemas instead of unconstrained `T.any()` in research
   workflows.

They also suggest a documentation principle: every shared-state primitive should
be introduced through a complete case study with an information structure and an
analysis question. A state transition that executes is necessary; a simulation
that means something is the actual standard.
