from types import SimpleNamespace

import pytest

from edsl import (
    Agent,
    QuestionBudget,
    QuestionCheckBox,
    QuestionCompute,
    QuestionFreeText,
    Scenario,
    Survey,
)
from edsl.inference_services.services.test_service import TestService
from edsl.runner.direct_answer import DirectAnswerEntry, DirectAnswerRegistry


@pytest.mark.asyncio
async def test_compute_direct_answer_receives_prior_answer_piping_context():
    prior = QuestionFreeText(question_name="channels", question_text="Channels?")
    compute = QuestionCompute(
        question_name="clean_channels",
        question_text="{{ channels.answer }}",
    )
    survey = Survey([prior, compute])

    service = SimpleNamespace(
        _gather_current_answers=lambda job_id, interview_id: {
            "channels": ["Channel A", "Channel B"],
            "channels.answer": ["Channel A", "Channel B"],
        },
        _jobs=SimpleNamespace(get_survey=lambda job_id: survey.to_dict()),
    )
    registry = DirectAnswerRegistry(job_service=service)
    entry = DirectAnswerEntry(
        task_id="compute-task",
        execution_type="functional",
        agent=None,
        question=compute,
        scenario=Scenario(),
        job_id="job",
        interview_id="interview",
    )
    registry.register(entry.task_id, entry)

    result = await registry.execute(entry.task_id)

    assert result["answer"] == "['Channel A', 'Channel B']"


def test_compute_answer_can_supply_dynamic_budget_options_without_memory():
    channels = QuestionCheckBox(
        question_name="channels",
        question_text="Which channels are used?",
        question_options=["Channel A", "Channel B", "Channel C", "Channel D"],
        min_selections=2,
    )
    clean_channels = QuestionCompute(
        question_name="clean_channels",
        question_text="{{ channels.answer | map('trim') | list }}",
    )
    allocation = QuestionBudget(
        question_name="allocation",
        question_text="Allocate channel spend.",
        question_options="{{ clean_channels.answer }}",
        budget_sum=100,
    )
    survey = Survey([channels, clean_channels, allocation])

    def scripted_response(user_prompt, system_prompt, files_list):
        if "Allocate your budget" in user_prompt:
            return "[20,24,28,28]"
        return '["Channel A","Channel B","Channel C","Channel D"]'

    model = TestService.create_model("test")(
        skip_api_key_check=True,
        func=scripted_response,
    )

    results = (
        survey.by(Agent())
        .by(model)
        .run(
            disable_remote_inference=True,
            stop_on_exception=True,
            cache=False,
        )
    )

    row = results.select(
        "answer.channels",
        "answer.clean_channels",
        "answer.allocation",
    ).to_list()[0]
    assert row == (
        ["Channel A", "Channel B", "Channel C", "Channel D"],
        "['Channel A', 'Channel B', 'Channel C', 'Channel D']",
        [20.0, 24.0, 28.0, 28.0],
    )
