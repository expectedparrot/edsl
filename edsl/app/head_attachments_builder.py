from __future__ import annotations
from typing import Any


class HeadAttachmentsBuilder:
    """Build `HeadAttachments` from app params and initial survey.

    Extracted from `App._prepare_from_params` for clarity and testability.
    """

    @staticmethod
    def build(app: "App", params: dict[str, Any]):
        from ..scenarios import Scenario, ScenarioList
        from ..surveys import Survey
        from ..agents import AgentList

        # Validate params shape
        if not isinstance(params, dict):
            raise TypeError(
                "App.output expects a params dict keyed by initial_survey question names. Got: "
                + type(params).__name__
            )

        # Unknown keys validation (allow fixed params)
        survey_question_names = {q.question_name for q in app.initial_survey}
        fixed_names = set(getattr(app, "fixed_params", {}).keys())
        unknown_keys = [
            k for k in params.keys() if k not in survey_question_names and k not in fixed_names
        ]
        if unknown_keys:
            raise ValueError(
                f"Params contain keys not in initial_survey: {sorted(unknown_keys)}. "
                f"Survey question names: {sorted(survey_question_names)}"
            )

        scenario_attachment: ScenarioList | Scenario | None = None
        survey_attachment: Survey | None = None
        agent_list_attachment: AgentList | None = None

        dest_assigned = {"scenario": False, "survey": False, "agent_list": False}
        scenario_vars: dict[str, Any] = {}

        # Value transformers keyed by question_type
        def _identity(v: Any) -> Any:
            return v

        def _to_filestore(v: Any) -> Any:
            try:
                from ..scenarios import FileStore

                return FileStore(path=v)
            except Exception:
                return v

        value_transformers = {
            "file_upload": _to_filestore,
        }

        # Registries
        from ..base import RegisterSubclassesMeta
        from ..questions.register_questions_meta import RegisterQuestionsMeta
        question_registry = RegisterQuestionsMeta.question_types_to_classes()
        edsl_registry = RegisterSubclassesMeta.get_registry()

        from ..agents import Agent as _Agent

        def _attach_scenario(obj: Any) -> None:
            nonlocal scenario_attachment
            if dest_assigned["scenario"]:
                raise ValueError(
                    "Only one scenario attachment is allowed (Scenario or ScenarioList)."
                )
            scenario_attachment = obj
            dest_assigned["scenario"] = True

        def _attach_survey(obj: Any) -> None:
            nonlocal survey_attachment
            if dest_assigned["survey"]:
                raise ValueError("Only one Survey attachment is allowed.")
            survey_attachment = obj
            dest_assigned["survey"] = True

        def _attach_agent(obj: Any) -> None:
            nonlocal agent_list_attachment
            if dest_assigned["agent_list"]:
                raise ValueError("Only one AgentList/Agent attachment is allowed.")
            agent_list_attachment = (
                obj if isinstance(obj, AgentList) else AgentList([obj])
            )
            dest_assigned["agent_list"] = True

        attach_dispatch: list[tuple[tuple[type, ...], Any]] = [
            ((Scenario, ScenarioList), _attach_scenario),
            ((Survey,), _attach_survey),
            ((AgentList, _Agent), _attach_agent),
        ]

        def _instantiate_edsl_object(
            expected_type: str, answer_value: Any, question_name: str
        ) -> tuple[bool, Any]:
            if answer_value is None:
                return False, None
            if not isinstance(answer_value, dict):
                return True, answer_value
            if expected_type in question_registry:
                target_cls = question_registry[expected_type]
            else:
                target_cls = edsl_registry.get(expected_type)
            if target_cls is None:
                raise ValueError(
                    f"Unknown expected_object_type '{expected_type}' for question '{question_name}'."
                )
            if hasattr(target_cls, "from_dict"):
                return True, target_cls.from_dict(answer_value)
            return True, target_cls(**answer_value)

        for q in app.initial_survey:
            q_name = q.question_name
            if q_name not in params:
                continue
            answer_value = params[q_name]

            if q.question_type == "edsl_object":
                present, obj_instance = _instantiate_edsl_object(
                    q.expected_object_type, answer_value, q_name
                )
                if not present:
                    continue
                for types, handler in attach_dispatch:
                    if isinstance(obj_instance, types):
                        handler(obj_instance)
                        break
            else:
                transform = value_transformers.get(q.question_type, _identity)
                scenario_vars[q_name] = transform(answer_value)

        for k, v in getattr(app, "fixed_params", {}).items():
            if k not in scenario_vars:
                scenario_vars[k] = v

        if not dest_assigned["scenario"] and scenario_vars:
            scenario_attachment = Scenario(scenario_vars)
            dest_assigned["scenario"] = True

        from .head_attachments import HeadAttachments

        return HeadAttachments(
            scenario=(
                scenario_attachment
                if isinstance(scenario_attachment, (Scenario, ScenarioList))
                else None
            ),
            survey=survey_attachment,
            agent_list=agent_list_attachment,
        )


