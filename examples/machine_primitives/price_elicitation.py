"""Bounded integer binary search, one Machine scope per respondent."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    append,
    assert_,
    choose,
    constant,
    field,
    input_,
    record,
    round_ratio,
    set_,
    state_field,
    when,
)


def build_machine(lower=0, upper=100, max_questions=7, tolerance=0):
    for name, value in (("lower", lower), ("upper", upper), ("tolerance", tolerance)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if upper < lower or type(max_questions) is not int or not 1 <= max_questions <= 32:
        raise ValueError("require lower <= upper and 1..32 questions")
    low, high, history = field("lower"), field("upper"), field("history")
    step, answer = input_("step"), input_("answer")
    price = round_ratio(low + high, 2, rounding="ceiling")
    done = (high - low <= constant("tolerance")) | (
        history.length() >= constant("max_questions")
    )
    replay = step < history.length()
    previous = choose(replay, history.at(step), {})
    return Machine(
        name="PriceElicitation",
        constants={"max_questions": max_questions, "tolerance": tolerance},
        fields={
            "lower": state_field(T.integer(minimum=lower, maximum=upper), lower),
            "upper": state_field(T.integer(minimum=lower, maximum=upper), upper),
            "history": state_field(
                T.sequence(
                    T.record(
                        {
                            "step": T.integer(minimum=0),
                            "price": T.integer(minimum=lower, maximum=upper),
                            "answer": T.choice(["Yes", "No"]),
                        }
                    )
                ),
                [],
            ),
            "closed": state_field(T.boolean(), False),
        },
        commands={
            "observe": Command(
                inputs={
                    "step": T.integer(minimum=0),
                    "answer": T.choice(["Yes", "No"]),
                },
                effects=(
                    assert_(
                        ~replay | (previous.get("answer") == answer),
                        code="answer_changed",
                    ),
                    when(
                        ~replay,
                        assert_(~done & ~field("closed"), code="elicitation_finished"),
                    ),
                    when(
                        ~replay,
                        assert_(step == history.length(), code="unexpected_step"),
                    ),
                    when(~replay, set_("lower", choose(answer == "Yes", price, low))),
                    when(
                        ~replay, set_("upper", choose(answer == "No", price - 1, high))
                    ),
                    when(
                        ~replay,
                        append(
                            "history", record(step=step, price=price, answer=answer)
                        ),
                    ),
                ),
            )
        },
        complete_when=done,
        close_effects=(set_("closed", True),),
        view={
            "lower": low,
            "upper": high,
            "price": price,
            "next_step": history.length(),
            "done": done | field("closed"),
            "precise": high - low <= constant("tolerance"),
        },
    )


DEMO = [
    ("observe", {"step": i, "answer": answer})
    for i, answer in enumerate(["Yes", "No", "Yes", "No", "Yes", "No"])
]
