import json

import pytest

from edsl import QuestionYesNo, Survey
from edsl.causal import (
    CausalAnalysisPlan,
    EndogenousVariable,
    Equation,
    EstimatorSpec,
    ExperimentDesign,
    ExogenousVariable,
    Measurement,
    ParticipantScope,
    PathEffect,
    ScenarioScope,
    StructuralCausalModel,
    FittedSCM,
)


def mug_objects():
    survey = Survey([QuestionYesNo(question_name="deal", question_text="Did a deal occur?")])
    deal = EndogenousVariable("deal", "binary", "indicator", "1 if a sale was agreed", Measurement("buyer", survey, "deal"), levels=[0, 1])
    budget = ExogenousVariable("budget", "continuous", "USD", "maximum buyer payment", ParticipantScope("buyer"), [5, 10, 20, 40], "Your budget is {{ value }} USD")
    attachment = ExogenousVariable("attachment", "ordinal", "level", "seller attachment", ParticipantScope("seller"), ["none", "high"], "Your attachment is {{ value }}", levels=["none", "high"])
    scm = StructuralCausalModel([budget, attachment, deal], [Equation(deal, [budget, attachment], family="linear_probability", interactions=[[budget, attachment]])], name="mug")
    return budget, attachment, deal, scm


def test_scm_and_analysis_plan_round_trip_as_json():
    budget, attachment, deal, scm = mug_objects()
    restored = StructuralCausalModel.from_dict(json.loads(json.dumps(scm.to_dict())))
    assert restored == scm
    plan = CausalAnalysisPlan(scm, [PathEffect(budget, deal), PathEffect(attachment, deal)], EstimatorSpec(covariance="HC3"))
    assert CausalAnalysisPlan.from_dict(json.loads(json.dumps(plan.to_dict()))) == plan


def test_scm_rejects_cycles_and_unknown_variables():
    survey = Survey([QuestionYesNo(question_name="value", question_text="Value?")])
    measurement = Measurement("observer", survey, "value")
    y = EndogenousVariable("y", "binary", "indicator", "Y", measurement, levels=[0, 1])
    z = EndogenousVariable("z", "binary", "indicator", "Z", measurement, levels=[0, 1])
    with pytest.raises(ValueError, match="acyclic"):
        StructuralCausalModel([y, z], [Equation(y, [z]), Equation(z, [y])])
    with pytest.raises(ValueError, match="unknown"):
        StructuralCausalModel([y], [Equation(y, ["missing"])])


def test_analysis_plan_rejects_non_path_estimand():
    budget, attachment, deal, scm = mug_objects()
    with pytest.raises(ValueError, match="direct path"):
        CausalAnalysisPlan(scm, [PathEffect(budget, attachment)])


def test_factorial_design_is_stable_serializable_and_can_sample():
    budget, attachment, _, _ = mug_objects()
    full = ExperimentDesign.factorial([budget, attachment], replications=2, seed="mug-v1")
    assert len(full.cells) == 16
    assert len({cell.cell_id for cell in full.cells}) == 16
    assert ExperimentDesign.from_dict(json.loads(json.dumps(full.to_dict()))) == full
    sampled1 = ExperimentDesign.factorial([budget, attachment], replications=1, seed="sample", max_cells=3)
    sampled2 = ExperimentDesign.factorial([budget, attachment], replications=1, seed="sample", max_cells=3)
    assert sampled1 == sampled2
    assert len(sampled1.cells) == 3


def test_scenario_scope_and_variable_validation():
    variable = ExogenousVariable("weather", "nominal", "category", "weather condition", ScenarioScope(), ["sun", "rain"], "Weather is {{ value }}", visibility="public")
    assert variable.to_dict()["scope"] == {"type": "scenario"}
    with pytest.raises(ValueError, match="exactly two"):
        EndogenousVariable("bad", "binary", "indicator", "bad binary", Measurement("observer", Survey([QuestionYesNo(question_name="x", question_text="X?")]), "x"), levels=[0])


def test_analysis_plan_fits_and_hashes_exact_linear_data():
    survey = Survey([QuestionYesNo(question_name="y", question_text="Y?")])
    y = EndogenousVariable("y", "continuous", "points", "observed score", Measurement("observer", survey, "y"))
    x = ExogenousVariable("x", "continuous", "points", "assigned input", ScenarioScope(), [0, 1, 2], "Input is {{ value }}", visibility="public")
    scm = StructuralCausalModel([x, y], [Equation(y, [x])], name="linear")
    plan = CausalAnalysisPlan(scm, [PathEffect(x, y)], EstimatorSpec(covariance="classical"))
    observations = [{"x": value, "y": 1 + 2 * value} for value in range(5)]
    fitted = plan.fit(observations)
    assert fitted.equations[0].coefficients["intercept"] == pytest.approx(1)
    assert fitted.equations[0].coefficients["x"] == pytest.approx(2)
    assert FittedSCM.from_dict(json.loads(json.dumps(fitted.to_dict()))) == fitted
    assert plan.fit(observations).data_manifest_hash == fitted.data_manifest_hash
    assert plan.fit(list(reversed(observations))).data_manifest_hash != fitted.data_manifest_hash


def test_fit_rejects_rank_deficient_or_too_small_design():
    budget, attachment, deal, scm = mug_objects()
    plan = CausalAnalysisPlan(scm, [PathEffect(budget, deal)])
    with pytest.raises(ValueError, match="more observations"):
        plan.fit([{"budget": 5, "attachment": "none", "deal": 0}])
