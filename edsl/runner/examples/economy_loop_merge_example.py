"""Dynamic Loop & Merge example: an investor-sentiment survey about the economy.

This is a self-contained, offline demo. It runs on the canned ``test`` model
(no API keys, no network, fully deterministic), so it always exercises all
three per-iteration navigation paths.

The respondent first names the economic sectors they follow. For EACH sector
named -- unknown until runtime -- the survey loops a small block of follow-up
questions, using per-iteration ``skip_when`` / ``jump_when`` rules:

  Block per sector:  outlook -> concern -> allocation
    - outlook    (bullish / neutral / bearish)  -- always asked
    - concern    -- SKIP when bullish on this sector, or a high-risk investor
                    overall (references an OUTER answer by its real name)
    - allocation -- reached normally, BUT if outlook is 'bearish' we JUMP to
                    NEXT_ITEM right after `outlook`, skipping the rest of the
                    block for that sector.

So each sector takes a different path:
    bullish  -> outlook, (skip concern), allocation
    neutral  -> outlook, concern, allocation
    bearish  -> outlook, (jump to next item: skip concern AND allocation)

Run it:  python -m edsl.runner.examples.economy_loop_merge_example
"""

from edsl import (
    QuestionList,
    QuestionMultipleChoice,
    QuestionFreeText,
    QuestionNumerical,
    Survey,
    Model,
)

# --- Outer (regular) survey questions ---------------------------------------
risk_tolerance = QuestionMultipleChoice(
    question_name="risk_tolerance",
    question_text="Overall, how would you describe your risk tolerance?",
    question_options=["low", "medium", "high"],
)

sectors = QuestionList(
    question_name="sectors",
    question_text="Which sectors of the economy do you actively follow?",
)

# --- Loop-block questions (NOT added to the survey directly) -----------------
outlook = QuestionMultipleChoice(
    question_name="outlook",
    question_text="What is your 12-month outlook on the {{ sector }} sector?",
    question_options=["bullish", "neutral", "bearish"],
    # After answering outlook: if bearish, skip the rest of this sector's block.
).jump_when("{{ outlook.answer }} == 'bearish'", to=QuestionMultipleChoice.NEXT_ITEM)

concern = QuestionFreeText(
    question_name="concern",
    question_text="What is your single biggest concern about {{ sector }}?",
    # Skip for sectors the investor is bullish on, or if they are high-risk
    # overall (an OUTER answer referenced by its real name).
).skip_when(
    "{{ outlook.answer }} == 'bullish' or {{ risk_tolerance.answer }} == 'high'"
)

allocation = QuestionNumerical(
    question_name="allocation",
    question_text="What percent of your portfolio would you allocate to {{ sector }}?",
)

# --- Assemble: two outer questions + a dynamic loop over `sectors` -----------
survey = Survey([risk_tolerance, sectors]).loop_over(
    "sectors",
    ask=[outlook, concern, allocation],
    item="sector",
)

# --- Canned answers so it runs offline on the `test` model ------------------
# Injected question names are mangled as <base>_<source>_<iteration>.
canned = {
    "risk_tolerance": "medium",
    "sectors": ["Technology", "Energy", "Real Estate"],
    # Technology (iter 0): bullish -> concern skipped, allocation asked
    "outlook_sectors_0": "bullish",
    "allocation_sectors_0": 25,
    # Energy (iter 1): neutral -> full block
    "outlook_sectors_1": "neutral",
    "concern_sectors_1": "Volatile commodity prices squeezing margins.",
    "allocation_sectors_1": 15,
    # Real Estate (iter 2): bearish -> jump to next item; concern & allocation skipped
    "outlook_sectors_2": "bearish",
}


def main() -> None:
    results = survey.by(Model("test", canned_response=canned)).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    sector_names = results.select("sectors").to_list()[0]
    print("\nRisk tolerance:", results.select("risk_tolerance").to_list()[0])
    print("Sectors followed:", sector_names)
    print("\nPer-sector loop block:")
    print(f"{'sector':<13}{'outlook':<10}{'concern':<45}{'allocation'}")
    print("-" * 82)

    def get(base, i):
        """Injected <base>_sectors_<i> answer, or None if skipped/absent."""
        col = f"answer.{base}_sectors_{i}"
        if col not in results.columns:
            return None
        return results.select(f"{base}_sectors_{i}").to_list()[0]

    for i, sector in enumerate(sector_names):
        outlook_v = get("outlook", i)
        concern_v = get("concern", i)
        alloc_v = get("allocation", i)
        concern_disp = "— (skipped)" if concern_v is None else str(concern_v)
        alloc_disp = "— (skipped)" if alloc_v is None else f"{alloc_v}%"
        print(f"{sector:<13}{str(outlook_v):<10}{concern_disp:<45}{alloc_disp}")


if __name__ == "__main__":
    main()
