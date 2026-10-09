"""Sealed ranked ballots with close-time plurality, Borda, and Condorcet results."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, put, reduce_, set_, state_field

SPEC = Machine(
    name="SharedVotingGame",
    constants={"candidates": ("A", "B", "C"), "voter_count": 3},
    fields={
        "ballots": state_field(StateType.map(StateType.text(), StateType.rank(constant("candidates"))), {}),
        "results": state_field(StateType.optional(StateType.map()), None),
    },
    commands={
        "vote": Command(
            inputs={"voter": StateType.text(), "ranking": StateType.rank(constant("candidates"))},
            effects=(put("ballots", arg("voter"), arg("ranking")),),
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
