"""Score explicit setup questions and inspect exact saved-state trade replays."""

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from edsl import Results

from .comprehension import INTEGER_KEYS, OUTPUT, PROBES
from .experiment import ROOT
from .full_report import table


def score_value(key, actual, expected):
    if not isinstance(actual, (int, float)):
        return False
    tolerance = (
        0 if key in INTEGER_KEYS else 0.02 if key == "discounted_share_value" else 0.011
    )
    return abs(actual - expected) <= tolerance


def build():
    output = ROOT / "comprehension-report"
    output.mkdir(exist_ok=True)
    rows, grades, calls, replay_rows = [], [], [], []
    evidence = {}
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    for job in manifest:
        source = json.loads((Path(job["job"]).parent / "source.json").read_text())
        evidence[job["case"]] = source
        results = Results.load(job["result"])
        assert len(results) == job["expected_rows"], "Missing model responses"
        for result in results:
            data = result.to_dict()
            question = "decision" if job["mode"] == "replay" else "comprehension"
            answer = data["answer"][question]
            raw = data["raw_model_response"]
            response = raw[f"{question}_raw_model_response"]
            finish = response["choices"][0]["finish_reason"]
            assert finish == "stop", f"Incomplete response: {finish}"
            row = {
                "case": job["case"],
                "mode": job["mode"],
                "model": result.model.model,
                "iteration": data["iteration"],
                "answer": answer,
                "served_model": response.get("model"),
                "finish_reason": finish,
                "usage": response.get("usage"),
                "recorded_cost": raw.get(f"{question}_cost", 0) or 0,
            }
            calls.append({**row, "result": data})
            if job["mode"] == "probe":
                tests = {
                    key: score_value(key, answer.get(key), expected)
                    for key, expected in source["answer_key"].items()
                }
                row.update(
                    passed=sum(tests.values()),
                    total=len(tests),
                    all_correct=all(tests.values()),
                )
                for key, correct in tests.items():
                    grades.append(
                        {
                            "case": job["case"],
                            "model": result.model.model,
                            "iteration": data["iteration"],
                            "key": key,
                            "expected": source["answer_key"][key],
                            "actual": answer.get(key),
                            "correct": correct,
                        }
                    )
            else:
                for key in ["system_prompt", "user_prompt"]:
                    assert (
                        data["prompt"][f"decision_{key}"]["text"]
                        == source["source_call"]["result"]["prompt"][f"decision_{key}"][
                            "text"
                        ]
                    )
                account = source["private_view"]["your_account"]
                side, qty, price = answer["side"], answer["quantity"], answer["price"]
                oversell = side == "sell" and qty > account["shares"]
                overspend = (
                    side == "buy" and qty * round(price * 100) > account["cash_cents"]
                )
                replay_rows.append(
                    {
                        "case": job["case"],
                        "model": result.model.model,
                        "iteration": data["iteration"],
                        **answer,
                        "cash": account["cash_cents"] / 100,
                        "shares": account["shares"],
                        "oversells": oversell,
                        "overspends_at_limit": overspend,
                    }
                )
            rows.append(row)
    assert len(rows) == 48 and len(grades) == 312
    models = sorted({r["model"] for r in rows})
    summaries = []
    for model in models:
        probes = [r for r in rows if r["model"] == model and r["mode"] == "probe"]
        replays = [r for r in replay_rows if r["model"] == model]
        unanchored = [
            r
            for r in grades
            if r["model"] == model
            and r["case"] != "original_ra_open"
            and r["key"] == "discounted_share_value"
        ]
        summaries.append(
            {
                "model": model,
                "correct_items": sum(r["passed"] for r in probes),
                "total_items": sum(r["total"] for r in probes),
                "perfect_probes": sum(r["all_correct"] for r in probes),
                "probe_count": len(probes),
                "unanchored_valuation_correct": sum(r["correct"] for r in unanchored),
                "unanchored_valuation_total": len(unanchored),
                "overselling_replays": sum(r["oversells"] for r in replays),
                "overspending_replays": sum(r["overspends_at_limit"] for r in replays),
                "replay_count": len(replays),
                "recorded_cost": sum(
                    r["recorded_cost"] for r in rows if r["model"] == model
                ),
            }
        )
    summary = {
        "responses": len(rows),
        "graded_items": len(grades),
        "models": summaries,
        "all_replay_prompts_match": True,
        "all_finish_reasons_stop": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "responses.json").write_text(json.dumps(calls, indent=2) + "\n")
    for name, records in [("item-scores", grades), ("trade-replays", replay_rows)]:
        with (output / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    summary_table = table(
        [
            "Model",
            "Correct factual answers",
            "Perfect comprehension responses",
            "Derived $14 without supplied value",
            "Overselling trade replays",
            "Overspending trade replays",
        ],
        [
            [
                s["model"],
                f"{s['correct_items']}/{s['total_items']}",
                f"{s['perfect_probes']}/{s['probe_count']}",
                f"{s['unanchored_valuation_correct']}/{s['unanchored_valuation_total']}",
                f"{s['overselling_replays']}/{s['replay_count']}",
                f"{s['overspending_replays']}/{s['replay_count']}",
            ]
            for s in summaries
        ],
    )
    groups = defaultdict(list)
    for r in grades:
        groups[r["key"], r["model"]].append(r["correct"])
    item_table = table(
        ["Question", "Expected", *models],
        [
            [
                PROBES[key],
                "Depends on account"
                if key
                in {
                    "cash_dollars",
                    "shares_owned",
                    "cash_only_max_buy_at_2",
                    "max_sell_now",
                    "expected_dividend_current_holdings",
                    "expected_cash_after_income",
                }
                else evidence["speculative_ra_open"]["answer_key"][key],
                *[f"{sum(groups[key, m])}/{len(groups[key, m])}" for m in models],
            ]
            for key in PROBES
        ],
    )
    details = []
    for case, source in evidence.items():
        original = source["source_call"]["result"]["answer"]["decision"]
        private = source["private_view"]["your_account"]
        text = f"<section><h2>{html.escape(case)}</h2><p>Cash ${private['cash_cents'] / 100:.2f}; shares {private['shares']}; period {source['private_view']['period']}.</p><h3>Original response</h3><pre>{html.escape(json.dumps(original, indent=2))}</pre>"
        text += "<h3>Fresh trade replays</h3>" + table(
            [
                "Model",
                "Repeat",
                "Side",
                "Limit",
                "Qty",
                "Forecast now",
                "Oversells",
                "Rationale",
            ],
            [
                [
                    r["model"],
                    r["iteration"],
                    r["side"],
                    r["price"],
                    r["quantity"],
                    r["forecast_0"],
                    r["oversells"],
                    r["rationale"],
                ]
                for r in replay_rows
                if r["case"] == case
            ],
        )
        for mode in ["replay", "probe"]:
            subset = [c for c in calls if c["case"] == case and c["mode"] == mode]
            prompt = subset[0]["result"]["prompt"]
            question = "decision" if mode == "replay" else "comprehension"
            text += f"<details><summary>Full {mode} prompts and all six responses</summary><h4>System</h4><pre>{html.escape(prompt[question + '_system_prompt']['text'])}</pre><h4>User</h4><pre>{html.escape(prompt[question + '_user_prompt']['text'])}</pre>"
            for c in subset:
                text += f"<h4>{c['model']} · repeat {c['iteration']}</h4><pre>{html.escape(json.dumps(c['answer'], indent=2))}</pre>"
            text += "</details>"
        details.append(text + "</section>")
    css = (ROOT / "report_assets" / "full_report.css").read_text()
    report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Do the traders understand the market?</title><style>{css} pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style><main>
<section class="hero"><p class="eyebrow">EDSL saved-state diagnostic</p><h1>Do the traders understand the setup?</h1><p class="dek">GPT-4o-mini versus GPT-5 mini: 24 exact trade replays and 24 separate comprehension responses.</p></section>
<section><h2>Results</h2>{summary_table}<p>All 48 responses completed without token truncation. Every replay's system and user prompt matched its original recorded prompt exactly. Each model answered three times per case. These are selected diagnostic cases, not a representative estimate of overall model performance.</p>{item_table}</section>
<section><h2>Concrete failure patterns</h2><ul><li><strong>Dividend versus share value.</strong> On the unanchored Rational Arbitrageur trade replay, GPT-4o-mini bid $0.70 in all three repeats, grounding its quote in one-period dividends. GPT-5 mini independently calculated the $14 discounted value in all three repeats and held. A low bid alone is permitted; the quoted explanations expose the valuation mismatch.</li><li><strong>Submitted order versus executed purchase.</strong> In the period-20 Precommitter case, the earlier period-18 buy order requested ten shares but filled zero. The current account still held zero shares. GPT-4o-mini nevertheless offered to sell ten shares in all three replays; one explanation explicitly claimed a previous purchase. This suggests it carried forward its own earlier narrative instead of the actual fill/account records. GPT-5 mini submitted affordable buys in all three replays.</li><li><strong>Knowledge versus application.</strong> When asked explicitly, both models correctly reported the zero-share account and zero legal selling capacity in all three repetitions of that case. The old model's trade errors therefore persist despite answering the direct inventory questions correctly.</li><li><strong>Cents versus dollars.</strong> For the original prompt containing <code>cash_cents: 10000</code>, GPT-4o-mini correctly reported $100 cash but answered that it could afford 5,000 shares at $2 in all three probes. GPT-5 mini answered 50. The newer dollar-display cases did not show this affordability error.</li></ul><p>GPT-5 mini was not perfect: one probe evaluated the correct discounted-value formula as $14.02862 rather than $14, failing the predeclared two-cent tolerance. Its late Precommitter responses also sometimes claimed a concrete previously stated schedule that was not in the supplied history. Better arithmetic and inventory handling do not establish faithful persona memory.</p></section>
<section><h2>What the check distinguishes</h2><p>Explicit comprehension questions ask for objective arithmetic and rules. Passing them does not demonstrate that the same model spontaneously applies that knowledge while trading. A low bid can be a valid strategy, so we do not score low bids as comprehension failures. An order that sells more shares than the trader owns violates the submitted-order constraint, even though the exchange later caps it.</p><p>The original anchored condition already supplies $14. The three speculative conditions require deriving it. Valuation uses the expected remaining dividends plus redemption, discounted at the cash return: V = sum(0.70 / 1.05^t) + 14 / 1.05^T = $14. One-period expected dividend is $0.70; final-period expected dividend plus redemption is $14.70. $100 can afford 50 shares at $2 on cash arithmetic alone; this question explicitly excludes market supply and exchange caps.</p><p>Both models receive the same prompts within each task. GPT-4o-mini uses temperature 0.7 and 650 tokens for replays, 1800 for probes. GPT-5 mini uses medium reasoning, temperature 1, and an 8000-token completion allowance including reasoning. These are usable configurations, not identical sampling settings. Current support and reasoning-token handling were checked against <a href="https://developers.openai.com/api/docs/models/gpt-5-mini">official model documentation</a> and <a href="https://developers.openai.com/api/docs/guides/reasoning">reasoning guidance</a>.</p><p><a href="../COMPREHENSION_CHECK.md">Design and scoring rules fixed before calls</a>. No comprehension feedback preceded any trade replay. No market orders were settled, and historical simulation artifacts were preserved.</p></section>
{"".join(details)}
<section><h2>Downloads</h2><div class="downloads"><a href="summary.json">Summary</a><a href="item-scores.csv">Every scored item</a><a href="trade-replays.csv">Every replay and rationale</a><a href="responses.json">All raw Results and prompts</a></div><p>Durable Jobs and Results packages are in examples/asset_market/runs/comprehension-v1/.</p></section></main></html>"""
    (output / "index.html").write_text(report)
    print(
        json.dumps(
            {
                "status": "ok",
                "data": {"report": str(output / "index.html"), **summary},
                "warnings": [],
            }
        )
    )


if __name__ == "__main__":
    build()
