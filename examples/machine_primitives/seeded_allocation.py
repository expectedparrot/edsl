"""Reproducible lottery: stable participant IDs, explicit cohort, separate prize draw."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    append,
    assert_,
    constant,
    field,
    input_,
    seeded_integer,
    seeded_order,
    set_,
    state_field,
    take,
)


def build_machine(seed="study-2026", scope="cohort-1", seats=2):
    return Machine(
        name="SeededAllocation",
        constants={"seed": seed, "scope": scope, "seats": seats},
        fields={
            "entrants": state_field(T.sequence(T.text()), []),
            "winners": state_field(T.sequence(T.text()), []),
            "bonus_units": state_field(T.integer(), 0),
            "settled": state_field(T.boolean(), False),
        },
        commands={
            "enter": Command(
                inputs={"participant": T.text()},
                require=~field("settled"),
                effects=(
                    assert_(input_("participant").length() > 0, code="empty_id"),
                    assert_(
                        ~field("entrants").contains(input_("participant")),
                        code="duplicate_id",
                    ),
                    append("entrants", input_("participant")),
                ),
            )
        },
        close_effects=(
            set_(
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
            set_(
                "bonus_units",
                seeded_integer(
                    constant("seed"),
                    100,
                    201,
                    scope=constant("scope"),
                    key="participation-bonus",
                ),
            ),
            set_("settled", True),
        ),
        view={"winners": field("winners"), "bonus_units": field("bonus_units")},
    )


DEMO = [("enter", {"participant": p}) for p in ["C", "A", "D", "B"]] + [("$close", {})]
