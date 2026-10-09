"""Admission quotas: ten distinct respondents in each of A and B.

Admission reserves a place permanently. A trusted host supplies stable respondent
IDs; the Machine does not authenticate them or reclaim abandoned reservations.
"""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    assert_,
    constant,
    current_value,
    field,
    arg,
    put,
    record,
    reduce_,
    set_,
    state_field,
    when,
)


def build_machine(quota_a=10, quota_b=10):
    for quota in (quota_a, quota_b):
        if type(quota) is not int or quota < 0:
            raise ValueError("quotas must be nonnegative integers")
    admissions = field("admissions")
    respondent, group = arg("respondent_id"), arg("group")
    existing = admissions.contains(respondent)
    counts = reduce_("count_by", admissions.values())
    limits = constant("limits")
    full = (counts.get("A", 0) >= limits.get("A")) & (
        counts.get("B", 0) >= limits.get("B")
    )
    your_group = admissions.get(current_value("respondent_id", ""))
    return Machine(
        name="SurveyQuota",
        constants={"limits": {"A": quota_a, "B": quota_b}},
        fields={
            "admissions": state_field(StateType.map(StateType.text(), StateType.choice(["A", "B"])), {}),
            "enrollment_closed": state_field(StateType.boolean(), False),
        },
        commands={
            "screen": Command(
                inputs={"respondent_id": StateType.text(), "group": StateType.text()},
                effects=(
                    assert_(
                        respondent.stripped().length() > 0, code="missing_respondent_id"
                    ),
                    assert_(
                        ~existing | (admissions.get(respondent) == group),
                        code="respondent_type_changed",
                    ),
                    when(
                        ~existing,
                        assert_(~field("enrollment_closed"), code="enrollment_closed"),
                    ),
                    when(
                        ~existing,
                        assert_(limits.contains(group), code="ineligible_type"),
                    ),
                    when(~existing, assert_(~full, code="quotas_full")),
                    when(
                        ~existing,
                        assert_(
                            counts.get(group, 0) < limits.get(group),
                            code="type_quota_full",
                        ),
                    ),
                    put("admissions", respondent, group, once=True),
                ),
            )
        },
        complete_when=full,
        close_effects=(set_("enrollment_closed", True),),
        view={
            "counts": record(A=counts.get("A", 0), B=counts.get("B", 0)),
            "quotas_full": full,
            "accepting": ~field("enrollment_closed") & ~full,
            "admitted": your_group != None,
            "your_group": your_group,
        },
    )


DEMO = (
    [("screen", {"respondent_id": f"A{i}", "group": "A"}) for i in range(10)]
    + [
        ("screen", {"respondent_id": "A-overflow", "group": "A"}),
        ("screen", {"respondent_id": "other", "group": "Other"}),
    ]
    + [("screen", {"respondent_id": f"B{i}", "group": "B"}) for i in range(10)]
    + [
        ("screen", {"respondent_id": "late", "group": "B"}),
        ("screen", {"respondent_id": "A0", "group": "A"}),
    ]
)
