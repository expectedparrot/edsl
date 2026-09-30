"""Self-selected teams with atomic per-role seats and immutable membership."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    assert_,
    choose,
    constant,
    current_value,
    field,
    filter_items,
    input_,
    local,
    put,
    record,
    set_,
    state_field,
    when,
)

DEFAULT_TEAMS = ("Orion", "Lyra")
DEFAULT_ROLES = {"Designer": 1, "Builder": 2}


def build_machine(teams=DEFAULT_TEAMS, role_seats=None):
    role_seats = dict(DEFAULT_ROLES if role_seats is None else role_seats)
    if isinstance(teams, str):
        raise ValueError("teams must be a sequence")
    teams = list(teams)
    if (
        not teams
        or any(not isinstance(t, str) or not t.strip() for t in teams)
        or len(set(teams)) != len(teams)
    ):
        raise ValueError("teams must be distinct nonempty labels")
    if not role_seats or any(
        not isinstance(k, str) or not k.strip() or type(v) is not int or v < 1
        for k, v in role_seats.items()
    ):
        raise ValueError("roles require nonempty labels and positive integer seats")
    rid, role, team = input_("respondent_id"), input_("role"), input_("team")
    profiles, members = field("profiles"), field("members")

    def eligible(for_role):
        return filter_items(
            constant("teams"),
            item="team",
            predicate=filter_items(
                members.values(),
                item="m",
                predicate=(local("m").get("team") == local("team"))
                & (local("m").get("role") == for_role),
            ).length()
            < constant("role_seats").get(for_role, 0),
        )

    you = current_value("respondent_id", "")
    your_team = members.get(you, {}).get("team")
    return Machine(
        name="TeamFormation",
        constants={
            "teams": teams,
            "role_seats": role_seats,
            "total_seats": len(teams) * sum(role_seats.values()),
        },
        fields={
            "profiles": state_field(T.map(T.text(), T.choice(list(role_seats))), {}),
            "members": state_field(
                T.map(
                    T.text(),
                    T.record(
                        {"team": T.choice(teams), "role": T.choice(list(role_seats))}
                    ),
                ),
                {},
            ),
            "closed": state_field(T.boolean(), False),
        },
        commands={
            "register": Command(
                inputs={"respondent_id": T.text(), "role": T.choice(list(role_seats))},
                effects=(
                    assert_(rid.stripped().length() > 0, code="missing_respondent_id"),
                    assert_(
                        ~profiles.contains(rid) | (profiles.get(rid) == role),
                        code="role_changed",
                    ),
                    when(
                        ~profiles.contains(rid),
                        assert_(~field("closed"), code="teams_closed"),
                    ),
                    put("profiles", rid, role, once=True),
                ),
            ),
            "join": Command(
                inputs={"respondent_id": T.text(), "team": T.choice(teams)},
                effects=(
                    assert_(profiles.contains(rid), code="role_required"),
                    assert_(
                        ~members.contains(rid)
                        | (members.get(rid, {}).get("team") == team),
                        code="team_changed",
                    ),
                    when(
                        ~members.contains(rid),
                        assert_(~field("closed"), code="teams_closed"),
                    ),
                    when(
                        ~members.contains(rid),
                        assert_(
                            eligible(profiles.get(rid)).contains(team), code="role_full"
                        ),
                    ),
                    put(
                        "members",
                        rid,
                        record(team=team, role=profiles.get(rid)),
                        once=True,
                    ),
                ),
            ),
        },
        complete_when=members.length() == constant("total_seats"),
        close_effects=(set_("closed", True),),
        view={
            "options": choose(
                your_team != None,
                [your_team],
                choose(field("closed"), [], eligible(profiles.get(you))),
            ),
            "team": your_team,
            "role": profiles.get(you),
            "members": members.length(),
            "complete": members.length() == constant("total_seats"),
        },
    )


DEMO = [
    (command, inputs)
    for i, role in enumerate(
        ["Designer", "Designer", "Builder", "Builder", "Builder", "Builder"]
    )
    for command, inputs in [
        ("register", {"respondent_id": f"R{i}", "role": role}),
        ("join", {"respondent_id": f"R{i}", "team": DEFAULT_TEAMS[i % 2]}),
    ]
]
