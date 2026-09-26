"""Sealed ranked ballots with close-time plurality, Borda, and Condorcet results."""

from edsl.sharedstate import Command, Machine, T, choose, constant, current, field, input_, put, reduce_, set_, state_field

SPEC = Machine(
    name="SharedVotingGame",
    constants={"candidates": ("A", "B", "C"), "voter_count": 3},
    fields={
        "ballots": state_field(T.map(T.text(), T.rank(constant("candidates"))), {}),
        "results": state_field(T.optional(T.map()), None),
    },
    commands={
        "vote": Command(
            inputs={"voter": T.text(), "ranking": T.rank(constant("candidates"))},
            effects=(put("ballots", input_("voter"), input_("ranking")),),
        )
    },
    view={
        "candidates": constant("candidates"),
        "voter_count": constant("voter_count"),
        "ballot_count": field("ballots").length(),
        "ballots": choose(current("closed"), field("ballots"), {}),
        "results": choose(current("closed"), field("results"), None),
    },
    complete_when=field("ballots").length() == constant("voter_count"),
    close_effects=(set_("results", reduce_("ranked_ballot_results", field("ballots"), candidates=constant("candidates"))),),
)
