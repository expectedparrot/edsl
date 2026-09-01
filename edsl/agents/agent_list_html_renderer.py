"""Standalone HTML rendering for AgentList artifacts."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, TYPE_CHECKING

from edsl.base.html_artifacts import package_remote_context

if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListHTMLRenderer:
    """Build a standalone, interactive HTML artifact for an AgentList."""

    def __init__(self, agent_list: "AgentList") -> None:
        self.agent_list = agent_list

    def render(
        self,
        *,
        title: str = "AgentList",
        include_prompts: bool = True,
    ) -> str:
        """Return a standalone HTML document for the AgentList.

        Args:
            title: Document and page title.
            include_prompts: Whether to render each agent prompt for the detail drawer.
        """
        payload = self._payload(title=title, include_prompts=include_prompts)
        data = json.dumps(payload, ensure_ascii=False, default=str).replace(
            "</", "<\\/"
        )
        escaped_title = escape(title)

        return HTML_TEMPLATE.replace("__TITLE__", escaped_title).replace(
            "__AGENTLIST_DATA__", data
        )

    def save(
        self,
        filename: str | Path,
        *,
        title: str = "AgentList",
        include_prompts: bool = True,
    ) -> Path:
        """Write a standalone HTML artifact and return its path."""
        path = Path(filename)
        path.write_text(
            self.render(title=title, include_prompts=include_prompts),
            encoding="utf-8",
        )
        return path

    @classmethod
    def from_package(cls, path: str | Path, ref: str = "HEAD") -> "AgentListPackageHTMLRenderer":
        return AgentListPackageHTMLRenderer(Path(path), ref=ref)

    def _payload(self, *, title: str, include_prompts: bool) -> dict[str, Any]:
        trait_keys = self._trait_keys_in_order()
        codebook, codebook_status, codebook_message = self._common_codebook()
        rows = []

        for index, agent in enumerate(self.agent_list.data):
            prompt_text = None
            prompt_error = None
            if include_prompts:
                try:
                    prompt_text = agent.prompt().text
                except Exception as exc:  # pragma: no cover - defensive artifact detail
                    prompt_error = f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "index": index,
                    "name": agent.name,
                    "traits": self._jsonable(dict(agent.traits)),
                    "instruction": getattr(agent, "instruction", None),
                    "traits_presentation_template": getattr(
                        agent, "traits_presentation_template", None
                    ),
                    "prompt": prompt_text,
                    "prompt_error": prompt_error,
                    "raw": self._jsonable(agent.to_dict(add_edsl_version=False)),
                }
            )

        diagnostics = self._diagnostics(
            trait_keys, codebook, codebook_status, codebook_message
        )

        named_count = sum(1 for agent in self.agent_list.data if agent.name is not None)
        hidden_traits = [key for key in trait_keys if key.startswith("_")]
        template_count = len(
            {
                getattr(agent, "traits_presentation_template", None)
                for agent in self.agent_list.data
            }
        )
        custom_instruction_count = sum(
            1
            for agent in self.agent_list.data
            if getattr(agent, "instruction", None)
            != getattr(agent, "default_instruction", None)
        )

        return {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "agents": len(self.agent_list.data),
                "traits": len(trait_keys),
                "named_agents": named_count,
                "codebook_entries": len(codebook),
                "codebook_coverage": self._coverage(trait_keys, codebook),
                "hidden_traits": len(hidden_traits),
                "distinct_templates": template_count,
                "custom_instructions": custom_instruction_count,
            },
            "trait_keys": trait_keys,
            "codebook": codebook,
            "codebook_status": codebook_status,
            "diagnostics": diagnostics,
            "rows": rows,
        }

    def _trait_keys_in_order(self) -> list[str]:
        keys: list[str] = []
        for agent in self.agent_list.data:
            for key in agent.traits.keys():
                if key not in keys:
                    keys.append(key)
        return keys

    def _common_codebook(self) -> tuple[dict[str, str], str, str | None]:
        if not self.agent_list.data:
            return {}, "empty", None
        try:
            return dict(self.agent_list.codebook or {}), "consistent", None
        except Exception as exc:
            first = dict(getattr(self.agent_list.data[0], "codebook", {}) or {})
            return first, "inconsistent", str(exc)

    def _diagnostics(
        self,
        trait_keys: list[str],
        codebook: dict[str, str],
        codebook_status: str,
        codebook_message: str | None,
    ) -> list[dict[str, str]]:
        diagnostics: list[dict[str, str]] = []
        trait_set = set(trait_keys)
        codebook_set = set(codebook)

        if codebook_status == "inconsistent":
            diagnostics.append(
                {
                    "level": "error",
                    "title": "Inconsistent codebooks",
                    "detail": codebook_message
                    or "Agents do not share the same codebook.",
                }
            )

        missing = sorted(trait_set - codebook_set)
        if missing:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": "Traits without codebook entries",
                    "detail": ", ".join(missing),
                }
            )

        unused = sorted(codebook_set - trait_set)
        if unused:
            diagnostics.append(
                {
                    "level": "info",
                    "title": "Codebook entries not used by these agents",
                    "detail": ", ".join(unused),
                }
            )

        missing_by_agent = []
        for index, agent in enumerate(self.agent_list.data):
            missing_keys = sorted(trait_set - set(agent.traits.keys()))
            if missing_keys:
                missing_by_agent.append(f"#{index}: {', '.join(missing_keys)}")
        if missing_by_agent:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": "Heterogeneous trait sets",
                    "detail": "; ".join(missing_by_agent),
                }
            )

        hidden = sorted(key for key in trait_keys if key.startswith("_"))
        if hidden:
            diagnostics.append(
                {
                    "level": "info",
                    "title": "Hidden prompt traits present",
                    "detail": ", ".join(hidden),
                }
            )

        if not diagnostics:
            diagnostics.append(
                {
                    "level": "ok",
                    "title": "No diagnostics",
                    "detail": "Trait keys and codebook look consistent.",
                }
            )
        return diagnostics

    def _coverage(self, trait_keys: list[str], codebook: dict[str, str]) -> float:
        if not trait_keys:
            return 1.0
        return len(set(trait_keys) & set(codebook)) / len(trait_keys)

    def _jsonable(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(k): self._jsonable(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [self._jsonable(v) for v in value]
            return repr(value)


class AgentListPackageHTMLRenderer:
    """Build an HTML artifact from an AgentList git package tree."""

    def __init__(self, path: Path, ref: str = "HEAD") -> None:
        self.path = Path(path)
        self.ref = ref

    def render(
        self,
        *,
        title: str = "AgentList",
        include_prompts: bool = True,
    ) -> str:
        payload = self._payload(title=title, include_prompts=include_prompts)
        data = json.dumps(payload, ensure_ascii=False, default=str).replace(
            "</", "<\\/"
        )
        return HTML_TEMPLATE.replace("__TITLE__", escape(title)).replace(
            "__AGENTLIST_DATA__", data
        )

    def save(
        self,
        filename: str | Path,
        *,
        title: str = "AgentList",
        include_prompts: bool = True,
    ) -> Path:
        path = Path(filename)
        path.write_text(
            self.render(title=title, include_prompts=include_prompts),
            encoding="utf-8",
        )
        return path

    def _payload(self, *, title: str, include_prompts: bool) -> dict[str, Any]:
        from edsl.base import git_package as gitpkg
        from .agent import Agent
        from .agent_list_git import AgentListGitError, _load_manifest_at_ref

        manifest = _load_manifest_at_ref(self.path, self.ref)
        agent_ids = manifest.get("agent_order", [])
        agent_dicts = [
            gitpkg.read_json_at_ref(
                self.path,
                f"agents/{agent_id}.json",
                self.ref,
                error_cls=AgentListGitError,
            )
            for agent_id in agent_ids
        ]
        rows = []
        trait_keys = self._trait_keys_in_order(agent_dicts)
        codebook, codebook_status, codebook_message = self._common_codebook(
            manifest, agent_dicts
        )

        for index, agent_data in enumerate(agent_dicts):
            prompt_text = None
            prompt_error = None
            if include_prompts:
                try:
                    prompt_text = Agent.from_dict(agent_data).prompt().text
                except Exception as exc:  # pragma: no cover - defensive artifact detail
                    prompt_error = f"{type(exc).__name__}: {exc}"
            rows.append(
                {
                    "index": index,
                    "id": agent_ids[index],
                    "name": agent_data.get("name"),
                    "traits": self._jsonable(dict(agent_data.get("traits") or {})),
                    "instruction": agent_data.get("instruction")
                    or manifest.get("instruction"),
                    "traits_presentation_template": agent_data.get(
                        "traits_presentation_template"
                    )
                    or manifest.get("traits_presentation_template"),
                    "prompt": prompt_text,
                    "prompt_error": prompt_error,
                    "raw": self._jsonable(agent_data),
                }
            )

        diagnostics = self._diagnostics(
            trait_keys, codebook, manifest, codebook_status, codebook_message
        )
        named_count = sum(1 for row in rows if row["name"] is not None)
        hidden_traits = [key for key in trait_keys if key.startswith("_")]
        templates = {
            row.get("traits_presentation_template")
            for row in rows
            if row.get("traits_presentation_template") is not None
        }
        custom_instruction_count = sum(
            1 for row in rows if row.get("instruction") is not None
        )

        provenance = {
            "path": str(self.path),
            "ref": self.ref,
        }
        try:
            provenance["commit"] = gitpkg.resolve_commit(
                self.path, self.ref, error_cls=AgentListGitError
            )
            provenance["branch"] = gitpkg.current_branch(
                self.path, error_cls=AgentListGitError
            )
        except Exception:
            pass

        return {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
            "manifest": manifest,
            "remote_context": package_remote_context(
                self.path, self.ref, manifest=manifest, error_cls=AgentListGitError
            ),
            "summary": {
                "agents": len(rows),
                "traits": len(trait_keys),
                "named_agents": named_count,
                "codebook_entries": len(codebook),
                "codebook_coverage": self._coverage(trait_keys, codebook),
                "hidden_traits": len(hidden_traits),
                "distinct_templates": len(templates),
                "custom_instructions": custom_instruction_count,
            },
            "trait_keys": trait_keys,
            "codebook": codebook,
            "codebook_status": codebook_status,
            "diagnostics": diagnostics,
            "rows": rows,
        }

    def _trait_keys_in_order(self, agent_dicts: list[dict[str, Any]]) -> list[str]:
        keys: list[str] = []
        for agent_data in agent_dicts:
            for key in (agent_data.get("traits") or {}).keys():
                if key not in keys:
                    keys.append(key)
        return keys

    def _common_codebook(
        self, manifest: dict[str, Any], agent_dicts: list[dict[str, Any]]
    ) -> tuple[dict[str, str], str, str | None]:
        manifest_codebook = manifest.get("codebook")
        if manifest_codebook:
            return dict(manifest_codebook), "consistent", None
        codebooks = [dict(agent.get("codebook") or {}) for agent in agent_dicts]
        nonempty = [codebook for codebook in codebooks if codebook]
        if not nonempty:
            return {}, "consistent", None
        first = nonempty[0]
        if all(codebook == first for codebook in nonempty):
            return first, "consistent", None
        return first, "inconsistent", "Agents do not share the same codebook."

    def _diagnostics(
        self,
        trait_keys: list[str],
        codebook: dict[str, str],
        manifest: dict[str, Any],
        codebook_status: str,
        codebook_message: str | None,
    ) -> list[dict[str, str]]:
        diagnostics: list[dict[str, str]] = []
        trait_set = set(trait_keys)
        codebook_set = set(codebook)

        if codebook_status == "inconsistent":
            diagnostics.append(
                {
                    "level": "error",
                    "title": "Inconsistent codebooks",
                    "detail": codebook_message
                    or "Agents do not share the same codebook.",
                }
            )

        if manifest.get("n_agents") != len(manifest.get("agent_order", [])):
            diagnostics.append(
                {
                    "level": "warning",
                    "title": "Manifest count mismatch",
                    "detail": "n_agents does not match agent_order length.",
                }
            )

        missing = sorted(trait_set - codebook_set)
        if missing:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": "Traits without codebook entries",
                    "detail": ", ".join(missing),
                }
            )

        unused = sorted(codebook_set - trait_set)
        if unused:
            diagnostics.append(
                {
                    "level": "info",
                    "title": "Codebook entries not used by these agents",
                    "detail": ", ".join(unused),
                }
            )

        hidden = sorted(key for key in trait_keys if key.startswith("_"))
        if hidden:
            diagnostics.append(
                {
                    "level": "info",
                    "title": "Hidden prompt traits present",
                    "detail": ", ".join(hidden),
                }
            )

        if not diagnostics:
            diagnostics.append(
                {
                    "level": "ok",
                    "title": "No diagnostics",
                    "detail": "Package manifest, trait keys, and codebook look consistent.",
                }
            )
        return diagnostics

    def _coverage(self, trait_keys: list[str], codebook: dict[str, str]) -> float:
        if not trait_keys:
            return 1.0
        return len(set(trait_keys) & set(codebook)) / len(trait_keys)

    def _jsonable(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(k): self._jsonable(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [self._jsonable(v) for v in value]
            return repr(value)


def render_agent_list_html_via_package(
    agent_list: "AgentList",
    *,
    title: str = "AgentList",
    include_prompts: bool = True,
) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        package_path = Path(temp_dir) / "agent_list.agent_list.ep"
        render_list = deepcopy(agent_list)
        render_list.git.save(package_path, message="Render AgentList HTML")
        return AgentListPackageHTMLRenderer(render_list.git.worktree_path).render(
            title=title, include_prompts=include_prompts
        )


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light;
  --bg: #ffffff;
  --panel: #ffffff;
  --ink: #1a1a1a;
  --muted: #666666;
  --line: #e0e0e0;
  --accent: #428a5f;
  --accent-strong: #00663a;
  --accent-light: #5ba97a;
  --accent-2: #1da66a;
  --accent-3: #2f6f4d;
  --danger: #b42318;
  --soft-green: #f0f7f2;
  --light-gray: #f5f5f5;
  --warn-bg: #fff8ec;
  --ok-bg: #f0f7f2;
  --shadow: 0 8px 20px rgba(26, 26, 26, 0.05);
  --font-serif: Georgia, "Times New Roman", serif;
  --font-sans: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
button, input { font: inherit; }
.app { min-height: 100vh; display: grid; grid-template-rows: auto auto 1fr; }
header {
  background: #fff;
  color: var(--ink);
  padding: 16px 28px 14px;
  border-bottom: 3px solid var(--accent);
}
.topline { display: flex; align-items: end; justify-content: space-between; gap: 18px; flex-wrap: wrap; }
h1 {
  margin: 8px 0 0;
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 620;
  letter-spacing: 0;
  color: var(--ink);
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--accent-strong);
  font-size: 13px;
  font-weight: 760;
  text-transform: uppercase;
  letter-spacing: .08em;
}
.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  color: var(--accent-strong);
  font-family: var(--font-sans);
  font-size: 24px;
  font-weight: 820;
  letter-spacing: 0;
  text-transform: none;
  line-height: 1;
}
.subtitle { margin-top: 4px; color: var(--muted); font-size: 13px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.btn {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 7px;
  padding: 8px 10px;
  cursor: pointer;
}
.btn:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--soft-green); }
.btn.copied { border-color: var(--accent); color: var(--accent-strong); background: var(--soft-green); }
.toolbar {
  position: sticky;
  top: 0;
  z-index: 4;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px 28px;
  background: rgba(255,255,255,.94);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.search {
  width: 100%;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 7px;
  padding: 10px 12px;
  color: var(--ink);
}
.main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  padding: 12px 28px 28px;
}
.facts {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 10px;
  color: var(--muted);
  font-size: 13px;
}
.fact { white-space: nowrap; }
.fact strong {
  color: var(--ink);
  font-weight: 760;
  font-variant-numeric: tabular-nums;
}
.fact + .fact::before {
  content: "/";
  color: #a1aab5;
  margin-right: 14px;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.panel { overflow: hidden; }
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
}
.panel-title { font-weight: 720; }
.table-wrap { overflow: auto; max-height: calc(100vh - 180px); }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
th {
  position: sticky;
  top: 0;
  z-index: 2;
  text-align: left;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  min-width: 140px;
}
tbody tr { background: #fff; }
tbody tr:nth-child(even) { background: var(--light-gray); }
tbody tr:hover { background: #e8f5e9; }
td.index { color: var(--muted); font-variant-numeric: tabular-nums; width: 54px; }
.missing { color: #9aa3ad; font-style: italic; }
.value { max-width: 300px; white-space: normal; overflow-wrap: anywhere; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 680;
  border: 1px solid var(--line);
  background: #fff;
}
.side { display: grid; gap: 14px; align-content: start; }
.side .panel-body { padding: 12px 14px; }
.column-tools {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}
.mini-btn {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 7px;
  padding: 6px 8px;
  font-size: 12px;
  cursor: pointer;
}
.mini-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
  background: var(--soft-green);
}
.codebook-list, .diagnostic-list, .column-list { display: grid; gap: 8px; }
.codebook-item, .diag {
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 9px 10px;
  background: #fff;
}
.key { font-family: var(--font-mono); font-size: 12px; color: var(--accent-3); }
.desc { margin-top: 4px; color: #34414d; overflow-wrap: anywhere; }
.column-head {
  display: grid;
  gap: 5px;
}
.column-name {
  font-weight: 760;
  white-space: nowrap;
}
.column-stat {
  display: grid;
  gap: 4px;
  min-width: 120px;
  color: rgba(255,255,255,.88);
  font-size: 11px;
  font-weight: 520;
  line-height: 1.25;
}
.column-stat-line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-variant-numeric: tabular-nums;
}
.mini-bars {
  display: flex;
  align-items: end;
  gap: 2px;
  height: 16px;
}
.mini-bar {
  width: 7px;
  min-height: 2px;
  background: rgba(255,255,255,.74);
  border-radius: 2px 2px 0 0;
}
.stats-btn {
  width: 20px;
  height: 20px;
  border: 1px solid rgba(255,255,255,.78);
  background: transparent;
  color: #fff;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 760;
  cursor: pointer;
}
.stats-btn:hover {
  background: rgba(255,255,255,.18);
}
.top-values {
  display: flex;
  gap: 3px;
  align-items: center;
}
.top-value {
  height: 8px;
  background: rgba(255,255,255,.74);
  border-radius: 999px;
}
.profile-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 6px;
  font-size: 13px;
}
.profile-row span:first-child { color: var(--muted); }
.profile-row strong {
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.profile-definition {
  border-left: 4px solid var(--accent);
  background: var(--soft-green);
  padding: 8px 10px;
  border-radius: 0 7px 7px 0;
  font-size: 13px;
  color: #34414d;
}
.bars {
  display: grid;
  gap: 6px;
}
.bar-row {
  display: grid;
  grid-template-columns: minmax(80px, 1fr) 42px;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}
.bar-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-track {
  grid-column: 1 / -1;
  height: 7px;
  background: var(--light-gray);
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: var(--accent);
}
.histogram {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 8px;
  align-items: end;
}
.histogram-y {
  height: 180px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.histogram-plot {
  height: 180px;
  display: flex;
  align-items: end;
  gap: 3px;
  padding: 0 0 6px;
  border-left: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.histogram-bin {
  flex: 1;
  min-width: 10px;
  background: var(--accent);
  border-radius: 3px 3px 0 0;
}
.histogram-labels {
  grid-column: 2;
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.diag[data-level="warning"] { background: var(--warn-bg); border-color: #fed7aa; }
.diag[data-level="error"] { background: #fef2f2; border-color: #fecaca; }
.diag[data-level="ok"] { background: var(--ok-bg); border-color: #bbf7d0; }
.diag-title { font-weight: 700; }
.diag-detail { margin-top: 4px; color: #4b5563; font-size: 12px; overflow-wrap: anywhere; }
.column-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.drawer {
  position: fixed;
  right: 18px;
  bottom: 18px;
  width: min(720px, calc(100vw - 36px));
  max-height: min(720px, calc(100vh - 36px));
  display: none;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  z-index: 10;
}
.drawer.open { display: flex; }
.drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 13px 15px; border-bottom: 1px solid var(--line); }
.drawer-body { padding: 14px 15px; overflow: auto; display: grid; gap: 12px; }
.modal-backdrop {
  position: fixed;
  inset: 0;
  display: none;
  align-items: center;
  justify-content: center;
  background: rgba(26, 26, 26, .34);
  z-index: 30;
  padding: 20px;
}
.modal-backdrop.open { display: flex; }
.modal {
  width: min(760px, 100%);
  max-height: min(760px, calc(100vh - 40px));
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 24px 70px rgba(26, 26, 26, .28);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 15px;
  border-bottom: 1px solid var(--line);
}
.modal-body {
  padding: 14px 15px;
  overflow: auto;
  display: grid;
  gap: 12px;
}
.modal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
}
pre {
  margin: 0;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 7px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.tab { color: var(--ink); background: #fff; border: 1px solid var(--line); border-radius: 7px; padding: 7px 9px; cursor: pointer; }
.tab.active { border-color: var(--accent); color: var(--accent-strong); background: var(--soft-green); }
.empty { color: var(--muted); padding: 22px; text-align: center; }
.toast {
  position: fixed;
  top: 18px;
  right: 28px;
  z-index: 20;
  transform: translateY(-12px);
  opacity: 0;
  pointer-events: none;
  background: var(--accent-strong);
  color: #fff;
  border-radius: 7px;
  padding: 9px 12px;
  box-shadow: 0 12px 28px rgba(26, 26, 26, .16);
  transition: opacity .16s ease, transform .16s ease;
}
.toast.show {
  transform: translateY(0);
  opacity: 1;
}
@media (max-width: 980px) {
  .toolbar { grid-template-columns: 1fr; }
  .main { grid-template-columns: 1fr; padding: 14px; }
  .fact + .fact::before { content: ""; margin-right: 0; }
  header { padding: 18px 14px; }
}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="topline">
      <div>
        <div class="brand">
          <span class="brand-mark" aria-label="Expected Parrot logo">E[🦜]</span>
          <span>Expected Parrot</span>
        </div>
        <h1 id="title"></h1>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <div class="actions">
        <button class="btn" id="copy-json">Copy JSON</button>
        <button class="btn" id="download-json">Download JSON</button>
      </div>
    </div>
  </header>
  <div class="toolbar">
    <input class="search" id="search" type="search" placeholder="Search agents, traits, prompts, or codebook text">
    <span class="pill" id="visible-count"></span>
    <span class="pill" id="coverage"></span>
  </div>
  <main class="main">
    <section>
      <div class="facts" id="facts"></div>
      <div class="panel">
        <div class="panel-head">
          <div class="panel-title">Agents</div>
          <div class="pill">Click a row for details</div>
        </div>
        <div class="table-wrap">
          <table id="agent-table"></table>
        </div>
      </div>
    </section>
    <aside class="side">
      <div class="panel">
        <div class="panel-head"><div class="panel-title">Columns</div></div>
        <div class="column-tools">
          <button class="mini-btn" id="select-all-columns">Select all</button>
          <button class="mini-btn" id="unselect-all-columns">Unselect all</button>
        </div>
        <div class="panel-body column-list" id="columns"></div>
      </div>
      <div class="panel">
        <div class="panel-head"><div class="panel-title">Codebook</div><span class="pill" id="codebook-status"></span></div>
        <div class="panel-body codebook-list" id="codebook"></div>
      </div>
      <div class="panel">
        <div class="panel-head"><div class="panel-title">Diagnostics</div></div>
        <div class="panel-body diagnostic-list" id="diagnostics"></div>
      </div>
    </aside>
  </main>
</div>
<div class="drawer" id="drawer">
  <div class="drawer-head">
    <strong id="drawer-title"></strong>
    <button class="tab" id="drawer-close">Close</button>
  </div>
  <div class="drawer-body">
    <div class="tabs">
      <button class="tab active" data-tab="traits">Traits</button>
      <button class="tab" data-tab="prompt">Prompt</button>
      <button class="tab" data-tab="raw">Raw</button>
    </div>
    <pre id="drawer-content"></pre>
  </div>
</div>
<div class="modal-backdrop" id="column-modal" role="dialog" aria-modal="true" aria-labelledby="column-modal-title">
  <div class="modal">
    <div class="modal-head">
      <strong id="column-modal-title"></strong>
      <button class="tab" id="column-modal-close">Close</button>
    </div>
    <div class="modal-body" id="column-modal-body"></div>
  </div>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
const DATA = __AGENTLIST_DATA__;
const state = {
  sortKey: "index",
  sortDir: 1,
  query: "",
  visibleColumns: new Set(["index", "name", ...DATA.trait_keys]),
  selected: null,
  tab: "traits"
};

const fmt = new Intl.NumberFormat();
const pct = value => `${Math.round(value * 100)}%`;
const text = value => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
};
const cellText = value => {
  if (value === null || value === undefined) return "<span class='missing'>NA</span>";
  if (typeof value === "string" && value.length === 0) return "<span class='missing'>empty</span>";
  return escapeHtml(text(value));
};
const escapeHtml = value => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function init() {
  document.getElementById("title").textContent = DATA.title;
  document.getElementById("subtitle").textContent = `Generated ${DATA.generated_at} · standalone AgentList artifact`;
  renderFacts();
  renderColumns();
  renderCodebook();
  renderDiagnostics();
  bindEvents();
  renderTable();
}

function renderFacts() {
  const s = DATA.summary;
  const items = [
    ["agents", fmt.format(s.agents)],
    ["traits", fmt.format(s.traits)],
    ["named", fmt.format(s.named_agents)],
    ["codebook", `${fmt.format(s.codebook_entries)} entries`],
    ["coverage", pct(s.codebook_coverage)],
    ["hidden", fmt.format(s.hidden_traits)],
    ["templates", fmt.format(s.distinct_templates)],
    ["custom instructions", fmt.format(s.custom_instructions)]
  ];
  document.getElementById("facts").innerHTML = items.map(([label, value]) => `
    <span class="fact"><strong>${value}</strong> ${label}</span>
  `).join("");
  document.getElementById("coverage").textContent = `Codebook coverage ${pct(s.codebook_coverage)}`;
}

function renderColumns() {
  const columns = ["index", "name", ...DATA.trait_keys];
  document.getElementById("columns").innerHTML = columns.map(key => `
    <label class="column-item">
      <input type="checkbox" data-column="${escapeHtml(key)}" ${state.visibleColumns.has(key) ? "checked" : ""}>
      <span>${escapeHtml(key)}</span>
    </label>
  `).join("");
}

function renderCodebook() {
  document.getElementById("codebook-status").textContent = DATA.codebook_status;
  const entries = Object.entries(DATA.codebook);
  document.getElementById("codebook").innerHTML = entries.length
    ? entries.map(([key, desc]) => `
      <div class="codebook-item">
        <div class="key">${escapeHtml(key)}</div>
        <div class="desc">${escapeHtml(desc)}</div>
      </div>
    `).join("")
    : "<div class='empty'>No codebook entries.</div>";
}

function profileForColumn(key) {
  const values = DATA.rows.map(row => {
    if (key === "index") return row.index;
    if (key === "name") return row.name;
    return row.traits[key];
  });
  const present = values.filter(value => value !== null && value !== undefined && value !== "");
  const numeric = present.length > 0 && present.every(value => typeof value === "number" && Number.isFinite(value));
  const distinct = new Set(present.map(value => text(value))).size;
  const profile = {
    key,
    total: values.length,
    nonMissing: present.length,
    missing: values.length - present.length,
    distinct,
    definition: DATA.codebook[key] || "",
    type: numeric ? "numeric" : inferCategoricalType(present),
    values: present
  };
  if (numeric) addNumericStats(profile, present);
  else addCategoricalStats(profile, present);
  return profile;
}

function inferCategoricalType(values) {
  if (!values.length) return "empty";
  if (values.every(value => typeof value === "boolean")) return "boolean";
  return "categorical";
}

function addNumericStats(profile, values) {
  const sorted = [...values].sort((a, b) => a - b);
  const sum = sorted.reduce((acc, value) => acc + value, 0);
  profile.min = sorted[0];
  profile.max = sorted[sorted.length - 1];
  profile.mean = sum / sorted.length;
  profile.median = quantile(sorted, 0.5);
  profile.histogram = histogram(sorted, 8);
}

function addCategoricalStats(profile, values) {
  const counts = new Map();
  values.forEach(value => {
    const key = text(value);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  profile.topValues = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 8)
    .map(([label, count]) => ({ label, count, share: count / values.length }));
}

function quantile(sorted, q) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] === undefined) return sorted[base];
  return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
}

function histogram(sorted, bins) {
  if (!sorted.length) return [];
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  if (min === max) return [{ label: formatNumber(min), count: sorted.length, share: 1 }];
  const width = (max - min) / bins;
  const counts = Array.from({ length: bins }, () => 0);
  sorted.forEach(value => {
    const idx = Math.min(bins - 1, Math.floor((value - min) / width));
    counts[idx] += 1;
  });
  const peak = Math.max(...counts);
  return counts.map((count, idx) => {
    const start = min + idx * width;
    const end = idx === bins - 1 ? max : start + width;
    return {
      label: `${formatNumber(start)}-${formatNumber(end)}`,
      count,
      share: peak ? count / peak : 0
    };
  });
}

function numericProfileHtml(profile) {
  return `
    <div class="profile-row"><span>min</span><strong>${formatNumber(profile.min)}</strong></div>
    <div class="profile-row"><span>mean</span><strong>${formatNumber(profile.mean)}</strong></div>
    <div class="profile-row"><span>median</span><strong>${formatNumber(profile.median)}</strong></div>
    <div class="profile-row"><span>max</span><strong>${formatNumber(profile.max)}</strong></div>
    <div class="bars">${profile.histogram.map(item => barHtml(item.label, item.count, item.share)).join("")}</div>
  `;
}

function categoricalProfileHtml(profile) {
  if (!profile.topValues || !profile.topValues.length) return "";
  return `<div class="bars">${profile.topValues.map(item => barHtml(item.label, item.count, item.share)).join("")}</div>`;
}

function barHtml(label, count, share) {
  return `
    <div class="bar-row" title="${escapeHtml(label)}">
      <div class="bar-label">${escapeHtml(label)}</div>
      <strong>${fmt.format(count)}</strong>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, Math.round(share * 100))}%"></div></div>
    </div>
  `;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function renderDiagnostics() {
  document.getElementById("diagnostics").innerHTML = DATA.diagnostics.map(d => `
    <div class="diag" data-level="${escapeHtml(d.level)}">
      <div class="diag-title">${escapeHtml(d.title)}</div>
      <div class="diag-detail">${escapeHtml(d.detail)}</div>
    </div>
  `).join("");
}

function filteredRows() {
  const q = state.query.trim().toLowerCase();
  let rows = DATA.rows;
  if (q) {
    rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(q));
  }
  rows = [...rows].sort((a, b) => {
    const av = sortValue(a, state.sortKey);
    const bv = sortValue(b, state.sortKey);
    return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * state.sortDir;
  });
  return rows;
}

function sortValue(row, key) {
  if (key === "index") return String(row.index).padStart(10, "0");
  if (key === "name") return text(row.name);
  return text(row.traits[key]);
}

function renderTable() {
  const columns = ["index", "name", ...DATA.trait_keys].filter(key => state.visibleColumns.has(key));
  const rows = filteredRows();
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} visible`;
  const table = document.getElementById("agent-table");
  if (!DATA.rows.length) {
    table.innerHTML = "<tbody><tr><td class='empty'>No agents.</td></tr></tbody>";
    return;
  }
  table.innerHTML = `
    <thead><tr>${columns.map(col => `<th data-sort="${escapeHtml(col)}">${columnHeaderHtml(col)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.map(row => `<tr data-index="${row.index}">
        ${columns.map(col => `<td class="${col === "index" ? "index" : ""}"><div class="value">${cellFor(row, col)}</div></td>`).join("")}
      </tr>`).join("")}
    </tbody>
  `;
}

function headerLabel(col) {
  if (col === "index") return "#";
  if (col === "name") return "Name";
  return col;
}

function sortMark(col) {
  if (col !== state.sortKey) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function columnHeaderHtml(col) {
  const label = `${headerLabel(col)}${sortMark(col)}`;
  const stat = (col === "index" || col === "name") ? "" : columnStatHtml(profileForColumn(col));
  return `<div class="column-head"><div class="column-name">${escapeHtml(label)}</div>${stat}</div>`;
}

function columnStatHtml(profile) {
  if (profile.type === "numeric") {
    return `
      <div class="column-stat" title="${escapeHtml(profile.definition || profile.key)}">
        <div class="column-stat-line"><span>${formatNumber(profile.min)}</span><span>${formatNumber(profile.median)}</span><span>${formatNumber(profile.max)}</span><button class="stats-btn" data-column-modal="${escapeHtml(profile.key)}" title="Column details">i</button></div>
        <div class="mini-bars">${profile.histogram.map(item => `<span class="mini-bar" style="height:${Math.max(2, Math.round(item.share * 16))}px"></span>`).join("")}</div>
      </div>
    `;
  }
  const values = profile.topValues || [];
  return `
    <div class="column-stat" title="${escapeHtml(profile.definition || profile.key)}">
      <div class="column-stat-line"><span>${fmt.format(profile.distinct)} distinct</span><span>${fmt.format(profile.missing)} NA</span><button class="stats-btn" data-column-modal="${escapeHtml(profile.key)}" title="Column details">i</button></div>
      <div class="top-values">${values.slice(0, 5).map(item => `<span class="top-value" style="width:${Math.max(6, Math.round(item.share * 56))}px"></span>`).join("")}</div>
    </div>
  `;
}

function cellFor(row, col) {
  if (col === "index") return String(row.index);
  if (col === "name") return cellText(row.name);
  return cellText(row.traits[col]);
}

function bindEvents() {
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderTable();
  });
  document.getElementById("columns").addEventListener("change", event => {
    const key = event.target.dataset.column;
    if (!key) return;
    if (event.target.checked) state.visibleColumns.add(key);
    else state.visibleColumns.delete(key);
    renderTable();
  });
  document.getElementById("select-all-columns").addEventListener("click", () => {
    state.visibleColumns = new Set(["index", "name", ...DATA.trait_keys]);
    renderColumns();
    renderTable();
  });
  document.getElementById("unselect-all-columns").addEventListener("click", () => {
    state.visibleColumns = new Set(["index", "name"]);
    renderColumns();
    renderTable();
  });
  document.getElementById("agent-table").addEventListener("click", event => {
    const statsButton = event.target.closest("[data-column-modal]");
    if (statsButton) {
      event.stopPropagation();
      openColumnModal(statsButton.dataset.columnModal);
      return;
    }
    const th = event.target.closest("th");
    if (th) {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir *= -1;
      else { state.sortKey = key; state.sortDir = 1; }
      renderTable();
      return;
    }
    const tr = event.target.closest("tr[data-index]");
    if (tr) openDrawer(Number(tr.dataset.index));
  });
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("column-modal-close").addEventListener("click", closeColumnModal);
  document.getElementById("column-modal").addEventListener("click", event => {
    if (event.target.id === "column-modal") closeColumnModal();
  });
  document.querySelector(".tabs").addEventListener("click", event => {
    const tab = event.target.dataset.tab;
    if (!tab) return;
    state.tab = tab;
    document.querySelectorAll(".tab[data-tab]").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tab));
    renderDrawer();
  });
  document.getElementById("copy-json").addEventListener("click", event => copyText(JSON.stringify(DATA, null, 2), event.currentTarget));
  document.getElementById("download-json").addEventListener("click", downloadJson);
}

function openColumnModal(key) {
  const profile = profileForColumn(key);
  document.getElementById("column-modal-title").textContent = key;
  document.getElementById("column-modal-body").innerHTML = columnModalHtml(profile);
  document.getElementById("column-modal").classList.add("open");
}

function closeColumnModal() {
  document.getElementById("column-modal").classList.remove("open");
}

function columnModalHtml(profile) {
  const definition = profile.definition
    ? `<div class="profile-definition">${escapeHtml(profile.definition)}</div>`
    : `<div class="profile-definition">No codebook definition.</div>`;
  const common = `
    ${definition}
    <div class="modal-grid">
      <div class="profile-row"><span>type</span><strong>${escapeHtml(profile.type)}</strong></div>
      <div class="profile-row"><span>distinct</span><strong>${fmt.format(profile.distinct)}</strong></div>
      <div class="profile-row"><span>non-missing</span><strong>${fmt.format(profile.nonMissing)} / ${fmt.format(profile.total)}</strong></div>
      <div class="profile-row"><span>missing</span><strong>${fmt.format(profile.missing)}</strong></div>
    </div>
  `;
  const detail = profile.type === "numeric" ? numericModalHtml(profile) : categoricalModalHtml(profile);
  return common + detail;
}

function numericModalHtml(profile) {
  return `
    <div class="modal-grid">
      <div class="profile-row"><span>min</span><strong>${formatNumber(profile.min)}</strong></div>
      <div class="profile-row"><span>mean</span><strong>${formatNumber(profile.mean)}</strong></div>
      <div class="profile-row"><span>median</span><strong>${formatNumber(profile.median)}</strong></div>
      <div class="profile-row"><span>max</span><strong>${formatNumber(profile.max)}</strong></div>
    </div>
    ${histogramHtml(profile)}
  `;
}

function categoricalModalHtml(profile) {
  if (!profile.topValues || !profile.topValues.length) return "";
  return `<div class="bars">${profile.topValues.map(item => barHtml(item.label, item.count, item.share)).join("")}</div>`;
}

function histogramHtml(profile) {
  const bins = profile.histogram || [];
  if (!bins.length) return "";
  const maxCount = Math.max(...bins.map(item => item.count));
  return `
    <div class="histogram" aria-label="Histogram for ${escapeHtml(profile.key)}">
      <div class="histogram-y"><span>${fmt.format(maxCount)}</span><span>${fmt.format(Math.round(maxCount / 2))}</span><span>0</span></div>
      <div class="histogram-plot">
        ${bins.map(item => `<div class="histogram-bin" title="${escapeHtml(item.label)}: ${fmt.format(item.count)}" style="height:${Math.max(2, Math.round((item.count / maxCount) * 174))}px"></div>`).join("")}
      </div>
      <div class="histogram-labels"><span>${formatNumber(profile.min)}</span><span>${formatNumber(profile.max)}</span></div>
    </div>
  `;
}

function openDrawer(index) {
  state.selected = DATA.rows.find(row => row.index === index);
  state.tab = "traits";
  document.querySelectorAll(".tab[data-tab]").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === "traits"));
  document.getElementById("drawer").classList.add("open");
  renderDrawer();
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
}

function renderDrawer() {
  const row = state.selected;
  if (!row) return;
  document.getElementById("drawer-title").textContent = `Agent #${row.index}${row.name ? " · " + row.name : ""}`;
  let content;
  if (state.tab === "prompt") {
    content = row.prompt_error ? row.prompt_error : (row.prompt || "");
  } else if (state.tab === "raw") {
    content = JSON.stringify(row.raw, null, 2);
  } else {
    content = JSON.stringify(row.traits, null, 2);
  }
  document.getElementById("drawer-content").textContent = content || "(empty)";
}

function copyText(value, button) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(value).then(
      () => showCopySuccess(button),
      () => showToast("Clipboard blocked by browser")
    );
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (copied) showCopySuccess(button);
  else showToast("Clipboard blocked by browser");
}

function showCopySuccess(button) {
  showToast("JSON copied");
  if (!button) return;
  const original = button.textContent;
  button.textContent = "Copied";
  button.classList.add("copied");
  setTimeout(() => {
    button.textContent = original;
    button.classList.remove("copied");
  }, 1300);
}

let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 1600);
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${DATA.title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "agent-list"}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

init();
</script>
</body>
</html>
"""


SIMPLE_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light;
  --bg: #f7f8f7;
  --panel: #ffffff;
  --ink: #202322;
  --muted: #66706b;
  --line: #dde3df;
  --line-strong: #c7d1cb;
  --accent: #2f6f4d;
  --accent-soft: #eef6f1;
  --warn: #9a5b12;
  --warn-bg: #fff7e8;
  --error: #a33a32;
  --error-bg: #fff0ee;
  --ok: #2f6f4d;
  --ok-bg: #eef6f1;
  --shadow: 0 8px 24px rgba(31, 41, 35, .06);
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  letter-spacing: 0;
}
button, input { font: inherit; }
button { cursor: pointer; }
.shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
header { display: grid; gap: 12px; padding: 8px 0 18px; }
.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.brand-mark { font-size: 19px; line-height: 1; text-transform: none; }
.title-row {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
h1 { margin: 0; font-size: 30px; font-weight: 680; letter-spacing: 0; }
.subtitle { color: var(--muted); font-size: 13px; margin-top: 5px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.btn {
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--ink);
  border-radius: 7px;
  padding: 8px 10px;
}
.btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.facts { display: flex; gap: 10px; flex-wrap: wrap; }
.fact {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 7px;
  padding: 8px 10px;
  color: var(--muted);
  font-size: 13px;
}
.fact strong {
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  margin-right: 4px;
}
.notice {
  display: none;
  border-radius: 7px;
  padding: 10px 12px;
  font-size: 13px;
  border: 1px solid var(--line);
}
.notice.show { display: block; }
.notice.ok { background: var(--ok-bg); border-color: #b9dec8; color: var(--ok); }
.notice.warning { background: var(--warn-bg); border-color: #f0cc8a; color: var(--warn); }
.notice.error { background: var(--error-bg); border-color: #efb4ad; color: var(--error); }
.remote-heading { margin-bottom: 8px; }
.remote-meta {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
  font-size: 12px;
}
.remote-meta th,
.remote-meta td {
  position: static;
  padding: 5px 8px;
  border: 1px solid #cfe3d6;
  background: rgba(255, 255, 255, .55);
  color: inherit;
  text-align: left;
  vertical-align: top;
}
.remote-meta th {
  width: 132px;
  color: var(--muted);
  font-weight: 650;
}
.remote-meta td { overflow-wrap: anywhere; }
.copy-mini {
  border: 1px solid #b9dec8;
  border-radius: 5px;
  background: #fff;
  color: var(--ok);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  padding: 2px 6px;
  margin-left: 8px;
}
.tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--line);
  margin-top: 8px;
}
.tab {
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--muted);
  padding: 10px 11px 9px;
  font-weight: 650;
}
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px;
  border-bottom: 1px solid var(--line);
}
.search {
  min-width: min(420px, 100%);
  flex: 1;
  border: 1px solid var(--line-strong);
  border-radius: 7px;
  padding: 9px 10px;
  background: #fff;
  color: var(--ink);
}
.muted { color: var(--muted); font-size: 13px; }
.view { display: none; margin-top: 16px; }
.view.active { display: block; }
.table-wrap { overflow: auto; max-height: calc(100vh - 260px); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f1f5f2;
  color: #303832;
  font-weight: 700;
}
th[data-sort] { cursor: pointer; }
tbody tr { background: #fff; }
tbody tr:hover { background: #f2f8f4; }
td.index { width: 58px; color: var(--muted); font-variant-numeric: tabular-nums; }
.value { max-width: 360px; overflow-wrap: anywhere; }
.missing { color: #9aa39e; font-style: italic; }
.empty { padding: 28px; color: var(--muted); text-align: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; padding: 14px; }
.item { border: 1px solid var(--line); border-radius: 7px; padding: 10px; background: #fff; }
.key { font-family: var(--font-mono); color: var(--accent); font-size: 12px; overflow-wrap: anywhere; }
.desc { margin-top: 5px; color: #35423a; overflow-wrap: anywhere; }
.diag[data-level="ok"] { background: var(--ok-bg); border-color: #b9dec8; }
.diag[data-level="warning"] { background: var(--warn-bg); border-color: #f0cc8a; }
.diag[data-level="error"] { background: var(--error-bg); border-color: #efb4ad; }
.diag-title { font-weight: 700; }
.diag-detail { margin-top: 5px; color: #4e5a54; font-size: 13px; overflow-wrap: anywhere; }
.package-list { display: grid; gap: 9px; padding: 14px; }
.package-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 12px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px;
  font-size: 13px;
}
.package-row:last-child { border-bottom: 0; }
.package-row span:first-child { color: var(--muted); }
.package-row code { font-family: var(--font-mono); font-size: 12px; overflow-wrap: anywhere; }
details { margin: 0 14px 14px; border: 1px solid var(--line); border-radius: 7px; background: #fff; }
summary { padding: 10px 12px; cursor: pointer; font-weight: 650; }
pre {
  margin: 0;
  padding: 12px;
  border-top: 1px solid var(--line);
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #17201a;
  color: #eef7f0;
  font-family: var(--font-mono);
  font-size: 12px;
}
.drawer-backdrop {
  position: fixed;
  inset: 0;
  display: none;
  background: rgba(24, 32, 27, .28);
  z-index: 20;
}
.drawer-backdrop.open { display: block; }
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: min(560px, 100vw);
  height: 100vh;
  background: #fff;
  border-left: 1px solid var(--line);
  box-shadow: -16px 0 40px rgba(31, 41, 35, .16);
  transform: translateX(100%);
  transition: transform .16s ease;
  z-index: 21;
  display: grid;
  grid-template-rows: auto auto 1fr;
}
.drawer.open { transform: translateX(0); }
.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.drawer-title { font-weight: 720; }
.drawer-tabs { display: flex; gap: 6px; padding: 10px 12px 0; border-bottom: 1px solid var(--line); }
.drawer-body { overflow: auto; padding: 14px; }
.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 30;
  opacity: 0;
  transform: translateY(8px);
  pointer-events: none;
  background: var(--accent);
  color: #fff;
  border-radius: 7px;
  padding: 9px 12px;
  transition: opacity .14s ease, transform .14s ease;
}
.toast.show { opacity: 1; transform: translateY(0); }
@media (max-width: 760px) {
  .shell { padding: 16px; }
  h1 { font-size: 24px; }
  .package-row { grid-template-columns: 1fr; gap: 4px; }
  .table-wrap { max-height: none; }
}
</style>
</head>
<body>
<div class="shell">
  <header>
    <div class="brand"><span class="brand-mark">E[🦜]</span><span>Expected Parrot</span></div>
    <div class="title-row">
      <div>
        <h1 id="title"></h1>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <div class="actions">
        <button class="btn" id="copy-json">Copy JSON</button>
        <button class="btn" id="download-json">Download JSON</button>
      </div>
    </div>
    <div class="facts" id="facts"></div>
    <div class="notice" id="diagnostic-summary"></div>
    <div class="notice" id="remote-summary"></div>
  </header>

  <nav class="tabs" aria-label="AgentList views">
    <button class="tab active" data-view-tab="agents">Agents</button>
    <button class="tab" data-view-tab="codebook">Codebook</button>
    <button class="tab" data-view-tab="package">Package</button>
  </nav>

  <section class="view active" id="view-agents">
    <div class="panel">
      <div class="toolbar">
        <input class="search" id="search" type="search" placeholder="Search agents and traits">
        <span class="muted" id="visible-count"></span>
      </div>
      <div class="table-wrap">
        <table id="agent-table"></table>
      </div>
    </div>
  </section>

  <section class="view" id="view-codebook">
    <div class="panel">
      <div class="toolbar">
        <strong>Codebook</strong>
        <span class="muted" id="codebook-status"></span>
      </div>
      <div class="grid" id="codebook"></div>
      <details>
        <summary>Diagnostics</summary>
        <div class="grid" id="diagnostics"></div>
      </details>
    </div>
  </section>

  <section class="view" id="view-package">
    <div class="panel">
      <div class="toolbar">
        <strong>Package</strong>
        <span class="muted">Git-backed object provenance</span>
      </div>
      <div class="package-list" id="package"></div>
      <details>
        <summary>Manifest JSON</summary>
        <pre id="manifest-json"></pre>
      </details>
    </div>
  </section>
</div>

<div class="drawer-backdrop" id="drawer-backdrop"></div>
<aside class="drawer" id="drawer">
  <div class="drawer-head">
    <div>
      <div class="drawer-title" id="drawer-title"></div>
      <div class="muted" id="drawer-subtitle"></div>
    </div>
    <button class="btn" id="drawer-close">Close</button>
  </div>
  <div class="drawer-tabs">
    <button class="tab active" data-drawer-tab="traits">Traits</button>
    <button class="tab" data-drawer-tab="prompt">Prompt</button>
    <button class="tab" data-drawer-tab="raw">Raw JSON</button>
  </div>
  <div class="drawer-body">
    <pre id="drawer-content"></pre>
  </div>
</aside>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script>
const DATA = __AGENTLIST_DATA__;
const state = {
  view: "agents",
  drawerTab: "traits",
  query: "",
  sortKey: "index",
  sortDir: 1,
  selected: null
};

const fmt = new Intl.NumberFormat();
const pct = value => `${Math.round(value * 100)}%`;
const escapeHtml = value => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const text = value => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
};
const cellText = value => {
  if (value === null || value === undefined) return "<span class='missing'>NA</span>";
  if (typeof value === "string" && value.length === 0) return "<span class='missing'>empty</span>";
  return escapeHtml(text(value));
};

function init() {
  document.getElementById("title").textContent = DATA.title;
  document.getElementById("subtitle").textContent = subtitleText();
  renderFacts();
  renderDiagnosticSummary();
  renderRemoteSummary();
  renderTable();
  renderCodebook();
  renderPackage();
  bindEvents();
}

function subtitleText() {
  const p = DATA.provenance || {};
  const bits = [];
  if (p.path) bits.push(p.path.split("/").pop());
  if (p.branch) bits.push(p.branch);
  if (p.commit) bits.push(p.commit.slice(0, 8));
  return bits.length ? bits.join(" · ") : `Generated ${DATA.generated_at}`;
}

function renderFacts() {
  const s = DATA.summary;
  const items = [
    [fmt.format(s.agents), "agents"],
    [fmt.format(s.traits), "traits"],
    [`${fmt.format(s.codebook_entries)}`, "codebook entries"],
    [pct(s.codebook_coverage), "coverage"]
  ];
  document.getElementById("facts").innerHTML = items.map(([value, label]) => `
    <span class="fact"><strong>${value}</strong>${label}</span>
  `).join("");
}

function meaningfulDiagnostics() {
  return DATA.diagnostics.filter(d => d.level !== "ok");
}

function renderDiagnosticSummary() {
  const notice = document.getElementById("diagnostic-summary");
  const diagnostics = meaningfulDiagnostics();
  if (!diagnostics.length) {
    notice.className = "notice show ok";
    notice.textContent = "No package or codebook issues detected.";
    return;
  }
  const hasError = diagnostics.some(d => d.level === "error");
  notice.className = `notice show ${hasError ? "error" : "warning"}`;
  notice.textContent = diagnostics.map(d => d.title).join("; ");
}

function renderRemoteSummary() {
  const notice = document.getElementById("remote-summary");
  const context = DATA.remote_context || {};
  const rows = context.display_rows || [];
  if (!rows.length) {
    notice.className = "notice";
    notice.textContent = "";
    return;
  }
  const firstUrl = rows.find(row => row.label.toLowerCase().includes("url"));
  const primary = firstUrl || rows[0];
  const heading = context.display_name && firstUrl
    ? { label: "object", value: context.display_name, href: firstUrl.href || firstUrl.value }
    : primary;
  const headingCopy = context.display_name ? copyButtonHtml({ label: "display name", value: context.display_name }) : "";
  notice.className = "notice show ok";
  notice.innerHTML = `<div class="remote-heading"><strong>Expected Parrot Server:</strong> ${remoteValueHtml(heading)}${headingCopy}</div>${remoteMetaHtml(rows)}`;
}

function remoteValueHtml(row) {
  const href = row.href || (isHttpUrl(row.value) ? row.value : "");
  if (!href) return escapeHtml(row.value);
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(row.value)}</a>`;
}

function copyButtonHtml(row) {
  const label = row.label.toLowerCase();
  if (label !== "url" && label !== "alias url" && label !== "uuid" && label !== "display name") return "";
  return `<button class="copy-mini" data-copy="${escapeHtml(row.value)}" type="button">Copy</button>`;
}

function isHttpUrl(value) {
  return typeof value === "string" && (value.startsWith("https://") || value.startsWith("http://"));
}

function remoteMetaHtml(rows) {
  const preferred = ["object alias", "owner", "URL", "UUID", "description", "visibility", "updated", "created"];
  const rank = row => {
    const index = preferred.indexOf(row.label);
    return index === -1 ? preferred.length : index;
  };
  const visible = rows
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, 8);
  if (!visible.length) return "";
  return `<table class="remote-meta"><tbody>${visible.map(row => `
    <tr><th>${escapeHtml(row.label)}</th><td>${remoteValueHtml(row)}${copyButtonHtml(row)}</td></tr>
  `).join("")}</tbody></table>`;
}

function filteredRows() {
  const q = state.query.trim().toLowerCase();
  let rows = DATA.rows;
  if (q) rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(q));
  return [...rows].sort((a, b) => {
    const av = sortValue(a, state.sortKey);
    const bv = sortValue(b, state.sortKey);
    return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * state.sortDir;
  });
}

function sortValue(row, key) {
  if (key === "index") return String(row.index).padStart(10, "0");
  if (key === "name") return row.name || "";
  return text(row.traits[key]);
}

function renderTable() {
  const columns = ["index", "name", ...DATA.trait_keys];
  const rows = filteredRows();
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} of ${fmt.format(DATA.rows.length)} visible`;
  if (!DATA.rows.length) {
    document.getElementById("agent-table").innerHTML = "<tbody><tr><td class='empty'>No agents.</td></tr></tbody>";
    return;
  }
  document.getElementById("agent-table").innerHTML = `
    <thead><tr>${columns.map(key => `<th data-sort="${escapeHtml(key)}">${escapeHtml(key)}${sortArrow(key)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.map(row => `<tr data-index="${row.index}">
        ${columns.map(key => cellHtml(row, key)).join("")}
      </tr>`).join("")}
    </tbody>
  `;
}

function sortArrow(key) {
  if (state.sortKey !== key) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function cellHtml(row, key) {
  if (key === "index") return `<td class="index">${row.index + 1}</td>`;
  if (key === "name") return `<td><div class="value">${cellText(row.name)}</div></td>`;
  return `<td><div class="value">${cellText(row.traits[key])}</div></td>`;
}

function renderCodebook() {
  document.getElementById("codebook-status").textContent = `${DATA.codebook_status} · ${pct(DATA.summary.codebook_coverage)} coverage`;
  const entries = Object.entries(DATA.codebook);
  document.getElementById("codebook").innerHTML = entries.length
    ? entries.map(([key, desc]) => `
      <div class="item">
        <div class="key">${escapeHtml(key)}</div>
        <div class="desc">${escapeHtml(desc)}</div>
      </div>
    `).join("")
    : "<div class='empty'>No codebook entries.</div>";
  document.getElementById("diagnostics").innerHTML = DATA.diagnostics.map(d => `
    <div class="item diag" data-level="${escapeHtml(d.level)}">
      <div class="diag-title">${escapeHtml(d.title)}</div>
      <div class="diag-detail">${escapeHtml(d.detail)}</div>
    </div>
  `).join("");
}

function renderPackage() {
  const p = DATA.provenance || {};
  const remoteRows = (DATA.remote_context?.display_rows || []).map(row => ({ label: row.label, value: row.value, href: row.href }));
  const rows = [
    { label: "path", value: p.path },
    { label: "ref", value: p.ref },
    { label: "branch", value: p.branch },
    { label: "commit", value: p.commit },
    { label: "format", value: DATA.manifest?.format },
    { label: "edsl version", value: DATA.manifest?.edsl_version },
    { label: "generated", value: DATA.generated_at },
    ...remoteRows
  ].filter(row => row.value !== undefined && row.value !== null && row.value !== "");
  document.getElementById("package").innerHTML = rows.map(row => `
    <div class="package-row"><span>${escapeHtml(row.label)}</span><code>${remoteValueHtml(row)}</code></div>
  `).join("");
  document.getElementById("manifest-json").textContent = JSON.stringify(DATA.manifest, null, 2);
}

function bindEvents() {
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.addEventListener("click", () => setView(button.dataset.viewTab));
  });
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderTable();
  });
  document.getElementById("agent-table").addEventListener("click", event => {
    const th = event.target.closest("th[data-sort]");
    if (th) {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir *= -1;
      else {
        state.sortKey = key;
        state.sortDir = 1;
      }
      renderTable();
      return;
    }
    const row = event.target.closest("tr[data-index]");
    if (row) openDrawer(Number(row.dataset.index));
  });
  document.querySelectorAll("[data-drawer-tab]").forEach(button => {
    button.addEventListener("click", () => setDrawerTab(button.dataset.drawerTab));
  });
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
  document.getElementById("copy-json").addEventListener("click", copyJson);
  document.getElementById("download-json").addEventListener("click", downloadJson);
  document.getElementById("remote-summary").addEventListener("click", event => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    navigator.clipboard?.writeText(button.dataset.copy).then(
      () => showToast("Copied"),
      () => showToast("Clipboard blocked by browser")
    );
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeDrawer();
  });
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.viewTab === view);
  });
  document.querySelectorAll(".view").forEach(section => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
}

function openDrawer(index) {
  state.selected = DATA.rows.find(row => row.index === index);
  state.drawerTab = "traits";
  document.getElementById("drawer-title").textContent = state.selected.name || `Agent ${index + 1}`;
  document.getElementById("drawer-subtitle").textContent = state.selected.id ? `agent file ${state.selected.id}.json` : "";
  setDrawerTab("traits");
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-backdrop").classList.add("open");
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-backdrop").classList.remove("open");
}

function setDrawerTab(tab) {
  state.drawerTab = tab;
  document.querySelectorAll("[data-drawer-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.drawerTab === tab);
  });
  renderDrawerContent();
}

function renderDrawerContent() {
  if (!state.selected) return;
  let value;
  if (state.drawerTab === "traits") {
    value = {
      traits: state.selected.traits,
      instruction: state.selected.instruction,
      traits_presentation_template: state.selected.traits_presentation_template
    };
  } else if (state.drawerTab === "prompt") {
    value = state.selected.prompt_error || state.selected.prompt || "Prompt was not generated for this artifact.";
  } else {
    value = state.selected.raw;
  }
  document.getElementById("drawer-content").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function copyJson() {
  const json = JSON.stringify(DATA, null, 2);
  navigator.clipboard?.writeText(json).then(
    () => showToast("JSON copied"),
    () => showToast("Clipboard blocked by browser")
  );
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${DATA.title.replace(/[^a-z0-9_-]+/gi, "_").toLowerCase() || "agent_list"}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 1700);
}

init();
</script>
</body>
</html>
"""

HTML_TEMPLATE = SIMPLE_HTML_TEMPLATE
