"""JobInspectorWidget for interactively exploring EDSL Jobs objects."""

from .inspector_widget import InspectorWidget


class JobInspectorWidget(InspectorWidget):
    """Interactive inspector widget for Jobs objects.

    Provides an interactive interface to explore Jobs objects including:
    - Job configuration and parameters
    - Survey components and questions
    - Agent collections
    - Scenario collections
    - Model configurations
    - Execution flow visualization
    """

    widget_short_name = "job_inspector"

    associated_class = "Jobs"

    def _validate_object(self, obj) -> bool:
        """Accept any Jobs object."""
        if obj is None:
            return True
        from edsl.jobs.jobs import Jobs

        return isinstance(obj, Jobs)

    def _process_object_data(self):
        """Add job-specific computed properties after base data extraction."""
        if self.data and "error" not in self.data:
            # Add computed job statistics
            self.data["job_stats"] = self.job_stats

    @property
    def survey_data(self):
        """Get survey data from the job."""
        return self.data.get("survey", {})

    @property
    def agents_data(self):
        """Get agents data from the job."""
        return self.data.get("agents", [])

    @property
    def models_data(self):
        """Get models data from the job."""
        return self.data.get("models", [])

    @property
    def scenarios_data(self):
        """Get scenarios data from the job."""
        return self.data.get("scenarios", [])

    @property
    def job_stats(self):
        """Get job statistics and configuration."""
        return {
            "num_agents": len(self.agents_data),
            "num_models": len(self.models_data),
            "num_scenarios": len(self.scenarios_data),
            "num_questions": len(self.survey_data.get("questions", [])),
            "total_interviews": len(self.agents_data or [1])
            * len(self.models_data or [1])
            * len(self.scenarios_data or [1]),
        }
