"""Grow a reason catalog until ten distinct respondents add nothing new."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    append,
    require,
    choose,
    constant,
    field,
    arg,
    local,
    map_sequence,
    put,
    assign,
    state_field,
    when,
)

DEFAULT_SEEDS = ("Lower price", "Better quality")


def build_machine(seed_reasons=DEFAULT_SEEDS, patience=10):
    if type(patience) is not int or patience < 1:
        raise ValueError("patience must be a positive integer")
    if isinstance(seed_reasons, str):
        raise ValueError("seed_reasons must be a sequence of distinct reason labels")
    seeds = list(seed_reasons)
    if not seeds or any(not isinstance(s, str) or not s.strip() for s in seeds):
        raise ValueError("seed reasons must be nonempty text")
    seeds = [s.strip() for s in seeds]
    keys = [s.casefold() for s in seeds]
    if len(set(keys)) != len(keys) or "other" in keys:
        raise ValueError("seed reasons must be distinct and cannot be Other")
    respondent, reason = arg("respondent_id"), arg("reason").stripped()
    key = reason.casefolded()
    keys = map_sequence(
        field("reasons"), item="label", value_expr=local("label").casefolded()
    )
    new = ~keys.contains(key)
    seen = field("responses").contains(respondent)
    saturated = field("quiet_streak") >= constant("patience")

    def response_effects(allow_new):
        # Authoring helper only: these ordinary effects are expanded into JSON.
        return (
            require(respondent.stripped().length() > 0, code="missing_respondent_id"),
            require(reason.length() > 0, code="empty_reason"),
            require(key != "other", code="reserved_reason"),
            require(
                ~seen | (field("responses").get(respondent) == key),
                code="respondent_reason_changed",
            ),
            when(
                ~seen, require(~field("closed") & ~saturated, code="discovery_closed")
            ),
            *(() if allow_new else (require(~new, code="unknown_choice"),)),
            when(~seen & new, append("reasons", reason)),
            when(
                ~seen, assign("quiet_streak", choose(new, 0, field("quiet_streak") + 1))
            ),
            put("responses", respondent, key, once=True),
        )

    return Machine(
        name="ReasonDiscovery",
        constants={"patience": patience},
        fields={
            "reasons": state_field(StateType.sequence(StateType.text()), seeds),
            "responses": state_field(StateType.map(StateType.text(), StateType.text()), {}),
            "quiet_streak": state_field(StateType.integer(minimum=0, maximum=patience), 0),
            "closed": state_field(StateType.boolean(), False),
        },
        commands={
            "select": Command(
                inputs={"respondent_id": StateType.text(), "reason": StateType.text()},
                # Other is a routing choice, not a completed observation.
                require=arg("reason") != "Other",
                effects=response_effects(False),
            ),
            "suggest": Command(
                inputs={"respondent_id": StateType.text(), "reason": StateType.text()},
                effects=response_effects(True),
            ),
        },
        complete_when=saturated,
        close_effects=(assign("closed", True),),
        view={
            "reasons": field("reasons"),
            "options": field("reasons").appended("Other"),
            "quiet_streak": field("quiet_streak"),
            "respondents": field("responses").length(),
            "saturated": saturated,
            "accepting": ~field("closed") & ~saturated,
        },
    )


DEMO = [
    ("select", {"respondent_id": "R0", "reason": "Lower price"}),
    ("select", {"respondent_id": "R1", "reason": "Other"}),
    ("suggest", {"respondent_id": "R1", "reason": "Convenience"}),
    ("suggest", {"respondent_id": "R2", "reason": "Recommendation"}),
    ("suggest", {"respondent_id": "R3", "reason": "Habit"}),
] + [
    ("select", {"respondent_id": f"R{i}", "reason": "Lower price"})
    for i in range(4, 14)
]
