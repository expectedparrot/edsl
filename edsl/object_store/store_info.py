"""Thin wrapper types for ObjectStore operation results.

Each class subclasses ``dict`` or ``list`` so that programmatic access
(``info["uuid"]``, ``len(items)``, ``items[0]``) works unchanged.
Display methods (``__repr__``, ``_repr_html_``) delegate to
``ScenarioList.table()`` for rich formatting.
"""

from __future__ import annotations


def _to_table(rows: list[dict]) -> str:
    """Render a list of dicts as a rich table string via ScenarioList."""
    from edsl.scenarios import Scenario, ScenarioList

    sl = ScenarioList([Scenario(row) for row in rows])
    return repr(sl.table())


class StoreSaveInfo(dict):
    """Return type for ``obj.store.save()``.

    Behaves as a plain dict with keys: ``status``, ``uuid``, ``branch``,
    ``commit``, and ``message``.

    >>> info = StoreSaveInfo(status="ok", uuid="abc-123", branch="main",
    ...                      commit="deadbeef1234", message="created abc-123")
    >>> info["status"]
    'ok'
    >>> info["uuid"]
    'abc-123'
    """

    def __repr__(self) -> str:
        status = self.get("status", "?")
        uuid = self.get("uuid", "?")
        branch = self.get("branch", "?")
        commit = self.get("commit", "?")
        msg = self.get("message", "")
        return (
            f"StoreSaveInfo(status={status!r}, uuid={uuid!r}, "
            f"branch={branch!r}, commit={commit!r}, message={msg!r})"
        )

    def _repr_html_(self) -> str:
        rows = "".join(
            f"<tr><td style='font-weight:600'>{k}</td><td>{v}</td></tr>"
            for k, v in self.items()
        )
        return f"<table>{rows}</table>"


class StoreListInfo(list):
    """Return type for ``obj.store.list()`` / ``Cls.store.list()``.

    Behaves as a plain list of dicts. Displays as a rich table via
    ``ScenarioList.table()``.

    >>> items = StoreListInfo([{"uuid": "abc", "type": "AgentList"}])
    >>> len(items)
    1
    >>> items[0]["uuid"]
    'abc'
    """

    def __repr__(self) -> str:
        if not self:
            return "(no objects in store)"
        return _to_table(list(self))

    def _repr_html_(self) -> str:
        if not self:
            return "<em>No objects in store.</em>"
        from edsl.scenarios import Scenario, ScenarioList

        sl = ScenarioList([Scenario(row) for row in self])
        return sl.table()._repr_html_()


class StoreLogInfo(list):
    """Return type for ``obj.store.log()``.

    Behaves as a plain list of commit dicts. Displays as a rich table via
    ``ScenarioList.table()``.

    >>> entries = StoreLogInfo([{"hash": "abc123", "message": "init", "branch": "main"}])
    >>> len(entries)
    1
    >>> entries[0]["message"]
    'init'
    """

    def __repr__(self) -> str:
        if not self:
            return "(no commits)"
        return _to_table(list(self))

    def _repr_html_(self) -> str:
        if not self:
            return "<em>No commits.</em>"
        from edsl.scenarios import Scenario, ScenarioList

        sl = ScenarioList([Scenario(row) for row in self])
        return sl.table()._repr_html_()


class StoreDiffInfo(str):
    """Return type for ``obj.store.diff()``.

    Subclasses ``str`` so the diff text is directly usable as a string
    while ``__repr__`` renders it with ANSI colour in terminals and
    ``_repr_html_`` renders it for Jupyter notebooks.

    >>> d = StoreDiffInfo("--- a\\n+++ b\\n", commit_a="abc", commit_b="def")
    >>> "---" in d
    True
    >>> d.commit_a
    'abc'
    >>> d.commit_b
    'def'
    """

    def __new__(cls, text: str, commit_a: str = "", commit_b: str = ""):
        instance = super().__new__(cls, text)
        instance.commit_a = commit_a
        instance.commit_b = commit_b
        return instance

    def __repr__(self) -> str:
        lines = []
        for line in self.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(f"\033[32m{line}\033[0m")   # green
            elif line.startswith("-") and not line.startswith("---"):
                lines.append(f"\033[31m{line}\033[0m")   # red
            elif line.startswith("@@"):
                lines.append(f"\033[36m{line}\033[0m")   # cyan
            else:
                lines.append(line)
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """Syntax-coloured HTML for Jupyter notebooks."""
        lines = []
        for line in self.splitlines():
            escaped = line.replace("&", "&amp;").replace("<", "&lt;")
            if escaped.startswith("+") and not escaped.startswith("+++"):
                lines.append(f"<span style='color:green'>{escaped}</span>")
            elif escaped.startswith("-") and not escaped.startswith("---"):
                lines.append(f"<span style='color:red'>{escaped}</span>")
            elif escaped.startswith("@@"):
                lines.append(f"<span style='color:teal'>{escaped}</span>")
            else:
                lines.append(escaped)
        return "<pre style='font-family:monospace'>" + "<br>".join(lines) + "</pre>"
