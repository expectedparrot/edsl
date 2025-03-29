"""Compose two questions where the answer to q1 is used as an input to q2."""

from .question_functional import QuestionFunctional
from .question_base import QuestionBase
from ..scenarios import Scenario
from .exceptions import QuestionValueError


def compose_questions(
    q1: QuestionBase, q2: QuestionBase, question_name: str = None
) -> QuestionFunctional:
    """
    Compose two questions where the answer to q1 is used as an input to q2.

    The resulting question is a question that can be used like other questions.
    Note that the same result can also be achieved in other ways:
    - Using the `add_targeted_memory(q2, q1)` method in Survey
    - Using the __add__ method in Question
    """
    if question_name is None:
        question_name = f"{q1.question_name}_{q2.question_name}"
    if q1.question_name not in q2.question_text:
        raise QuestionValueError(
            f"q2 requires a field not present in q1's answer. "
            f"q1: {q1.question_name}, q2: {q2.question_name}"
        )

    def combo(
        scenario: Scenario, agent_traits: dict[str, str] = None
    ) -> QuestionFunctional:
        """Return the answer to the second question given the answer to the first question."""
        # get the answer to the first question
        from ..agents.agent import Agent

        first_answer = (
            q1.by(scenario)
            .by(Agent(traits=agent_traits))
            .run()
            .select(q1.question_name)[0]
        )
        # update the scenario with the answer to the first question
        scenario.update({q1.question_name: first_answer})
        # get the answer to the second question
        second_answer = (
            q2.by(scenario)
            .by(Agent(traits=agent_traits))
            .run()
            .select(q2.question_name)[0]
        )
        return second_answer

    return QuestionFunctional(
        question_name=question_name, question_text="functional", func=combo
    )


# UNCOMMENT BELOW TO SEE HOW THIS WORKS

# if __name__ == "__main__":
#     from edsl.questions import QuestionFreeText, QuestionFunctional
#     from edsl.questions.compose_questions import compose_questions
#     from edsl.scenarios.Scenario import Scenario

#     q1 = QuestionFreeText(
#         question_text="What is the capital of {{country}}", question_name="capital"
#     )
#     q2 = QuestionFreeText(
#         question_text="What is the population of {{capital}}",
#         question_name="population",
#     )
#     q3 = compose_questions(q1, q2)

#     jobs = q3.by(
#         Scenario({"country": "France"}),
#         Scenario({"country": "Germany"}),
#         Scenario({"country": "Greece"}),
#     )

#     print("Without an agent persona")
#     results1 = jobs.run()

#     print("Adding an agent persona")
#     results2 = jobs.by(
#         Agent(traits={"name": "Bob, who always mentions his travel agency."})
#     ).run()
#     results2.select("capital_population").table()

#     q1 = QuestionFreeText(
#         question_text="What is the capital of {{country}}", question_name="capital"
#     )
#     q2 = QuestionFreeText(
#         question_text="Is this {{population}} large?", question_name="population"
#     )
#     q3 = compose_questions(q1, q2)
#     print("Should throw an exception:")
#     try:
#         q3.by(Scenario({"country": "France"})).run()
#     except ValueError as e:
#         print(e)
