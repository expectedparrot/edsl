from types import SimpleNamespace
from edsl.jobs.cost_estimation.job_cost_estimator import _compute_reach_probabilities
from edsl.surveys.base import EndOfSurvey


def make_survey(names):
    return SimpleNamespace(
        question_names=names,
        question_name_to_index={n: i for i, n in enumerate(names)},
    )


class TestLinearSurvey:
    """Without branch_weights, every question has reach 1.0."""

    def test_all_reach_one(self):
        survey = make_survey(["q1", "q2", "q3"])
        reach, warnings = _compute_reach_probabilities(survey, {})
        assert reach == {"q1": 1.0, "q2": 1.0, "q3": 1.0}
        assert warnings == []

    def test_single_question(self):
        survey = make_survey(["q1"])
        reach, _ = _compute_reach_probabilities(survey, {})
        assert reach["q1"] == 1.0


class TestSkipLogic:
    """Branch weights redistribute reach from a source question to its destination."""

    def test_full_skip(self):
        # q1 sends everyone to q3, q2 is unreachable
        survey = make_survey(["q1", "q2", "q3"])
        reach, _ = _compute_reach_probabilities(survey, {("q1", "q3"): 1.0})
        assert reach["q2"] == 0.0
        assert reach["q3"] == 1.0

    def test_partial_skip(self):
        # q1 sends 60% to q3, 40% continue to q2; both paths converge at q3
        survey = make_survey(["q1", "q2", "q3"])
        reach, _ = _compute_reach_probabilities(survey, {("q1", "q3"): 0.6})
        assert abs(reach["q2"] - 0.4) < 1e-9
        assert abs(reach["q3"] - 1.0) < 1e-9

    def test_multiple_converging_paths(self):
        """Reach is additive — multiple paths to the same question sum correctly."""
        # From the docstring example:
        # q1 → q4 (0.9), q1 → q2 (0.1)
        # q2 → q5 (0.8), q2 → q3 (0.2)
        # q3 → q4 (fallthrough)
        # q4 → q5 (fallthrough)
        survey = make_survey(["q1", "q2", "q3", "q4", "q5"])
        reach, _ = _compute_reach_probabilities(
            survey, {("q1", "q4"): 0.9, ("q2", "q5"): 0.8}
        )
        assert abs(reach["q2"] - 0.1) < 1e-9
        assert abs(reach["q3"] - 0.02) < 1e-9
        assert abs(reach["q4"] - 0.92) < 1e-9
        assert abs(reach["q5"] - 1.0) < 1e-9

    def test_end_of_survey_exit(self):
        """Probability routed to EndOfSurvey is absorbed — doesn't forward to any question."""
        survey = make_survey(["q1", "q2"])
        reach, _ = _compute_reach_probabilities(survey, {("q1", EndOfSurvey): 1.0})
        assert reach["q2"] == 0.0

    def test_end_of_survey_string(self):
        """String 'EndOfSurvey' is treated the same as the EndOfSurvey sentinel."""
        survey = make_survey(["q1", "q2"])
        reach, _ = _compute_reach_probabilities(survey, {("q1", "EndOfSurvey"): 1.0})
        assert reach["q2"] == 0.0


class TestWarnings:
    """Invalid branch_weights entries emit warnings but don't crash."""

    def test_unknown_from_q(self):
        survey = make_survey(["q1", "q2"])
        _, warnings = _compute_reach_probabilities(survey, {("ghost", "q2"): 0.5})
        assert any("ghost" in w for w in warnings)

    def test_unknown_to_q(self):
        survey = make_survey(["q1", "q2"])
        _, warnings = _compute_reach_probabilities(survey, {("q1", "ghost"): 0.5})
        assert any("ghost" in w for w in warnings)

    def test_weight_sum_over_one(self):
        survey = make_survey(["q1", "q2", "q3"])
        _, warnings = _compute_reach_probabilities(
            survey, {("q1", "q2"): 0.7, ("q1", "q3"): 0.6}
        )
        assert any("1.0" in w or "sum" in w.lower() for w in warnings)
