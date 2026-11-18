"""Self-selected teams with atomic per-role seats and immutable membership."""

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
    rid, role, team = arg("respondent_id"), arg("role"), arg("team")
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
            "profiles": state_field(StateType.map(StateType.text(), StateType.choice(list(role_seats))), {}),
            "members": state_field(
                StateType.map(
                    StateType.text(),
                    StateType.record(
                        {"team": StateType.choice(teams), "role": StateType.choice(list(role_seats))}
                    ),
                ),
                {},
            ),
            "closed": state_field(StateType.boolean(), False),
        },
        commands={
            "register": Command(
                inputs={"respondent_id": StateType.text(), "role": StateType.choice(list(role_seats))},
                effects=(
                    require(rid.stripped().length() > 0, code="missing_respondent_id"),
                    require(
                        ~profiles.contains(rid) | (profiles.get(rid) == role),
                        code="role_changed",
                    ),
                    when(
                        ~profiles.contains(rid),
                        require(~field("closed"), code="teams_closed"),
                    ),
                    put("profiles", rid, role, once=True),
                ),
            ),
            "join": Command(
                inputs={"respondent_id": StateType.text(), "team": StateType.choice(teams)},
                effects=(
                    require(profiles.contains(rid), code="role_required"),
                    require(
                        ~members.contains(rid)
                        | (members.get(rid, {}).get("team") == team),
                        code="team_changed",
                    ),
                    when(
                        ~members.contains(rid),
                        require(~field("closed"), code="teams_closed"),
                    ),
                    when(
                        ~members.contains(rid),
                        require(
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
        close_effects=(assign("closed", True),),
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
