"""
Unified Results Inspector Widget

A comprehensive widget that combines both Results-level overview and individual Result
inspection with integrated statistical analysis capabilities. This widget provides:
- Overview of Results collection with summary statistics
- Paginated table view of individual results with drill-down capability  
- Detailed Result inspection for individual items
- Comprehensive statistical analysis and visualization tools
- Settings and configuration options
"""

import json
import traitlets
from .inspector_widget import InspectorWidget


class UnifiedResultsInspectorWidget(InspectorWidget):
    """Unified widget for comprehensive Results inspection with statistical analysis."""

    widget_short_name = "unified_results_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "Results"

    # Results-specific data traitlets for JavaScript frontend
    results_data = traitlets.Dict().tag(sync=True)
    paginated_results = traitlets.Dict().tag(sync=True)
    analysis_data = traitlets.Dict().tag(sync=True)

    current_page = traitlets.Int(0).tag(sync=True)
    page_size = traitlets.Int(10).tag(sync=True)

    def __init__(self, obj=None, **kwargs):
        """Initialize the Unified Results Inspector Widget.

        Args:
            obj: An EDSL Results object to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        # Initialize traitlets with default values to prevent "No Results Data" error
        self.results_data = {}
        self.paginated_results = {}
        self.analysis_data = {}
        
        super().__init__(obj, **kwargs)

        # Set up observers for frontend requests
        self.observe(self._on_pagination_change, names=["current_page", "page_size"])
        
        # If object was provided, ensure data processing happens
        if obj is not None:
            print(f"🚀 Widget initialized with {type(obj)} object")
            # The base class should have called _process_object_data via the observer
            # But let's make sure our traitlets are set
            if not self.results_data:
                print("⚠️ results_data is still empty, triggering manual processing")
                self._process_object_data()

    def _process_object_data(self):
        """Process the Results object data for all tabs."""

        print("🔄 Processing object data...")
        print(f"   - Object available: {self.object is not None}")
        print(f"   - Data available: {self.data is not None and len(self.data) > 0}")

        if not self.object:
            print("❌ No object to process")
            return

        results = self.object
        
        # Get data - try self.data first (from base class), fall back to to_dict
        results_dict = self.data
        if not results_dict and hasattr(results, 'to_dict'):
            try:
                print("   - Trying to get data via to_dict(full_dict=True)...")
                results_dict = results.to_dict(full_dict=True)
                self.data = results_dict
                print(f"   - Got data with keys: {list(results_dict.keys())}")
            except Exception as e:
                print(f"   - Error getting data via to_dict: {e}")
                
        if not results_dict:
            print("❌ No data available for processing")
            return

        try:
            # Process main results data (same as original results_inspector)
            print("   - Processing main results data...")
            formatted_results = self._process_results_data(results, results_dict)
            
            # Process analysis data for the analysis tab
            print("   - Processing analysis data...")
            analysis_data = self._process_analysis_data(results)

            self.results_data = formatted_results
            self.analysis_data = analysis_data

            print("✅ Data processing complete!")
            print(f"   - Results data: {len(formatted_results.get('data', [])) if formatted_results else 0} items")
            print(f"   - Analysis data: {analysis_data.get('status', 'unknown')} status")

            self._on_pagination_change()

            return formatted_results
            
        except Exception as e:
            print(f"❌ Error in data processing: {e}")
            import traceback
            traceback.print_exc()
            
            # Set error state
            self.results_data = {"error": str(e)}
            self.analysis_data = {"status": "error", "error_message": str(e), "dataset": [], "columns": []}
            return None

    def _process_results_data(self, results, results_dict):
        """Process the main Results data (existing logic from results_inspector)."""
        
        formatted_results = {}

        # Summary information
        results_summary = results._summary()
        summary = {
            "total_results": results_summary["observations"],
            "num_questions": results_summary["questions"],
            "num_agents": results_summary["agents"],
            "num_scenarios": results_summary["scenarios"],
        }
        formatted_results["summary"] = summary

        # Survey information
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

        # Individual results data
        formatted_results["data"] = []

        for result in results_dict["data"]:
            formatted_result = {}
            formatted_result["num_questions"] = len(result["answer"])
            
            # Transcript (question-answer pairs)
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

            # Model information
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

            # Prompts
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

            # Costs
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

            # Agent information
            agent = {
                "traits": [
                    {"trait_name": key, "trait_value": str(value)}
                    for key, value in result["agent"]["traits"].items()
                ]
            }
            formatted_result["agent"] = agent

            # Scenario information
            scenario = {
                "variables": [
                    {"variable_name": key, "variable_value": str(value)}
                    for key, value in result["scenario"].items()
                    if key not in ["edsl_class_name", "edsl_version", "scenario_index"]
                ]
            }
            formatted_result["scenario"] = scenario

            # Raw JSON
            formatted_result["json_string"] = json.dumps(result, indent=2)

            formatted_results["data"].append(formatted_result)

        return formatted_results

    def _process_analysis_data(self, results):
        """Process data for the statistical analysis tab."""
        
        try:
            # Convert Results to dataset format for analysis
            dataset = results.to_dataset()
            
            # Prepare data in the format expected by our analysis components
            analysis_data = {
                "dataset": dataset.to_dicts(remove_prefix=False),
                "columns": list(dataset.relevant_columns()),
                "status": "ready"
            }
            
            return analysis_data
            
        except Exception as e:
            # If conversion fails, return error state
            return {
                "dataset": [],
                "columns": [],
                "status": "error",
                "error_message": str(e)
            }

    def _on_pagination_change(self, change=None):
        """Get a paginated subset of results for the results table."""
        
        print(f"🔄 Pagination change - Page: {self.current_page}, Size: {self.page_size}")
        
        if not self.object:
            print("❌ No object for pagination")
            self.paginated_results = {"columns": [], "records": []}
            return

        try:
            start = self.current_page * self.page_size
            end = start + self.page_size
            
            object_len = len(self.object)
            print(f"   - Object length: {object_len}, Start: {start}, End: {end}")

            # This prevents an issue where the page size is changed but the current page is not reset to 0 as yet
            # TODO: Fix this by combining the pagination data into a single traitlet
            if start >= object_len:
                print("   - Start index beyond object length, resetting to page 0")
                self.current_page = 0
                start = 0
                end = self.page_size

            results_subset = self.object[start:end]
            print(f"   - Results subset length: {len(results_subset)}")

            dataset = results_subset.to_dataset()
            columns = []
            for column in dataset.relevant_columns():
                columns.append(
                    {
                        "column_name": column,
                        "column_group": column.split(".")[0],
                    }
                )

            tabular_data = {
                "columns": columns,
                "records": dataset.to_dicts(remove_prefix=False)
            }
            
            print(f"   - Tabular data: {len(columns)} columns, {len(tabular_data['records'])} records")

            self.paginated_results = tabular_data
            print("✅ Pagination update complete")
            return tabular_data
            
        except Exception as e:
            print(f"❌ Error in pagination: {e}")
            import traceback
            traceback.print_exc()
            
            # Set empty but valid data structure
            self.paginated_results = {"columns": [], "records": []}
            return self.paginated_results


# Convenience function for easy import
def create_unified_results_inspector_widget(results=None):
    """Create and return a new Unified Results Inspector Widget instance."""
    return UnifiedResultsInspectorWidget(obj=results)


# Export the main class
__all__ = ["UnifiedResultsInspectorWidget", "create_unified_results_inspector_widget"]