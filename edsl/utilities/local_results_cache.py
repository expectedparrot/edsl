from contextlib import contextmanager
from pathlib import Path
import tempfile



@contextmanager
def local_results_cache(job, cache_dir: str | None = None, verbose: bool = True):
    """Context-manager that caches `job.run()` results to disk.

    Usage
    -----
    >>> with local_results_cache(job) as results:  # doctest: +SKIP
    ...     pass  # use results
    """

    from edsl import Results  # local import to avoid heavy import cost

    # Determine cache directory and file locations (single cache per script)
    root = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "edsl_job_cache"
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
            yield results_obj
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
    yield results_obj

