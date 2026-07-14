"""End-to-end tests for dynamic Loop & Merge.

All cases run on the canned ``test`` model (no API keys needed):

- static loop:  the loop set is known *before* the run via ``Question.loop()``,
  which name-mangles one question per scenario up front (ordinary static tasks).
- dynamic loop: the loop set is derived from an answer given mid-interview
  (``Survey.loop_over``). This is now expanded *statically at build time* into a
  plain survey: ``max_items`` copies of each ``ask`` question, each piping the
  i-th item via ``{{ <source>.answer[i] }}`` and carrying an overflow guard so
  iterations past the actual answer length are skipped. There is no runtime
  injection, so the survey runs identically on every runner.
- per-iteration skip: an ``ask`` question's ``skip_when`` rule becomes a native
  survey skip rule on each copy; the question is skipped where it is truthy.
- per-iteration jump: an ``ask`` question's ``jump_when`` rule becomes a native
  survey jump rule, jumping forward within the block (or to the next item).

Because loop conditions become native survey rules, their expressions are
subject to the ordinary rule validator (which reads bare Jinja-filter names
like ``length`` as unknown questions); use list operations instead.
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
        "head__loop0__departments": "Ada Lovelace",
        "head__loop1__departments": "Grace Hopper",
        "head__loop2__departments": "Katherine Johnson",
    }
    results = _run(survey, canned)

    for name in (
        "head__loop0__departments",
        "head__loop1__departments",
        "head__loop2__departments",
    ):
        assert f"answer.{name}" in results.columns
    assert _val(results, "head__loop0__departments") == "Ada Lovelace"
    assert _val(results, "head__loop1__departments") == "Grace Hopper"
    assert _val(results, "head__loop2__departments") == "Katherine Johnson"


def test_dynamic_loop_merge_no_scenario():
    """Dynamic Loop & Merge with NO ScenarioList/Scenario at all."""
    src = QuestionList(question_name="colors", question_text="Name some colors.")
    follow = QuestionFreeText(
        question_name="why",
        question_text="Why do people like {{ item }}?",
    )
    survey = Survey([src]).loop_over("colors", ask=follow, max_items=2)

    canned = {
        "colors": ["red", "blue"],
        "why__loop0__colors": "It is warm.",
        "why__loop1__colors": "It is calm.",
    }
    results = _run(survey, canned)

    answer_cols = sorted(c for c in results.columns if c.startswith("answer."))
    assert answer_cols == [
        "answer.colors",
        "answer.why__loop0__colors",
        "answer.why__loop1__colors",
    ]
    assert _val(results, "why__loop0__colors") == "It is warm."
    assert _val(results, "why__loop1__colors") == "It is calm."


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
    ).skip_when("{{ scenario.loop_index }} == 0")

    survey = Survey([src]).loop_over(
        "products", ask=[used_recently, recent_exp, deep_dive], max_items=2
    )

    canned = {
        "products": ["A", "B"],
        "used_recently__loop0__products": "Yes",
        "used_recently__loop1__products": "No",
        "recent_exp__loop0__products": "Loved it",
        "recent_exp__loop1__products": "SHOULD NOT APPEAR",
        "deep_dive__loop0__products": "SHOULD NOT APPEAR",
        "deep_dive__loop1__products": "Tell me more",
    }
    results = _run(survey, canned)

    assert _val(results, "used_recently__loop0__products") == "Yes"
    assert _val(results, "used_recently__loop1__products") == "No"
    assert _val(results, "recent_exp__loop0__products") == "Loved it"
    assert _val(results, "recent_exp__loop1__products") is None  # skipped (block-local)
    assert (
        _val(results, "deep_dive__loop0__products") is None
    )  # skipped (loop_index==0)
    assert _val(results, "deep_dive__loop1__products") == "Tell me more"


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

    survey = Survey([src]).loop_over(
        "items", ask=[interested, details, wrap_up], max_items=3
    )

    canned = {
        "items": ["A", "B", "C"],
        "interested__loop0__items": "yes",
        "interested__loop1__items": "no",
        "interested__loop2__items": "stop",
        "details__loop0__items": "Details for A",
        "details__loop1__items": "SHOULD NOT APPEAR",
        "details__loop2__items": "SHOULD NOT APPEAR",
        "wrap_up__loop0__items": "Wrap A",
        "wrap_up__loop1__items": "Wrap B",
        "wrap_up__loop2__items": "SHOULD NOT APPEAR",
    }
    results = _run(survey, canned)

    assert _val(results, "interested__loop0__items") == "yes"
    assert _val(results, "interested__loop1__items") == "no"
    assert _val(results, "interested__loop2__items") == "stop"
    assert _val(results, "details__loop0__items") == "Details for A"
    assert _val(results, "details__loop1__items") is None  # jumped over (-> wrap_up)
    assert _val(results, "details__loop2__items") is None  # jumped over (-> next_item)
    assert _val(results, "wrap_up__loop0__items") == "Wrap A"
    assert _val(results, "wrap_up__loop1__items") == "Wrap B"
    assert _val(results, "wrap_up__loop2__items") is None  # next_item skipped it


def test_dynamic_jump_invalid_target_raises():
    """A jump target outside the block fails loudly at build (expansion) time."""
    src = QuestionList(question_name="items", question_text="List.")
    q1 = QuestionFreeText(question_name="a", question_text="{{ item }}?").jump_when(
        "True", to="outside_the_block"
    )
    q2 = QuestionFreeText(question_name="b", question_text="{{ item }}?")

    from edsl.surveys.exceptions import SurveyCreationError

    with pytest.raises(SurveyCreationError, match="not a question in the same"):
        Survey([src]).loop_over("items", ask=[q1, q2])


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
    ).jump_when(
        "{{ outlook.answer }} == 'bearish'", to=QuestionMultipleChoice.NEXT_ITEM
    )
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
        "sectors", ask=[outlook, concern, allocation], item="sector", max_items=3
    )


_ECONOMY_CANNED = {
    "risk_tolerance": "medium",
    "sectors": ["Technology", "Energy", "Real Estate"],
    "outlook__loop0__sectors": "bullish",
    "allocation__loop0__sectors": 25,
    "outlook__loop1__sectors": "neutral",
    "concern__loop1__sectors": "Volatile commodity prices.",
    "allocation__loop1__sectors": 15,
    "outlook__loop2__sectors": "bearish",
}


def test_loop_merge_serializes_to_json():
    """After static expansion the loop is an ordinary survey: the expanded
    questions and their skip/jump rules must survive a to_dict/from_dict
    round-trip like any other survey (no special ``loop_merge`` block needed)."""
    survey = _economy_survey()

    # Static expansion => plain survey; no dynamic loop spec rides along.
    d = json.loads(json.dumps(survey.to_dict()))
    assert "loop_merge" not in d
    assert not getattr(survey, "_loop_merge_specs", None)

    # The per-item questions are real survey members (3 templates x 3 items),
    # named via the public loop naming scheme.
    for i in range(3):
        for base in ("outlook", "concern", "allocation"):
            assert (
                Survey.loop_question_name(base, "sectors", i) in survey.question_names
            )
    # The name marker parses back to its parts (what a consumer would detect on).
    assert Survey.parse_loop_question_name("outlook__loop1__sectors") == {
        "base": "outlook",
        "source": "sectors",
        "index": 1,
    }
    # Piping was rewritten to index the source answer.
    qm = survey.question_names_to_questions()
    assert (
        qm["outlook__loop1__sectors"].question_text
        == "Outlook on {{ sectors.answer[1] }}?"
    )

    # A full JSON round-trip (exactly like a remote job upload) is faithful.
    survey2 = Survey.from_dict(d)
    assert survey2 == survey
    assert survey2.question_names == survey.question_names


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
    assert original["answer.concern__loop0__sectors"] is None  # skipped (bullish)
    assert original["answer.concern__loop2__sectors"] is None  # jumped over (bearish)
    assert original["answer.allocation__loop2__sectors"] is None  # jumped over
    assert original["answer.allocation__loop0__sectors"] == 25


def test_deprecated_aliases_still_work():
    """Old names (add_loop_merge / with_loop_skip / with_loop_jump / END_OF_LOOP)
    still function, forwarding to the new API, and emit DeprecationWarning."""
    src = QuestionList(question_name="items", question_text="List items.")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        gate = QuestionFreeText(
            question_name="gate",
            question_text="Proceed with {{ loop_item }}? (yes/stop)",
        ).with_loop_jump(
            "{{ gate.answer }} == 'stop'", target=QuestionFreeText.END_OF_LOOP
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
        "gate__loop0__items": "yes",
        "gate__loop1__items": "stop",
        "note__loop0__items": "note A",
        "note__loop1__items": "SHOULD NOT APPEAR",
    }
    results = _run(survey, canned)

    assert _val(results, "gate__loop0__items") == "yes"
    assert _val(results, "note__loop0__items") == "note A"
    assert _val(results, "gate__loop1__items") == "stop"
    assert _val(results, "note__loop1__items") is None  # jumped past via NEXT_ITEM
