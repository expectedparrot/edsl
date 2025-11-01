from __future__ import annotations

from typing import Any


class MacroValidator:
    @staticmethod
    def validate_parameters(macro: Any) -> None:
        # macro.parameters_scenario_list returns a ScenarioList, iterate over it to get question_name
        input_survey_params = [param["question_name"] for param in macro.parameters_scenario_list]
        head_params = macro.jobs_object.head_parameters

        # If the initial survey declares an EDSL object that supplies scenarios or a survey,
        # scenario fields may originate from that object rather than direct survey question names.
        has_object_driven_scenarios = False
        for q in macro.initial_survey:
            if q.question_type != "edsl_object":
                continue
            expected_type = q.expected_object_type
            if expected_type in ("Survey", "Scenario", "ScenarioList"):
                has_object_driven_scenarios = True
                break

        for param in head_params:
            if "." not in param:
                continue  # not a scenario parameter - could be a calculated field, for example
            prefix, param_name = param.split(".")
            if prefix != "scenario":
                continue
            if has_object_driven_scenarios:
                # Skip strict name check; fields come from attached object
                continue
            if param_name not in input_survey_params:
                raise ValueError(
                    f"The parameter {param_name} is not in the input survey."
                    f"Input survey parameters: {input_survey_params}, Head job parameters: {head_params}"
                )

        if macro.jobs_object.has_post_run_methods:
            raise ValueError(
                "Cannot have post_run_methods in the jobs object if using output formatters."
            )

        # Ensure reserved formatter key exists and is correctly mapped
        try:
            _ = macro.output_formatters.get_formatter("raw_results")
        except Exception:
            raise ValueError(
                "OutputFormatters must include a reserved 'raw_results' formatter."
            )

    @staticmethod
    def validate_initial_survey_edsl_uniqueness(macro: Any) -> None:
        """Ensure at most one EDSL object per attachment destination is requested by the initial_survey."""
        counts = {"scenario": 0, "survey": 0, "agent_list": 0}
        for q in macro.initial_survey:
            if q.question_type != "edsl_object":
                continue
            expected = q.expected_object_type
            if expected is None:
                continue
            if expected in ("Scenario", "ScenarioList"):
                counts["scenario"] += 1
            elif expected == "Survey":
                counts["survey"] += 1
            elif expected in ("Agent", "AgentList"):
                counts["agent_list"] += 1

        errors: list[str] = []
        for dest, cnt in counts.items():
            if cnt > 1:
                errors.append(
                    f"initial_survey requests multiple EDSL objects for '{dest}' attachments ({cnt} found)"
                )
        if errors:
            raise ValueError(
                "Only one EDSL object of each type can be provided by the initial_survey: "
                + "; ".join(errors)
            )
