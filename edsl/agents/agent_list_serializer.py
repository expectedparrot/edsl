"""AgentList serialization operations module."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Iterable, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent
    from .agent_list import AgentList


class AgentListSerializer:
    """Handles serialization and deserialization operations for AgentList objects.

    Instantiated with a reference to an AgentList; instance methods handle
    export while static/class methods handle import (where no instance exists yet).
    """

    def __init__(self, agent_list: "AgentList") -> None:
        self._agent_list = agent_list

    # ------------------------------------------------------------------
    # dict serialization
    # ------------------------------------------------------------------

    def to_dict(
        self,
        sorted: bool = False,
        add_edsl_version: bool = True,
        full_dict: bool = False,
    ) -> dict:
        """Serialize the AgentList to a dictionary.

        Args:
            sorted: Whether to sort agents before serialization.
            add_edsl_version: Whether to include EDSL version information.
            full_dict: Whether to include full dictionary representation.

        Returns:
            A dictionary representation of the AgentList.

        Examples:
            >>> from edsl import AgentList
            >>> al = AgentList.example()
            >>> result = al.to_dict(add_edsl_version=False)
            >>> 'agent_list' in result
            True
            >>> len(result['agent_list'])
            2
        """
        if sorted:
            data = self._agent_list.data[:]
            data.sort(key=lambda x: hash(x))
        else:
            data = self._agent_list.data

        d = {
            "agent_list": [
                agent.to_dict(add_edsl_version=add_edsl_version, full_dict=full_dict)
                for agent in data
            ]
        }

        if len(self._agent_list.data) > 0:
            first_codebook = self._agent_list.data[0].codebook
            all_same = all(
                agent.codebook == first_codebook for agent in self._agent_list.data
            )
            if all_same and first_codebook:
                d["codebook"] = first_codebook

            shared_tpt = self._shared_agent_value("traits_presentation_template")
            if shared_tpt is not None:
                d["traits_presentation_template"] = shared_tpt

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "AgentList"

        return d

    @staticmethod
    def from_dict(data: dict) -> "AgentList":
        """Deserialize a dictionary back to an AgentList object.

        Args:
            data: A dictionary representing an AgentList.

        Returns:
            A new AgentList object created from the dictionary.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent.example(), Agent.example()])
            >>> serialized = al.to_dict()
            >>> al2 = AgentList.from_dict(serialized)
            >>> len(al2)
            2
        """
        from .agent import Agent
        from .agent_list import AgentList

        agent_data = data.get("agent_list", None)
        if agent_data is None:
            raise ValueError("agent_list key not found in data")

        agents = [Agent.from_dict(agent_dict) for agent_dict in agent_data]
        agent_list = AgentList(agents)

        if "codebook" in data and data["codebook"]:
            agent_list.set_codebook(data["codebook"])

        if "traits_presentation_template" in data and data["traits_presentation_template"]:
            agent_list.set_traits_presentation_template(data["traits_presentation_template"])

        return agent_list

    # ------------------------------------------------------------------
    # JSONL serialization
    # ------------------------------------------------------------------

    _EXPLICIT_FLAGS = {
        "instruction": "set_instructions",
        "traits_presentation_template": "set_traits_presentation_template",
    }

    def _shared_agent_value(self, attr: str):
        """Return the value of *attr* if every agent shares the same explicitly-set value, else ``None``."""
        agents = self._agent_list.data
        if not agents:
            return None

        flag = self._EXPLICIT_FLAGS.get(attr)
        if flag is not None:
            if not all(getattr(a, flag, False) for a in agents):
                return None

        first = getattr(agents[0], attr, None)
        if first and all(getattr(a, attr, None) == first for a in agents):
            return first
        return None

    def _build_metadata(self, add_edsl_version: bool = True) -> dict:
        """Build the metadata header row for JSONL export."""
        meta: dict = {
            "edsl_class_name": "AgentList",
            "n_agents": len(self._agent_list.data),
        }
        if add_edsl_version:
            from edsl import __version__

            meta["edsl_version"] = __version__

        for attr in ("codebook", "instruction", "traits_presentation_template"):
            shared = self._shared_agent_value(attr)
            if shared is not None:
                meta[attr] = shared

        return meta

    def to_jsonl_rows(
        self, add_edsl_version: bool = True
    ) -> Generator[str, None, None]:
        """Yield one JSON string per line in JSONL format.

        The first yielded string is the metadata header; every subsequent
        string is a serialized Agent record.

        Args:
            add_edsl_version: Whether to include EDSL version in the header.

        Yields:
            JSON-encoded strings (without trailing newlines).

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22})])
            >>> rows = list(al._agent_list_serializer.to_jsonl_rows(add_edsl_version=False))
            >>> import json
            >>> meta = json.loads(rows[0])
            >>> meta['n_agents']
            1
            >>> agent_row = json.loads(rows[1])
            >>> agent_row['traits']
            {'age': 22}
        """
        yield json.dumps(self._build_metadata(add_edsl_version))
        for agent in self._agent_list.data:
            yield json.dumps(agent.to_dict(add_edsl_version=False))

    def to_jsonl(self, filename: Union[str, Path, None] = None) -> Union[str, None]:
        """Export the AgentList as JSONL.

        The first line is a metadata header; each subsequent line is one
        serialized Agent.  When *filename* is provided the data is streamed
        directly to disk and ``None`` is returned.  Otherwise the full
        JSONL content is returned as a string.

        Args:
            filename: Optional path to write to.  If ``None``, returns a string.

        Returns:
            The JSONL string when *filename* is ``None``; otherwise ``None``.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> text = al.to_jsonl()
            >>> lines = text.strip().splitlines()
            >>> len(lines)
            3
            >>> import json; json.loads(lines[0])['n_agents']
            2
        """
        if filename is not None:
            with open(filename, "w") as f:
                for row in self.to_jsonl_rows():
                    f.write(row + "\n")
            return None

        return "\n".join(self.to_jsonl_rows()) + "\n"

    # ------------------------------------------------------------------
    # CAS (content-addressable storage) — git-like versioning
    # ------------------------------------------------------------------
    #
    # Layout:
    #   <dir>/blobs/<hash>.json   — one per unique agent
    #   <dir>/trees/<hash>.json   — ordered list of blob hashes + metadata
    #   <dir>/commits/<hash>.json — points to tree, parent, timestamp, message
    #   <dir>/HEAD               — current commit hash
    #

    @staticmethod
    def _cas_hash(content: str) -> str:
        """SHA-256 hex digest of a string."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _cas_write(path: Path, content: str) -> None:
        """Write *content* to *path*, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def to_cas(
        self,
        directory: Union[str, Path],
        message: str = "",
    ) -> str:
        """Commit the AgentList to a CAS repository.

        Writes blob, tree, and commit objects.  Only new objects are
        written; unchanged agents reuse existing blobs.

        Args:
            directory: Path to the CAS repository (created if needed).
            message: Human-readable commit message.

        Returns:
            The commit hash.

        Examples:
            >>> import tempfile, json
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> d = tempfile.mkdtemp()
            >>> commit1 = al.to_cas(d, message="initial")
            >>> len(commit1)
            64
            >>> head = open(f"{d}/HEAD").read().strip()
            >>> head == commit1
            True
        """
        directory = Path(directory)

        # --- blobs ---
        blob_hashes: list[str] = []
        for agent in self._agent_list.data:
            content = json.dumps(agent.to_dict(add_edsl_version=False), sort_keys=True)
            h = self._cas_hash(content)
            blob_hashes.append(h)
            blob_path = directory / "blobs" / f"{h}.json"
            if not blob_path.exists():
                self._cas_write(blob_path, content)

        # --- tree ---
        tree_obj = {
            "hashes": blob_hashes,
            "metadata": self._build_metadata(),
        }
        tree_content = json.dumps(tree_obj, sort_keys=True)
        tree_hash = self._cas_hash(tree_content)
        tree_path = directory / "trees" / f"{tree_hash}.json"
        if not tree_path.exists():
            self._cas_write(tree_path, tree_content)

        # --- commit ---
        head_path = directory / "HEAD"
        parent: Optional[str] = None
        if head_path.exists():
            parent = head_path.read_text().strip() or None

        commit_obj = {
            "tree": tree_hash,
            "parent": parent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }
        commit_content = json.dumps(commit_obj, sort_keys=True)
        commit_hash = self._cas_hash(commit_content)
        self._cas_write(
            directory / "commits" / f"{commit_hash}.json", commit_content
        )

        # --- update HEAD ---
        self._cas_write(head_path, commit_hash + "\n")

        # --- overwrite readable snapshot ---
        self.to_jsonl(directory / "current.jsonl")

        return commit_hash

    @staticmethod
    def from_cas(
        directory: Union[str, Path],
        commit: Optional[str] = None,
    ) -> "AgentList":
        """Load an AgentList from a CAS commit.

        Args:
            directory: Path to a CAS repository.
            commit: Commit hash to load.  Defaults to HEAD.

        Returns:
            The AgentList at the given commit.

        Examples:
            >>> import tempfile
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> d = tempfile.mkdtemp()
            >>> c = al.to_cas(d, message="v1")
            >>> al2 = AgentList.from_cas(d)
            >>> al == al2
            True
            >>> al3 = AgentList.from_cas(d, commit=c)
            >>> al == al3
            True
        """
        from .agent import Agent
        from .agent_list import AgentList

        directory = Path(directory)

        if commit is None:
            head_path = directory / "HEAD"
            if not head_path.exists():
                raise FileNotFoundError(f"No HEAD in CAS directory: {directory}")
            commit = head_path.read_text().strip()

        commit_obj = json.loads(
            (directory / "commits" / f"{commit}.json").read_text()
        )
        tree_obj = json.loads(
            (directory / "trees" / f"{commit_obj['tree']}.json").read_text()
        )

        agents = []
        for h in tree_obj["hashes"]:
            agent_data = json.loads(
                (directory / "blobs" / f"{h}.json").read_text()
            )
            agents.append(Agent.from_dict(agent_data))

        agent_list = AgentList(agents)
        meta = tree_obj.get("metadata", {})
        if meta.get("codebook"):
            agent_list.set_codebook(meta["codebook"])
        if meta.get("instruction"):
            agent_list.set_instruction(meta["instruction"])
        if meta.get("traits_presentation_template"):
            agent_list.set_traits_presentation_template(
                meta["traits_presentation_template"]
            )
        return agent_list

    @staticmethod
    def cas_log(
        directory: Union[str, Path],
        commit: Optional[str] = None,
    ) -> List[dict]:
        """Walk the commit chain and return the history.

        Args:
            directory: Path to a CAS repository.
            commit: Starting commit hash. Defaults to HEAD.

        Returns:
            A list of dicts (newest first), each with keys
            ``hash``, ``tree``, ``parent``, ``timestamp``, ``message``.

        Examples:
            >>> import tempfile
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22})])
            >>> d = tempfile.mkdtemp()
            >>> al.to_cas(d, message="first")  # doctest: +ELLIPSIS
            '...'
            >>> al2 = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> al2.to_cas(d, message="added agent")  # doctest: +ELLIPSIS
            '...'
            >>> log = AgentList.cas_log(d)
            >>> len(log)
            2
            >>> log[0]['message']
            'added agent'
            >>> log[1]['message']
            'first'
        """
        directory = Path(directory)

        if commit is None:
            head_path = directory / "HEAD"
            if not head_path.exists():
                raise FileNotFoundError(f"No HEAD in CAS directory: {directory}")
            commit = head_path.read_text().strip()

        history: list[dict] = []
        current: Optional[str] = commit
        while current:
            commit_obj = json.loads(
                (directory / "commits" / f"{current}.json").read_text()
            )
            history.append({"hash": current, **commit_obj})
            current = commit_obj.get("parent")
        return history

    # ------------------------------------------------------------------
    # JSONL deserialization (static — no instance needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
        """Normalise *source* into an iterable of lines."""
        if isinstance(source, Path):
            with open(source, "r") as fh:
                yield from fh
            return

        if isinstance(source, str):
            # A multi-line string is JSONL content, not a file path.
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

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]]) -> "AgentList":
        """Create an AgentList from a JSONL source.

        The first line must be a metadata header produced by
        :meth:`to_jsonl`; every subsequent line is an Agent record.

        Args:
            source: A file path, a JSONL string, or any iterable of
                JSON-encoded lines.

        Returns:
            A fully materialised AgentList.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> al2 = AgentList.from_jsonl(al.to_jsonl())
            >>> al == al2
            True
        """
        from .agent import Agent
        from .agent_list import AgentList

        lines = AgentListSerializer._open_lines(source)
        line_iter = iter(lines)
        meta = json.loads(next(line_iter))
        agents = [
            Agent.from_dict(json.loads(line))
            for line in line_iter
            if line.strip()
        ]
        agent_list = AgentList(agents)
        if meta.get("codebook"):
            agent_list.set_codebook(meta["codebook"])
        if meta.get("instruction"):
            agent_list.set_instruction(meta["instruction"])
        if meta.get("traits_presentation_template"):
            agent_list.set_traits_presentation_template(
                meta["traits_presentation_template"]
            )
        return agent_list

    @staticmethod
    def iter_agents_from_jsonl(
        source: Union[str, Path, Iterable[str]],
    ) -> Generator["Agent", None, None]:
        """Lazily yield Agent objects from a JSONL source.

        Reads and discards the metadata header, then yields one Agent
        per remaining line without materialising the full list.

        Args:
            source: A file path, a JSONL string, or any iterable of
                JSON-encoded lines.

        Yields:
            Agent instances.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
            >>> agents = list(AgentList.iter_agents_from_jsonl(al.to_jsonl()))
            >>> len(agents)
            2
            >>> agents[0].traits['age']
            22
        """
        from .agent import Agent

        lines = AgentListSerializer._open_lines(source)
        line_iter = iter(lines)
        next(line_iter)  # skip metadata header
        for line in line_iter:
            if line.strip():
                yield Agent.from_dict(json.loads(line))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
