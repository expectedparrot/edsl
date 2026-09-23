"""Fluent workload definitions and compilation for independent judgments."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass
from itertools import product

from jinja2 import StrictUndefined, meta
from edsl.utilities.jinja import make_environment

from edsl.base import PersistenceMixin
from .model import JudgmentModel
from .persistence import evaluation_git


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


class EvaluationValidationError(ValueError):
    def __init__(self, errors):
        self.errors = list(dict.fromkeys(errors))
        super().__init__(
            "Evaluation cannot be compiled:\n"
            + "\n".join(f"- {e}" for e in self.errors)
        )


@dataclass
class EvaluationBatch:
    row: int
    model: JudgmentModel
    state: dict
    questions: dict

    def to_dict(self):
        return {
            "row": self.row,
            "model": self.model.to_dict(),
            "state": self.state,
            "questions": self.questions,
        }


@dataclass
class EvaluationRow:
    agent: object
    scenario: object
    model: JudgmentModel
    iteration: int
    questions: dict
    indices: dict


class EvaluationPlan:
    """An inspectable snapshot of a validated workload; never uses Jobs/Runner."""

    def __init__(self, survey, rows, batches):
        self.survey = survey
        self.rows = rows
        self.batches = batches

    def to_dict(self):
        return {
            "result_count": len(self.rows),
            "request_count": len(self.batches),
            "batches": [b.to_dict() for b in self.batches],
        }

    async def run_async(self, *, cache=None, max_concurrency=8):
        from .executor import execute

        return await execute(self, cache=cache, max_concurrency=max_concurrency)

    def run(self, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("An event loop is running; use await plan.run_async()")
        return asyncio.run(self.run_async(**kwargs))

    def __repr__(self):
        return f"EvaluationPlan(results={len(self.rows)}, requests={len(self.batches)})"


class Evaluation(PersistenceMixin):
    """Bind a survey to contexts and judgment models using ``.by()``.

    Only independent questions are supported. Compilation checks the complete
    workload before any inference. Every scenario field is included in state.
    """

    git = evaluation_git()

    def __init__(self, survey, *, scenarios=None, agents=None, models=None):
        self.survey = survey
        self.scenarios = []
        self.agents = []
        self.models = []
        for objects in (scenarios, agents, models):
            if objects is not None:
                self.by(objects)

    def by(self, *objects):
        from edsl import Agent, Scenario
        from edsl.dataset import Dataset

        if len(objects) == 1 and isinstance(objects[0], Dataset):
            objects = (objects[0].to_scenario_list(),)
        if len(objects) == 1 and not isinstance(
            objects[0], (Agent, Scenario, JudgmentModel)
        ):
            try:
                objects = tuple(objects[0])
            except TypeError:
                raise TypeError(
                    "by() expects agents, scenarios, or JudgmentModel objects"
                ) from None
        if not objects:
            raise ValueError("by() requires a nonempty collection")
        for kind, key in (
            (Agent, "agents"),
            (Scenario, "scenarios"),
            (JudgmentModel, "models"),
        ):
            if all(isinstance(obj, kind) for obj in objects):
                current = getattr(self, key)
                if key == "models":
                    # Match Jobs' model replacement semantics on subsequent by().
                    updated = list(objects)
                elif current:
                    from edsl.jobs.jobs_component_constructor import (
                        JobsComponentConstructor,
                    )

                    updated = list(
                        JobsComponentConstructor._merge_objects(objects, current)
                    )
                else:
                    updated = list(objects)
                setattr(self, key, updated)
                return self
        raise TypeError(
            "Each by() call needs a homogeneous collection of agents, scenarios, or JudgmentModel objects"
        )

    def compile(self, *, n=1, max_questions_per_request=None):
        from edsl import Agent, Scenario, Survey

        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("n must be a positive integer")
        if max_questions_per_request is not None and (
            isinstance(max_questions_per_request, bool)
            or not isinstance(max_questions_per_request, int)
            or max_questions_per_request < 1
        ):
            raise ValueError("max_questions_per_request must be a positive integer")
        errors = []
        if not self.models:
            errors.append("Supply at least one JudgmentModel with .by(models)")
        if not self.survey.questions:
            errors.append("The survey has no questions")
        if self.survey.rule_collection.non_default_rules:
            errors.append("Survey branching/skip/stop rules are unsupported")
        if any(
            m.get("prior_questions")
            for m in self.survey.memory_plan.to_dict()["data"].values()
        ):
            errors.append("Survey memory is unsupported")
        if self.survey.questions_to_randomize or self.survey.options_to_pin:
            errors.append("Survey option randomization/pinning is unsupported")
        survey = Survey.from_dict(self.survey.to_dict())
        agents = self.agents or [Agent(instruction="Evaluate the supplied context.")]
        scenarios = self.scenarios or [Scenario({})]
        rows, batches = [], []
        for (ai, agent), (si, scenario), (mi, model), iteration in product(
            enumerate(agents), enumerate(scenarios), enumerate(self.models), range(n)
        ):
            label = f"{model.model}, agent {ai}, scenario {si}"
            try:
                if getattr(agent, "dynamic_traits_function", None) or hasattr(
                    agent, "answer_question_directly"
                ):
                    raise ValueError(
                        "Dynamic traits/direct-answer agents are unsupported"
                    )
                if getattr(agent, "set_traits_presentation_template", False):
                    raise ValueError(
                        "Custom agent presentation templates are unsupported"
                    )
                # JSON validation rejects file objects and arbitrary Python state.
                state = json.loads(
                    canonical(
                        {
                            "scenario": dict(scenario),
                            "agent": {
                                "traits": dict(agent.traits),
                                "codebook": dict(agent.codebook),
                            },
                        }
                    )
                )
                context = {
                    **dict(scenario),
                    "scenario": dict(scenario),
                    "agent": {**agent.traits, "traits": dict(agent.traits)},
                }
                rendered, questions = {}, {}
                for question in survey.questions:
                    try:
                        rendered_q, definition = compile_question(
                            survey, question, context, agent, model
                        )
                        rendered[question.question_name] = rendered_q
                        questions[question.question_name] = definition
                    except (ValueError, TypeError, KeyError) as exc:
                        errors.append(f"{label}, {question.question_name}: {exc}")
                row_index = len(rows)
                rows.append(
                    EvaluationRow(
                        copy.deepcopy(agent),
                        copy.deepcopy(scenario),
                        copy.deepcopy(model),
                        iteration,
                        rendered,
                        {"agent": ai, "scenario": si, "model": mi},
                    )
                )
                limit = max_questions_per_request or len(questions) or 1
                if not model.capabilities.batching:
                    limit = 1
                group = {}
                for name, definition in questions.items():
                    single = {name: definition}
                    if (
                        len(
                            canonical({"state": state, "question": definition}).encode()
                        )
                        > model.capabilities.max_context_bytes
                    ):
                        errors.append(
                            f"{label}, {name}: state plus question exceeds the context byte budget"
                        )
                        continue

                    def request_size(qs):
                        return len(
                            canonical(
                                {"model": model.model, "state": state, "questions": qs}
                            ).encode()
                        )

                    if request_size(single) > model.capabilities.max_request_bytes:
                        errors.append(
                            f"{label}, {name}: exceeds the request byte budget"
                        )
                        continue
                    if group and (
                        len(group) >= limit
                        or request_size({**group, **single})
                        > model.capabilities.max_request_bytes
                    ):
                        batches.append(
                            EvaluationBatch(row_index, rows[-1].model, state, group)
                        )
                        group = {}
                    group.update(single)
                if group:
                    batches.append(
                        EvaluationBatch(row_index, rows[-1].model, state, group)
                    )
            except (ValueError, TypeError) as exc:
                errors.append(f"{label}: {exc}")
        if errors:
            raise EvaluationValidationError(errors)
        return EvaluationPlan(survey, rows, batches)

    def run(self, *, n=1, max_questions_per_request=None, **kwargs):
        return self.compile(
            n=n, max_questions_per_request=max_questions_per_request
        ).run(**kwargs)

    async def run_async(self, *, n=1, max_questions_per_request=None, **kwargs):
        return await self.compile(
            n=n, max_questions_per_request=max_questions_per_request
        ).run_async(**kwargs)

    def to_dict(self, add_edsl_version=True):
        data = {
            "survey": self.survey.to_dict(add_edsl_version=add_edsl_version),
            **{
                key: [
                    obj.to_dict(add_edsl_version=add_edsl_version)
                    for obj in getattr(self, key)
                ]
                for key in ("agents", "scenarios", "models")
            },
        }
        if add_edsl_version:
            from edsl import __version__

            data.update(edsl_class_name="Evaluation", edsl_version=__version__)
        return data

    @classmethod
    def from_dict(cls, data):
        from edsl import Survey, Agent, Scenario

        evaluation = cls(Survey.from_dict(data["survey"]))
        for key, kind in (
            ("agents", Agent),
            ("scenarios", Scenario),
            ("models", JudgmentModel),
        ):
            setattr(evaluation, key, [kind.from_dict(d) for d in data[key]])
        return evaluation

    def __repr__(self):
        return (
            f"Evaluation(questions={len(self.survey.questions)}, scenarios={len(self.scenarios)}, "
            f"agents={len(self.agents)}, models={len(self.models)})"
        )


def compile_question(survey, question, context, agent, model):
    from jinja2 import TemplateError

    if question.question_type not in {"multiple_choice", "linear_scale", "yes_no"}:
        raise ValueError(f"unsupported question type {question.question_type!r}")
    if getattr(question, "_question_presentation", None) or getattr(
        question, "_answering_instructions", None
    ):
        raise ValueError(
            "Custom question presentation/answering templates are unsupported; use survey instructions"
        )
    env = make_environment(undefined=StrictUndefined)
    # Detect piping even if a scenario field happens to shadow a question name.
    serialized = canonical(question.to_dict(add_edsl_version=False))
    dependencies = meta.find_undeclared_variables(env.parse(serialized)) & set(
        survey.question_names
    )
    if dependencies:
        raise ValueError(f"Answer piping is unsupported: {sorted(dependencies)}")
    try:

        def check_templates(value):
            if isinstance(value, str):
                env.from_string(value).render(context)
            elif isinstance(value, dict):
                for item in value.values():
                    check_templates(item)
            elif isinstance(value, list):
                for item in value:
                    check_templates(item)

        check_templates(question.to_dict(add_edsl_version=False))
        rendered = question.render(context, jinja_env=env)
        remaining = meta.find_undeclared_variables(
            env.parse(canonical(rendered.to_dict(add_edsl_version=False)))
        )
        if remaining:
            raise ValueError(f"Unresolved template variables: {sorted(remaining)}")
        instructions = [str(env.from_string(agent.instruction).render(context))]
        instructions.extend(
            str(env.from_string(i.text).render(context))
            for i in survey._relevant_instructions(question)
        )
        instructions.append(rendered.question_text)
    except (TemplateError, ValueError) as exc:
        raise ValueError(f"Cannot render question/context: {exc}") from exc
    options = rendered.question_options
    if not isinstance(options, list) or len(options) < 2:
        raise ValueError("At least two concrete options are required")
    if any(
        not isinstance(o, (str, int, float)) or isinstance(o, bool) for o in options
    ):
        raise ValueError("Options must be strings or numbers")
    if len({str(o) for o in options}) != len(options):
        raise ValueError("Options must have distinct string representations")
    primitive = "choice"
    criteria = {str(i): str(o) for i, o in enumerate(options)}
    if question.question_type == "linear_scale":
        primitive = "score"
        labels = rendered.option_labels or {}
        if any(o not in labels or not str(labels[o]).strip() for o in options):
            raise ValueError(
                "Score requires a descriptive option_label for every scale level"
            )
        criteria = [str(labels[o]) for o in options]
        if len(options) > model.capabilities.max_levels:
            raise ValueError(
                f"Score supports at most {model.capabilities.max_levels} levels"
            )
    elif question.question_type == "yes_no":
        if [str(o).lower() for o in options] not in (["no", "yes"], ["yes", "no"]):
            raise ValueError("Binary judgments require explicit Yes/No options")
        primitive = "binary"
        criteria = {"true": "Yes", "false": "No"}
    if primitive not in model.capabilities.primitives:
        raise ValueError(f"Model does not support {primitive} judgments")
    if len(options) > model.capabilities.max_options:
        raise ValueError(
            f"Model supports at most {model.capabilities.max_options} options"
        )
    return rendered, {
        "type": primitive,
        "instructions": "\n\n".join(instructions),
        "criteria": criteria,
    }
