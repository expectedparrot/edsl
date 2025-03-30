"""
DEPRECATED: This module has been consolidated into jobs.py.

The functionality previously in this module has been moved to the Jobs class,
specifically in the _run_job_locally method.

This file will be removed in a future release.
"""

# Keep imports to avoid breaking imports elsewhere temporarily
from __future__ import annotations
import os
import time
import gc
from typing import TYPE_CHECKING, Optional
import weakref 
from functools import wraps
import asyncio
from queue import Queue

from ..results import Results, Result
from ..tasks import TaskHistory
from ..utilities.decorators import jupyter_nb_handler
from ..utilities.memory_debugger import MemoryDebugger

from .jobs_runner_status import JobsRunnerStatus
from .async_interview_runner import AsyncInterviewRunner
from .data_structures import RunEnvironment, RunParameters, RunConfig
from .results_exceptions_handler import ResultsExceptionsHandler
from .progress_bar_manager import ProgressBarManager

if TYPE_CHECKING:
    from ..jobs import Jobs

# Dummy class to maintain backwards compatibility temporarily
class JobsRunnerAsyncio:
    """
    DEPRECATED: This class has been consolidated into the Jobs class.
    """
    
    def __init__(self, jobs: "Jobs", environment: RunEnvironment, results_queue: Optional[Queue] = None):
        """DEPRECATED: Use Jobs._run_job_locally instead."""
        self.jobs = jobs
        self.environment = environment
        self.start_time = None
        self.completed = None
        self.results_queue = results_queue or Queue()
        
    async def run_async(self, parameters: RunParameters) -> Results:
        """DEPRECATED: Use Jobs.run_async instead."""
        import warnings
        warnings.warn("JobsRunnerAsyncio is deprecated. Use Jobs.run_async instead.", DeprecationWarning, stacklevel=2)
        return None
        
    async def run(self, parameters: RunParameters) -> Results:
        """DEPRECATED: Use Jobs.run instead."""
        import warnings
        warnings.warn("JobsRunnerAsyncio is deprecated. Use Jobs.run instead.", DeprecationWarning, stacklevel=2)
        return None
        
    def __len__(self):
        """Return the number of interviews that will be conducted."""
        return len(self.jobs)