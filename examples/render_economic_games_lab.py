"""Render the live shared-state economic game suite as a self-contained HTML lab."""

from __future__ import annotations

import html
import json
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "economic_games_lab.html"


SOCIAL_EXAMPLES = [
    {
        "title": "Family message board",
        "file": "shared_state_family_message_board.py",
        "logs": [],
        "tags": ["social", "message board", "personas", "serial"],
        "setup": "John and Robin and their children Ada and Paul discuss a family outing over multiple ordered turns. Each post sees all earlier posts and may reply by author.",
        "result": "The family advocated sailing, kayaking, and video games in distinct voices while reacting to prior relatives and negotiating inclusive compromises.",
        "lesson": "Relationship traits belong in personas, while the message board remains canonical shared state with reply structure.",
    },
    {
        "title": "Bilateral negotiations",
        "file": "shared_state_bilateral_negotiation.py",
        "logs": ["bilateral-negotiations.jsonl"],
        "tags": ["social", "negotiation", "parallel pairs", "stop condition"],
        "setup": "Three buyer/seller pairs negotiate sailboat prices in parallel, with serial alternating offers inside each pair and up to five rounds.",
        "result": "Pair 2 reached agreement at 84 and stopped; another pair continued through a final 75 versus 95 gap. Pair histories remained isolated.",
        "lesson": "Grouped ordering plus per-scope terminal predicates supports parallel conversations that finish at different times.",
    },
    {
        "title": "Meeting agenda proposal and voting",
        "file": "shared_state_meeting_agenda.py",
        "logs": ["meeting-agenda.jsonl"],
        "tags": ["social", "agenda", "matrix voting", "multi-phase"],
        "setup": "Leadership personas first propose decision-oriented agenda items, then vote up, neutral, or down on the resulting dynamic slate.",
        "result": "Five distinct proposals were collected and five complete matrix ballots recorded, producing an auditable scored agenda.",
        "lesson": "Dynamic question items currently require a caller-visible phase boundary after proposals are known.",
    },
    {
        "title": "Customer-feedback synthesis",
        "file": "shared_state_customer_feedback_synthesis.py",
        "data_file": "customer_feedback_sample.csv",
        "logs": ["customer-feedback-synthesis-live.jsonl"],
        "tags": ["company", "customer research", "evidence", "prioritization"],
        "setup": "Product, support, UX, and analytics reviewers analyze 18 CSV comments, propose evidence-linked themes, consolidate them through typed synthesis phases, and independently rate five canonical themes for next-quarter priority.",
        "result": "Collaboration and Content Management scored 8/8. Administrative Transparency, Core Reliability, and Everyday UX/Accessibility each scored 7/8; Enterprise Operational Maturity scored 6/8. Every finding cites source comment IDs.",
        "lesson": "Nested list-of-object responses were unreliable and worked after decomposition into typed phases. Persisted phase gates enabled recovery, but retries duplicated four completed editor records, revealing the need for logical upsert or idempotency keys.",
    },
    {
        "title": "Product launch readiness review",
        "file": "shared_state_launch_readiness_review.py",
        "logs": ["launch-readiness-review-live.jsonl"],
        "tags": [
            "company",
            "launch readiness",
            "blockers",
            "veto",
            "conditional approval",
        ],
        "setup": "Seven functional leaders privately score a September 30 launch and submit evidence-backed blockers. The group then sees all blockers, proposes owned mitigations, and independently re-votes. Security and Legal hold explicit veto authority, while deterministic policy turns the persisted reviews into a decision, conditions, dissent record, and owner list.",
        "result": "The decision was delay. Median readiness rose from 45 to 50, but Security retained a conditional veto pending verified closure of the privileged-session-timeout finding, and Legal retained one pending written outside-counsel confirmation of the DPA. Product, Sales, Customer Success, and Operations dissented in favor of a limited lighthouse-customer launch; all seven functions recorded evidence-linked approval conditions and deadlines.",
        "lesson": "The review cleanly separates private assessment, shared diagnosis, mitigation, and accountable decision policy. It also exposes an important boundary: a proposed mitigation is not verified closure. A production workflow needs an evidence-submission and blocker-status phase, ideally with idempotency keys and structured dates, before vetoes can be lifted.",
    },
    {
        "title": "Strategic planning workshop",
        "file": "shared_state_strategic_planning_workshop.py",
        "logs": ["strategic-planning-workshop.jsonl"],
        "tags": ["company", "strategy", "budget", "portfolio", "challenge"],
        "setup": "Five executives propose costed annual initiatives, challenge one another serially, revise their business cases, privately rate the revised slate, and feed persisted costs and support into an exhaustive 100-unit portfolio optimizer.",
        "result": "The optimizer funded only Sofia's P3, Deepening Customer Ecosystems for Accelerated Market Share, at 60/100 units with support 8/10. Every revised initiative cost 50–60 units, so no pair was feasible.",
        "lesson": "A single sponsor-provided cost encourages indivisible, inflated proposals and can defeat portfolio diversification. Practical planning needs minimum/target/expanded funding tiers, marginal value curves, or a package-negotiation phase.",
    },
    {
        "title": "Tiered strategic planning workshop",
        "file": "shared_state_strategic_planning_tiered.py",
        "logs": ["strategic-planning-tiered.jsonl"],
        "tags": ["company", "strategy", "funding tiers", "portfolio", "dependencies"],
        "setup": "Sponsors convert initiatives into minimum, target, and expanded tiers. Reviewers rate five initiatives, a deterministic mechanism enumerates feasible tier combinations, and executives debate and privately rank the top three packages.",
        "result": "Portfolio 3 won the final ballot 8–4–3 and used all 100 units: P1 AI-personalization prototype at minimum (20), P2 platform modernization at target (35), P3 market pilot at minimum (25), and P5 capital-allocation proof of concept at minimum (20).",
        "lesson": "Tiering restored portfolio breadth and package discussion surfaced P2 as a dependency for P1. A failed 15-row tier matrix succeeded after reduction to five initiative ratings, showing that large dynamic matrices need chunking or a dedicated allocation question.",
    },
    {
        "title": "Rumor diffusion network",
        "file": "shared_state_rumor_diffusion.py",
        "logs": ["rumor-diffusion.jsonl"],
        "tags": ["social", "network", "viewer-filtered", "rumor"],
        "setup": "One unverified four-day-workweek rumor spreads for three rounds over a fixed five-person graph. Prompts see only addressed messages and their own sent messages.",
        "result": "The rumor reached the connected network in round 1. Facts and the no-official-memo caveat remained stable, while optimistic and skeptical framing diverged.",
        "lesson": "Viewer-relative projections are essential; a global prompt log would silently turn the graph into a complete network.",
    },
    {
        "title": "Forecast revision",
        "file": "shared_state_forecast_revision.py",
        "logs": ["forecast-revision-snapshot.jsonl"],
        "tags": ["social learning", "forecast", "private signals", "round snapshots"],
        "setup": "Five forecasters revise probabilities over three rounds from private signals 78, 64, 42, 28, and 55 while observing completed prior-round consensus.",
        "result": "Round 1 exactly matched private signals, proving same-round invisibility. Final forecasts were 75, 64, 53, 48, and 58.",
        "lesson": "Snapshot rounds separate social learning from arbitrary within-round completion order.",
    },
    {
        "title": "Anonymous Delphi forecast",
        "file": "shared_state_delphi_forecast.py",
        "logs": ["delphi-enterprise-launch.jsonl"],
        "anonymize_actors": True,
        "tags": ["company", "Delphi", "forecast", "anonymous", "convergence"],
        "setup": "Six functional experts estimate an enterprise product's on-time launch probability from private evidence. Sealed rounds reveal only anonymous prior-round statistics and facilitator-synthesized arguments, stopping on range and median-stability criteria.",
        "result": "The panel converged after four rounds. Median probability fell from 60% to 40%, the range narrowed from 43 to 8 points, and the final confidence-weighted estimate was 40.8%. Final anonymous estimates were 37, 40, 40, 40, 45, and 45.",
        "lesson": "Anonymous snapshot feedback produced measurable convergence while preserving minority arguments. Inter-round LLM facilitation still requires a caller loop, and long structured facilitator output needed a free-text fallback. Named identities remain in the restricted audit log, not the participant view.",
    },
    {
        "title": "Peer-review matching",
        "file": "shared_state_peer_review_matching.py",
        "logs": ["peer-review-matching.jsonl"],
        "tags": ["social", "matching", "preferences", "capacity"],
        "setup": "Six reviewers rank three papers subject to conflicts. A deterministic serial-dictatorship allocator uses declared priority and paper capacity two.",
        "result": "Every conflict was ranked last; every paper received two reviewers. Later-priority reviewers were displaced when preferred capacity filled.",
        "lesson": "Concurrent preference collection is compatible with deterministic allocation, but append order must not become priority.",
    },
    {
        "title": "Hiring committee",
        "file": "shared_state_hiring_committee.py",
        "logs": ["hiring-committee-live.jsonl"],
        "tags": ["social", "hiring", "private review", "secret ballot"],
        "setup": "Five executives independently rank four candidates, an anonymized Borda score creates a three-person shortlist, members deliberate serially in public, and then cast private final rankings.",
        "result": "Avery, Blake, and Devon made the shortlist. After five public statements, Blake won the secret Borda ballot 8–6–1 over Avery and Devon.",
        "lesson": "Public deliberation and private decisions can share one workflow, but repetitive agreement suggests discussion prompts need explicit novelty or challenge requirements.",
    },
    {
        "title": "Adversarial hiring committee",
        "file": "shared_state_adversarial_hiring_committee.py",
        "logs": ["hiring-committee-adversarial-live.jsonl"],
        "tags": ["social", "hiring", "recusal", "persuasion", "pre-post"],
        "setup": "Five executives privately rank four deliberately conflicting candidates, publicly challenge prior arguments in serial order, and rank again. Sofia discloses a conflict with Rowan and is recused from the final ballot.",
        "result": "Morgan won the four-person final Borda ballot 10–7–6–1 over Atlas, Quinn, and Rowan. Maya and Priya changed their rankings after deliberation; Eli and Noah did not. Sofia disclosed her conflict and did not cast a final ballot.",
        "lesson": "Pre/post rankings measure persuasion directly, while challenge requirements reduce empty agreement. A failed first run also showed that each phase must receive its domain context: shared history alone is not enough.",
    },
    {
        "title": "Graduate-program matching market",
        "file": "shared_state_matching_market.py",
        "logs": ["matching-market.jsonl"],
        "tags": ["matching", "deferred acceptance", "private preferences", "capacity"],
        "setup": "Six applicants privately rank three two-seat graduate programs. A student-proposing deferred-acceptance primitive combines those preferences with fixed program priorities.",
        "result": "Each program drew exactly two first choices, so every applicant received a first-choice match: Amina and Diego to Northstar, Chloe and Evan to Lakeside, and Ben and Farah to CivicLab.",
        "lesson": "Settlement was deterministic and order-independent, but the balanced run never exercised rejection chains. Adding the primitive also exposed Survey's centralized operation allowlist as an extensibility limitation.",
    },
    {
        "title": "Congested matching market",
        "file": "shared_state_congested_matching_market.py",
        "logs": ["matching-market-congested.jsonl"],
        "tags": ["matching", "deferred acceptance", "congestion", "stability"],
        "setup": "Five of six applicants rank two-seat CivicLab first. Student-proposing deferred acceptance processes rejections using fixed program priorities, then a checker searches for blocking pairs.",
        "result": "CivicLab retained Farah and Ben from five first-choice applicants. Amina and Diego moved to Northstar; Chloe moved to Lakeside with Evan. All seats filled and the stability checker found zero blocking pairs.",
        "lesson": "The settlement is correct, but tentative holds, rejections, and reapplications are not persisted as events. Mechanism-level auditability needs a settlement trace, not only final state.",
    },
    {
        "title": "Live atomic review queue",
        "file": "shared_state_live_review_queue.py",
        "logs": ["live-review-queue.jsonl"],
        "tags": ["social", "work queue", "atomic claim", "before action"],
        "setup": "Four concurrent reviewers atomically claim one paper immediately before their review prompt, then complete that exact work item.",
        "result": "All four papers were claimed exactly once and received paper-specific reviews. Claim order followed concurrent render timing, not AgentList order.",
        "lesson": "Atomicity ensures uniqueness, not skill fit; routing and claiming are separate problems.",
    },
    {
        "title": "Disaster-response coordination",
        "file": "shared_state_disaster_response.py",
        "logs": ["disaster-response.jsonl"],
        "tags": ["social", "disaster response", "resources", "atomic allocation"],
        "setup": "Fire, EMS, utility, and police commanders allocate one capability-specific resource each across two incident waves. Resources remain committed after assignment, and incompatible or duplicate attempts are rejected atomically.",
        "result": "Wave 1 assigned the ambulance to a bus crash, engine to a warehouse fire, and grid crew to a downed line. Wave 2 assigned patrol to an evacuation; a hospital generator failure and brush fire remained unserved because utility and fire resources were still committed.",
        "lesson": "Later critical incidents require resource release, reassignment, or preemption. The run also exposed that operation logs persist attempted arguments but not acceptance or rejection outcomes, which can make a raw audit trace misleading.",
    },
    {
        "title": "Coalition formation",
        "file": "shared_state_coalition_formation.py",
        "logs": ["coalition-formation-scarce.jsonl"],
        "tags": ["social", "coalitions", "capacity", "rejection"],
        "setup": "Seven participants request membership in Growth, Safety, or Bridge coalitions with only six total seats over two rotated live rounds.",
        "result": "All coalitions filled. Gus was rejected twice; Clara’s attempted move to full Growth preserved her old Bridge seat atomically.",
        "lesson": "Unilateral atomic moves preserve invariants but cannot realize mutually beneficial contingent swaps.",
    },
    {
        "title": "Shared civic budget",
        "file": "shared_state_budget_allocation.py",
        "logs": ["budget-allocation.jsonl"],
        "tags": ["social", "budget", "scarcity", "partial fulfillment"],
        "setup": "Six delegates request up to $20 from a live $75 civic budget across named projects; the final request may be partially filled.",
        "result": "Three delegates received $20 and a fourth received the final $15. Immediate exhaustion skipped two delegates and all later rounds.",
        "lesson": "Atomic decrement ensures correctness but immediate serial stopping can be distributively unfair.",
    },
    {
        "title": "Legislative amendment experiment",
        "file": "shared_state_legislative_amendments.py",
        "logs": ["legislative-amendments.jsonl"],
        "tags": ["social", "document", "revision", "failure case"],
        "setup": "Four legislators repeatedly receive the latest bill and atomically replace it with a complete revised draft plus rationale.",
        "result": "Writes serialized correctly, but eight LLM rewrites truncated the bill and drifted into unrelated criminal appeals, lighting, and water mains.",
        "lesson": "Serialization prevents races, not semantic corruption. Documents need stable clauses, typed patches, diffs, and enactment authority.",
    },
    {
        "title": "Distributed incident response",
        "file": "shared_state_incident_response.py",
        "logs": ["incident-response.jsonl"],
        "tags": ["social", "incident", "work claims", "synthesis"],
        "setup": "Four responders atomically claim investigations and post evidence; a commander then synthesizes root cause and mitigation.",
        "result": "All investigations were unique and completed. The evidence converged on release 4.8 retry amplification, but the commander resolution was truncated.",
        "lesson": "Claims need capability routing and leases; a terminal resolution needs a validated schema rather than a log label.",
    },
    {
        "title": "Binary prediction market",
        "file": "shared_state_binary_prediction_market.py",
        "logs": ["binary-prediction-market-rotating.jsonl"],
        "tags": ["prediction market", "LMSR", "private beliefs", "rotating order"],
        "setup": "Five private-belief agents trade a YES/NO LMSR contract for three live serial rounds with trader order rotated each round.",
        "result": "YES closed at 0.556 on 74 YES versus 65 NO shares. Rotating the last mover avoided the earlier exact return to 0.500.",
        "lesson": "The complete price path matters; terminal price alone can hide disagreement and fixed-order effects.",
    },
    {
        "title": "Prediction market with private news",
        "file": "shared_state_prediction_market_private_news.py",
        "logs": ["prediction-market-private-news.jsonl"],
        "tags": ["prediction market", "private news", "before action", "viewer state"],
        "setup": "Four traders receive one private signal just in time before each of three rotated rounds, while observing a public LMSR price and private portfolio.",
        "result": "All 12 signals released to the intended trader immediately before trading. Positive final news moved YES to 0.737.",
        "lesson": "Time-varying private information should not be static persona traits; before-question actions are a generic lifecycle concept.",
    },
    {
        "title": "Repeated public goods baseline",
        "file": "shared_state_public_goods.py",
        "logs": ["public-goods.jsonl", "public-goods-snapshot.jsonl"],
        "tags": ["public goods", "social learning", "serial vs snapshot"],
        "setup": "Four personas contribute from 20-token endowments for four rounds, compared under live-serial and snapshot-per-round visibility.",
        "result": "Serial play went 80, 80, 20, 0 after observed free-riding. Snapshot contributions declined 50, 40, 28, 20 without within-round cascades.",
        "lesson": "Execution visibility is part of the experimental treatment and materially changes behavior.",
    },
]


GAMES = SOCIAL_EXAMPLES + [
    {
        "title": "Ultimatum game",
        "file": "economic_game_ultimatum.py",
        "logs": ["economic-game-ultimatum-role-paths-v2.jsonl"],
        "tags": ["sequential", "bargaining", "private preferences"],
        "setup": "A proposer divides $100; the responder observes the offer and accepts or rejects. Three pairs run in parallel with serial turns inside each pair.",
        "result": "Offers were $50, $25, and $50. All were accepted, yielding 50/50, 75/25, and 50/50 payoffs.",
        "lesson": "Role-specific question paths and automatic pair finalization remove dummy actions from asymmetric games.",
    },
    {
        "title": "11–20 money request",
        "file": "economic_game_11_20_money_request.py",
        "logs": ["economic-game-11-20-auto-finalize-v2.jsonl"],
        "tags": ["simultaneous", "sealed", "level-k reasoning"],
        "setup": "Two players request 11–20. Both receive their request; asking exactly one less than the opponent earns a $20 bonus.",
        "result": "Four pairs chose (20,19), (19,18), (18,11), and (19,16). The one-step undercutter earned the bonus in the first two pairs.",
        "lesson": "Snapshot watermarks keep choices sealed even though commits arrive in nondeterministic order.",
    },
    {
        "title": "Prisoner’s dilemma and stag hunt",
        "file": "economic_games_matrix.py",
        "logs": [
            "economic-game-prisoners-dilemma.jsonl",
            "economic-game-stag-hunt.jsonl",
        ],
        "tags": ["normal form", "sealed", "coordination"],
        "setup": "The same three persona pairs play a one-shot prisoner’s dilemma and stag hunt using a generic payoff matrix.",
        "result": "PD produced mutual cooperation, mutual defection, and exploited cooperation. Stag hunt produced stag/stag, hare/hare, and stag/hare miscoordination.",
        "lesson": "Stable declared seats—not completion order—must index asymmetric payoff matrices.",
    },
    {
        "title": "Repeated prisoner’s dilemma",
        "file": "economic_game_repeated_prisoners_dilemma.py",
        "logs": ["economic-game-repeated-pd.jsonl"],
        "tags": ["repeated", "sealed rounds", "history dependent"],
        "setup": "Two pairs play three rounds. Completed history is revealed before the next round, while current actions remain sealed.",
        "result": "Tit-for-tat/forgiving sustained cooperation for 9–9. Always-defect exploited grim-trigger once, followed by mutual defection, ending 7–2.",
        "lesson": "Round-indexed state is necessary for conditional strategies; a one-shot seat value cannot simply be overwritten.",
    },
    {
        "title": "Dictator and trust games",
        "file": "economic_games_transfer.py",
        "logs": ["economic-game-dictator.jsonl", "economic-game-trust.jsonl"],
        "tags": ["transfers", "sequential", "reciprocity"],
        "setup": "Dictators unilaterally divide $100. In trust, senders transfer from $100, the transfer triples, and receivers choose a return.",
        "result": "Dictator transfers were 50, 20, and 0. Trust produced full trust/reciprocity, cautious partial trust, and zero trust.",
        "lesson": "Similar-looking transfers still need different authority and terminal semantics.",
    },
    {
        "title": "Beauty contest and common pool",
        "file": "economic_games_group.py",
        "logs": [
            "economic-game-beauty-contest.jsonl",
            "economic-game-common-pool.jsonl",
        ],
        "tags": ["group", "aggregate payoff", "commons"],
        "setup": "Beauty contest targets two-thirds of the mean. Common-pool players request 0–20 from stock 60, with proportional rationing above capacity.",
        "result": "Beauty choices ranged 0–49; target 15.28 and Cleo won at 26. Pool requests totaled 84, rewarding aggressive requests under rationing.",
        "lesson": "Aggregate settlement belongs after the sealed reveal boundary; fixed expected player counts are brittle under failures.",
    },
    {
        "title": "Centipede game",
        "file": "economic_game_centipede.py",
        "logs": ["economic-game-centipede.jsonl"],
        "tags": ["sequential", "early stop", "backward induction"],
        "setup": "Alice and Bob alternate take/pass over six scheduled nodes, with a growing pot and immediate terminal settlement after take.",
        "result": "Alice took at node 1 for payoff (2,0). Nodes 2–6 were skipped and the scope closed after one model call.",
        "lesson": "A terminal predicate can finalize shared state and suppress already-scheduled downstream interviews.",
    },
    {
        "title": "Public goods with punishment",
        "file": "economic_game_public_goods_punishment.py",
        "logs": ["economic-game-public-goods-punishment.jsonl"],
        "tags": ["public goods", "sanctions", "multi-phase"],
        "setup": "Four sealed contributions are revealed, followed by sealed 0–3 peer-punishment assignments costing 1 and harming the target by 3.",
        "result": "Contributions were 0, 20, 10, 10. All three contributors gave the free-rider 3 punishment points, reducing that payoff from 36 to 9.",
        "lesson": "The two-run implementation exposes the need for native intra-job phases and reveal barriers.",
    },
    {
        "title": "Market entry",
        "file": "economic_game_market_entry.py",
        "logs": ["economic-game-market-entry.jsonl"],
        "tags": ["simultaneous", "congestion", "coordination failure"],
        "setup": "Six firms choose enter or stay out. Staying out pays 2; each entrant earns 10 − 3k when k firms enter.",
        "result": "Three firms entered, making entry pay 1 versus the outside payoff 2: a realized excess-entry failure.",
        "lesson": "Sealed aggregate games can represent valid off-equilibrium outcomes without treating them as execution failures.",
    },
    {
        "title": "Auction mechanism comparison",
        "file": "economic_games_auction_comparison.py",
        "logs": [
            "economic-game-auction-first_price.jsonl",
            "economic-game-auction-second_price.jsonl",
            "economic-game-auction-all_pay.jsonl",
        ],
        "tags": ["auction", "private values", "mechanism comparison"],
        "setup": "The same five private values (92, 76, 61, 47, 33) bid under first-price, second-price, and all-pay rules.",
        "result": "First-price revenue 91; second-price revenue 76 with truthful bids; all-pay revenue 168 and value-47 Dina beat value-92 Arun.",
        "lesson": "All-pay requires debiting losers, and private values in raw operation logs need a production privacy policy.",
    },
    {
        "title": "Continuous double auction",
        "file": "economic_game_continuous_double_auction.py",
        "logs": ["economic-game-double-auction.jsonl"],
        "tags": ["auction", "order book", "atomic matching", "price-time priority"],
        "setup": "Four buyers with private values 112, 98, 84, and 69 and four sellers with private costs 42, 58, 76, and 91 submit unit limit orders over three live-state concurrent rounds.",
        "result": "Three round-1 trades cleared: Buyer 1/Seller 4 at 112, Buyer 4/Seller 1 at 50, and Buyer 2/Seller 2 at 60. Realized surplus was 88 versus the efficient benchmark of 118, or 74.6%.",
        "lesson": "Atomic price-time matching worked, but arrival order produced allocative inefficiency. Open orders also need clearer prompt guidance or automated expiry/repricing because Buyer 3 and Seller 3 simply held non-crossing orders.",
    },
    {
        "title": "Adverse-selection trade",
        "file": "economic_game_adverse_selection.py",
        "logs": ["economic-game-adverse-selection.jsonl"],
        "tags": ["private costs", "posted price", "trade"],
        "setup": "Buyers value an asset at 100 but do not observe seller costs. They post a take-it-or-leave-it price; sellers respond privately.",
        "result": "Offers 60 and 75 traded against costs 30 and 60. An offer of 1 against cost 75 was rejected.",
        "lesson": "Hidden cost may determine settlement without appearing in the buyer’s public view.",
    },
    {
        "title": "Education signaling",
        "file": "economic_game_signaling.py",
        "logs": ["economic-game-signaling.jsonl"],
        "tags": ["signaling", "hidden type", "screening"],
        "setup": "Workers privately know productivity and education cost, choose education 0–3, and employers observe only education before hiring at wage 60.",
        "result": "Observed separation, screening, high-type under-signaling, and successful low-type mimicry that cost the employer −20.",
        "lesson": "A hidden type must affect terminal payoff while remaining absent from the receiver’s state view.",
    },
    {
        "title": "Nash demand bargaining",
        "file": "economic_game_nash_demand.py",
        "logs": ["economic-game-nash-demand.jsonl"],
        "tags": ["simultaneous bargaining", "sealed", "infeasibility"],
        "setup": "Two players simultaneously demand shares of a 100-unit pie. Compatible demands are paid; demands above 100 give both zero.",
        "result": "Pairs produced 50/50, feasible 55/40 with five wasted, and destructive 100/100 demands yielding zero.",
        "lesson": "Infeasible agreement is a valid economic result, not a failed write.",
    },
    {
        "title": "Information cascade",
        "file": "economic_game_information_cascade.py",
        "logs": ["economic-game-information-cascade.jsonl"],
        "tags": ["social learning", "sequential", "private signals"],
        "setup": "True state A; private signals B, B, A, A, A, A. Agents see prior choices but not prior signals.",
        "result": "Every agent chose B. Four A-signaled observers followed the first two public choices into a complete incorrect cascade.",
        "lesson": "Public actions are informationally dependent observations; a log preserves order but does not encode that dependence.",
    },
    {
        "title": "Voting rules",
        "file": "economic_game_voting_rules.py",
        "logs": ["economic-game-voting-rules.jsonl"],
        "tags": ["social choice", "sealed ballots", "rule comparison"],
        "setup": "Seven sincere rankings are resolved under plurality, Borda, and pairwise Condorcet rules.",
        "result": "Plurality elected Alpha 3–2–2. Borda elected Beta 9–6–6, and Beta was the Condorcet winner.",
        "lesson": "One immutable ballot profile supports controlled comparisons between collective settlement rules.",
    },
    {
        "title": "Strategic voting",
        "file": "economic_game_strategic_voting.py",
        "logs": ["economic-game-strategic-voting.jsonl"],
        "tags": ["plurality", "strategic reports", "polls"],
        "setup": "The same true preferences vote under plurality after a poll suggests Gamma cannot defeat Alpha.",
        "result": "Both Gamma supporters moved Beta first, flipping plurality from Alpha to Beta, 4–3.",
        "lesson": "Private preferences and reported ballots are distinct state requiring distinct provenance and access control.",
    },
    {
        "title": "Cheap talk",
        "file": "economic_game_cheap_talk.py",
        "logs": ["economic-game-cheap-talk.jsonl"],
        "tags": ["communication", "hidden state", "babbling"],
        "setup": "Senders observe L/R and send costless messages. Receivers know whether sender interests are aligned or biased toward action R.",
        "result": "Aligned messages were truthful and followed. Biased senders always said R; receivers ignored them and always chose L.",
        "lesson": "Hidden state can score truthfulness after settlement without entering the receiver’s prompt-visible state.",
    },
    {
        "title": "Principal-agent moral hazard",
        "file": "economic_game_moral_hazard.py",
        "logs": ["economic-game-moral-hazard.jsonl"],
        "tags": ["contracts", "hidden action", "precision"],
        "setup": "Principals offer success bonuses. Workers privately choose high effort (.8 success, cost 20) or low effort (.2, cost 0).",
        "result": "Bonus 33.333 induced low effort; 33.34 induced high effort. A tiny rounding difference crossed the exact 33⅓ incentive boundary.",
        "lesson": "Display, validation, model-visible, and payoff precision need one explicit policy at indifference boundaries.",
    },
]


def log_summary(names):
    blocks, count, scopes, ops = [], 0, set(), {}
    for name in names:
        path = ROOT / name
        if not path.exists():
            blocks.append(f"Missing log: {name}")
            continue
        rows = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        count += len(rows)
        scopes.update(str(row.get("scope")) for row in rows)
        for row in rows:
            op = row.get("op", "unknown")
            ops[op] = ops.get(op, 0) + 1
        blocks.append(
            f"# {name}\n" + "\n".join(json.dumps(row, indent=2) for row in rows)
        )
    return count, sorted(scopes), ops, "\n\n".join(blocks)


ACTOR_KEYS = (
    "player",
    "trader",
    "bidder",
    "observer",
    "voter",
    "sender",
    "speaker",
    "member",
    "sponsor",
    "forecaster",
    "claimant",
    "worker",
    "buyer",
    "dictator",
    "principal",
    "author",
    "proposer",
    "student",
    "reviewer",
    "responder",
    "analyst",
    "challenger",
    "expert",
    "owner",
)
PRIVATE_KEYS = {"private_value", "seller_cost", "productivity", "signal_cost"}


def readable_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return " → ".join(readable_value(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(
            f"{key.replace('_', ' ').title()}: {readable_value(item)}"
            for key, item in value.items()
        )
    return str(value)


def human_trace(names, anonymize_actors=False):
    rows_html = []
    sequence = 0
    actor_aliases = {}
    for name in names:
        path = ROOT / name
        if not path.exists():
            continue
        for row in (
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ):
            sequence += 1
            args = dict(row.get("args") or {})
            actor = next(
                (str(args.pop(key)) for key in ACTOR_KEYS if key in args), "System"
            )
            if anonymize_actors and actor != "System":
                actor_aliases.setdefault(actor, f"Expert {len(actor_aliases) + 1}")
                actor = actor_aliases[actor]
            round_value = args.pop("round", "—")
            operation = str(row.get("op", "event")).replace("_", " ")
            if operation == "  close  ":
                operation = "finalize"
                detail = "Scope closed and settlement became final."
            else:
                visible_args = {
                    key: value for key, value in args.items() if key not in PRIVATE_KEYS
                }
                detail = "; ".join(
                    f"{key.replace('_', ' ').title()}: {readable_value(value)}"
                    for key, value in visible_args.items()
                )
                if not detail:
                    detail = "Event recorded."
            cells = (
                sequence,
                row.get("scope", "—"),
                round_value,
                actor,
                operation,
                detail,
            )
            rows_html.append(
                "<tr>"
                + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells)
                + "</tr>"
            )
    if not rows_html:
        return (
            '<div class="no-trace">No structured event log was saved for this early '
            "prototype. Its interpreted outcome and source code are retained below.</div>"
        )
    return f"""<details class="trace" open><summary>Chronological event trace ({sequence} events)</summary>
<div class="table-wrap"><table><thead><tr><th>#</th><th>Scope</th><th>Round</th><th>Actor</th><th>Event</th><th>What happened</th></tr></thead>
<tbody>{"".join(rows_html)}</tbody></table></div></details>"""


def render():
    formatter = HtmlFormatter(cssclass="code", style="friendly")
    cards, sections = [], []
    for index, game in enumerate(GAMES, 1):
        slug = f"game-{index}"
        source_path = ROOT / "examples" / game["file"]
        source = source_path.read_text()
        code = highlight(source, PythonLexer(), formatter)
        data_details = ""
        if game.get("data_file"):
            data_path = ROOT / "examples" / game["data_file"]
            data_details = (
                f"<details><summary>View input dataset <code>{html.escape(game['data_file'])}</code>"
                f'</summary><pre class="log">{html.escape(data_path.read_text())}</pre></details>'
            )
        event_count, scopes, ops, raw_log = log_summary(game["logs"])
        trace = human_trace(
            game["logs"], anonymize_actors=game.get("anonymize_actors", False)
        )
        if game["title"] == "Family message board":
            trace += (
                '<p><a class="artifact-link" href="shared_state_family_board_relationships.html">'
                "Open the original rendered family conversation →</a></p>"
            )
        tags = "".join(f"<span>{html.escape(tag)}</span>" for tag in game["tags"])
        cards.append(
            f'<a class="card" href="#{slug}" data-search="{html.escape((game["title"] + " " + " ".join(game["tags"])).lower())}">'
            f'<small>{index:02d}</small><strong>{html.escape(game["title"])}</strong><div class="tags">{tags}</div></a>'
        )
        op_text = ", ".join(f"{key}: {value}" for key, value in sorted(ops.items()))
        sections.append(
            f'''<section id="{slug}">
<div class="section-head"><div><p class="eyebrow">Experiment {index:02d}</p><h2>{html.escape(game["title"])}</h2></div><a href="#top">Back to index ↑</a></div>
<div class="summary-grid">
  <article><h3>Setup</h3><p>{html.escape(game["setup"])}</p></article>
  <article class="result"><h3>Live Gemini result</h3><p>{html.escape(game["result"])}</p></article>
  <article><h3>Design lesson</h3><p>{html.escape(game["lesson"])}</p></article>
</div>
<div class="readable"><h3>Human-readable live results</h3><p>{html.escape(game["result"])}</p>{trace}</div>
<div class="run-meta"><b>{event_count}</b> persisted events · <b>{len(scopes)}</b> scope(s) · {html.escape(op_text)}</div>
<details><summary>View complete Python setup <code>{html.escape(game["file"])}</code></summary>{code}</details>
{data_details}
<details><summary>View replayable JSONL event log</summary><pre class="log">{html.escape(raw_log)}</pre></details>
</section>'''
        )

    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDSL Shared-State Simulation Lab</title><style>
:root{{--ink:#18201d;--muted:#66716c;--paper:#f4f1e8;--panel:#fffdf7;--line:#d8d3c5;--green:#185c4a;--gold:#d99b32;--blue:#315b78}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,sans-serif}}
header{{padding:72px max(6vw,24px) 54px;background:linear-gradient(125deg,#123d35,#1d6653);color:white}}header .kicker,.eyebrow{{font-size:.75rem;letter-spacing:.14em;text-transform:uppercase;font-weight:800}}h1{{font:700 clamp(2.5rem,6vw,5.8rem)/.95 Georgia,serif;max-width:980px;margin:.2em 0}}header p{{max-width:760px;font-size:1.15rem;color:#d8eee6}}.stats{{display:flex;gap:28px;flex-wrap:wrap;margin-top:32px}}.stats b{{font-size:1.7rem;display:block;color:#ffd083}}main{{width:min(1180px,92vw);margin:auto}}nav{{padding:48px 0}}#filter{{width:100%;padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);font-size:1rem;margin-bottom:18px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;text-decoration:none;color:inherit;transition:.15s}}.card:hover{{transform:translateY(-2px);border-color:var(--green);box-shadow:0 8px 20px #183b3020}}.card small{{color:var(--gold);font-weight:800;display:block}}.card strong{{font:700 1.2rem Georgia,serif}}.tags{{margin-top:10px}}.tags span{{font-size:.7rem;background:#e5eee9;color:var(--green);padding:3px 7px;border-radius:99px;margin:0 4px 4px 0;display:inline-block}}section{{padding:54px 0;border-top:1px solid var(--line);scroll-margin-top:12px}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px}}.section-head h2{{font:700 clamp(2rem,4vw,3.3rem)/1 Georgia,serif;margin:.1em 0}}.section-head a{{color:var(--green)}}.summary-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}}article{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}}article.result{{border-top:4px solid var(--gold)}}article h3{{margin-top:0;font-size:.85rem;text-transform:uppercase;letter-spacing:.08em;color:var(--green)}}.readable{{background:#edf4ef;border-left:5px solid var(--green);padding:20px;border-radius:10px;margin:22px 0}}.readable h3{{margin:0;text-transform:uppercase;letter-spacing:.08em;font-size:.9rem;color:var(--green)}}.table-wrap{{overflow:auto;max-height:560px;border-top:1px solid var(--line)}}table{{width:100%;border-collapse:collapse;font-size:.82rem;background:white}}th,td{{padding:9px 11px;border-bottom:1px solid #e8e4da;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#e5eee9;color:var(--green);z-index:1}}td:first-child,td:nth-child(3){{text-align:right;color:var(--muted)}}details.trace{{background:white}}details.trace summary{{font-size:.82rem}}.no-trace{{padding:14px;background:white;border:1px dashed var(--line);border-radius:8px;color:var(--muted)}}.artifact-link{{color:var(--green);font-weight:700}}.run-meta{{font-family:ui-monospace,monospace;color:var(--muted);margin:15px 0 25px}}details{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:10px 0;overflow:hidden}}summary{{padding:15px 18px;cursor:pointer;font-weight:700}}details>div.code,pre.log{{border-top:1px solid var(--line);margin:0;max-height:680px;overflow:auto;font-size:.78rem}}pre.log{{padding:18px;background:#17201d;color:#dce8e2;white-space:pre-wrap}}{formatter.get_style_defs(".code")}.code pre{{padding:18px;margin:0}}footer{{padding:50px 6vw;background:#17201d;color:#b9cbc3;margin-top:40px}}@media(max-width:760px){{.summary-grid{{grid-template-columns:1fr}}header{{padding-top:48px}}}}
</style></head><body><header id="top"><p class="kicker">Expected Parrot · EDSL shared state</p><h1>Shared-State Simulation Laboratory</h1><p>A live, replayable collection of social simulations, coordination protocols, prediction markets, and economic games. Every experiment includes its setup, observed Gemini 2.5 Flash result, complete EDSL Python, and persisted event log where available.</p><div class="stats"><div><b>{len(GAMES)}</b>experiments</div><div><b>{sum(len(g["logs"]) for g in GAMES)}</b>live log files</div><div><b>26</b>focused tests passing</div></div></header><main><nav><h2>Experiment index</h2><input id="filter" placeholder="Filter social simulations, games, mechanisms, or tags…" aria-label="Filter experiments"><div class="cards">{"".join(cards)}</div></nav>{"".join(sections)}</main><footer>Generated from the working tree by <code>examples/render_economic_games_lab.py</code>. Event logs are replay artifacts; private values in prototype logs are not production access-controlled.</footer><script>const f=document.querySelector('#filter');f.addEventListener('input',()=>{{const q=f.value.toLowerCase();document.querySelectorAll('.card').forEach(x=>x.style.display=x.dataset.search.includes(q)?'block':'none')}})</script></body></html>"""
    OUTPUT.write_text(body)
    print(OUTPUT)


if __name__ == "__main__":
    render()
