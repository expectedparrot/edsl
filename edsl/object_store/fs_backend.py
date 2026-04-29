"""Filesystem implementation of :class:`StorageBackend`."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator


class FileSystemBackend:
    """StorageBackend backed by a local directory.

    Examples:
        >>> import tempfile
        >>> backend = FileSystemBackend(tempfile.mkdtemp())
        >>> backend.write("a/b.txt", "hello")
        >>> backend.read("a/b.txt")
        'hello'
        >>> backend.exists("a/b.txt")
        True
        >>> list(backend.list_prefix("a/"))
        ['a/b.txt']
        >>> backend.delete("a/b.txt")
        >>> backend.exists("a/b.txt")
        False
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def read(self, key: str) -> str:
        p = self.root / key
        if not p.exists():
            raise KeyError(key)
        return p.read_text()

    def write(self, key: str, content: str) -> None:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def delete(self, key: str) -> None:
        p = self.root / key
        if p.exists():
            p.unlink()

    def list_prefix(self, prefix: str) -> Iterator[str]:
        base = self.root / prefix
        if not base.exists():
            return
        # If prefix points to a directory, list files inside it
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    yield str(p.relative_to(self.root))
        # If it's a file-like prefix, glob the parent
        else:
            parent = base.parent
            if parent.exists():
                name_prefix = base.name
                for p in sorted(parent.iterdir()):
                    if p.is_file() and p.name.startswith(name_prefix):
                        yield str(p.relative_to(self.root))

    def delete_tree(self, prefix: str) -> None:
        p = self.root / prefix if prefix else self.root
        if p.exists() and p.is_dir():
            shutil.rmtree(p)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
