from typing import TYPE_CHECKING
from typing import Callable
from edsl.agents import Agent
#from edsl.surveys import Survey

if TYPE_CHECKING:
    from edsl.surveys import Survey
    from edsl.results import Results
    from edsl.questions import QuestionBase

class Simulator:
    def __init__(self, survey: "Survey"):
        self.survey = survey

    @classmethod
    def random_survey(cls):
        """Create a random survey."""
        from edsl.questions import QuestionMultipleChoice, QuestionFreeText
        from random import choice
        from edsl.surveys import Survey

        num_questions = 10
        questions = []
        for i in range(num_questions):
            if choice([True, False]):
                q = QuestionMultipleChoice(
                    question_text="nothing",
                    question_name="q_" + str(i),
                    question_options=list(range(3)),
                )
                questions.append(q)
            else:
                questions.append(
                    QuestionFreeText(
                        question_text="nothing", question_name="q_" + str(i)
                    )
                )
        s = Survey(questions)
        start_index = choice(range(num_questions - 1))
        end_index = choice(range(start_index + 1, 10))
        s = s.add_rule(f"q_{start_index}", "True", f"q_{end_index}")
        question_to_delete = choice(range(num_questions))
        s.delete_question(f"q_{question_to_delete}")
        return s

    def simulate(self) -> dict:
        """Simulate the survey and return the answers."""
        i = self.survey.gen_path_through_survey()
        q = next(i)
        num_passes = 0
        while True:
            num_passes += 1
            try:
                answer = q._simulate_answer()
                q = i.send({q.question_name: answer["answer"]})
            except StopIteration:
                break

            if num_passes > 100:
                print("Too many passes.")
                from .exceptions import SurveyError
                raise SurveyError("Too many passes.")
        return self.survey.answers

    def create_agent(self) -> "Agent":
        """Create an agent from the simulated answers."""
        answers_dict = self.survey.simulate()
        from edsl.agents import Agent

        def construct_answer_dict_function(traits: dict) -> Callable:
            def func(self, question: "QuestionBase", scenario=None):
                return traits.get(question.question_name, None)

            return func

        return Agent(traits=answers_dict).add_direct_question_answering_method(
            construct_answer_dict_function(answers_dict)
        )

    def simulate_results(self) -> "Results":
        """Simulate the survey and return the results."""
        a = self.create_agent()
        return self.survey.by([a]).run()
