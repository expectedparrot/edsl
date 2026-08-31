"""Proposals and matrix ballots using generated IDs and reducers."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    append,
    decode_matrix,
    expr,
    field,
    input_,
    local,
    map_sequence,
    record,
    reduce_,
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
    fields={"proposals": state_field(T.sequence(), []), "ballots": state_field(T.sequence(), [])},
    commands={
        "propose": Command(
            inputs={"proposer": T.text(), "title": T.text()},
            effects=(append("proposals", record(id=proposal_id, proposer=input_("proposer"), title=input_("title"))),),
        ),
        "vote": Command(
            inputs={"voter": T.text(), "votes": T.map()},
            effects=(
                append(
                    "ballots",
                    record(
                        voter=input_("voter"),
                        votes=decode_matrix(
                            input_("votes"),
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
        "scores": reduce_("weighted_matrix_tally", field("ballots"), weights={"up": 1, "neutral": 0, "down": -1}),
    },
)
