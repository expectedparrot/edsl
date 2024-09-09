from edsl.agents.Invigilator import InvigilatorAI
from edsl import Agent
from edsl.data import Cache
from edsl.prompts.Prompt import Prompt

c = Cache()
a = Agent()

from edsl.questions import QuestionNumerical

q = QuestionNumerical.example()


class InvigilatorTest(InvigilatorAI):
    def get_prompts(self):
        return {
            "user_prompt": Prompt("XX1XX"),
            "system_prompt": Prompt("XX1XX"),
        }


def test_good_answer_cached():
    cache = Cache()
    from edsl import Model

    m = Model("test", canned_response=1)
    results = q.by(m).run(cache=cache)
    results.select("answer.*").print()
    assert cache.data != {}
