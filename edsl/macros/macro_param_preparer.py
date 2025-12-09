from __future__ import annotations

from typing import Any, Optional

from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..agents import AgentList
from ..base import RegisterSubclassesMeta
from ..questions.register_questions_meta import RegisterQuestionsMeta


class MacroParamPreparer:
    @staticmethod
    def prepare(macro: Any, params: Any):
        """Derive head attachments exclusively from the initial_survey answers."""
        if not isinstance(params, dict):
            raise TypeError(
                "Macro.output expects a params dict keyed by initial_survey question names. Got: "
                + type(params).__name__
            )

        survey_question_names = {q.question_name for q in macro.initial_survey}
        unknown_keys = [k for k in params.keys() if k not in survey_question_names]
        if unknown_keys:
            raise ValueError(
                f"Params contain keys not in initial_survey: {sorted(unknown_keys)}. "
                f"Survey question names: {sorted(survey_question_names)}"
            )

        scenario_attachment: Optional[ScenarioList | Scenario] = None
        survey_attachment: Optional[Survey] = None
        agent_list_attachment: Optional[AgentList] = None

        # Track destination occupancy to enforce uniqueness
        dest_assigned = {"scenario": False, "survey": False, "agent_list": False}

        # For scenario variables from non-edsl questions
        scenario_vars: dict[str, Any] = {}

        # Registries for constructing objects from dicts
        question_registry = RegisterQuestionsMeta.question_types_to_classes()
        edsl_registry = RegisterSubclassesMeta.get_registry()

        # Iterate in the order of the survey questions
        for q in macro.initial_survey:
            q_name = q.question_name
            if q_name not in params:
                continue
            answer_value = params[q_name]

            if q.question_type == "edsl_object":
                # Instantiate the object from the provided dict (or pass-through if already an instance)
                expected_type = q.expected_object_type
                obj_instance: Any = None
                if answer_value is None:
                    obj_instance = None
                elif not isinstance(answer_value, dict):
                    # Allow passing pre-instantiated objects
                    obj_instance = answer_value
                else:
                    # Map expected type to a class
                    if expected_type in question_registry:
                        target_cls = question_registry[expected_type]
                    else:
                        target_cls = edsl_registry.get(expected_type)
                    if target_cls is None:
                        raise ValueError(
                            f"Unknown expected_object_type '{expected_type}' for question '{q_name}'."
                        )
                    if hasattr(target_cls, "from_dict"):
                        obj_instance = target_cls.from_dict(answer_value)
                    else:
                        obj_instance = target_cls(**answer_value)

                # Attach by destination
                from ..agents import Agent as _Agent

                if isinstance(obj_instance, (Scenario, ScenarioList)):
                    if dest_assigned["scenario"]:
                        raise ValueError(
                            "Only one scenario attachment is allowed (Scenario or ScenarioList)."
                        )
                    scenario_attachment = obj_instance
                    dest_assigned["scenario"] = True
                elif isinstance(obj_instance, Survey):
                    if dest_assigned["survey"]:
                        raise ValueError("Only one Survey attachment is allowed.")
                    survey_attachment = obj_instance
                    dest_assigned["survey"] = True
                elif isinstance(obj_instance, AgentList) or isinstance(
                    obj_instance, _Agent
                ):
                    if dest_assigned["agent_list"]:
                        raise ValueError(
                            "Only one AgentList/Agent attachment is allowed."
                        )
                    agent_list_attachment = (
                        obj_instance
                        if isinstance(obj_instance, AgentList)
                        else AgentList([obj_instance])
                    )
                    dest_assigned["agent_list"] = True
                else:
                    # Other EDSL objects are not attached to head; ignore here
                    pass
            else:
                # Non-EDSL answers are considered scenario variables
                value = answer_value
                # Normalize file uploads based on the initial_survey metadata
                if q.question_type == "file_upload":
                    try:
                        from ..scenarios import FileStore

                        # Handle both string paths and FileStore dicts
                        if isinstance(value, str):
                            # String path - use path parameter
                            value = FileStore(path=value)
                        elif isinstance(value, FileStore):
                            # Already a FileStore - keep as-is
                            pass
                        else:
                            value = answer_value
                    except Exception:
                        value = answer_value
                scenario_vars[q_name] = value

        # If no edsl scenario provided but we have scenario variables, build a single Scenario
        if not dest_assigned["scenario"] and scenario_vars:
            scenario_attachment = Scenario(scenario_vars)
            dest_assigned["scenario"] = True

        # Local import avoids circular dependency at module import time
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
