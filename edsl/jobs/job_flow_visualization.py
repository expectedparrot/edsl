"""Visualization utilities for showing the execution flow of a `Jobs` object.

This module now delegates to the JobVisualizationService.
The original pydot-based code has been moved to the service.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .jobs import Jobs


class JobsFlowVisualization:
    """Create a flowchart diagram for a :class:`edsl.jobs.jobs.Jobs` instance.
    
    This class now delegates to the JobVisualizationService.
    """

    def __init__(self, job: "Jobs") -> None:
        from edsl.jobs.jobs import Jobs  # local import to avoid circularity

        if not isinstance(job, Jobs):
            raise TypeError("Expected an `edsl.jobs.jobs.Jobs` instance.")

        self.job = job

    def show_flow(self, filename: Optional[str] = None, verbose: bool = True) -> None:
        """Render or save a flowchart for *self.job*.

        This method delegates to the JobVisualizationService.

        Args:
            filename: Optional path to save the PNG. If None, displays inline.
            verbose: Whether to show progress messages.
            
        Returns:
            FileStore containing the PNG image.
        """
        from edsl_services.job_visualization_service import JobVisualizationService
        
        if verbose:
            print("[job_visualization] Generating job flow diagram...")
        
        params = {
            "operation": "flow",
            "data": self.job.to_dict(),
            "filename": filename,
        }
        
        result = JobVisualizationService.execute(params)
        fs = JobVisualizationService.parse_result(result)
        
        if verbose:
            print("[job_visualization] ✓ Flow diagram created")
        
        if filename is None:
            fs.view()
        else:
            print(f"Flowchart saved to {filename}")
        
        return fs
