"""Proposals and matrix ballots using generated IDs and reducers."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    append,
    decode_matrix,
    expr,
    field,
    arg,
    local,
    map_sequence,
    record,
    reduce,
    state_field,
)

proposal_id = expr("concat", "A", field("proposals").length() + 1)
proposal_titles = map_sequence(
    field("proposals"),
    item="proposal",
    value_expr=local("proposal").get("title"),
)
vote_options = ["up", "neutral", "down"]

SPEC = Machine(
    name="SharedAgenda",
    constants={"vote_weights": {"up": 1, "neutral": 0, "down": -1}},
    fields={"proposals": state_field(StateType.sequence(), []), "ballots": state_field(StateType.sequence(), [])},
    commands={
        "propose": Command(
            inputs={"proposer": StateType.text(), "title": StateType.text()},
            effects=(append("proposals", record(id=proposal_id, proposer=arg("proposer"), title=arg("title"))),),
        ),
        "vote": Command(
            inputs={"voter": StateType.text(), "votes": StateType.map()},
            effects=(
                append(
                    "ballots",
                    record(
                        voter=arg("voter"),
                        votes=decode_matrix(
                            arg("votes"),
                            rows=proposal_titles,
                            options=vote_options,
                        ),
                    ),
                ),
            ),
        ),
    },
    view={
        "proposals": field("proposals"),
        "ballots": field("ballots"),
        "scores": reduce("weighted_matrix_tally", field("ballots"), weights={"up": 1, "neutral": 0, "down": -1}),
    },
)
