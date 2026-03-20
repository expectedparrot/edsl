"""Study — captures a directory as a CAS-storable snapshot."""

from __future__ import annotations

import base64
import fnmatch
import json
from pathlib import Path
from typing import Callable, Generator, Iterable, Optional, Union


_BLOB_SENTINEL = "__cas_blob__"
_BLOB_HASH_KEY = "__blob_hash__"


class Study:
    """A snapshot of a directory tree, storable in the EDSL CAS.

    Examples:
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as d:
        ...     p = Path(d) / "proj"
        ...     _ = p.mkdir()
        ...     _ = (p / "hello.txt").write_text("hi")
        ...     s = Study(p)
        ...     s.root_name
        'proj'
        >>> with tempfile.TemporaryDirectory() as d:
        ...     p = Path(d) / "proj"
        ...     _ = p.mkdir()
        ...     _ = (p / "hello.txt").write_text("hi")
        ...     s = Study(p)
        ...     s2 = Study.from_jsonl(s.to_jsonl())
        ...     s == s2
        True
    """

    _store_class_name = "Study"
    from edsl.base.store_accessor import StoreDescriptor
    store = StoreDescriptor()

    def __init__(
        self,
        path: Union[str, Path, None] = None,
        exclude: Optional[list[str]] = None,
        *,
        _files: Optional[dict[str, bytes]] = None,
        _root_name: Optional[str] = None,
    ) -> None:
        if _files is not None:
            self.root_name: str = _root_name or ""
            self.files: dict[str, bytes] = _files
            return

        if path is None:
            self.root_name = ""
            self.files = {}
            return

        path = Path(path).resolve()
        if not path.is_dir():
            raise ValueError(f"{path} is not a directory")

        self.root_name = path.name
        exclude = exclude or []
        self.files = {}

        for filepath in sorted(path.rglob("*")):
            if not filepath.is_file():
                continue
            rel = filepath.relative_to(path)
            rel_str = str(rel)
            if any(fnmatch.fnmatch(rel_str, pat) for pat in exclude):
                continue
            self.files[rel_str] = filepath.read_bytes()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(self, target_path: Union[str, Path]) -> None:
        """Reconstruct the captured directory at target_path/root_name.

        Examples:
            >>> import tempfile
            >>> from pathlib import Path
            >>> with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            ...     p = Path(src) / "proj"
            ...     _ = p.mkdir()
            ...     _ = (p / "a.txt").write_text("alpha")
            ...     s = Study(p)
            ...     s.extract(dst)
            ...     (Path(dst) / "proj" / "a.txt").read_text()
            'alpha'
        """
        target_path = Path(target_path)
        root = target_path / self.root_name
        for rel_str, content in self.files.items():
            dest = root / rel_str
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

    # ------------------------------------------------------------------
    # JSONL serialization
    # ------------------------------------------------------------------

    def _build_header(self, has_blobs: bool = False) -> dict:
        import edsl
        return {
            "__header__": True,
            "edsl_class_name": "Study",
            "root_name": self.root_name,
            "n_files": len(self.files),
            "has_blobs": has_blobs,
            "edsl_version": edsl.__version__,
        }

    def to_jsonl_rows(
        self, blob_writer: Optional[Callable[[str], str]] = None
    ) -> Generator[str, None, None]:
        """Yield one JSON string per row: header then one row per file.

        Each file's bytes are base64-encoded. When *blob_writer* is provided
        the content is offloaded to CAS blobs and replaced with a sentinel.

        Examples:
            >>> import tempfile, json
            >>> from pathlib import Path
            >>> with tempfile.TemporaryDirectory() as d:
            ...     p = Path(d) / "proj"
            ...     _ = p.mkdir()
            ...     _ = (p / "f.txt").write_text("x")
            ...     rows = list(Study(p).to_jsonl_rows())
            ...     json.loads(rows[0])["edsl_class_name"]
            'Study'
            >>> with tempfile.TemporaryDirectory() as d:
            ...     p = Path(d) / "proj"
            ...     _ = p.mkdir()
            ...     _ = (p / "f.txt").write_text("x")
            ...     rows = list(Study(p).to_jsonl_rows())
            ...     json.loads(rows[1])["rel_path"]
            'f.txt'
        """
        yield json.dumps(self._build_header(has_blobs=blob_writer is not None))
        for rel_path, raw_bytes in self.files.items():
            b64 = base64.b64encode(raw_bytes).decode("ascii")
            if blob_writer is not None:
                blob_hash = blob_writer(b64)
                content_field = {
                    "base64_string": _BLOB_SENTINEL,
                    _BLOB_HASH_KEY: blob_hash,
                }
            else:
                content_field = b64
            yield json.dumps({"rel_path": rel_path, "content": content_field})

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        blob_writer: Optional[Callable[[str], str]] = None,
        **kwargs,
    ) -> Optional[str]:
        """Export as JSONL string or write to *filename*.

        Examples:
            >>> import tempfile, json
            >>> from pathlib import Path
            >>> with tempfile.TemporaryDirectory() as d:
            ...     p = Path(d) / "proj"
            ...     _ = p.mkdir()
            ...     _ = (p / "f.txt").write_text("x")
            ...     lines = Study(p).to_jsonl().strip().splitlines()
            ...     len(lines)
            2
        """
        if filename is not None:
            with open(filename, "w") as f:
                for row in self.to_jsonl_rows(blob_writer=blob_writer):
                    f.write(row + "\n")
            return None
        return "\n".join(self.to_jsonl_rows(blob_writer=blob_writer)) + "\n"

    @classmethod
    def from_jsonl(
        cls,
        source: Union[str, Path, Iterable[str]],
        blob_reader: Optional[Callable[[str], str]] = None,
        **kwargs,
    ) -> "Study":
        """Reconstruct a Study from JSONL.

        Examples:
            >>> import tempfile
            >>> from pathlib import Path
            >>> with tempfile.TemporaryDirectory() as d:
            ...     p = Path(d) / "proj"
            ...     _ = p.mkdir()
            ...     _ = (p / "hello.txt").write_text("hi")
            ...     s = Study(p)
            ...     s2 = Study.from_jsonl(s.to_jsonl())
            ...     s == s2
            True
        """
        lines = cls._open_lines(source)
        line_iter = iter(lines)
        meta = json.loads(next(line_iter))
        root_name = meta.get("root_name", "")
        has_blobs = meta.get("has_blobs", False)

        files: dict[str, bytes] = {}
        for line in line_iter:
            if not line.strip():
                continue
            row = json.loads(line)
            content = row["content"]
            if (
                has_blobs
                and blob_reader is not None
                and isinstance(content, dict)
                and content.get("base64_string") == _BLOB_SENTINEL
            ):
                b64 = blob_reader(content[_BLOB_HASH_KEY])
            else:
                b64 = content
            files[row["rel_path"]] = base64.b64decode(b64)

        return cls(_files=files, _root_name=root_name)

    @staticmethod
    def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
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

    # ------------------------------------------------------------------
    # Diff support
    # ------------------------------------------------------------------

    def to_yaml(self) -> str:
        """Human-readable summary used by ObjectStore.diff().

        Shows file paths and sizes rather than raw content.
        """
        lines = [f"root_name: {self.root_name}", "files:"]
        for path in sorted(self.files):
            lines.append(f"  {path}: {len(self.files[path])} bytes")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Study):
            return NotImplemented
        return self.root_name == other.root_name and self.files == other.files

    def __repr__(self) -> str:
        total = sum(len(v) for v in self.files.values())
        return (
            f"Study(root_name={self.root_name!r}, "
            f"n_files={len(self.files)}, "
            f"total_bytes={total})"
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod()
