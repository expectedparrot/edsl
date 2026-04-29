"""CAS streaming integration for the Runner.

Manages streaming CAS writes for a running job — registers itself as
an interview-completion callback on JobService and incrementally
persists results as each interview completes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from ..object_store.fs_backend import FileSystemBackend
from ..object_store.streaming_writer import StreamingCASWriter
from ..object_store.store import ObjectStore

if TYPE_CHECKING:
    from ..surveys import Survey
    from .service import JobService

logger = logging.getLogger(__name__)


class RunnerCASIntegration:
    """Manages streaming CAS writes for a running job.

    Registers itself as an interview-completion callback on JobService.
    The Runner only needs to create this object — everything else is automatic.

    The callback only records completed interview IDs.  Serialization
    happens at flush time to avoid per-interview DB round-trips.

    Args:
        job_id: The runner job ID.
        survey: The Survey for this job (used to build the JSONL preamble).
        service: The JobService to register the callback on.
        root: CAS directory root. Defaults to ObjectStore.DEFAULT_ROOT / uuid.
        batch_size: Number of completed interviews to accumulate before
                    flushing a CAS commit.  Default 1 = commit per interview.
        uuid: Optional UUID for the CAS object. Auto-generated if omitted.
    """

    def __init__(
        self,
        job_id: str,
        survey: "Survey",
        service: "JobService",
        root: Optional[Path] = None,
        batch_size: int = 1,
        uuid: Optional[str] = None,
    ):
        self._uuid = uuid or str(uuid4())
        self._job_id = job_id
        self._service = service
        self._batch_size = batch_size
        self._pending_ids: list[str] = []  # interview IDs awaiting flush

        cas_root = root or (ObjectStore.DEFAULT_ROOT / self._uuid)
        self._backend = FileSystemBackend(cas_root)
        self._writer = StreamingCASWriter(self._backend, branch="main")

        # Write preamble (header + manifest + survey rows)
        preamble = self._build_preamble(survey)
        self._writer.write_preamble(preamble)

        # Register as callback
        service.register_interview_callback(job_id, self._on_interview_complete)

        # Register in metadata index so ObjectStore can find this object
        ObjectStore()._update_meta(self._uuid, "Results", f"Job {job_id}")

        logger.info(
            "CAS streaming enabled for job %s → %s (batch_size=%d)",
            job_id[:8],
            cas_root,
            batch_size,
        )

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def n_results(self) -> int:
        return self._writer.n_results

    @property
    def tip(self) -> Optional[str]:
        return self._writer.tip

    def _on_interview_complete(self, job_id: str, interview_id: str):
        """Called by JobService when an interview finishes.

        Just records the ID — serialization is deferred to flush.
        """
        self._pending_ids.append(interview_id)
        if len(self._pending_ids) >= self._batch_size:
            self._flush()

    def finalize(self):
        """Flush any remaining pending results."""
        if self._pending_ids:
            self._flush()

    def _flush(self):
        """Serialize pending interviews and write to CAS."""
        rows = []
        for iid in self._pending_ids:
            try:
                result = self._service.build_edsl_result(self._job_id, iid)
                rows.append(json.dumps(result.to_dict(add_edsl_version=True)))
            except Exception:
                logger.exception(
                    "CAS streaming: failed to serialize interview %s", iid
                )
        self._pending_ids.clear()

        if rows:
            prev = self._writer.n_results
            total = prev + len(rows)
            if len(rows) == 1:
                msg = f"Result {total}"
            else:
                msg = f"Results {prev + 1}-{total}"
            self._writer.append_results_batch(rows, message=msg)
            logger.debug(
                "CAS flush: %d results committed (total %d)",
                len(rows),
                self._writer.n_results,
            )

    @staticmethod
    def _build_preamble(survey: "Survey") -> list[str]:
        from .. import __version__

        header = json.dumps({
            "__header__": True,
            "edsl_class_name": "Results",
            "edsl_version": __version__,
            "format": "inline",
        })
        survey_rows = list(survey.to_jsonl_rows())
        manifest = json.dumps({
            "created_columns": [],
            "name": None,
            "n_survey_lines": len(survey_rows),
        })
        return [header, manifest] + survey_rows
