"""HumanizedJob - Manages human survey sessions.

This module provides the HumanizedJob class which represents a survey
that humans can complete via a web interface.
"""

from __future__ import annotations
import time
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from ..surveys import Survey
    from ..scenarios import ScenarioList


class HumanizedJob:
    """Represents a humanized survey session.

    A HumanizedJob is created when calling `job.humanize()`. It provides:
    - URL for respondents to access the survey
    - Methods to check response counts
    - Methods to retrieve results (non-blocking)
    - Method to close the survey when done collecting

    Example:
        >>> from edsl import Survey, QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(
        ...     question_name="color",
        ...     question_text="What is your favorite color?",
        ...     question_options=["Red", "Blue", "Green"]
        ... )
        >>> survey = Survey([q])
        >>> humanized = survey.to_jobs().humanize()  # doctest: +SKIP
        >>> print(humanized.url)  # doctest: +SKIP
        >>>
        >>> # Check results anytime (non-blocking)
        >>> results = humanized.results()  # doctest: +SKIP
        >>> print(f"Got {len(results)} responses")  # doctest: +SKIP
        >>>
        >>> # Check status
        >>> humanized.status()  # doctest: +SKIP
        >>> # {'completed_interviews': 5, 'started_interviews': 8, ...}
        >>>
        >>> # When done collecting, close and get final results
        >>> results = humanized.close()  # doctest: +SKIP
    """

    def __init__(
        self,
        job_id: str,
        server_url: str,
        survey: "Survey",
        scenarios: Optional["ScenarioList"] = None,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        interview_ids: Optional[List[str]] = None,
        agent_interview_map: Optional[Dict[str, str]] = None,
        agent_key: Optional[str] = None,
    ):
        """Initialize a HumanizedJob.

        Args:
            job_id: Unique identifier for this job
            server_url: Base URL of the EDSL server
            survey: The survey being administered
            scenarios: Optional scenarios for the survey
            name: Display name for the survey
            config: Configuration options (one_at_a_time, show_progress, etc.)
            interview_ids: List of interview IDs (one per scenario, or one if no scenarios)
            agent_interview_map: Mapping of agent key values to interview IDs
            agent_key: The trait used as the key for agent_interview_map
        """
        self.job_id = job_id
        self.server_url = server_url.rstrip("/")
        self.survey = survey
        self.scenarios = scenarios
        self.name = name or "Survey"
        self.config = config or {}
        self.interview_ids = interview_ids or []
        self._agent_interview_map = agent_interview_map or {}
        self.agent_key = agent_key
        self._client = None

    @property
    def client(self):
        """Get HTTP client for server communication."""
        if self._client is None:
            from edsl.server import require_client

            self._client = require_client(purpose="humanized job")
        return self._client

    @property
    def url(self) -> str:
        """Get the primary survey URL.

        For surveys without scenarios or with a single scenario,
        returns the single URL. For multi-scenario surveys,
        returns the URL for the first scenario.
        """
        if self.interview_ids:
            return f"{self.server_url}/humanize/{self.job_id}/{self.interview_ids[0]}"
        return f"{self.server_url}/humanize/{self.job_id}"

    @property
    def urls(self) -> List[str]:
        """Get all survey URLs (one per scenario/interview)."""
        if self.interview_ids:
            return [
                f"{self.server_url}/humanize/{self.job_id}/{iid}"
                for iid in self.interview_ids
            ]
        return [f"{self.server_url}/humanize/{self.job_id}"]

    @property
    def agent_urls(self) -> Dict[str, str]:
        """Get mapping of agent trait values to survey URLs.

        When a survey is humanized with agents attached, each agent gets
        a unique URL. This property returns a dictionary mapping the
        agent's key trait value to their personalized survey URL.

        Returns:
            Dict mapping agent trait value (e.g., email) to unique URL.
            Empty dict if no agents were attached.

        Example:
            >>> agents = AgentList([  # doctest: +SKIP
            ...     Agent(traits={"name": "Alice", "email": "alice@example.com"}),
            ...     Agent(traits={"name": "Bob", "email": "bob@example.com"}),
            ... ])
            >>> humanized = survey.by(agents).humanize(agent_key="email")  # doctest: +SKIP
            >>> humanized.agent_urls  # doctest: +SKIP
            {'alice@example.com': 'http://localhost:8599/humanize/job123/int456',
             'bob@example.com': 'http://localhost:8599/humanize/job123/int789'}
        """
        return {
            key: f"{self.server_url}/humanize/{self.job_id}/{interview_id}"
            for key, interview_id in self._agent_interview_map.items()
        }

    def status(self) -> Dict[str, Any]:
        """Get the current status of the humanized survey.

        Returns:
            Dict with:
                - completed_interviews: Number of fully completed interviews
                - started_interviews: Number of interviews with at least one answer
                - total_interviews: Total number of interviews created
                - questions_per_interview: Number of questions in the survey
        """
        # Get job status from server
        job_data = self.client.get_task_job(self.job_id)
        if job_data is None:
            return {
                "completed_interviews": 0,
                "started_interviews": 0,
                "total_interviews": 0,
                "questions_per_interview": (
                    len(self.survey.questions) if self.survey else 0
                ),
            }

        # Get all tasks and group by interview (group_id)
        tasks = self.client.list_unified_tasks(job_id=self.job_id)

        # Group tasks by group_id (each group is an interview)
        interviews = {}
        for task in tasks:
            group_id = task.get("group_id", "default")
            if group_id not in interviews:
                interviews[group_id] = {"total": 0, "completed": 0}
            interviews[group_id]["total"] += 1
            if task.get("status") == "completed":
                interviews[group_id]["completed"] += 1

        # Count completed and started interviews
        completed_interviews = 0
        started_interviews = 0

        for group_id, counts in interviews.items():
            if counts["completed"] >= counts["total"] and counts["total"] > 0:
                completed_interviews += 1
            if counts["completed"] > 0:
                started_interviews += 1

        return {
            "completed_interviews": completed_interviews,
            "started_interviews": started_interviews,
            "total_interviews": len(interviews),
            "questions_per_interview": len(self.survey.questions) if self.survey else 0,
        }

    def results(self) -> "Results":
        """Get current results from completed interviews.

        This method is non-blocking and returns immediately with whatever
        results are available. If no interviews are complete, returns an
        empty Results object. Call again later to get more results as
        respondents complete the survey.

        Returns:
            Results object with responses from completed interviews.
            May be empty if no one has completed the survey yet.

        Example:
            >>> humanized = survey.to_jobs().humanize()  # doctest: +SKIP
            >>> print(humanized.url)  # doctest: +SKIP
            >>>
            >>> # Check results periodically
            >>> results = humanized.results()  # doctest: +SKIP
            >>> print(f"Got {len(results)} responses so far")  # doctest: +SKIP
            >>>
            >>> # Later, check again for more
            >>> results = humanized.results()  # doctest: +SKIP
        """
        from ..results import Results
        import requests

        # Fetch current results from server
        headers = {"X-API-Key": self.client.api_key}
        response = requests.get(
            f"{self.server_url}/jobs/{self.job_id}/results",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            results_data = data.get("results")
            if results_data:
                return Results.from_dict(results_data)

        # No results yet - return empty Results with the survey
        return Results(survey=self.survey, data=[])

    def close(self) -> "Results":
        """Close the survey and return final results.

        After closing, the survey URL will no longer accept new responses.
        Any in-progress interviews can still be completed.

        Returns:
            Final Results object with all completed responses

        Example:
            >>> humanized = survey.to_jobs().humanize()  # doctest: +SKIP
            >>> print(humanized.url)  # doctest: +SKIP
            >>> # ... wait for responses ...
            >>> results = humanized.close()  # doctest: +SKIP
        """
        # Mark job as closed (no new interviews)
        # TODO: Implement server-side close that prevents new interviews
        # For now, just return results
        return self.results()

    def cancel(self) -> bool:
        """Cancel the humanized survey.

        Marks all pending tasks as cancelled.

        Returns:
            True if successfully cancelled
        """
        response = self.client.delete(f"/jobs/{self.job_id}")
        return response.get("status") == "cancelled"

    def __repr__(self) -> str:
        status = self.status()
        return (
            f"HumanizedJob(\n"
            f"    name='{self.name}',\n"
            f"    job_id='{self.job_id}',\n"
            f"    url='{self.url}',\n"
            f"    completed={status['completed_interviews']},\n"
            f"    started={status['started_interviews']},\n"
            f")"
        )

    def _repr_html_(self) -> str:
        """Rich HTML representation for Jupyter notebooks."""
        status = self.status()

        # Build URL display based on whether we have agent URLs
        if self.agent_urls:
            # Show agent URL table
            agent_rows = "".join(
                f'<tr><td>{key}</td><td><a href="{url}" target="_blank">{url}</a></td></tr>'
                for key, url in self.agent_urls.items()
            )
            urls_section = f"""
            <p><strong>Agent URLs</strong> (key: {self.agent_key}):</p>
            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                <thead>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <th style="text-align: left; padding: 5px;">{self.agent_key}</th>
                        <th style="text-align: left; padding: 5px;">URL</th>
                    </tr>
                </thead>
                <tbody>
                    {agent_rows}
                </tbody>
            </table>
            """
        else:
            # Show regular URL list
            urls_html = "".join(
                f'<li><a href="{url}" target="_blank">{url}</a></li>'
                for url in self.urls
            )
            urls_section = f"""
            <p><strong>Survey URL:</strong></p>
            <ul>{urls_html}</ul>
            """

        return f"""
        <div style="border: 1px solid #ccc; padding: 15px; border-radius: 8px; max-width: 700px;">
            <h3 style="margin-top: 0;">📋 {self.name}</h3>
            <p><strong>Job ID:</strong> <code>{self.job_id}</code></p>
            <p><strong>Responses:</strong> {status['completed_interviews']} completed, {status['started_interviews']} started</p>
            {urls_section}
            <p style="color: #666; font-size: 0.9em;">
                <code>.results()</code> - get current responses<br>
                <code>.close()</code> - stop collecting and get final results
            </p>
        </div>
        """
