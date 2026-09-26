# Shared-state simulation learnings

This is a running lab notebook for live EDSL shared-state simulations. It records
observed behavior, runtime implications, and changes suggested by evidence rather
than by API aesthetics alone.

## Repeated public-goods game

Run: `examples/shared_state_public_goods.py` with Gemini 2.5 Flash, four agents,
four rounds, and serial just-in-time state reads.

Observed result:

- Rounds 1 and 2 reached full cooperation: 80 of 80 tokens contributed.
- In round 3, Avery contributed 20, Blake free-rode with 0, and Casey and Devon
  subsequently contributed 0 after seeing the new within-round history.
- Round 4 collapsed to zero contributions from every player.
- Blake, Casey, and Devon earned 112 total tokens; Avery earned 92.

What this demonstrates:

1. A generic `SharedLog` is sufficient canonical state for this application.
   The game-specific totals and payoffs can remain application-level views.
2. Just-in-time reads create genuine within-round path dependence. This is not
   equivalent to a simultaneous-move public-goods game. A snapshot execution
   mode would be needed for simultaneous rounds.
3. Serial execution is costly when a turn contains multiple model questions.
   The 32 calls were strictly sequential and took several minutes.
4. Separate decision and rationale questions preserve numerical range validation
   but double calls. A structured one-call answer would be faster, but current
   `QuestionDict` fields do not express the numerical bounds used here.
5. Personas influence language but do not rigidly constrain behavior. The
   group-oriented player defected after observing free-riding, so agent labels
   should be treated as preferences, not deterministic policies.

Suggested refactors:

- Add a snapshot-per-round schedule for simultaneous-move games.
- Support references to fields inside structured answers so one validated answer
  can atomically write multiple values.
- Consider constrained fields in `QuestionDict` before replacing separate typed
  questions merely to reduce model calls.
- Preserve shared-state read/write provenance in Results so behavioral claims can
  be tied directly to the snapshot each agent saw.

### Snapshot-round rerun

After adding `InterviewSchedule.rounds(..., state_visibility="snapshot")`, the
same public-goods design was rerun with one immutable watermark per round.

- Round 1 contributions were 20, 20, 10, and 0. Blake defected independently
  from the empty initial history; the others could not react within the round.
- Group contributions then declined by round: 50 → 40 → 28 → 20.
- The group-oriented Casey continued contributing 20 in every round while the
  conditional and reciprocal agents reduced their contributions.
- Total payoffs ranged from 135.2 for Blake to 55.2 for Casey.
- Runtime fell substantially because agents within a round ran concurrently.

This comparison confirms that execution semantics change the substantive result:
the original live-serial run created an observational cascade inside round 3,
whereas the snapshot run produced independent within-round decisions and only
allowed reactions in the following round.

## Rumor diffusion over a network

Run: `examples/shared_state_rumor_diffusion.py` with Gemini 2.5 Flash, five
agents, three rounds, and a filtered `SharedLog` over a fixed network.

Observed result:

- One unverified claim seeded to Alice reached the entire connected network in
  the first round.
- The factual content remained surprisingly stable: every retelling continued
  to mention the lack of an official memo.
- Framing diverged persistently. Cara and Eli amplified excitement; Ben and Dina
  repeatedly emphasized that the claim was unsubstantiated.
- The canonical log contained 16 events, while each prompt received only the
  messages addressed to that agent plus the agent's own sent messages.

What this demonstrates:

1. Viewer-relative state is necessary for network simulations; a global log in
   every prompt would silently turn the network into a complete graph.
2. Filtering must happen immediately before render using the current agent, just
   like scope resolution.
3. Network position controlled information access while persona primarily
   controlled framing. The simulation did not produce much factual mutation,
   suggesting future runs should introduce lossy recall or message-length limits.
4. Putting `visible_to` directly on `SharedLog` works but conflates canonical
   storage with a viewer-specific projection. Issue #2537's separate `views=`
   concept is cleaner and should be the longer-term API.

Suggested refactors:

- Separate `SharedLog` from `FilteredLogView` rather than configuring visibility
  on the primitive itself.
- Record the exact filtered view and state version used for every prompt.
- Add snapshot-per-round execution to distinguish network topology effects from
  within-round ordering effects.

## Forecast revision with private signals

Run: `examples/shared_state_forecast_revision.py` with Gemini 2.5 Flash, five
forecasters, three rounds, and serial live consensus updates.

Private signals were 78, 64, 42, 28, and 55 percent. Final forecasts were 77,
67, 47, 45, and 58 percent, producing a 58.8 percent mean and a 60.8 percent
confidence-weighted consensus.

Observed result:

- Aria, whose private signal was 78, remained anchored near it: 78 → 75 → 77.
- Basil moved modestly upward from 64: 69 → 69 → 67.
- Chen initially herded strongly from a 42 signal to 58, then moved back to 48
  and 47 in later rounds.
- Dara moved most strongly toward the group, from a 28 signal to 40, 39, and 45.
- Emi stayed near a 55 signal at 60, 57, and 58.

What this demonstrates:

1. The latest-per-respondent revision policy works naturally over an immutable
   history: analysis can retain every revision while the live view selects the
   most recent forecast for each person.
2. Visible consensus produced heterogeneous herding. Agents with low private
   signals moved much more than the high-signal agent.
3. Serial ordering contaminates a nominal round because later forecasters can
   see earlier forecasts from that same round. A proper snapshot-per-round mode
   is required for clean experimental interpretation.
4. Growing prompt history and 30 strictly serialized calls made this the slowest
   run. The live view should expose latest forecasts and summary statistics while
   keeping full history available for analysis but out of prompts by default.
5. `SharedForecast` is useful as a prototype, but its mechanics are generic:
   append-only revisions plus latest-by-key and aggregate views. Those views
   should ultimately compose over `SharedLog` rather than remain a core
   domain-specific primitive.

Suggested refactors:

- Introduce reusable `LatestByKeyView` and numeric aggregate views over logs.
- Add snapshot barriers between rounds.
- Support one constrained structured response for probability and confidence.
- Store each read version and write receipt with Results for causal auditing.

### Snapshot-round rerun

With the new round barriers, every first-round forecast exactly matched its
private signal: 78, 64, 42, 28, and 55 percent. This is a strong end-to-end
check that same-round writes were invisible. Social learning began only in round
2. By round 3 the forecasts were 75, 64, 53, 48, and 58 percent.

Compared with the serial baseline, low-signal agents still moved toward the
group, but that movement was attributable to a completed prior-round consensus
rather than the arbitrary position of an agent within the current round.

## Peer-review matching

Run: `examples/shared_state_peer_review_matching.py` with Gemini 2.5 Flash, six
reviewers, three papers, capacity two per paper, and deterministic declared
reviewer priority.

Observed result:

- Every reviewer ranked their conflicted paper last, so the private constraint
  was respected in all six ballots.
- Four reviewers ranked P1 first, while P2 and P3 each received one first choice.
- Serial dictatorship assigned two reviewers to every paper without violating a
  conflict: Rina→P3, Omar→P1, Lin→P1, Mateo→P3, Grace→P2, and Tariq→P2.
- Mateo and Tariq were displaced from their first choices after earlier-priority
  reviewers exhausted capacity.

What this demonstrates:

1. Concurrent preference collection and deterministic allocation are compatible,
   but allocation must use declared priority rather than append/completion order.
2. Closing the pool is a useful explicit phase boundary: open-state views expose
   demand, while assignments appear only after close.
3. Serial dictatorship is easy to explain and replay but can sacrifice aggregate
   fit. A later allocator should support auditable alternative rules such as
   maximum-weight matching.
4. This is batch assignment, not live work claiming. The peer-review case from
   issue #2537 still motivates an atomic before-question `claim` action when the
   review task itself must be inserted into the next prompt.

Suggested refactors:

- Keep claimant identity and priority as first-class matching inputs.
- Add assignment-rule metadata to the closed-state result.
- Implement pre-question actions with returned values before attempting a live
  review queue; selecting from a stale rendered list is not safe enough.

## Live atomic review queue

Run: `examples/shared_state_live_review_queue.py` with Gemini 2.5 Flash, four
concurrent reviewers, four papers, and a `SharedWorkPool.claim_before(...)`
action executed immediately before prompt rendering.

Observed result:

- All four papers were claimed exactly once and the pool ended with zero
  available items.
- Every prompt contained the paper atomically claimed for that reviewer.
- Each structured review was committed back to the same claimant and item.
- All reviewers recommended revision and gave paper-specific strengths and
  concerns, confirming that the claimed value reached the model prompt.
- Claim order was Rina, Grace, Lin, Omar rather than AgentList order. Claims were
  unique but FIFO routing reflected concurrent render timing.

What this demonstrates:

1. Before-question actions are genuinely different from after-answer writes: the
   atomic operation's returned state changes what the respondent is asked.
2. An idempotency key tied to interview, question, target, and operation prevents
   render retries from consuming multiple work items.
3. Atomicity guarantees uniqueness, not suitability. A FIFO queue can assign a
   privacy specialist an agent-auditing paper depending on claim timing.
4. Queue exhaustion needs explicit control flow. A claimant receiving `None`
   should wait, skip, or receive a clear no-work route rather than render the
   ordinary review question.
5. The current in-process file store proves lifecycle semantics locally, but a
   distributed implementation needs the same claim and idempotency guarantees in
   the state service.

Suggested refactors:

- Separate routing from claiming: filter eligible items by capabilities, then
  atomically claim from that eligible set.
- Add `on_empty="wait|skip|error"` to claim actions.
- Persist action receipts and claimed values in Results provenance.
- Add lease, completion, release, and requeue semantics for abandoned work.

## Binary contract prediction market

Run: `examples/shared_state_binary_prediction_market.py` with Gemini 2.5 Flash,
five traders, three live serial rounds, private YES beliefs from 0.22 to 0.80,
and an LMSR market maker with liquidity 40.

Observed result:

- The YES price traversed 0.494–0.657 as agents traded on their private beliefs.
- Bullish traders bought 70 YES shares in total and bearish traders bought
  exactly 70 NO shares, returning the terminal price to 0.500.
- The balanced trader sometimes bought NO and once submitted a zero-quantity
  order, showing that both the latest quote and perceived edge reached the model.
- After resolving the contract YES, final wealth ranged from 85.96 to 117.08;
  the two most bullish traders finished first.

What this demonstrates:

1. Each trader observed the just-in-time price produced by all preceding trades;
   the within-round price path is direct evidence of live shared-state reads.
2. A terminal price alone can conceal substantial information aggregation and
   disagreement. The complete event path is part of the result, not merely
   debugging data.
3. Fixed serial ordering creates a last-mover effect. Dara traded last in every
   round and happened to restore the price to 0.500 in the final transaction.
4. Direction plus integer quantity is easy for an LLM to use, but it does not
   elicit a trader's desired quote and can produce coarse, path-dependent prices.

Suggested refactors:

- Rotate or randomize trader order between rounds while recording the realized
  order for replay.
- Support signed position changes or a target-price order in addition to the
  simple buy-YES/buy-NO interface.
- Render the full price path and trade ledger in the HTML view.
- Compare live serial rounds with batch call-auction rounds when order effects
  should be removed.

Follow-up with rotating order:

- Added `order_by="trader_order", round_order="rotate"` to round schedules.
- Realized order was Aria→Basil→Emi→Chen→Dara, then
  Basil→Emi→Chen→Dara→Aria, then Emi→Chen→Dara→Aria→Basil.
- The rerun ended at YES 0.556 on 74 YES versus 65 NO shares, rather than
  returning to 0.500 under a repeated last mover.
- Rotation reduces systematic positional advantage while retaining live serial
  price discovery. It does not eliminate path dependence, which is intrinsic to
  this continuous market mechanism.

## Capacity-constrained coalition formation

Run: `examples/shared_state_coalition_formation.py` with Gemini 2.5 Flash,
seven participants, two rotated live rounds, and three coalitions with two seats
each.

Observed result:

- Growth filled with Amina and Ben, Safety with Diego and Elena, and Bridge with
  Clara and Farah.
- Gus's round-one request for Bridge was rejected because it was full.
- In round two Clara attempted to move from Bridge to full Growth and retained
  her Bridge seat; Gus then attempted Growth and was rejected again.
- The event log preserved every accepted and rejected request while membership
  remained exclusive and capacity-safe.

What this demonstrates:

1. A primitive can atomically maintain invariants spanning several internal
   collections: coalition rosters, capacities, and exclusive memberships.
2. Rejection is domain state, not necessarily an execution exception. Recording
   it allowed the next-round prompt to expose the failed request to the agent.
3. Once every coalition was full, unilateral moves could not realize a bilateral
   swap. Atomic single-agent operations can create a stable state that is not a
   preferred or efficient matching.
4. An after-answer write receipt is not available to the same interview until a
   later question or round. Immediate fallback therefore needs returned action
   receipts, conditional steps, or a composite operation.

Suggested refactors:

- Let write operations expose a receipt to subsequent questions in the same
  interview.
- Support conditional offers such as “move me only if Clara moves to Safety.”
- Distinguish unmatched membership from rejected attempts in standard views.
- Consider transactional operations spanning multiple actors, while keeping
  authorization and deadlock behavior explicit.

## Prediction market with just-in-time private news

Run: `examples/shared_state_prediction_market_private_news.py` with Gemini 2.5
Flash, four traders, three rotated live rounds, and one private signal released
per trader immediately before each market decision.

Observed result:

- The schedule released 12 signals: exactly four in each round. Every release
  event immediately preceded the intended participant's trade event.
- The YES price closed at 0.737 after broadly positive final-round news.
- Quinn changed from zero-size NO orders in the first two rounds to buying three
  YES shares after receiving expedited regulatory approval.
- Oren changed from zero-size NO orders to buying six YES shares after learning
  that no launch blockers remained.

What this demonstrates:

1. Time-varying private context should not be encoded as static agent traits,
   where future signals may leak into the persona prompt. A viewer-filtered
   signal schedule can reveal it just in time.
2. Before-question actions are a generic lifecycle need, not a work-queue-only
   feature. Signal release required broadening the action allowlist.
3. Public market state and private viewer state can coexist in one atomic state
   snapshot without exposing other traders' signal contents.
4. A two-question direction/quantity order permits inconsistent-looking answers:
   several agents chose `buy_no` and then quantity zero. A single structured or
   signed-order response would express intent more cleanly.

Suggested refactors:

- Replace primitive-name allowlists for before-actions with a declared primitive
  capability.
- Store private payloads separately from the public event stream; release events
  should carry opaque references rather than signal contents.
- Support a single signed quantity or structured trade response.
- Include before-action receipts and state versions in result provenance.

## Finite shared-budget allocation

Run: `examples/shared_state_budget_allocation.py` with Gemini 2.5 Flash, six
delegates, a $75 budget, live serial allocation, partial final fulfillment, and
a budget-exhaustion stop condition.

Observed result:

- Inez, Jamal, and Keiko each requested and received $20 for their preferred
  projects.
- Luis requested Youth arts after only $15 remained and received exactly that
  partial amount.
- The budget then stopped the remaining two first-round interviews and every
  second-round interview; only four allocations were committed.
- Final funding was Cooling centers $20, Library hours $20, Bike safety $20, and
  Youth arts $15.

What this demonstrates:

1. Atomic partial fulfillment prevents overspending under contention and makes
   the final grant an ordinary domain outcome.
2. Stop predicates also work for round schedules and can avoid model calls once
   further action is pointless.
3. Immediate stopping makes serial position distributively decisive. Mara and
   Noah never received a turn, so rotating later rounds could not compensate.
4. Efficiency and fairness require separate scheduling policies. A technically
   correct atomic decrement does not imply a defensible allocation process.

Suggested refactors:

- Add batch request collection followed by a declared allocation rule such as
  proportional rationing, equal shares, or priority scoring.
- Distinguish “stop immediately” from “finish the current round, then stop.”
- Surface skipped interviews and their stop reason in Results.
- Compare serial grants against snapshot-visible sealed requests resolved at a
  round barrier.

## Legislative whole-document amendments

Run: `examples/shared_state_legislative_amendments.py` with Gemini 2.5 Flash,
four legislators and two rotated live rounds. Each agent received the latest
bill and atomically replaced it with a complete revised draft plus rationale.

Observed result:

- Eight revisions committed without write races, and every writer received the
  latest serialized draft.
- The final bill was truncated midway through its second clause.
- Several rationales drifted into unrelated domains—criminal convictions, smart
  lighting, and water-main replacement—even though the shared document concerned
  automated government decisions.
- Revision metadata survived, but it did not identify which clause changed or
  prove that untouched provisions were preserved.

What this demonstrates:

1. Serial execution prevents lost writes but cannot guarantee semantic document
   integrity.
2. Whole-document replacement asks an LLM to copy all unchanged text perfectly
   on every turn; errors compound through the shared state.
3. A revision history containing only rationales is insufficient provenance when
   the underlying text drifts or disappears.
4. Legislative workflows need separate proposal, debate, vote, and enactment
   phases. Treating every proposal as immediately enacted conflates authority.

Suggested refactors:

- Represent documents as stable addressable clauses and apply typed patches.
- Store before/after hashes and exact diffs for every proposed change.
- Validate that a patch touches only its declared clauses before committing it.
- Separate proposed amendments from enacted text and require an explicit voting
  or adjudication operation to merge them.

## Distributed incident response

Run: `examples/shared_state_incident_response.py` with Gemini 2.5 Flash, four
concurrent responders atomically claiming investigations, followed by a commander
synthesis phase.

Observed result:

- All four investigations were claimed exactly once, completed, and posted to a
  public evidence log.
- Claim order followed concurrent prompt timing rather than expertise: the
  dependency lead received metrics while the SRE received dependency traffic.
- Investigators collectively connected transient dependency failures, expanded
  retries, database locks, and post-release latency into a plausible causal chain.
- The commander selected release 4.8's retry expansion as the leading cause, but
  the resolution text was truncated and still committed as a resolution entry.

What this demonstrates:

1. Atomic uniqueness is not intelligent routing; claim eligibility and ranking
   must be distinct from the atomic act of claiming.
2. A phase boundary built as two runs works, but the workflow and evidence that
   all prerequisite tasks completed remain external to shared state.
3. A log label such as `commander_resolution` does not enforce a resolution
   schema, completeness, verification, or authority.
4. Completed work has no lease or requeue path if an agent fails after claiming.

Suggested refactors:

- Add capability-filtered claims and deterministic routing policies.
- Add leases, heartbeat, abandonment, and requeue behavior.
- Model incident phases and terminal status explicitly rather than as log kinds.
- Require structured resolution fields and validation before allowing closure.

## Ultimatum games across parallel pairs

Run: `examples/economic_game_ultimatum.py` with Gemini 2.5 Flash, three isolated
pairs executing concurrently, and proposer→responder ordering within each pair.

Observed result:

- Fairness-oriented pair 1 offered and accepted $50, producing a 50/50 split.
- Strategically self-interested P2 offered $25 to a responder willing to accept
  any positive amount; it was accepted for payoffs 75/25.
- Pair 3 also settled at 50/50 because its responder required an even split.

What this demonstrates:

1. Templated scopes and grouped serial scheduling naturally represent many
   independent games running in parallel.
2. The responder received the committed offer just in time, while activity in
   other pairs did not create dependencies or leak state.
3. A shared survey for heterogeneous roles forced both roles to answer irrelevant
   questions whose values the primitive ignored. Role-conditional question paths
   would make the experiment cleaner and cheaper.

## 11–20 money-request game

Run: `examples/economic_game_11_20_money_request.py` with Gemini 2.5 Flash, four
isolated pairs, simultaneous snapshot-visible choices, and a $20 bonus for asking
exactly one less than the opponent.

Observed result:

- Choices were (20,19), (19,18), (18,11), and (12,19).
- The lower requester earned the bonus in the first two pairs, yielding payoffs
  (20,39) and (19,38); neither player earned a bonus in the other pairs.
- Commit order varied inside pairs, but no prompt could observe the opponent's
  same-round choice because both used the pair's version-zero watermark.

What this demonstrates:

1. Snapshot rounds provide sealed simultaneous play without delaying atomic
   commits themselves.
2. Hidden-until-close views are a primitive responsibility; scheduling alone
   does not define what state is private.
3. Settlement at close cleanly separates action collection from deterministic
   payoff calculation.
4. Closing several templated scopes is currently an explicit caller loop; a job
   does not automatically enumerate and close every realized group scope.

Suggested refactors:

- Add role-conditional survey paths for asymmetric games.
- Add group-finalization semantics so pair-scoped games settle automatically once
  all required actions arrive.
- Record the snapshot watermark in each result row to audit sealed play directly.

Foundation follow-up:

- Agent-trait skip rules now pass authoring validation, allowing role-specific
  questions in a shared survey. Ultimatum proposers no longer answer responder
  questions or vice versa.
- Round schedules now declare `reveal="after_round"` for sealed play instead of
  relying on the less expressive `state_visibility="snapshot"` alone.
- Schedules accept `finalize_when`, allowing each realized pair scope to close and
  settle automatically when its primitive reports completion.
- A concurrent 11–20 rerun exposed and fixed a predicate-contract bug: schedule
  predicates receive public primitive views, not raw internal state.

## Sealed matrix games

Run: `examples/economic_games_matrix.py` with Gemini 2.5 Flash, three persona
pairs each in a prisoner's dilemma and stag hunt.

Observed result:

- Prisoner's dilemma produced mutual cooperation (3,3), mutual defection (1,1),
  and exploited cooperation (0,5) across the three heterogeneous pairs.
- Stag hunt produced payoff-dominant stag coordination (4,4), risk-dominant hare
  coordination (3,3), and stag/hare miscoordination (0,3).
- All six pair scopes closed automatically at version 3, and completion order did
  not determine player position because payoff lookup used declared seats.

What this demonstrates:

1. A generic sealed normal-form primitive can support many games without
   hard-coding their economic interpretation.
2. Stable player seats are necessary; insertion or completion order is not a safe
   way to index an asymmetric payoff matrix.
3. Persona heterogeneity survives sealed execution and generates the expected
   range of equilibrium and off-equilibrium outcomes.

## Dictator and trust games

Run: `examples/economic_games_transfer.py` with Gemini 2.5 Flash and three
persona treatments per game.

Observed result:

- Dictator transfers were $50, $20, and $0 as personas moved from egalitarian to
  strictly payoff maximizing.
- The high-trust sender transferred all $100; the receiver returned $150 of the
  tripled $300, producing equal $150 payoffs.
- The cautious pair sent $25 and returned $25, while the strictly self-interested
  pair sent and returned zero.
- Every scope finalized automatically after its actual terminal action.

What this demonstrates:

1. Role-conditional paths remove dummy answers cleanly in sequential asymmetric
   games.
2. Domain validation must use state-dependent bounds: receiver returns cannot
   exceed the multiplied transfer, even though the numerical question has a
   broader static maximum.
3. Distinct game primitives remain useful where action authority and settlement
   semantics differ, even if scheduling infrastructure is shared.

## Beauty contest and common-pool extraction

Run: `examples/economic_games_group.py` with Gemini 2.5 Flash and sealed group
actions.

Observed result:

- Beauty-contest choices were 49, 31.25, 26, 0, 31.25, and 0. Their mean was
  22.92 and the two-thirds target was 15.28; Cleo's 26 was closest.
- Common-pool requests totaled 84 against a stock of 60. Three agents requested
  20 and two requested 12, triggering proportional rationing.
- Aggressive requesters received 14.29 each while conservative requesters
  received 8.57 each.

What this demonstrates:

1. Automatic finalization generalizes from pairs to configured-size groups.
2. Aggregate statistics and deterministic winner/payoff calculation belong at
   the reveal boundary, after all sealed actions arrive.
3. The common-pool mechanism generated a genuine social dilemma: conservation
   was collectively helpful but privately punished under proportional rationing.
4. A fixed `player_count` is brittle if an interview fails or is skipped; group
   membership should ultimately come from the realized schedule manifest.

## Repeated prisoner's dilemma

Run: `examples/economic_game_repeated_prisoners_dilemma.py` with Gemini 2.5
Flash, two pairs, three sealed rounds, and completed-round history revealed before
the next round.

Observed result:

- Tit-for-tat Tara and forgiving Felix cooperated in all three rounds and earned
  cumulative payoffs of 9 each.
- Always-defect Dex exploited grim-trigger Greta in round one for payoffs 5–0.
- Greta then defected in rounds two and three, producing mutual defection and
  final cumulative payoffs Dex 7, Greta 2.
- Both pair scopes finalized automatically after their sixth action.

What this demonstrates:

1. Reveal-after-round supports history-dependent strategies without leaking a
   current opponent action.
2. A repeated primitive needs round-indexed actions; a one-shot primitive that
   overwrites each seat cannot preserve strategic history.
3. Round barriers plus automatic finalization compose correctly across isolated
   parallel pairs.
4. The primitive currently trusts the configured round count; failures or skipped
   actions can leave the game permanently incomplete without timeout settlement.

## Centipede game

Run: `examples/economic_game_centipede.py` with Gemini 2.5 Flash and six
alternating scheduled decision nodes.

- Alice took immediately at node 1, yielding payoffs (2,0), consistent with
  backward induction.
- The scope closed at version 2 and nodes 2–6 were skipped without model calls.
- This confirms that a terminal predicate can both finalize state and suppress
  already-scheduled downstream interviews.

## Public goods with peer punishment

Run: `examples/economic_game_public_goods_punishment.py` with Gemini 2.5 Flash,
a sealed contribution phase followed by a sealed punishment phase.

- Contributions were Blake 0, Casey 20, Avery 10, and Devon 10.
- Each non-free-rider assigned Blake three punishment points. Blake received nine
  points total, reducing a pre-sanction payoff of 36 to 9.
- Punishers each paid three tokens; final payoffs were Blake 9, Casey 13, Avery
  23, and Devon 23.
- The experiment required two EDSL runs because one job cannot yet express an
  intra-round phase barrier: contribute concurrently, reveal, then punish
  concurrently.

Design implication: schedules need explicit subphases with different questions,
visibility boundaries, and settlement operations. Splitting phases in caller code
works but hides the protocol structure from Jobs provenance.

## Market entry

Run: `examples/economic_game_market_entry.py` with Gemini 2.5 Flash and six
sealed firms. Staying out paid 2; entrant payoff was `10 - 3k`.

- Three firms entered, so each entrant earned 1 while firms staying out earned 2.
- Optimistic Lena, overconfident Omar, and strategically contrarian Raj entered;
  cautious Milo, risk-neutral Nia, and risk-averse Pia stayed out.
- The realized profile exhibited excess entry: every entrant would have preferred
  the outside option given the final aggregate count.

This confirms that sealed aggregate games can capture off-equilibrium coordination
failures while keeping completion order irrelevant.

## Sealed auction mechanism comparison

Run: `examples/economic_games_auction_comparison.py` with Gemini 2.5 Flash, the
same five bidders and private values 92, 76, 61, 47, and 33 under first-price,
second-price, and all-pay rules.

Observed result:

- First-price bids were 91, 65, 54, 47, and 33. Value-92 Arun won, paid 91, and
  earned utility 1; seller revenue was 91.
- Second-price bids exactly matched all five private values. Arun won at the
  second-highest value of 76, earning utility 16; revenue was 76.
- All-pay bids were 46, 45, 30, 47, and 0. Aggressive value-47 Dina outbid the
  highest-value bidder, won at zero utility, and total revenue reached 168.
- All losing positive bidders had negative utility in the all-pay treatment.

What this demonstrates:

1. Identical agents and values across mechanisms create a useful controlled
   comparison of LLM strategic behavior.
2. The second-price treatment elicited the dominant truthful strategy, while the
   first-price winner shaded by only one unit.
3. All-pay settlement must debit losing bidders; winner-only auction abstractions
   cannot represent contests or lobbying expenditure.
4. Private values currently appear in operation payloads and the local event log.
   Viewer filtering protects prompts, but a production privacy model needs opaque
   private inputs or access-controlled event storage.

## Adverse-selection bilateral trade

Run: `examples/economic_game_adverse_selection.py` with Gemini 2.5 Flash and
three buyer/seller pairs. Buyers valued the asset at 100 but did not observe
seller costs of 30, 60, and 75.

- Offers of 60 and 75 were accepted, producing buyer/seller payoffs (40,30) and
  (25,15).
- An aggressive offer of 1 against cost 75 was rejected and both earned zero.
- Seller cost remained absent from buyer state views while still determining
  settlement after the seller response.

## Education signaling

Run: `examples/economic_game_signaling.py` with high-productivity/low-cost and
low-productivity/high-cost workers. Employers observed education but not type.

- A high type chose education 3, was hired, and produced worker/employer payoffs
  (45,40).
- A low type chose zero and was screened out.
- Another high type under-signaled at zero and lost a mutually profitable match.
- A low type mimicked with education 1, was hired, earned 40, and imposed a −20
  payoff on the employer.

This demonstrates separating, screening, under-signaling, and successful mimicry
within the same private-state mechanism. Hidden type must influence settlement
without appearing in the receiver's public view.

## Nash demand bargaining

Run: `examples/economic_game_nash_demand.py` with Gemini 2.5 Flash and three
sealed pairs dividing a pie of 100.

- Fairness-oriented players coordinated on 50/50.
- An assertive/accommodating pair demanded 55 and 40, reached agreement, and left
  five units unclaimed.
- Two aggressive players each demanded 100, making the profile infeasible and
  destroying the entire surplus.

The game confirms that sealed pair settlement must represent infeasible outcomes
as valid domain results rather than failed writes or execution errors.

## Information cascade

Run: `examples/economic_game_information_cascade.py` with Gemini 2.5 Flash,
true state A, private signals B, B, A, A, A, A, and sequential public choices.

- The first two observers followed their B signals.
- Every later observer chose B despite receiving a private A signal.
- The final public sequence was unanimously wrong, demonstrating a complete
  information cascade rather than a state propagation failure.

Public choices must remain distinguishable from independent evidence. A generic
log preserves provenance by actor and position, but does not encode informational
dependence; agents must reason about that from the protocol description.

## Voting-rule and strategic-voting comparisons

Runs: `examples/economic_game_voting_rules.py` and
`examples/economic_game_strategic_voting.py` with seven voters.

- Under sincere rankings, plurality elected Alpha 3–2–2, while Borda elected Beta
  with scores 9–6–6 and Beta was also the Condorcet winner.
- In the strategic plurality treatment, both Gamma-first voters ranked Beta first
  after observing a poll that made Gamma appear nonviable.
- With underlying preferences unchanged, reported first choices became Beta 4,
  Alpha 3, flipping the plurality winner to Beta.

What this demonstrates:

1. Collective outcome rules should be settlement functions over one immutable
   ballot profile, enabling controlled mechanism comparisons.
2. Strategic reports and private preferences are different data. The election
   state currently records ballots but not an access-controlled preference ground
   truth, so manipulation analysis requires external agent-trait reconstruction.
3. Sealed collection prevents same-round imitation but does not prevent responses
   to common public information such as polls.

## Cheap-talk communication

Run: `examples/economic_game_cheap_talk.py` with Gemini 2.5 Flash, two aligned
and two sender-biased pairs.

- Aligned senders truthfully reported L and R; receivers followed both messages,
  so both players earned 1.
- Biased senders sent R in both hidden states. Skeptical receivers ignored the
  message and chose L in both cases.
- Ignoring the biased message was correct when state was L and wrong when state
  was R, reproducing a babbling-equilibrium pattern.

The public receiver view contained the message but not hidden state. Settlement
could still score message truthfulness and receiver correctness after the action.

## Principal-agent moral hazard

Run: `examples/economic_game_moral_hazard.py` with Gemini 2.5 Flash. High effort
had success probability .8 and cost 20; low effort had probability .2 and zero
cost, making the exact incentive threshold a bonus of 33⅓.

- The calculated principal offered 33.333, microscopically below the threshold;
  the worker chose low effort.
- Both other principals offered 33.34, just above threshold, and induced high
  effort despite their “stingy” and “generous” personas.
- High-effort principal expected payoff was 53.328; the below-threshold contract
  produced only 13.3334.

What this demonstrates:

1. Private actions can influence settlement while remaining hidden in open state
   views.
2. Numerical precision at indifference boundaries creates discontinuous behavior;
   question validation, display rounding, primitive comparison, and model-visible
   numbers need one consistent precision policy.
3. Strong payoff arithmetic can dominate qualitative persona labels, which is a
   useful behavioral result rather than an execution failure.
