"""Jobs JSONL serialization via CAS pointers.

Unlike the component serializers (ScenarioListSerializer, etc.) which
inline all data, the Jobs serializer stores **pointers** (UUID + branch
+ commit) to component objects already saved in the ObjectStore.

JSONL format:
  - Line 1: metadata header (``__header__: true``, class name, version)
  - Line 2: manifest with CAS pointers for survey, agents, models, scenarios
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .jobs import Jobs


def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
    """Normalise *source* into an iterable of lines."""
    if isinstance(source, Path):
        with open(source, "r") as fh:
            yield from fh
        return

    if isinstance(source, str):
        if "\n" not in source.rstrip("\n"):
            candidate = Path(source)
            try:
                if candidate.is_file():
                    with open(candidate, "r") as fh:
                        yield from fh
                    return
            except OSError:
                pass
        yield from source.splitlines()
    else:
        yield from source


def _component_pointer(component, name: str, root=None, message: str = "") -> dict:
    """Return a CAS pointer dict for a component, auto-saving if needed."""
    if component.store.uuid is None:
        component.store.save(message=message or f"auto-saved by Jobs.to_jsonl()", root=root)
    return {
        "uuid": component.store.uuid,
        "branch": component.store.current_branch,
        "commit": component.store.commit,
    }


def _manifest_from_jobs(job: "Jobs", root=None, message: str = "") -> dict:
    """Build a manifest dict with CAS pointers for all components."""
    manifest: dict = {
        "survey": _component_pointer(job.survey, "survey", root=root, message=message),
        "agents": _component_pointer(job.agents, "agents", root=root, message=message),
        "models": _component_pointer(job.models, "models", root=root, message=message),
        "scenarios": _component_pointer(job.scenarios, "scenarios", root=root, message=message),
    }
    if job._post_run_methods:
        manifest["_post_run_methods"] = job._post_run_methods
    if job._depends_on is not None:
        manifest["_depends_on"] = _manifest_from_jobs(job._depends_on, root=root, message=message)
    return manifest


class JobsSerializer:
    """JSONL serialization for Jobs objects via CAS pointers."""

    def __init__(self, jobs: "Jobs") -> None:
        self._jobs = jobs

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def _build_header(self) -> dict:
        from edsl import __version__

        return {
            "__header__": True,
            "edsl_class_name": "Jobs",
            "edsl_version": __version__,
        }

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        root=None,
        message: str = "",
    ) -> Optional[str]:
        """Export as JSONL string or write to *filename*.

        Components that haven't been saved to the store yet will be
        auto-saved before serialization.
        """
        header = json.dumps(self._build_header())
        manifest = json.dumps(_manifest_from_jobs(self._jobs, root=root, message=message))
        content = header + "\n" + manifest + "\n"

        if filename is not None:
            with open(filename, "w") as f:
                f.write(content)
            return None
        return content

    # ------------------------------------------------------------------
    # import
    # ------------------------------------------------------------------

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]], root=None) -> "Jobs":
        """Create a Jobs instance from a JSONL source.

        Each component is loaded from the ObjectStore by its CAS pointer
        (UUID + commit + branch).
        """
        from .jobs import Jobs
        from ..surveys import Survey
        from ..agents import AgentList
        from ..language_models import ModelList
        from ..scenarios import ScenarioList

        line_iter = iter(_open_lines(source))
        _header = json.loads(next(line_iter))  # noqa: F841
        manifest = json.loads(next(line_iter))

        def _load_component(cls, pointer, root):
            return cls.store.load(
                pointer["uuid"],
                commit=pointer["commit"],
                branch=pointer["branch"],
                root=root,
            )

        survey = _load_component(Survey, manifest["survey"], root)
        agents = _load_component(AgentList, manifest["agents"], root)
        models = _load_component(ModelList, manifest["models"], root)
        scenarios = _load_component(ScenarioList, manifest["scenarios"], root)

        job = Jobs(survey=survey, agents=agents, models=models, scenarios=scenarios)

        # Re-attach CAS tracking for components whose setters may have
        # created new wrapper objects (e.g. empty ModelList is falsy).
        for attr, component, pointer in [
            ("survey", survey, manifest["survey"]),
            ("_agents", agents, manifest["agents"]),
            ("_models", models, manifest["models"]),
            ("_scenarios", scenarios, manifest["scenarios"]),
        ]:
            current = getattr(job, attr)
            if current is not component and current.store.uuid is None:
                current.store.uuid = pointer["uuid"]
                current.store.commit = pointer["commit"]
                current.store.current_branch = pointer["branch"]

        if "_post_run_methods" in manifest:
            job._post_run_methods = manifest["_post_run_methods"]

        if "_depends_on" in manifest:
            # Reconstruct the dependent job from its nested manifest
            dep_header = json.dumps({"__header__": True, "edsl_class_name": "Jobs"})
            dep_manifest = json.dumps(manifest["_depends_on"])
            job._depends_on = JobsSerializer.from_jsonl(
                dep_header + "\n" + dep_manifest + "\n", root=root
            )

        return job
