"""Run concurrent ultimatum games and render their event logs as a chat dashboard."""

import argparse
import html
import random
from pathlib import Path
from datetime import datetime

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionMultipleChoice
from edsl import QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import (
    Action,
    ConfiguredSharedGame,
    Equals,
    FileStateStore,
    Field,
    Ref,
    Settlement,
    SharedState,
    Subtract,
)


TRAITS_TEMPLATE = """Your behavioral traits use scales from -1 to 1:
- generosity = {{ generosity }}: -1 means maximizing your own payoff without concern for the other player; 1 means willingly sacrificing your payoff to benefit the other player.
- inequity_aversion = {{ inequity_aversion }}: -1 means readily accepting highly unequal outcomes; 1 means strongly opposing unequal outcomes and being willing to receive $0 rather than accept a division you consider unfair.
Treat intermediate values proportionally and act consistently with them. As a responder, rejection gives both players $0."""


def ultimatum_game(stake=100):
    """Configure an ultimatum game without a game-specific state class."""
    return ConfiguredSharedGame(
        constants={"stake": float(stake)},
        fields={
            "offer": Field.number(minimum=0, maximum=stake),
            "decision": Field.choice(("accept", "reject")),
        },
        actions={
            "offer": Action(actor="proposer", writes="offer"),
            "respond": Action(
                actor="responder", writes="decision", requires=("offer",)
            ),
        },
        terminal_when_set="decision",
        settlement=Settlement(
            when=Equals(Ref("decision"), "accept"),
            payoffs={
                "proposer": Subtract(Ref("stake"), Ref("offer")),
                "responder": Ref("offer"),
            },
        ),
    )


def players(persona_count: int = 50, seed: int = 20260828):
    """Create reproducible random personas and assign adjacent agents to pairs."""
    if persona_count < 2 or persona_count % 2:
        raise ValueError("persona_count must be an even integer of at least 2")
    rng = random.Random(seed)
    agents = []
    for index in range(persona_count):
        pair_number = index // 2 + 1
        turn = index % 2
        agents.append(
            Agent(
                name=f"Person {index + 1:02d}",
                traits={
                    "generosity": round(rng.uniform(-1, 1), 2),
                    "inequity_aversion": round(rng.uniform(-1, 1), 2),
                    # Operational metadata is omitted by TRAITS_TEMPLATE.
                    "pair_id": f"pair-{pair_number}",
                    "turn": turn,
                    "role": "proposer" if turn == 0 else "responder",
                },
            )
        )
    return AgentList(agents, traits_presentation_template=TRAITS_TEMPLATE)


def survey(state):
    offer = QuestionNumerical(
        question_name="offer",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }} in a $100 ultimatum "
            "game. Current game: {{ shared_state.game }}. "
            "Choose the dollars offered to the responder."
        ),
        min_value=0,
        max_value=100,
    )
    decision = QuestionMultipleChoice(
        question_name="decision",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }} in a $100 ultimatum "
            "Current game: {{ shared_state.game }}. Accept or reject the recorded "
            "offer based on your preference."
        ),
        question_options=["accept", "reject"],
    )
    result = Survey(
        [offer, state.game.bind("offer", offer), decision, state.game.bind("respond", decision)]
    )
    result.add_skip_rule("offer", "'{{ agent.role }}' != 'proposer'")
    result.add_skip_rule("decision", "'{{ agent.role }}' != 'responder'")
    return result


def run_simulation(
    log_path: str | Path = "economic-game-ultimatum.jsonl",
    model_name="gemini-2.5-flash",
    persona_count: int = 50,
    seed: int = 20260828,
    max_concurrency: int = 10,
):
    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(log_path),
        game=ultimatum_game(stake=100),
    )
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=GroupStopCondition("game", "terminal")
    )
    (
        survey(state)
        .by(players(persona_count, seed))
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
            max_concurrency=max_concurrency,
        )
    )
    return state


def read_games(source: SharedState | str | Path):
    """Read analysis-ready game records through SharedState's public read API."""
    state = (
        source
        if isinstance(source, SharedState)
        else SharedState("dashboard", FileStateStore(source), game=ultimatum_game())
    )
    events_by_scope = {scope: [] for scope in state.scopes()}
    for event in state.history(target="game"):
        events_by_scope[event.scope].append(event)
    games = []
    for record in state.records(target="game"):
        proposer = record.get("proposer")
        responder = record.get("responder")
        payoffs = record.get("payoffs") or {}
        decision = record.get("decision")
        games.append(
            record
            | {
                "pair_id": record["scope"],
                "events": events_by_scope[record["scope"]],
                "proposer_payoff": payoffs.get(proposer, 0),
                "responder_payoff": payoffs.get(responder, 0),
                "status": (
                    "Accepted"
                    if decision == "accept"
                    else "Rejected"
                    if decision == "reject"
                    else "Incomplete"
                ),
            }
        )
    return sorted(games, key=lambda game: int(game["pair_id"].split("-")[-1]))


def render_dashboard(
    log_path: str | Path = "economic-game-ultimatum.jsonl",
    output_path: str | Path = "economic-game-ultimatum-dashboard.html",
    model_name: str = "gemini-2.5-flash",
    persona_count: int = 50,
    seed: int = 20260828,
):
    """Create a dependency-free HTML dashboard from a shared-state event log."""
    games = read_games(log_path)
    if not games:
        raise ValueError(f"No ultimatum-game events found in {log_path}")

    def esc(value):
        return html.escape(str(value))

    def trait_label(value):
        return f"{value:+.2f}" if isinstance(value, (int, float)) else "unknown"

    accepted = sum(game["status"] == "Accepted" for game in games)
    average_offer = sum(game.get("offer", 0) for game in games) / len(games)
    player_details = {agent.name: agent.traits for agent in players(persona_count, seed)}
    cards = []
    for index, game in enumerate(games, 1):
        proposer = game.get("proposer", f"P{index}")
        responder = game.get("responder", f"R{index}")
        offer = game.get("offer", 0)
        proposer_share = game["proposer_payoff"]
        responder_share = game["responder_payoff"]
        proposer_traits = player_details.get(proposer, {})
        responder_traits = player_details.get(responder, {})
        proposer_pref = f"generosity {trait_label(proposer_traits.get('generosity'))} · inequity aversion {trait_label(proposer_traits.get('inequity_aversion'))}"
        responder_pref = f"generosity {trait_label(responder_traits.get('generosity'))} · inequity aversion {trait_label(responder_traits.get('inequity_aversion'))}"
        event_times = [event.timestamp for event in game["events"]]
        timing = " → ".join(ts.strftime("%H:%M:%S UTC") for ts in event_times[:2])
        cards.append(f"""
        <article class="game-card">
          <div class="game-head"><div><span class="eyebrow">Table {index}</span><h2>{esc(game['pair_id'])}</h2></div><span class="status {game['status'].lower()}">{esc(game['status'])}</span></div>
          <div class="chat">
            <div class="message proposer"><div class="avatar">{esc(proposer)}</div><div class="bubble"><div class="speaker">{esc(proposer)} · proposer</div><p>I offer you <strong>${offer}</strong> from the $100 pot.</p><small>{esc(proposer_pref)}</small></div></div>
            <div class="message responder"><div class="bubble"><div class="speaker">{esc(responder)} · responder</div><p>I <strong>{esc(game.get('decision', 'have not responded'))}</strong> the offer.</p><small>{esc(responder_pref)}</small></div><div class="avatar">{esc(responder)}</div></div>
          </div>
          <div class="split" aria-label="Payoff split"><div class="p-share" style="width:{proposer_share}%"><span>${proposer_share}</span></div><div class="r-share" style="width:{responder_share}%"><span>${responder_share}</span></div></div>
          <div class="legend"><span><i class="dot p"></i>{esc(proposer)} payoff</span><span><i class="dot r"></i>{esc(responder)} payoff</span><span>{esc(timing)}</span></div>
        </article>""")

    generated = datetime.now().astimezone().strftime("%B %d, %Y at %H:%M %Z")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ultimatum Game · Run Dashboard</title>
<style>
:root{{--ink:#17211c;--muted:#66736b;--paper:#f4f0e7;--card:#fffdf7;--green:#2d6a4f;--lime:#b7d36b;--orange:#e88355;--line:#dcd5c7}}
*{{box-sizing:border-box}} body{{margin:0;color:var(--ink);background:var(--paper);font-family:Inter,ui-sans-serif,system-ui,sans-serif}} body:before{{content:"";position:fixed;inset:0;pointer-events:none;opacity:.18;background-image:radial-gradient(#65776a 1px,transparent 1px);background-size:24px 24px}}
header,main,footer{{position:relative;max-width:1100px;margin:auto}} header{{padding:68px 24px 34px}} .kicker,.eyebrow{{text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:800;color:var(--green)}} h1{{font-family:Georgia,serif;font-size:clamp(2.5rem,7vw,5.4rem);line-height:.92;max-width:850px;margin:.18em 0}} .lede{{max-width:680px;color:var(--muted);font-size:1.08rem;line-height:1.6}}
.scoreboard{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:30px}} .metric{{background:var(--ink);color:white;padding:20px;border-radius:18px}} .metric strong{{display:block;font:700 2rem Georgia,serif;color:var(--lime)}} .metric span{{color:#c9d0cb;font-size:.8rem}}
main{{padding:10px 24px 70px;display:grid;gap:22px}} .game-card{{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:24px;box-shadow:0 14px 40px #50605212}} .game-head{{display:flex;justify-content:space-between;align-items:start}} h2{{font:700 1.8rem Georgia,serif;margin:.2rem 0}} .status{{padding:7px 12px;border-radius:99px;background:#eee;font-size:.78rem;font-weight:800}} .status.accepted{{background:#dcebc8;color:#315b29}} .status.rejected{{background:#f7d8cb;color:#823f28}}
.chat{{margin:24px 0;display:grid;gap:16px}} .message{{display:flex;gap:12px;align-items:end}} .message.responder{{justify-content:flex-end}} .avatar{{width:48px;height:48px;flex:0 0 48px;border-radius:50%;display:grid;place-items:center;background:var(--green);color:white;font-weight:900}} .responder .avatar{{background:var(--orange)}} .bubble{{max-width:76%;background:#eef0e6;padding:14px 16px;border-radius:18px 18px 18px 4px}} .responder .bubble{{background:#f8e3d8;border-radius:18px 18px 4px 18px}} .speaker{{font-size:.75rem;font-weight:800;color:var(--muted)}} .bubble p{{font-family:Georgia,serif;font-size:1.2rem;margin:.35rem 0}} .bubble small{{color:var(--muted)}}
.split{{display:flex;height:48px;border-radius:14px;overflow:hidden;background:#ddd}} .split div{{display:flex;align-items:center;justify-content:center;min-width:0;font-weight:900;transition:width .4s}} .p-share{{background:var(--green);color:white}} .r-share{{background:var(--lime)}} .legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:.74rem;color:var(--muted)}} .legend span:last-child{{margin-left:auto}} .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}} .dot.p{{background:var(--green)}} .dot.r{{background:var(--lime)}} footer{{padding:0 24px 40px;color:var(--muted);font-size:.75rem}}
@media(max-width:620px){{.scoreboard{{grid-template-columns:1fr}} header{{padding-top:42px}} .legend span:last-child{{width:100%;margin:0}}}}
</style></head><body>
<header><div class="kicker">EDSL · Shared-state field notes</div><h1>{len(games)} offers.<br>{len(games)} decisions.</h1><p class="lede">A visual replay of {persona_count} random personas in {len(games)} parallel $100 ultimatum games. Each proposer chose a split; each responder saw the committed offer before deciding.</p>
<div class="scoreboard"><div class="metric"><strong>{len(games)}</strong><span>games completed</span></div><div class="metric"><strong>{accepted}/{len(games)}</strong><span>offers accepted</span></div><div class="metric"><strong>${average_offer:.0f}</strong><span>average responder offer</span></div></div></header>
<main>{''.join(cards)}</main><footer>Rendered {esc(generated)} from <code>{esc(Path(log_path).name)}</code> · model: {esc(model_name)} · the event log remains the source of truth.</footer>
</body></html>"""
    output = Path(output_path)
    output.write_text(document, encoding="utf-8")
    return output


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemini-2.5-flash", help="EDSL model name")
    parser.add_argument("--log", type=Path, default=Path("economic-game-ultimatum.jsonl"))
    parser.add_argument("--dashboard", type=Path, default=Path("economic-game-ultimatum-dashboard.html"))
    parser.add_argument("--personas", type=int, default=50, help="even number of personas (default: 50)")
    parser.add_argument("--seed", type=int, default=20260828, help="random seed for reproducible traits")
    parser.add_argument("--max-concurrency", type=int, default=10, help="maximum simultaneous interviews")
    parser.add_argument("--render-only", action="store_true", help="render the existing log without model calls")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.render_only:
        if args.log.exists():
            raise SystemExit(
                f"Refusing to append to existing log {args.log}. Move it or choose a new --log path."
            )
        result = run_simulation(args.log, args.model, args.personas, args.seed, args.max_concurrency)
        for pair_id in (f"pair-{number}" for number in range(1, args.personas // 2 + 1)):
            print(result.render_markdown(scope=pair_id), "\n")
    dashboard = render_dashboard(args.log, args.dashboard, args.model, args.personas, args.seed)
    print(f"Dashboard: {dashboard.resolve()}")
