from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Optional

# Reuse the generic loader we just implemented
from .edsl_load import load as _load_edsl_obj


@contextmanager
def object_disk_cache(job, cache_dir: Optional[str] = None, verbose: bool = True):
    """Context-manager that caches the output of ``job.run()`` to disk.

    This is a generalisation of the old ``local_results_cache`` helper: it works
    for *any* EDSL object (any subclass of :class:`edsl.base.base_class.Base`).

    Workflow
    --------
    1. Compute a content hash for *job* (using ``hash(job)``) and choose a file
       ``<hash>.json.gz`` inside the cache directory (defaults to
       ``$TMPDIR/edsl_job_cache``).
    2. If that file exists attempt to load it with
       :pyfunc:`edsl.utilities.edsl_load.load`.
    3. On success yield the cached object (cache *hit*).  On failure (corrupt or
       incompatible file) fall back to re-running the job.
    4. After running the job save the returned object back to the same path so
       future calls can use the cache.

    Parameters
    ----------
    job : Any
        Object with a ``run()`` method returning an EDSL object.
    cache_dir : str | None, optional
        Override the default cache directory.
    verbose : bool, default ``True``
        Print human-readable status messages to stdout.
    """

    # Defer heavy imports until we *need* them – avoids slowing down start-up
    from edsl.base.base_class import Base  # noqa: WPS433 – runtime import intentional

    # ------------------------------------------------------------------
    # Determine cache directory and file locations (single cache per script)
    # ------------------------------------------------------------------
    root = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "edsl_job_cache"
    root.mkdir(parents=True, exist_ok=True)

    current_hash = str(hash(job))
    cache_path = root / f"{current_hash}.json.gz"

    if verbose:
        print(f"[cache] directory: {root}")
        print(f"[cache] job hash: {current_hash}")
        print(f"[cache] cache file: {cache_path}")

    # ------------------------------------------------------------------
    # Attempt to load from cache
    # ------------------------------------------------------------------
    if cache_path.exists():
        try:
            cached_obj = _load_edsl_obj(str(cache_path))
            if verbose:
                print("[cache] hit – loaded object from disk")
            yield cached_obj
            return
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print("[cache] load failed – cache corrupt or incompatible, rerunning job")
                print("[cache]", exc)

    # ------------------------------------------------------------------
    # Cache miss → run and save
    # ------------------------------------------------------------------
    if verbose:
        print("[cache] miss – running job")
    obj = job.run()

    # Persist to disk (best-effort – if it fails we still yield the object)
    try:
        if isinstance(obj, Base):
            obj.save(str(cache_path))
        else:
            raise TypeError("The object returned by job.run() is not an EDSL object (subclass of Base)")
        if verbose:
            print("[cache] saved object to", cache_path)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print("[cache] failed to save cache:", exc)

    yield obj


# ---------------------------------------------------------------------------
# Backwards-compatibility alias
# ---------------------------------------------------------------------------
local_results_cache = object_disk_cache

