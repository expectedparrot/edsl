"""Shared helpers for standalone EDSL HTML artifacts."""

from __future__ import annotations

import json
import subprocess
from html import escape
from pathlib import Path
from typing import Any


EDSL_BRAND_HTML = (
    '<div class="brand"><span class="brand-mark">E[🦜]</span>'
    "<span>Expected Parrot</span></div>"
)


EDSL_ARTIFACT_CSS = """
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
"""


def json_for_html(data: Any) -> str:
    """Serialize JSON safely for embedding in a script tag."""
    return json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")


def render_standalone_html(
    *,
    title: str,
    data_variable: str,
    data: Any,
    body: str,
    script: str,
    extra_css: str = "",
) -> str:
    """Assemble a standalone EDSL artifact document."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
{EDSL_ARTIFACT_CSS}
{extra_css}
</style>
</head>
<body>
{body}
<script>
const {data_variable} = {json_for_html(data)};
{script}
</script>
</body>
</html>
"""


def package_remote_context(
    path: str | Path,
    ref: str = "HEAD",
    *,
    manifest: dict[str, Any] | None = None,
    error_cls: type[Exception] | None = None,
) -> dict[str, Any] | None:
    """Return display-ready Coop and git remote metadata for a package."""
    from edsl.base import git_package as gitpkg

    package_path = Path(path)
    manifest = manifest if manifest is not None else {}
    coop_info = _optional_json_at_ref(
        package_path, "coop_info.json", ref, error_cls=error_cls
    )
    remotes = gitpkg.manifest_remotes(manifest)
    primary_remote = manifest.get("primary_remote")
    if not coop_info and not remotes:
        return None

    display_rows: list[dict[str, str]] = []
    if coop_info:
        seen_keys: set[str] = set()
        for label, keys in [
            ("object alias", ["alias", "object_alias", "alias_name"]),
            ("alias URL", ["alias_url"]),
            ("URL", ["url"]),
            ("UUID", ["uuid", "id"]),
            ("owner", ["owner", "owner_username", "username", "user"]),
            ("owner UUID", ["owner_uuid", "user_uuid"]),
            ("description", ["description"]),
            ("visibility", ["visibility"]),
            ("created", ["created_ts", "created_at"]),
            ("updated", ["last_updated_ts", "updated_at", "updated_ts"]),
        ]:
            for key in keys:
                if key in seen_keys:
                    continue
                value = coop_info.get(key)
                if value in (None, "", [], {}):
                    continue
                display_rows.append(_display_row(label, value))
                seen_keys.add(key)
                break
        owner = _first_present(
            coop_info, ["owner", "owner_username", "username", "user"]
        )
        alias = _first_present(coop_info, ["alias", "object_alias", "alias_name"])
        display_name = f"{owner}/{alias}" if owner and alias else alias or owner
    else:
        display_name = None

    if primary_remote:
        display_rows.append(_display_row("primary remote", primary_remote))

    for name, metadata in remotes.items():
        label = f"remote {name}"
        remote_value = (
            metadata.get("display_name")
            or metadata.get("server_url")
            or metadata.get("remote_url")
            or metadata.get("kind")
        )
        if remote_value:
            display_rows.append(_display_row(label, remote_value))
        for key in ["kind", "server_url", "server_uuid", "remote_url"]:
            value = metadata.get(key)
            if value not in (None, "", [], {}):
                display_rows.append(_display_row(f"{label} {key}", value))

    return {
        "coop_info": coop_info,
        "primary_remote": primary_remote,
        "remotes": remotes,
        "display_rows": display_rows,
        "display_name": display_name,
    }


def _display_row(label: str, value: Any) -> dict[str, str]:
    row = {"label": label, "value": str(value)}
    if _is_http_url(value):
        row["href"] = str(value)
    return row


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _first_present(data: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return None


def _optional_json_at_ref(
    path: Path,
    file_path: str,
    ref: str,
    *,
    error_cls: type[Exception] | None = None,
) -> dict[str, Any] | None:
    from edsl.base import git_package as gitpkg

    exists = subprocess.run(
        ["git", "-C", str(path), "cat-file", "-e", f"{ref}:{file_path}"],
        text=True,
        capture_output=True,
    )
    if exists.returncode != 0:
        return None
    try:
        return gitpkg.read_json_at_ref(
            path,
            file_path,
            ref,
            error_cls=error_cls or gitpkg.GitPackageError,
        )
    except Exception:
        return None
