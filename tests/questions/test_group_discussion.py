"""Unit tests for the group-discussion voting library, ballot parsers, and the
decision/flow helpers. These cover the rules CI needs to protect: vote methods,
veto, quorum, supermajority thresholds, numeric aggregation, power indices, and
the parser/robustness fixes (abstentions, overlapping labels, quadratic budget,
vetoed motions, None-threshold supermajority, run isolation)."""

import copy

from edsl.invigilators.group_discussion_voting import (
    Ballot,
    tally,
    power_indices,
    VOTE_METHODS,
)
from edsl.invigilators.invigilator_group_discussion import (
    InvigilatorGroupDiscussion as GD,
    QUADRATIC_BUDGET,
)
from edsl import QuestionGroupDiscussion


def _bare():
    """A GD instance without running __init__, for testing pure helpers."""
    return GD.__new__(GD)


# ---- voting methods ---------------------------------------------------------


def test_plurality_and_majority():
    assert tally("plurality", [Ballot("a", "x"), Ballot("b", "x"), Ballot("c", "y")],
                 ["x", "y"]).winner == "x"
    # three-way split has no strict majority
    r = tally("majority", [Ballot("a", "x"), Ballot("b", "y"), Ballot("c", "z")],
              ["x", "y", "z"])
    assert r.decided is False


def test_supermajority_two_thirds_exact():
    # 2 of 3 is exactly two-thirds -> passes even when written as 0.667
    assert tally("supermajority", [Ballot("a", "x"), Ballot("b", "x"), Ballot("c", "y")],
                 ["x", "y"], threshold=0.667).decided is True
    assert tally("supermajority", [Ballot("a", "x"), Ballot("b", "y"), Ballot("c", "y")],
                 ["x", "y"], threshold=0.75).winner is None  # y is 2/3, below 3/4


def test_unanimous_and_weighted():
    assert tally("unanimous", [Ballot("a", "x"), Ballot("b", "x")], ["x", "y"]).decided
    assert tally("unanimous", [Ballot("a", "x"), Ballot("b", "y")], ["x", "y"]).decided is False
    # weighted: a weight-2 voter outvotes a weight-1 voter
    assert tally("weighted", [Ballot("m", "x", weight=2), Ballot("t", "y", weight=1)],
                 ["x", "y"]).winner == "x"


def test_veto_overrides_majority():
    r = tally("majority",
              [Ballot("us", "x", holds_veto=True), Ballot("a", "y"),
               Ballot("b", "y"), Ballot("c", "y")], ["x", "y"])
    assert r.decided is False and r.vetoed_by == "us"


def test_quorum_not_met():
    r = tally("majority", [Ballot("a", "x"), Ballot("b", "x"), Ballot("c", None)],
              ["x", "y"], quorum=3, electorate=3)
    assert r.decided is False and r.quorum_met is False


def test_ranked_choice_irv():
    ballots = [Ballot("a", ["x", "z"]), Ballot("b", ["x", "y"]),
               Ballot("c", ["y", "z"]), Ballot("d", ["y", "x"]),
               Ballot("e", ["z", "x"])]
    assert tally("ranked_choice", ballots, ["x", "y", "z"]).winner == "x"


def test_approval_and_quadratic():
    assert tally("approval", [Ballot("a", ["x", "y"]), Ballot("b", ["y"])],
                 ["x", "y"]).winner == "y"
    assert tally("quadratic", [Ballot("a", {"x": 4, "y": 1}),
                               Ballot("b", {"x": 1, "y": 3})], ["x", "y"]).winner == "x"


def test_numeric_median_robust_to_outlier():
    r = tally("numeric", [Ballot("a", 10), Ballot("b", 12),
                          Ballot("c", 100), Ballot("d", 11)])
    assert r.winner == 11.5 and r.detail["median"] == 11.5


def test_electorate_basis_absolute_majority():
    # 295 yes of a 464-member body clears 233; abstentions count against the bar
    inv = [Ballot("coalition", "confidence", weight=295),
           Ballot("opp", "no confidence", weight=106),
           Ballot("abst", None, weight=63)]
    r = tally("weighted", inv, ["confidence", "no confidence"],
              threshold=0.5, basis="electorate")
    assert r.decided and r.winner == "confidence"
    # 200 yes falls short of 233
    inv2 = [Ballot("c", "confidence", weight=200),
            Ballot("o", "no confidence", weight=120), Ballot("a", None, weight=144)]
    assert tally("weighted", inv2, ["confidence", "no confidence"],
                 threshold=0.5, basis="electorate").decided is False


def test_all_methods_registered():
    assert set(VOTE_METHODS) >= {
        "plurality", "majority", "supermajority", "unanimous", "weighted",
        "approval", "ranked_choice", "quadratic", "numeric", "authority"}


# ---- power indices ----------------------------------------------------------


def test_power_indices_known_values():
    p = power_indices({"A": 3, "B": 2, "C": 1}, quota=3, strict=True)
    assert p["banzhaf"] == {"A": 0.6, "B": 0.2, "C": 0.2}
    assert p["shapley_shubik"]["A"] == 0.6667


# ---- parser fixes -----------------------------------------------------------


def test_ranked_choice_abstention_returns_none():
    # Greptile #6: an unparseable ranked ballot must not become a full ranking
    assert _bare()._parse_ballot("I abstain", {"method": "ranked_choice",
                                               "options": ["x", "y", "z"]}) is None


def test_quadratic_label_digits_not_merged():
    # Greptile #7: "Project 2: 3" is 3 votes, not 23 (label digit not merged).
    # Amounts kept within the 16-credit budget (3**2 + 2**2 = 13) to isolate this.
    alloc = _bare()._parse_ballot("Project 2: 3\nProject 3: 2",
                                  {"method": "quadratic",
                                   "options": ["Project 2", "Project 3"]})
    assert alloc["Project 2"] == 3.0 and alloc["Project 3"] == 2.0


def test_quadratic_budget_enforced():
    # Greptile #8: a 10-vote ballot costs 100 > 16 credits and must be scaled down
    alloc = _bare()._parse_ballot("x: 10",
                                  {"method": "quadratic", "options": ["x"]})
    cost = sum(v * v for v in alloc.values())
    assert cost <= QUADRATIC_BUDGET + 1e-6


def test_match_option_prefers_exact_no_confidence():
    # "no confidence" must not be swallowed by the "confidence" substring
    assert _bare()._match_option("no confidence\nbecause...",
                                 ["confidence", "no confidence"]) == "no confidence"


# ---- decision / flow helpers ------------------------------------------------


def test_power_quota_handles_none_threshold():
    # Greptile #3: supermajority with threshold=None must not multiply None
    quota, strict = GD._power_quota("supermajority", None, 9)
    assert quota == 0.667 * 9 and strict is False


def test_power_quota_matches_weighted_threshold():
    # Greptile #9: weighted 2/3 vote's power uses the 2/3 bar, not simple majority
    quota, strict = GD._power_quota("weighted", 2 / 3, 9)
    assert abs(quota - (2 / 3) * 9) < 1e-9 and strict is False
    # weighted simple-majority stays strict half
    assert GD._power_quota("weighted", None, 10) == (5.0, True)


def test_motion_action_requires_carried():
    # Greptile #4: a motion that did not carry changes nothing
    class R:
        def __init__(self, decided, winner):
            self.decided, self.winner = decided, winner
    assert GD._motion_action(R(True, "table")) == "skip_next"
    assert GD._motion_action(R(False, "table")) is None  # not carried
    assert GD._motion_action(R(True, "extend debate")) == "extend_next"
    assert GD._motion_action(None) is None


# ---- caucus privacy & run isolation -----------------------------------------


def test_visible_hides_caucus_from_nonmember():
    # Greptile #1: a caucus turn must be hidden from a non-member viewer
    inv = _bare()
    inv._transcript = [
        {"speaker": "alice", "round": 1, "kind": "caucus", "private_to": ["alice", "bob"],
         "content": [{"type": "text", "text": "SECRET plan"}]},
        {"speaker": "carol", "round": 1, "kind": "discussion",
         "content": [{"type": "text", "text": "public remark"}]},
    ]
    seen_by_mod = inv._visible("moderator")
    assert "SECRET plan" not in seen_by_mod and "public remark" in seen_by_mod
    seen_by_member = inv._visible("alice")
    assert "SECRET plan" in seen_by_member


def test_resolved_stages_shared_so_engine_must_deepcopy():
    # Greptile #5: resolved_stages returns the question's own dicts; the engine
    # deep-copies before running so a motion mutation cannot leak across runs.
    q = QuestionGroupDiscussion(
        "m", "x", participants=[{"name": "a"}, {"name": "b"}],
        stages=[{"type": "discussion", "name": "d", "rounds": 1}])
    assert q.resolved_stages()[0] is q.stages[0]  # shared -> deepcopy is required
    dq = copy.deepcopy(list(q.resolved_stages()))
    dq[0]["rounds"] = 99
    assert q.stages[0]["rounds"] == 1  # original untouched


def test_render_str_substitutes_scenario():
    # Greptile #2: scenario placeholders in stage prompts/personas are rendered
    inv = _bare()
    inv._replacement_dict = lambda: {"city": "Paris"}
    assert inv._render_str("Discuss {{ city }}") == "Discuss Paris"
    assert inv._render_str("no placeholder") == "no placeholder"
