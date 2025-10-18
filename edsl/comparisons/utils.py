from __future__ import annotations

"""Utility functions for the EDSL comparisons framework."""

from contextlib import contextmanager
from pathlib import Path
import tempfile

__all__ = ["local_results_cache"]


@contextmanager
def local_results_cache(job, cache_dir: str | None = None, verbose: bool = True):
    """Context manager that caches EDSL job.run() results to disk for performance.

    This context manager automatically handles caching of expensive EDSL job results.
    On first run, it executes the job and saves results to disk. On subsequent runs
    with the same job hash, it loads results from cache instead of re-executing.

    Args:
        job: EDSL job object with a .run() method
        cache_dir: Optional directory for cache files. If None, uses system temp directory
        verbose: Whether to print cache status messages

    Yields:
        Results: The EDSL Results object, either from cache or fresh execution

    Raises:
        Exception: Any exception from job.run() or file I/O operations

    Examples:
        Basic usage with automatic caching:

        >>> from edsl import QuestionFreeText, ScenarioList
        >>> job = QuestionFreeText(
        ...     question_name="test",
        ...     question_text="What is 2+2?"
        ... ).by(ScenarioList.from_list("dummy", [1]))
        >>>
        >>> # First run executes job and caches result
        >>> with local_results_cache(job, verbose=False) as results:
        ...     len(results) > 0
        True

        Custom cache directory:

        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     with local_results_cache(job, cache_dir=tmpdir, verbose=False) as results:
        ...         len(results) > 0
        True

    Note:
        - Cache files are named using hash(job) for uniqueness
        - Corrupted cache files are automatically detected and regenerated
        - The context manager properly handles exceptions including debugger quits
    """

    from edsl import Results  # local import to avoid heavy import cost

    # Determine cache directory and file locations (single cache per script)
    root = (
        Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "edsl_job_cache"
    )
    root.mkdir(parents=True, exist_ok=True)

    current_hash = str(hash(job))

    results_path = root / f"{current_hash}.json.gz"

    if verbose:
        print(f"[cache] directory: {root}")
        print(f"[cache] job hash: {current_hash}")
        print(f"[cache] results file: {results_path}")

    # Attempt to load cache using hash-named file
    if results_path.exists():
        try:
            results_obj = Results.load(str(results_path))
            if verbose:
                print("[cache] hit – loaded results from disk")
            try:
                yield results_obj
            except Exception:
                # Re-raise any exception that occurs in the yield block
                # This prevents the "generator didn't stop after throw()" error
                raise
            return
        except Exception:
            if verbose:
                print("[cache] load failed – cache corrupt, rerunning job")

    # Cache miss → run and save
    if verbose:
        print("[cache] miss – running job")
    results_obj = job.run()
    try:
        results_obj.save(str(results_path))
        if verbose:
            print("[cache] saved results to", results_path)
    except Exception as e:
        if verbose:
            print("[cache] failed to save cache:", e)

    try:
        yield results_obj
    except Exception:
        # Re-raise any exception that occurs in the yield block
        # This prevents the "generator didn't stop after throw()" error
        raise
