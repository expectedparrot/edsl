"""Describe the local interview settings and render researcher-provided sample answers."""

from copy import copy

from jinja2 import meta

from edsl.utilities.jinja import make_environment


def describe_survey_context(survey, schema, answers=None):
    from edsl.coop.coop_humanize_schema import (
        InterviewHumanizeSchema,
        TextInterviewConfig,
        VoiceInterviewConfig,
    )
    from edsl.invigilators.prompt_constructor import PromptConstructor

    sample_questions = {}
    if answers is not None:
        unknown = answers.keys() - set(survey.question_names)
        if unknown:
            raise ValueError(
                f"Unknown sample answer keys: {', '.join(sorted(unknown))}."
            )

        sample_questions = PromptConstructor._add_answers(
            {q.question_name: copy(q) for q in survey.questions}, answers
        )

    env = make_environment()
    interviews = {}
    question_texts = {}
    warnings = []
    prior = set()
    context = {}
    for q in survey.questions:
        name = q.question_name
        if answers is not None:
            rendered = q.render(context, jinja_env=env, return_dict=True)
            if "question_text" in rendered:
                question_texts[name] = rendered["question_text"]
        if q.question_type == "interview":
            config = InterviewHumanizeSchema.model_validate(
                schema.get("questions", {}).get(name, {})
            )
            languages = {}
            if config.interview_mode in ("text", "both"):
                languages["text"] = (
                    config.text_interview_config or TextInterviewConfig()
                ).language
            if config.interview_mode in ("voice", "both"):
                languages["voice"] = (
                    config.voice_interview_config or VoiceInterviewConfig()
                ).language
            refs = set()
            for template in (q.question_text, q.interview_guide):
                refs.update(meta.find_undeclared_variables(env.parse(template)))
            row = {
                "mode": config.interview_mode,
                "languages": languages,
                "prior_question_references": sorted(refs & prior),
            }
            if answers is not None:
                row["rendered_interview_guide"] = rendered["interview_guide"]
                row["unreferenced_sample_answers"] = sorted(
                    (answers.keys() & prior) - refs
                )
                row["missing_sample_answers"] = sorted((refs & prior) - answers.keys())
                if refs - prior:
                    row["other_template_variables"] = sorted(refs - prior)
            unpiped = sorted(set(survey.memory_plan.get(name, ())) - refs)
            if unpiped:
                sample_pipe = "{{ " + unpiped[0] + ".answer }}"
                warnings.append(
                    {
                        "code": "INTERVIEW_MEMORY_NOT_PIPED",
                        "question": name,
                        "prior_questions": unpiped,
                        "message": (
                            f"The simulation memory for {name!r} includes {', '.join(unpiped)}. "
                            "Its browser interview text and guide do not reference those questions. "
                            f"If the interviewer needs a prior answer, pipe it into the guide, e.g. {sample_pipe}."
                        ),
                    }
                )
            interviews[name] = row
        prior.add(name)
        if answers is not None:
            context[name] = sample_questions[name]
    summary = {}
    if interviews:
        summary["interviews"] = interviews
    if answers is not None:
        summary["rendered_question_texts"] = question_texts
    return summary, warnings
