import reprlib
from typing import Optional

from .exceptions import CoopValueError
from ..scenarios import Scenario, ScenarioList


class CoopProlificFilters(ScenarioList):
    """Base class for Prolific filters supported on Coop.

    This abstract class extends ScenarioList to provide common functionality
    for working with Prolific filters.
    """

    def __init__(
        self, data: Optional[list] = None, codebook: Optional[dict[str, str]] = None
    ):
        super().__init__(data, codebook)

    def find(self, filter_id: str) -> Optional[Scenario]:
        """
        Find a filter by its ID. Raises a CoopValueError if the filter is not found.

        >>> filters = coop.list_prolific_filters()
        >>> filters.find("age")
        Scenario(
            {
                "filter_id": "age",
                "type": "range",
                "range_filter_min": 18,
                "range_filter_max": 100,
                ...
            }
        """

        # Prolific has inconsistent naming conventions for filters -
        # some use underscores and some use dashes, so we need to check for both
        id_with_dashes = filter_id.replace("_", "-")
        id_with_underscores = filter_id.replace("-", "_")

        for scenario in self:
            if (
                scenario["filter_id"] == id_with_dashes
                or scenario["filter_id"] == id_with_underscores
            ):
                return scenario
        raise CoopValueError(f"Filter with ID {filter_id} not found.")

    def create_study_filter(
        self,
        filter_id: str,
        min: Optional[int] = None,
        max: Optional[int] = None,
        values: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a valid filter dict that is compatible with Coop.create_prolific_study().
        This function will raise a CoopValueError if:
        - The filter ID is not found
        - A range filter is provided with no min or max value, or a value that is outside of the allowed range
        - A select filter is provided with no values, or a value that is not in the allowed options

        For a select filter, you should pass a list of values:
        >>> filters = coop.list_prolific_filters()
        >>> filters.create_study_filter("current_country_of_residence", values=["United States", "Canada"])
        {
            "filter_id": "current_country_of_residence",
            "selected_values": ["1", "45"],
        }

        For a range filter, you should pass a min and max value:
        >>> filters.create_study_filter("age", min=20, max=40)
        {
            "filter_id": "age",
            "selected_range": {
                "lower": 20,
                "upper": 40,
            },
        }
        """
        filter = self.find(filter_id)

        # .find() has logic to handle inconsistent naming conventions for filter IDs,
        # so we need to get the correct filter ID from the filter dict
        correct_filter_id = filter.get("filter_id")

        filter_type = filter.get("type")

        if filter_type == "range":
            filter_min = filter.get("range_filter_min")
            filter_max = filter.get("range_filter_max")

            if min is None and max is None:
                raise CoopValueError("Range filters require both a min and max value.")
            if min < filter_min:
                raise CoopValueError(
                    f"Min value {min} is less than the minimum allowed value {filter_min}."
                )
            if max > filter_max:
                raise CoopValueError(
                    f"Max value {max} is greater than the maximum allowed value {filter_max}."
                )
            if min > max:
                raise CoopValueError("Min value cannot be greater than max value.")
            return {
                "filter_id": correct_filter_id,
                "selected_range": {
                    "lower": min,
                    "upper": max,
                },
            }
        elif filter_type == "select":
            if values is None:
                raise CoopValueError("Select filters require a list of values.")

            if correct_filter_id == "custom_allowlist":
                return {
                    "filter_id": correct_filter_id,
                    "selected_values": values,
                }

            try:
                allowed_option_labels = filter.get("select_filter_options", {})
                option_labels_to_ids = {v: k for k, v in allowed_option_labels.items()}
                selected_option_ids = [option_labels_to_ids[value] for value in values]
            except KeyError:
                raise CoopValueError(
                    f"Invalid value(s) provided for filter {filter_id}: {values}. "
                    f"Call find() with the filter ID to examine the allowed values for this filter."
                )

            return {
                "filter_id": correct_filter_id,
                "selected_values": selected_option_ids,
            }
        else:
            raise CoopValueError(f"Unsupported filter type: {filter_type}.")

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the CoopProlificFilters as a table with truncated options display for select filters."""

        # Create a copy of the data with truncated options
        truncated_scenarios = []
        for scenario in self:
            scenario_dict = dict(scenario)
            if (
                "select_filter_options" in scenario_dict
                and scenario_dict["select_filter_options"] is not None
            ):

                # Create a truncated representation of the options list
                formatter = reprlib.Repr()
                formatter.maxstring = 50
                select_filter_options = list(
                    dict(scenario_dict["select_filter_options"]).values()
                )
                formatted_options = formatter.repr(select_filter_options)
                scenario_dict["select_filter_options"] = formatted_options
            truncated_scenarios.append(scenario_dict)

        temp_scenario_list = ScenarioList([Scenario(s) for s in truncated_scenarios])

        # Display the table with the truncated data
        return temp_scenario_list.table(
            *fields, tablefmt=tablefmt, pretty_labels=pretty_labels
        )
