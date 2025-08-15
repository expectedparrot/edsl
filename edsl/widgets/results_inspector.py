"""
Results Inspector Widget

An interactive widget for inspecting EDSL Results objects (collections of Result objects)
with detailed views of the survey, individual results, and aggregate statistics.
"""

import json
import traitlets
from typing import Dict
from .inspector_widget import InspectorWidget


class ResultsInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting EDSL Results objects (collections of Result objects)."""

    widget_short_name = "results_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "Results"

    # Results-specific data traitlet for JavaScript frontend
    results_data = traitlets.Dict().tag(sync=True)
    paginated_results = traitlets.Dict().tag(sync=True)

    current_page = traitlets.Int(0).tag(sync=True)
    page_size = traitlets.Int(10).tag(sync=True)

    def __init__(self, obj=None, **kwargs):
        """Initialize the Results Inspector Widget.

        Args:
            obj: An EDSL Results object to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)

        # # Set up observers for frontend requests
        self.observe(self._on_pagination_change, names=["current_page", "page_size"])

    def _process_object_data(self):
        """Process the Results object data."""

        if not self.object or not self.data:
            return

        results = self.object
        results_dict = self.data

        formatted_results = {}

        results_summary = results._summary()

        summary = {
            "total_results": results_summary["observations"],
            "num_questions": results_summary["questions"],
            "num_agents": results_summary["agents"],
            "num_scenarios": results_summary["scenarios"],
        }
        formatted_results["summary"] = summary

        survey = {
            "questions": [
                {
                    "question_name": question["question_name"],
                    "question_text": question["question_text"],
                    "question_type": question["question_type"],
                }
                for question in results_dict["survey"]["questions"]
            ]
        }
        formatted_results["survey"] = survey

        formatted_results["data"] = []

        for result in results_dict["data"]:
            formatted_result = {}
            formatted_result["num_questions"] = len(result["answer"])
            transcript = []
            for question_name, question_data in result[
                "question_to_attributes"
            ].items():
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
                        "system_prompt": result["prompt"][
                            f"{question_name}_system_prompt"
                        ]["text"],
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

            formatted_results["data"].append(formatted_result)

        self.results_data = formatted_results

        self._on_pagination_change()

        return formatted_results

    def _on_pagination_change(self, change=None):
        """Get a paginated subset of results."""
        start = self.current_page * self.page_size
        end = start + self.page_size

        # This prevents an issue where the page size is changed but the current page is not reset to 0 as yet
        # TODO: Fix this by combining the pagination data into a single traitlet
        if start > len(self.object):
            return

        results_subset = self.object[start:end]

        dataset = results_subset.to_dataset()
        tabular_data = {}
        columns = []
        for column in dataset.relevant_columns():
            columns.append(
                {
                    "column_name": column,
                    "column_group": column.split(".")[0],
                }
            )

        tabular_data["columns"] = columns

        tabular_data["records"] = dataset.to_dicts(remove_prefix=False)

        self.paginated_results = tabular_data
        return tabular_data


# Convenience function for easy import
def create_results_inspector_widget(results=None):
    """Create and return a new Results Inspector Widget instance."""
    return ResultsInspectorWidget(obj=results)


# Export the main class
__all__ = ["ResultsInspectorWidget", "create_results_inspector_widget"]
