import pytest
from edsl.questions import QuestionList, QuestionMultipleChoice
from edsl.surveys import Survey
from edsl.agents import Agent, AgentList
from edsl.language_models import LanguageModel


def test_survey_flow():

    a = Agent()
    m = LanguageModel.example("test")

    def f(self, question, scenario):
        if question.question_name == "q1":
            return ["red", "green", "blue"]
        if question.question_name == "q3":
            return "red"

    a.add_direct_question_answering_method(f)

    q1 = QuestionList(
        question_name="q1",
        question_text="What are your 3 favorite colors?",
        max_list_items=3,
    )

    q3 = QuestionMultipleChoice(
        question_name="q3",
        question_text="Which color is your #1 favorite?",
        question_options=["{{ q1.answer[0] }}", "{{ q1.answer[1] }}"],
    )

    survey = Survey([q1, q3])
    results = survey.by(a).by(m).run()
    assert results.select("q1", "q3").to_list() == [(["red", "green", "blue"], "red")]


def test_alt_piping():
    # this one uses a test model to return the answers
    from edsl.language_models.model import Model

    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """["Reading", "Sailing"]"""
            else:
                return "Sailing"

        return two_responses

    m = Model("test", func=two_responses_closure())
    q1 = QuestionList(question_text="What are your hobbies?", question_name="hobbies")
    q2 = QuestionMultipleChoice(
        question_text="Which is our favorite?",
        question_options=["{{hobbies.answer[0]}}", "{{hobbies.answer[1]}}"],
        question_name="favorite_hobby",
    )
    s = Survey([q1, q2])
    results = s.by(m).run(
        progress_bar=False,
        cache=False,
        disable_remote_cache=True,
        disable_remote_inference=True,
    )
    # assert results.select("answer.*").to_list() == [(["Reading", "Sailing"], "Sailing")]


def test_comment_piping():

    from edsl import QuestionFreeText, Model

    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """Parrots\nI think they are cool"""
            else:
                return "Oh, I love parrots!"

        return two_responses

    q1 = QuestionMultipleChoice(
        question_text="What is your favorite kind of bird?",
        question_name="bird",
        question_options=["Parrots", "Owls", "Eagles"],
    )
    q2 = QuestionFreeText(
        question_text="Why do you like {{ bird.answer }} - you also said {{ bird.comment}}?",
        question_name="why_bird",
    )
    m = Model("test", func=two_responses_closure())
    s = Survey([q1, q2])
    results = s.by(m).run()

    assert (
        results.select("prompt.why_bird_user_prompt").first().text
        == "Why do you like Parrots - you also said I think they are cool?"
    )


def test_option_piping_across_agents():
    """Test that option piping works correctly across different agents without bleed-over.
    
    This test reproduces the bug fix where q1 answers were bleeding across agents.
    Each agent should see their own q1 answers as options for q2.
    """
    # Create agents with distinct personas
    a1 = Agent(name="botanist", traits={"persona": "botanist who picks really weird colors"})
    a2 = Agent(name="economist", traits={"persona": "economist"})
    agents = AgentList([a1, a2])

    # Create scripted responses for the two agents
    scripted_responses = {
        'botanist': {
            'q1': ['moss green', 'rust red', 'deep purple', 'ocean teal'],
            'q2': 'moss green'
        },
        'economist': {
            'q1': ["market green", "bull gold", "bear red", "neutral blue"],
            'q2': 'bear red'
        }
    }

    # Create the scripted response model
    model = LanguageModel.from_scripted_responses(scripted_responses)

    # Create the survey with piping
    q1 = QuestionList(
        question_name="q1",
        question_text="What colors do you like?",
        min_list_items=3,
        max_list_items=5,
    )

    # q2 pipes q1's answer as the options
    q2 = QuestionMultipleChoice(
        question_name="q2", 
        question_text="Which color is your favorite?",
        question_options="{{ q1.answer }}",
    )

    survey = Survey(questions=[q1, q2])

    # Run the survey
    results = survey.by(agents).by(model).run(
        n=1, 
        disable_remote_inference=True,
        refresh=True,
        fresh=True,
        cache=False,
        stop_on_exceptions=True
    )

    # Verify results - each agent should get their own q1 answers as q2 options
    results_data = results.select("agent.agent_name", "answer.q1", "question_options.q2_question_options", "answer.q2").to_list()
    
    botanist_result = None
    economist_result = None
    
    for result in results_data:
        agent_name, q1_answer, q2_options, q2_answer = result
        if agent_name == "botanist":
            botanist_result = result
        elif agent_name == "economist":
            economist_result = result
    
    # Verify botanist got their own options
    assert botanist_result is not None, "Botanist result not found"
    botanist_name, botanist_q1, botanist_q2_options, botanist_q2 = botanist_result
    assert set(botanist_q2_options) == set(['moss green', 'rust red', 'deep purple', 'ocean teal'])
    assert botanist_q2 == 'moss green'
    
    # Verify economist got their own options  
    assert economist_result is not None, "Economist result not found"
    economist_name, economist_q1, economist_q2_options, economist_q2 = economist_result
    assert set(economist_q2_options) == set(["market green", "bull gold", "bear red", "neutral blue"])
    assert economist_q2 == 'bear red'
    
    # Verify no bleed-over: botanist options should not contain economist colors
    botanist_colors = set(botanist_q2_options)
    economist_colors = set(economist_q2_options)
    assert botanist_colors.isdisjoint(economist_colors), "Agent answers bled over - botanist got economist colors"


if __name__ == "__main__":
    pytest.main()
