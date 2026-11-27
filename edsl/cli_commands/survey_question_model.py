"""Configure per-question inference and inspect the saved survey's prompts."""

import click

from edsl.cli_shared import EXIT_USAGE, EXIT_VALIDATION, error, load_json_object, output


def presentation_warnings(question, prompts):
    """Flag literal authored wording missing from a custom model presentation."""
    text = question.question_text
    if not getattr(question, "_question_presentation", None) or not isinstance(
        text, str
    ):
        return []
    if any(token in text for token in ("{{", "{%", "{#")):
        return []
    wording = " ".join(text.split())
    if wording and all(
        wording not in " ".join(prompts[key].split())
        for key in ("system_prompt", "user_prompt")
    ):
        return [
            f"Custom question_presentation for {question.question_name!r} omits the authored question text from the rendered prompts. "
            "Inspect the respondent wording. Include {{ question_text }} in the presentation if it should be shown."
        ]
    return []


def model_override(question):
    """Describe the runtime override without exposing model connection credentials."""
    return {
        "model": question._model.model,
        "service": question._model._inference_service_,
        "system_prompt": question._system_prompt,
    }


def set_model(survey, name, model, service, system_prompt, clear):
    from edsl import Model
    from edsl.questions.question_base import QuestionBase
    from edsl.questions.question_thinking import thinking_question
    from .survey_edits import replace_question

    question = survey.get(name)
    if clear:
        if not getattr(question, "_is_thinking_question", False):
            return survey
        spec = question.to_dict()
        del spec["thinking_model"]
        spec.pop("thinking_system_prompt", None)
        return replace_question(survey, name, QuestionBase.from_dict(spec))

    selected = Model(model, service_name=service)
    wrapped = thinking_question(question, model=selected, system_prompt=system_prompt)
    revised = replace_question(survey, name, wrapped)
    restored = revised.get(name)
    expected = {"model": model, "service": service, "system_prompt": system_prompt}
    if (
        not getattr(restored, "_is_thinking_question", False)
        or model_override(restored) != expected
    ):
        raise ValueError(
            f"Could not preserve the requested model override on {name!r}."
        )
    return revised


def preview(survey, name, answers, traits, scenario):
    from edsl import Agent, Cache, Model, Scenario

    question = survey.get(name)
    prior_names = survey.question_names[: survey.question_names.index(name)]
    invalid = answers.keys() - set(prior_names)
    if invalid:
        raise ValueError(
            f"Expected earlier question names in --answers. Invalid: {sorted(invalid)}."
        )
    wrapped = getattr(question, "_is_thinking_question", False)
    model = question._model if wrapped else Model("test")
    invigilator = Agent(traits=traits).create_invigilator(
        question=question,
        survey=survey,
        scenario=Scenario(scenario),
        model=model,
        cache=Cache(),
        memory_plan=survey.memory_plan,
        current_answers=answers,
    )
    prompts = invigilator.get_prompts()
    return {
        "question_name": name,
        "question_type": question.question_type,
        "model_override": model_override(question) if wrapped else None,
        "user_prompt": prompts["user_prompt"].text,
        "system_prompt": prompts["system_prompt"].text,
    }


def register(group, edit):
    from .surveys import SurveyEditCommand, _load_survey

    local_file = click.Path(exists=True, dir_okay=False)

    @group.command("set-question-model", cls=SurveyEditCommand)
    @click.argument("survey_path", type=local_file)
    @click.argument("name")
    @click.option("--model", help="Model ID for this question.")
    @click.option("--service", help="Explicit inference service, e.g. openai.")
    @click.option(
        "--system-prompt",
        help="Replace the agent persona for this question. Defaults to empty.",
    )
    @click.option(
        "--clear", is_flag=True, help="Restore the question's normal model and persona."
    )
    @click.option(
        "--output",
        "-o",
        type=click.Path(dir_okay=False),
        help="Defaults to editing the input.",
    )
    def configure(survey_path, name, model, service, system_prompt, clear, output):
        """Give one question its own model and system prompt (thinking_question)."""
        if clear and any(v is not None for v in (model, service, system_prompt)):
            error("USAGE_ERROR", "Use --clear by itself.", exit_code=EXIT_USAGE)
        if not clear and not (model and service):
            error(
                "USAGE_ERROR",
                "Supply --model and --service, or use --clear.",
                exit_code=EXIT_USAGE,
            )
        edit(
            survey_path,
            output,
            lambda survey: set_model(
                survey, name, model, service, system_prompt or "", clear
            ),
        )

    @group.command("preview-prompt")
    @click.argument("survey_path", type=local_file)
    @click.argument("name")
    @click.option(
        "--answers",
        help="Prior answers keyed by question name as a JSON object or file.",
    )
    @click.option("--traits", help="Simulated agent traits as a JSON object or file.")
    @click.option("--scenario", help="Scenario values as a JSON object or file.")
    def preview_prompt(survey_path, name, answers, traits, scenario):
        """Render a question's text prompts locally with sample answers, without inference.

        Uses the saved question model when overridden, otherwise the test model.
        Supply earlier answers to check piping and memory in the rendered user prompt.
        """
        try:
            survey = _load_survey(survey_path, preview=True)
            args = [
                load_json_object(value) if value is not None else {}
                for value in (answers, traits, scenario)
            ]
            data = preview(survey, name, *args)
            output(data, warnings=presentation_warnings(survey.get(name), data))
        except Exception as exc:
            error(
                "VALIDATION_ERROR",
                str(exc),
                suggestion="Check the survey and sample inputs.",
                exit_code=EXIT_VALIDATION,
            )
