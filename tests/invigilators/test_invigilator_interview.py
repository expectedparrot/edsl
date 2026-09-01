import asyncio
import json

from edsl.agents import Agent
from edsl.caching import Cache
from edsl.inference_services.services.test_service import TestService
from edsl.questions import QuestionInterview
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.surveys.memory import MemoryPlan
from edsl.invigilators.invigilator_interview import InvigilatorInterview


def _build_test_model(scripted_func):
    return TestService.create_model("test")(skip_api_key_check=True, func=scripted_func)


def test_question_interview_uses_custom_invigilator():
    question = QuestionInterview.example()
    agent = Agent(traits={"persona": "helpful"})
    invigilator = agent.invigilator.create_invigilator(
        question=question,
        scenario=Scenario(),
        survey=Survey([question]),
        model=_build_test_model(lambda user_prompt, system_prompt, files_list: "done"),
        memory_plan=MemoryPlan(survey=Survey([question])),
        current_answers={},
        cache=Cache(),
    )

    assert isinstance(invigilator, InvigilatorInterview)


def test_interview_invigilator_runs_turn_based_transcript():
    state = {"interviewer": 0, "respondent": 0}

    interviewer_outputs = [
        json.dumps(
            {
                "done": False,
                "acknowledgment": "",
                "question": "What do you like about the product?",
            }
        ),
        json.dumps(
            {
                "done": False,
                "acknowledgment": "Thanks, that helps.",
                "question": "What frustrates you about it?",
            }
        ),
        json.dumps({"done": True, "acknowledgment": "Understood.", "question": ""}),
    ]
    respondent_outputs = [
        "I like how fast it is.",
        "The settings are hard to find.",
    ]

    def scripted_func(user_prompt, system_prompt, files_list):
        if "expert qualitative interviewer" in system_prompt.lower():
            output = interviewer_outputs[state["interviewer"]]
            state["interviewer"] += 1
            return output
        output = respondent_outputs[state["respondent"]]
        state["respondent"] += 1
        return output

    question = QuestionInterview(
        question_name="product_feedback",
        question_text="Understand the respondent's product experience.",
        interview_guide="Cover likes, frustrations, and whether they are done sharing.",
        max_turns=5,
    )
    survey = Survey([question])
    agent = Agent(
        traits={"occupation": "designer"},
        instruction="Answer as if you are the person described.",
    )

    invigilator = agent.invigilator.create_invigilator(
        question=question,
        scenario=Scenario(),
        survey=survey,
        model=_build_test_model(scripted_func),
        memory_plan=MemoryPlan(survey=survey),
        current_answers={},
        cache=Cache(),
    )

    result = asyncio.run(invigilator.async_answer_question())

    assert result.validated is True
    assert len(result.answer) == 4
    assert [message["role"] for message in result.answer] == [
        "interviewer",
        "respondent",
        "interviewer",
        "respondent",
    ]
    assert (
        result.answer[0]["content"][0]["text"] == "What do you like about the product?"
    )
    assert (
        result.answer[2]["content"][0]["text"]
        == "Thanks, that helps.\n\nWhat frustrates you about it?"
    )

    generated = json.loads(result.generated_tokens)
    assert generated["transcript"] == result.answer
    assert len(generated["turns"]) == 5


def test_interview_invigilator_stops_at_max_turns():
    state = {"interviewer": 0, "respondent": 0}

    def scripted_func(user_prompt, system_prompt, files_list):
        if "expert qualitative interviewer" in system_prompt.lower():
            state["interviewer"] += 1
            return json.dumps(
                {
                    "done": False,
                    "acknowledgment": "",
                    "question": f"Question {state['interviewer']}?",
                }
            )
        state["respondent"] += 1
        return f"Answer {state['respondent']}"

    question = QuestionInterview(
        question_name="bounded_interview",
        question_text="Stay bounded.",
        interview_guide="Keep going unless the runner stops you.",
        max_turns=1,
    )
    survey = Survey([question])
    agent = Agent(traits={"occupation": "engineer"})

    invigilator = agent.invigilator.create_invigilator(
        question=question,
        scenario=Scenario(),
        survey=survey,
        model=_build_test_model(scripted_func),
        memory_plan=MemoryPlan(survey=survey),
        current_answers={},
        cache=Cache(),
    )

    result = asyncio.run(invigilator.async_answer_question())

    assert len(result.answer) == 2
    assert state["interviewer"] == 1
    assert state["respondent"] == 1


def test_question_interview_preserves_max_turns_through_serialization():
    question = QuestionInterview(
        question_name="serialized_interview",
        question_text="Verify turn limits survive serialization.",
        interview_guide="Keep this interview short.",
        max_turns=2,
    )

    restored = QuestionInterview.from_dict(question.to_dict())

    assert restored.max_turns == 2


def test_parse_interviewer_decision_accepts_fenced_json():
    decision = InvigilatorInterview._parse_interviewer_decision(
        """```json
{
  "done": true,
  "acknowledgment": "Thanks.",
  "question": ""
}
```"""
    )

    assert decision == {
        "done": True,
        "acknowledgment": "Thanks.",
        "question": "",
    }
