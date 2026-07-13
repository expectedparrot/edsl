"""End-to-end tests for dynamic Loop & Merge on the new runner.

All cases run on the canned ``test`` model (no API keys needed):

- static loop:  the loop set is known *before* the run via ``Question.loop()``,
  which name-mangles one question per scenario up front (ordinary static tasks).
- dynamic loop: the loop set is derived from an answer given mid-interview
  (``Survey.loop_over``); the runner injects one follow-up task per item.
- per-iteration skip: an ``ask`` question's ``skip_when`` rule skips that
  question for iterations where the condition is truthy.
- per-iteration jump: an ``ask`` question's ``jump_when`` rule jumps forward
  within the block (or to the next item), skipping the questions in between.
"""

import json
import warnings

import pytest

from edsl import (
    QuestionList,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
    Model,
)
from edsl.scenarios import ScenarioList


def _run(survey, canned):
    return survey.by(Model("test", canned_response=canned)).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )


def _val(results, name):
    """Return the single-row answer for ``name``, or the sentinel if the column
    is absent entirely (a fully-skipped question with no injected None column)."""
    if f"answer.{name}" not in results.columns:
        return "<missing>"
    return results.select(name).to_list()[0]


def test_static_loop_scenario_list():
    """Static loop: loop set known before the run via Question.loop(ScenarioList)."""
    q = QuestionFreeText(
        question_name="head_{{ dept }}",
        question_text="Who is the head of the {{ dept }} department?",
    )
    questions = q.loop(
        ScenarioList.from_list("dept", ["Engineering", "Sales", "Marketing"])
    )
    survey = Survey(questions)

    canned = {
        "head_Engineering": "Ada Lovelace",
        "head_Sales": "Grace Hopper",
        "head_Marketing": "Katherine Johnson",
    }
    results = _run(survey, canned)

    for name, want in canned.items():
        assert f"answer.{name}" in results.columns
        assert results.select(name).to_list()[0] == want


def test_static_loop_plain_dicts():
    """Static loop with a plain list of dicts instead of a ScenarioList."""
    q = QuestionFreeText(
        question_name="head_{{ dept }}",
        question_text="Who is the head of the {{ dept }} department?",
    )
    questions = q.loop(
        [{"dept": "Engineering"}, {"dept": "Sales"}, {"dept": "Marketing"}]
    )
    survey = Survey(questions)

    canned = {
        "head_Engineering": "Ada Lovelace",
        "head_Sales": "Grace Hopper",
        "head_Marketing": "Katherine Johnson",
    }
    results = _run(survey, canned)

    for name, want in canned.items():
        assert f"answer.{name}" in results.columns
        assert results.select(name).to_list()[0] == want


def test_dynamic_loop_merge():
    """Dynamic Loop & Merge: loop set derived from a mid-interview answer."""
    q_source = QuestionList(
        question_name="departments",
        question_text="List the departments in a company.",
    )
    q_follow = QuestionFreeText(
        question_name="head",
        question_text="Who is the head of the {{ item }} department?",
    )
    survey = Survey([q_source]).loop_over("departments", ask=q_follow)

    canned = {
        "departments": ["Engineering", "Sales", "Marketing"],
        "head_departments_0": "Ada Lovelace",
        "head_departments_1": "Grace Hopper",
        "head_departments_2": "Katherine Johnson",
    }
    results = _run(survey, canned)

    for name in (
        "head_departments_0",
        "head_departments_1",
        "head_departments_2",
    ):
        assert f"answer.{name}" in results.columns
    assert _val(results, "head_departments_0") == "Ada Lovelace"
    assert _val(results, "head_departments_1") == "Grace Hopper"
    assert _val(results, "head_departments_2") == "Katherine Johnson"


def test_dynamic_loop_merge_no_scenario():
    """Dynamic Loop & Merge with NO ScenarioList/Scenario at all."""
    src = QuestionList(question_name="colors", question_text="Name some colors.")
    follow = QuestionFreeText(
        question_name="why",
        question_text="Why do people like {{ item }}?",
    )
    survey = Survey([src]).loop_over("colors", ask=follow)

    canned = {
        "colors": ["red", "blue"],
        "why_colors_0": "It is warm.",
        "why_colors_1": "It is calm.",
    }
    results = _run(survey, canned)

    answer_cols = sorted(c for c in results.columns if c.startswith("answer."))
    assert answer_cols == ["answer.colors", "answer.why_colors_0", "answer.why_colors_1"]
    assert _val(results, "why_colors_0") == "It is warm."
    assert _val(results, "why_colors_1") == "It is calm."


def test_dynamic_per_iteration_skip():
    """Per-iteration skip logic inside a dynamic Loop & Merge block.

    Three chained ``ask`` questions per product:
      1. used_recently  -- no skip rule
      2. recent_exp      -- skip when {{ used_recently.answer }} == 'No'
                            (block-local reference to an earlier question)
      3. deep_dive       -- skip when {{ scenario.loop_index }} == 0
                            (scenario reference; also references outer source)

    With products = ["A", "B"] and used_recently = 'Yes' (iter 0) / 'No' (iter 1):
      - recent_exp runs in iter 0, is SKIPPED in iter 1 (block-local skip).
      - deep_dive  is SKIPPED in iter 0, runs in iter 1 (scenario skip).
    """
    src = QuestionList(question_name="products", question_text="List two products.")
    used_recently = QuestionFreeText(
        question_name="used_recently",
        question_text="Have you used {{ item }} recently?",
    )
    recent_exp = QuestionFreeText(
        question_name="recent_exp",
        question_text="Describe your recent experience with {{ item }}.",
    ).skip_when("{{ used_recently.answer }} == 'No'")
    deep_dive = QuestionFreeText(
        question_name="deep_dive",
        question_text="Tell me more about {{ item }}.",
    ).skip_when("{{ products.answer | length }} > 5 or {{ scenario.loop_index }} == 0")

    survey = Survey([src]).loop_over(
        "products", ask=[used_recently, recent_exp, deep_dive]
    )

    canned = {
        "products": ["A", "B"],
        "used_recently_products_0": "Yes",
        "used_recently_products_1": "No",
        "recent_exp_products_0": "Loved it",
        "recent_exp_products_1": "SHOULD NOT APPEAR",
        "deep_dive_products_0": "SHOULD NOT APPEAR",
        "deep_dive_products_1": "Tell me more",
    }
    results = _run(survey, canned)

    assert _val(results, "used_recently_products_0") == "Yes"
    assert _val(results, "used_recently_products_1") == "No"
    assert _val(results, "recent_exp_products_0") == "Loved it"
    assert _val(results, "recent_exp_products_1") is None  # skipped (block-local)
    assert _val(results, "deep_dive_products_0") is None  # skipped (loop_index==0)
    assert _val(results, "deep_dive_products_1") == "Tell me more"


def test_dynamic_per_iteration_jump():
    """Per-iteration JUMP logic inside a dynamic Loop & Merge block.

    Block: interested -> details -> wrap_up. ``interested`` carries two
    forward-jump rules:
      - answer == 'no'   -> jump to wrap_up   (skip details)
      - answer == 'stop' -> jump to NEXT_ITEM (skip details AND wrap_up)

    With items = ["A", "B", "C"] and interested = yes / no / stop:
      - A: no jump      -> details runs, wrap_up runs
      - B: jump wrap_up -> details SKIPPED, wrap_up runs
      - C: jump next    -> details SKIPPED, wrap_up SKIPPED
    """
    src = QuestionList(question_name="items", question_text="List items.")
    interested = (
        QuestionFreeText(
            question_name="interested",
            question_text="Interested in {{ item }}? (yes/no/stop)",
        )
        .jump_when("{{ interested.answer }} == 'no'", to="wrap_up")
        .jump_when(
            "{{ interested.answer }} == 'stop'",
            to=QuestionFreeText.NEXT_ITEM,
        )
    )
    details = QuestionFreeText(
        question_name="details",
        question_text="Give details about {{ item }}.",
    )
    wrap_up = QuestionFreeText(
        question_name="wrap_up",
        question_text="Any final word on {{ item }}?",
    )

    survey = Survey([src]).loop_over("items", ask=[interested, details, wrap_up])

    canned = {
        "items": ["A", "B", "C"],
        "interested_items_0": "yes",
        "interested_items_1": "no",
        "interested_items_2": "stop",
        "details_items_0": "Details for A",
        "details_items_1": "SHOULD NOT APPEAR",
        "details_items_2": "SHOULD NOT APPEAR",
        "wrap_up_items_0": "Wrap A",
        "wrap_up_items_1": "Wrap B",
        "wrap_up_items_2": "SHOULD NOT APPEAR",
    }
    results = _run(survey, canned)

    assert _val(results, "interested_items_0") == "yes"
    assert _val(results, "interested_items_1") == "no"
    assert _val(results, "interested_items_2") == "stop"
    assert _val(results, "details_items_0") == "Details for A"
    assert _val(results, "details_items_1") is None  # jumped over (-> wrap_up)
    assert _val(results, "details_items_2") is None  # jumped over (-> next_item)
    assert _val(results, "wrap_up_items_0") == "Wrap A"
    assert _val(results, "wrap_up_items_1") == "Wrap B"
    assert _val(results, "wrap_up_items_2") is None  # next_item skipped it


def test_dynamic_jump_invalid_target_raises():
    """A jump target outside the block fails loudly at submit time."""
    src = QuestionList(question_name="items", question_text="List.")
    q1 = QuestionFreeText(
        question_name="a", question_text="{{ item }}?"
    ).jump_when("True", to="outside_the_block")
    q2 = QuestionFreeText(question_name="b", question_text="{{ item }}?")
    survey = Survey([src]).loop_over("items", ask=[q1, q2])

    canned = {"items": ["x"], "a_items_0": "y", "b_items_0": "z"}
    with pytest.raises(ValueError, match="not a question in the same"):
        _run(survey, canned)


def _economy_survey():
    """The economy example survey: skip + jump rules over a dynamic loop."""
    risk_tolerance = QuestionMultipleChoice(
        question_name="risk_tolerance",
        question_text="How would you describe your risk tolerance?",
        question_options=["low", "medium", "high"],
    )
    sectors = QuestionList(
        question_name="sectors", question_text="Which sectors do you follow?"
    )
    outlook = QuestionMultipleChoice(
        question_name="outlook",
        question_text="Outlook on {{ sector }}?",
        question_options=["bullish", "neutral", "bearish"],
    ).jump_when("{{ outlook.answer }} == 'bearish'", to=QuestionMultipleChoice.NEXT_ITEM)
    concern = QuestionFreeText(
        question_name="concern",
        question_text="Biggest concern about {{ sector }}?",
    ).skip_when(
        "{{ outlook.answer }} == 'bullish' or {{ risk_tolerance.answer }} == 'high'"
    )
    allocation = QuestionNumerical(
        question_name="allocation", question_text="Allocate to {{ sector }}?"
    )
    return Survey([risk_tolerance, sectors]).loop_over(
        "sectors", ask=[outlook, concern, allocation], item="sector"
    )


_ECONOMY_CANNED = {
    "risk_tolerance": "medium",
    "sectors": ["Technology", "Energy", "Real Estate"],
    "outlook_sectors_0": "bullish",
    "allocation_sectors_0": 25,
    "outlook_sectors_1": "neutral",
    "concern_sectors_1": "Volatile commodity prices.",
    "allocation_sectors_1": 15,
    "outlook_sectors_2": "bearish",
}


def test_loop_merge_serializes_to_json():
    """The loop config (and its non-member template questions + skip/jump rules)
    must survive a to_dict/from_dict round-trip -- otherwise remote jobs, Coop
    hosting, and the survey builder silently lose the loop block."""
    survey = _economy_survey()

    # A full JSON round-trip, exactly like a remote job upload.
    d = json.loads(json.dumps(survey.to_dict()))
    assert "loop_merge" in d

    survey2 = Survey.from_dict(d)
    specs = getattr(survey2, "_loop_merge_specs", None)
    assert specs, "loop specs lost on round-trip"
    spec = specs[0]
    assert spec["source"] == "sectors"
    assert spec["item_key"] == "sector"
    assert len(spec["templates"]) == 3
    # skip/jump rules reattached to the reconstructed template questions
    assert spec["templates"][0]._loop_jump_rules == [
        ("{{ outlook.answer }} == 'bearish'", "next_item")
    ]
    assert spec["templates"][1]._loop_skip_rule == (
        "{{ outlook.answer }} == 'bullish' or {{ risk_tolerance.answer }} == 'high'"
    )

    # Equality holds across the round-trip.
    assert survey2 == survey


def test_loop_merge_round_trip_runs_identically():
    """A survey reconstructed from JSON runs with identical skip/jump behavior --
    proving remote execution (which round-trips the job) matches local."""

    def answers(s):
        results = _run(s, _ECONOMY_CANNED)
        return {
            c: results.select(c.split(".", 1)[1]).to_list()[0]
            for c in sorted(results.columns)
            if c.startswith("answer.")
        }

    survey = _economy_survey()
    survey2 = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))

    original = answers(survey)
    round_tripped = answers(survey2)
    assert original == round_tripped
    # sanity: the skip/jump actually fired (not a trivially-equal empty run)
    assert original["answer.concern_sectors_0"] is None  # skipped (bullish)
    assert original["answer.concern_sectors_2"] is None  # jumped over (bearish)
    assert original["answer.allocation_sectors_2"] is None  # jumped over
    assert original["answer.allocation_sectors_0"] == 25


def test_deprecated_aliases_still_work():
    """Old names (add_loop_merge / with_loop_skip / with_loop_jump / END_OF_LOOP)
    still function, forwarding to the new API, and emit DeprecationWarning."""
    src = QuestionList(question_name="items", question_text="List items.")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        gate = (
            QuestionFreeText(
                question_name="gate",
                question_text="Proceed with {{ loop_item }}? (yes/stop)",
            )
            .with_loop_jump(
                "{{ gate.answer }} == 'stop'", target=QuestionFreeText.END_OF_LOOP
            )
        )
        note = QuestionFreeText(
            question_name="note",
            question_text="Note on {{ loop_item }}.",
        ).with_loop_skip("{{ gate.answer }} == 'skip'")
        survey = Survey([src]).add_loop_merge(
            source="items", templates=[gate, note], item_key="loop_item"
        )

    categories = [w.category for w in caught]
    assert DeprecationWarning in categories

    canned = {
        "items": ["A", "B"],
        "gate_items_0": "yes",
        "gate_items_1": "stop",
        "note_items_0": "note A",
        "note_items_1": "SHOULD NOT APPEAR",
    }
    results = _run(survey, canned)

    assert _val(results, "gate_items_0") == "yes"
    assert _val(results, "note_items_0") == "note A"
    assert _val(results, "gate_items_1") == "stop"
    assert _val(results, "note_items_1") is None  # jumped past via NEXT_ITEM
