"""Prepare saved-state trade replays and separate, objectively scored setup probes."""

from __future__ import annotations

import json
import sqlite3

from edsl import Agent, ModelList, QuestionDict, Survey

from .experiment import KEYS, ROOT

OUTPUT = ROOT / "runs" / "comprehension-v1"
CASES = [
    (
        "original_ra_open",
        "paper-six-archetypes/RA-MC-BT-PC-NT-OC-s140926",
        "trader-01",
        1,
    ),
    ("speculative_ra_open", "speculative-v1/speculative-v1-s140926", "trader-01", 1),
    ("speculative_mc_open", "speculative-v1/speculative-v1-s140926", "trader-00", 1),
    ("speculative_pc_empty", "speculative-v1/speculative-v1-s140926", "trader-06", 20),
]
PROBES = {
    "cash_dollars": "What is your CURRENT cash balance in dollars?",
    "shares_owned": "How many shares do you CURRENTLY own?",
    "expected_dividend": "What is the expected dividend in dollars per share for ONE period?",
    "interest_on_100": "How much interest does $100 in cash earn in ONE period, in dollars?",
    "cash_only_max_buy_at_2": "At a limit price of $2 per share, how many whole shares can your CURRENT cash alone afford? Ignore available supply and any exchange quantity cap for this arithmetic question.",
    "max_sell_now": "What is the maximum number of shares you can legally sell NOW without short selling?",
    "expected_dividend_current_holdings": "If you make no trade, what is your expected total dividend payment this period, in dollars?",
    "expected_cash_after_income": "If you make no trade, what is your expected cash balance after this period's interest and dividend income, BEFORE any terminal redemption? Round the interest payment to cents before adding expected dividends.",
    "discounted_share_value": "Ignoring speculative resale opportunities, what is the present expected value in dollars of ONE share's remaining dividends plus terminal redemption, discounting each future payment at the 5% per-period cash return?",
    "final_period_expected_share_payout": "For ONE share held through the final period, what is the expected total of that final period's dividend and redemption, in dollars, measured at period end? Exclude earlier dividends.",
    "no_trade_is_new_price": "If nobody trades in a period, does the record contain a new observed transaction price for that period? Answer 1 for yes or 0 for no.",
    "guaranteed_buyer_above_redemption": "Do the rules guarantee that another trader will buy your share above the terminal redemption amount? Answer 1 for yes or 0 for no.",
    "period_22_still_trades": "Does period 22 fall within this 30-period market's trading horizon? Answer 1 for yes or 0 for no.",
}
INTEGER_KEYS = {
    "shares_owned",
    "cash_only_max_buy_at_2",
    "max_sell_now",
    "no_trade_is_new_price",
    "guaranteed_buyer_above_redemption",
    "period_22_still_trades",
}


def expected_answers(view):
    account = view["your_account"]
    cash, shares = account["cash_cents"], account["shares"]
    periods_remaining = 31 - view["period"]
    # Independent discounted-cash-flow computation; do not send answers to models.
    pv = (
        sum(0.7 / 1.05**t for t in range(1, periods_remaining + 1))
        + 14 / 1.05**periods_remaining
    )
    return {
        "cash_dollars": cash / 100,
        "shares_owned": shares,
        "expected_dividend": 0.7,
        "interest_on_100": 5,
        "cash_only_max_buy_at_2": cash // 200,
        "max_sell_now": shares,
        "expected_dividend_current_holdings": round(shares * 0.7, 2),
        "expected_cash_after_income": round(
            (cash + (cash * 5 + 50) // 100) / 100 + shares * 0.7, 2
        ),
        "discounted_share_value": round(pv, 8),
        "final_period_expected_share_payout": 14.7,
        "no_trade_is_new_price": 0,
        "guaranteed_buyer_above_redemption": 0,
        "period_22_still_trades": 1,
    }


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    models = {
        mode: ModelList.from_dict(
            json.loads((OUTPUT / f"{mode}-models.json").read_text())
        )
        for mode in ["replay", "probe"]
    }
    manifest = []
    for case, directory, name, period in CASES:
        source = ROOT / "runs" / directory
        call = next(
            json.loads(line)
            for line in (source / "model-calls.jsonl").read_text().splitlines()
            if (json.loads(line)["participant"], json.loads(line)["step"])
            == (name, f"orders-{period}")
        )
        with sqlite3.connect(
            f"file:{source / 'shared-state.sqlite'}?mode=ro", uri=True
        ) as c:
            view = next(
                r["value"]
                for (payload,) in c.execute(
                    "SELECT payload FROM state_events WHERE kind='read'"
                )
                for r in [json.loads(payload)]
                if r["execution_id"] == call["work_item_id"]
            )
        agent = Agent.from_dict(call["result"]["agent"])
        original_text = call["result"]["question_to_attributes"]["decision"][
            "question_text"
        ]
        replay = QuestionDict(
            question_name="decision",
            question_text=original_text,
            answer_keys=KEYS,
            value_types=["float"] * 4 + ["str", "float", "int", "str"],
            include_comment=False,
        )
        # Separate interviews: no diagnostic answers or hints precede trade replays.
        context = (
            original_text.split("YOUR DECISION")[0]
            if "YOUR DECISION" in original_text
            else original_text.split("Forecast the market price now")[0]
        )
        probe_text = (
            "SETUP COMPREHENSION CHECK. This is a separate task; no trading order will be submitted. "
            "Report the objective rules and arithmetic, independently of your persona's trading preferences.\n\n"
            + context
            + "\n\nAnswer the following factual questions. All monetary answers are in dollars.\n"
            + "\n".join(f"{key}: {text}" for key, text in PROBES.items())
            + "\nexplanation: Briefly explain your valuation calculation and buying/selling limits."
        )
        probe = QuestionDict(
            question_name="comprehension",
            question_text=probe_text,
            answer_keys=[*PROBES, "explanation"],
            value_types=["int" if key in INTEGER_KEYS else "float" for key in PROBES]
            + ["str"],
            include_comment=False,
        )
        case_dir = OUTPUT / case
        case_dir.mkdir(exist_ok=True)
        source_evidence = {
            "case": case,
            "source_directory": str(source),
            "source_call": call,
            "private_view": view,
            "answer_key": expected_answers(view),
        }
        (case_dir / "source.json").write_text(
            json.dumps(source_evidence, indent=2) + "\n"
        )
        for mode, question in [("replay", replay), ("probe", probe)]:
            job = Survey([question]).by(agent).by(models[mode])
            path = case_dir / f"{mode}-jobs.ep"
            if path.exists():
                raise FileExistsError(path)
            job.save(str(path))
            manifest.append(
                {
                    "case": case,
                    "mode": mode,
                    "job": str(path),
                    "result": str(case_dir / f"{mode}-results.ep"),
                    "expected_rows": 6,
                }
            )
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "ok",
                "data": {
                    "jobs": len(manifest),
                    "model_responses": 48,
                    "manifest": str(OUTPUT / "manifest.json"),
                },
                "warnings": [],
            }
        )
    )


if __name__ == "__main__":
    build()
