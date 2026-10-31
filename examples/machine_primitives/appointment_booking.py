"""Atomic holds with durable reservation tokens; release is explicit, not timed."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    require,
    choose,
    constant,
    current_value,
    field,
    filter_items,
    arg,
    local,
    put,
    record,
    assign,
    state_field,
    when,
)

DEFAULT_SLOTS = ("09:00", "10:00", "11:00")


def build_machine(slots=DEFAULT_SLOTS):
    if isinstance(slots, str):
        raise ValueError("slots must be a sequence")
    slots = list(slots)
    if (
        not slots
        or any(not isinstance(s, str) or not s.strip() for s in slots)
        or len(set(slots)) != len(slots)
    ):
        raise ValueError("slots must be unique nonempty labels")
    bookings = field("bookings")
    token, rid, slot = arg("reservation_id"), arg("respondent_id"), arg("slot")
    seen = bookings.contains(token)
    old = bookings.get(token, {})
    active = filter_items(
        bookings.values(), item="b", predicate=local("b").get("status") != "released"
    )
    free = filter_items(
        constant("slots"),
        item="s",
        predicate=filter_items(
            active, item="b", predicate=local("b").get("slot") == local("s")
        ).length()
        == 0,
    )
    your = bookings.get(current_value("reservation_id", ""), {})
    yours = your.get("respondent_id") == current_value("respondent_id", "")
    status = choose(yours, your.get("status", "missing"), "missing")
    identity = (
        require(rid.stripped().length() > 0, code="missing_respondent_id"),
        require(token.stripped().length() > 0, code="missing_reservation_id"),
    )
    return Machine(
        name="AppointmentBooking",
        constants={"slots": slots},
        fields={
            "bookings": state_field(
                StateType.map(
                    StateType.text(),
                    StateType.record(
                        {
                            "respondent_id": StateType.text(),
                            "slot": StateType.choice(slots),
                            "status": StateType.choice(["held", "confirmed", "released"]),
                        }
                    ),
                ),
                {},
            ),
            "closed": state_field(StateType.boolean(), False),
        },
        commands={
            "hold": Command(
                inputs={
                    "respondent_id": StateType.text(),
                    "reservation_id": StateType.text(),
                    "slot": StateType.choice(slots),
                },
                effects=(
                    *identity,
                    require(
                        ~seen
                        | (
                            (old.get("respondent_id") == rid)
                            & (old.get("slot") == slot)
                        ),
                        code="reservation_changed",
                    ),
                    when(~seen, require(~field("closed"), code="booking_closed")),
                    when(
                        ~seen,
                        require(
                            filter_items(
                                active,
                                item="b",
                                predicate=local("b").get("respondent_id") == rid,
                            ).length()
                            == 0,
                            code="already_booked",
                        ),
                    ),
                    when(~seen, require(free.contains(slot), code="slot_unavailable")),
                    put(
                        "bookings",
                        token,
                        record(respondent_id=rid, slot=slot, status="held"),
                        once=True,
                    ),
                ),
            ),
            "decide": Command(
                inputs={
                    "respondent_id": StateType.text(),
                    "reservation_id": StateType.text(),
                    "decision": StateType.choice(["Confirm", "Release"]),
                },
                effects=(
                    *identity,
                    require(
                        seen & (old.get("respondent_id") == rid),
                        code="reservation_not_owned",
                    ),
                    require(
                        (arg("decision") == "Release")
                        | (old.get("status") != "released"),
                        code="reservation_released",
                    ),
                    put(
                        "bookings",
                        token,
                        old.with_item(
                            "status",
                            choose(
                                arg("decision") == "Confirm", "confirmed", "released"
                            ),
                        ),
                    ),
                ),
            ),
        },
        # Full now does not mean finished: a release can reopen availability.
        complete_when=False,
        close_effects=(assign("closed", True),),
        view={
            "options": choose(
                (status == "held") | (status == "confirmed"),
                [your.get("slot")],
                choose(field("closed"), [], free),
            ),
            "status": status,
            "slot": choose(yours, your.get("slot"), None),
            "available": free,
        },
    )


DEMO = [
    ("hold", {"respondent_id": "A", "reservation_id": "a1", "slot": "09:00"}),
    ("hold", {"respondent_id": "B", "reservation_id": "b1", "slot": "09:00"}),
    ("decide", {"respondent_id": "A", "reservation_id": "a1", "decision": "Release"}),
    ("hold", {"respondent_id": "B", "reservation_id": "b2", "slot": "09:00"}),
    ("decide", {"respondent_id": "B", "reservation_id": "b2", "decision": "Confirm"}),
    ("decide", {"respondent_id": "A", "reservation_id": "a1", "decision": "Confirm"}),
]
