"""
Result Inspector Widget

An anywidget for inspecting individual EDSL Results with detailed views of agent,
scenario, model, answers, prompts, and raw data structure.
"""

import json
import traitlets
from .inspector_widget import InspectorWidget


class ResultInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting individual EDSL Result objects with detailed exploration."""

    widget_short_name = "result_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "Result"

    # Result-specific data traitlet for JavaScript frontend
    result_data = traitlets.Dict().tag(sync=True)

    def _process_object_data(self):
        if not self.object or not self.data:
            return

        result = self.data

        formatted_result = {}
        formatted_result["num_questions"] = len(result["answer"])
        transcript = []
        for question_name, question_data in result["question_to_attributes"].items():
            transcript.append(
                {
                    "question_name": question_name,
                    "question_text": question_data["question_text"],
                    "comment": result["comments_dict"][f"{question_name}_comment"],
                    "answer": str(result["answer"][question_name]),
                }
            )
        formatted_result["transcript"] = transcript

        model = {
            "model": result["model"]["model"],
            "inference_service": result["model"]["inference_service"],
            "parameters": [
                {
                    "parameter_name": key.replace("_", " "),
                    "parameter_value": str(value),
                }
                for key, value in result["model"]["parameters"].items()
            ],
        }
        formatted_result["model"] = model

        prompts = []
        for question_name, _ in result["question_to_attributes"].items():
            prompts.append(
                {
                    "question_name": question_name,
                    "user_prompt": result["prompt"][f"{question_name}_user_prompt"][
                        "text"
                    ],
                    "system_prompt": result["prompt"][f"{question_name}_system_prompt"][
                        "text"
                    ],
                    "generated_tokens": result["generated_tokens"][
                        f"{question_name}_generated_tokens"
                    ],
                }
            )
        formatted_result["prompts"] = prompts

        costs = []
        for question_name, _ in result["question_to_attributes"].items():
            costs.append(
                {
                    "question_name": question_name,
                    "input_tokens": result["raw_model_response"][
                        f"{question_name}_input_tokens"
                    ],
                    "output_tokens": result["raw_model_response"][
                        f"{question_name}_output_tokens"
                    ],
                    "input_price_per_million_tokens": result["raw_model_response"][
                        f"{question_name}_input_price_per_million_tokens"
                    ],
                    "output_price_per_million_tokens": result["raw_model_response"][
                        f"{question_name}_output_price_per_million_tokens"
                    ],
                    "cost": result["raw_model_response"][f"{question_name}_cost"],
                }
            )
        formatted_result["costs"] = costs

        agent = {
            "traits": [
                {"trait_name": key, "trait_value": str(value)}
                for key, value in result["agent"]["traits"].items()
            ]
        }
        formatted_result["agent"] = agent

        scenario = {
            "variables": [
                {"variable_name": key, "variable_value": str(value)}
                for key, value in result["scenario"].items()
                if key not in ["edsl_class_name", "edsl_version", "scenario_index"]
            ]
        }
        formatted_result["scenario"] = scenario

        formatted_result["json_string"] = json.dumps(result, indent=2)

        self.result_data = formatted_result

        return formatted_result


# Convenience function for easy import
def create_result_inspector_widget(result=None):
    """Create and return a new Result Inspector Widget instance."""
    return ResultInspectorWidget(obj=result)


# Export the main class
__all__ = ["ResultInspectorWidget", "create_result_inspector_widget"]
