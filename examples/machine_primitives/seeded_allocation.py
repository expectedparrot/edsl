"""Reproducible lottery: stable participant IDs, explicit cohort, separate prize draw."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    append,
    require,
    constant,
    field,
    arg,
    seeded_integer,
    seeded_order,
    assign,
    state_field,
    take,
)


def build_machine(seed="study-2026", scope="cohort-1", seats=2):
    return Machine(
        name="SeededAllocation",
        constants={"seed": seed, "scope": scope, "seats": seats},
        fields={
            "entrants": state_field(StateType.sequence(StateType.text()), []),
            "winners": state_field(StateType.sequence(StateType.text()), []),
            "bonus_units": state_field(StateType.integer(), 0),
            "settled": state_field(StateType.boolean(), False),
        },
        commands={
            "enter": Command(
                inputs={"participant": StateType.text()},
                require=~field("settled"),
                effects=(
                    require(arg("participant").length() > 0, code="empty_id"),
                    require(
                        ~field("entrants").contains(arg("participant")),
                        code="duplicate_id",
                    ),
                    append("entrants", arg("participant")),
                ),
            )
        },
        close_effects=(
            assign(
                "winners",
                take(
                    seeded_order(
                        field("entrants"),
                        seed=constant("seed"),
                        scope=constant("scope"),
                        key="seat-priority",
                    ),
                    constant("seats"),
                ),
            ),
            assign(
                "bonus_units",
                seeded_integer(
                    constant("seed"),
                    100,
                    201,
                    scope=constant("scope"),
                    key="participation-bonus",
                ),
            ),
            assign("settled", True),
        ),
        view={"winners": field("winners"), "bonus_units": field("bonus_units")},
    )


DEMO = [("enter", {"participant": p}) for p in ["C", "A", "D", "B"]] + [("$close", {})]
