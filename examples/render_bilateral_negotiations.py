"""Render the persisted bilateral-negotiation state as a standalone HTML page."""

from html import escape
from pathlib import Path

from shared_state_bilateral_negotiation import build_negotiation


def render_report(
    log_path: str | Path = "bilateral-negotiations.jsonl",
    output_path: str | Path = "bilateral-negotiations.html",
) -> Path:
    _, shared_state = build_negotiation(log_path)
    cards = []
    for pair_id in ("p1", "p2", "p3"):
        snapshot = shared_state.read(scope=pair_id)
        view = snapshot.state["negotiation"]
        rows = []
        for turn in view["turns"]:
            action_class = turn["action"].replace(" ", "-")
            rows.append(
                "<tr>"
                f"<td>{turn['turn']}</td>"
                f"<td>{turn['round']}</td>"
                f"<td><strong>{escape(turn['speaker'])}</strong>"
                f"<span class='role'>{escape(turn['role'])}</span></td>"
                f"<td><span class='action {action_class}'>{escape(turn['action'])}</span></td>"
                f"<td class='amount'>${turn['amount']:g}</td>"
                f"<td>{escape(turn['message'])}</td>"
                "</tr>"
            )
        agreement = view["agreement"]
        outcome = (
            f"<span class='deal'>Agreement at ${agreement:g}</span>"
            if agreement is not None
            else "<span class='no-deal'>No agreement</span>"
        )
        cards.append(
            f"""
            <section class="pair-card">
              <header><div><p class="eyebrow">Negotiation pair</p><h2>{pair_id.upper()}</h2></div>{outcome}</header>
              <div class="table-wrap"><table>
                <thead><tr><th>Turn</th><th>Round</th><th>Speaker</th><th>Action</th><th>Amount</th><th>Message</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
              </table></div>
            </section>"""
        )

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilateral Negotiations</title>
<style>
:root{{--ink:#17202a;--muted:#68717b;--paper:#f6f3ec;--card:#fff;--line:#ded9ce;--teal:#176b68;--gold:#b77a22;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,sans-serif}}
main{{max-width:1280px;margin:auto;padding:52px 28px 80px}} .masthead{{margin-bottom:32px}}
.eyebrow{{margin:0 0 5px;color:var(--teal);font-size:12px;font-weight:800;letter-spacing:.13em;text-transform:uppercase}}
h1{{font:700 clamp(34px,5vw,62px)/1.02 Georgia,serif;margin:0 0 14px;letter-spacing:-.035em}} .dek{{max-width:760px;color:var(--muted);font-size:17px}}
.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}} .pill{{background:#e6efe9;border:1px solid #cadbd0;border-radius:99px;padding:7px 12px;font-weight:650}}
.pair-card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 10px 30px #3e342316;margin:22px 0;overflow:hidden}}
.pair-card>header{{display:flex;align-items:center;justify-content:space-between;padding:22px 24px;border-bottom:1px solid var(--line)}} h2{{font:700 28px/1 Georgia,serif;margin:0}}
.deal,.no-deal{{border-radius:99px;padding:8px 13px;font-weight:800}} .deal{{color:#145c3c;background:#dff2e7}} .no-deal{{color:#873c32;background:#f7e4df}}
.table-wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;min-width:900px}} th{{color:var(--muted);font-size:11px;letter-spacing:.09em;text-align:left;text-transform:uppercase;background:#fbfaf7}}
th,td{{padding:13px 15px;border-bottom:1px solid #ece8df;vertical-align:top}} tbody tr:last-child td{{border-bottom:0}} tbody tr:hover{{background:#fcfaf4}}
.role{{display:block;color:var(--muted);font-size:12px;text-transform:capitalize}} .amount{{font-variant-numeric:tabular-nums;font-weight:750}}
.action{{display:inline-block;padding:3px 8px;border-radius:5px;background:#e9eef0;font-size:12px;font-weight:800;text-transform:uppercase}} .action.accept{{background:#dff2e7;color:#145c3c}} .action.offer{{background:#e7eef8;color:#315b8c}}
footer{{color:var(--muted);margin-top:25px;font-size:13px}} @media(max-width:600px){{main{{padding:32px 14px}}.pair-card>header{{padding:18px}}}}
</style></head><body><main>
<header class="masthead"><p class="eyebrow">EDSL shared state experiment</p><h1>Parallel bilateral negotiations</h1>
<p class="dek">Three buyer–seller pairs negotiated a used sailboat for five rounds. Pairs ran concurrently; turns remained serial within each pair, and each transcript lived in an isolated shared-state scope.</p>
<div class="summary"><span class="pill">3 independent pairs</span><span class="pill">5 rounds</span><span class="pill">30 total turns</span><span class="pill">Gemini 2.5 Flash</span></div></header>
{''.join(cards)}
<footer>Generated from <code>{escape(str(log_path))}</code>. Private reservation values were supplied to each agent but were not shown to its counterpart.</footer>
</main></body></html>"""
    output = Path(output_path)
    output.write_text(document, encoding="utf-8")
    return output.resolve()


if __name__ == "__main__":
    print(render_report())
