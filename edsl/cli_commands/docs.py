"""Search and retrieve the published EDSL documentation."""

from __future__ import annotations

import itertools
import json
import re

import click
import httpx

from edsl.cli_shared import EXIT_REMOTE, EXIT_USAGE, error, output


DOCS_URL = "https://docs.expectedparrot.com"
MCP_URL = f"{DOCS_URL}/mcp"
_request_ids = itertools.count(1)


_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_LABELED_RESULT = re.compile(
    r"Title:\s*(?P<title>.*?)\s+Link:\s*(?P<url>\S+)\s+"
    r"Page:\s*(?P<page>.*?)\s+Content:\s*(?P<content>.*)",
    re.DOTALL,
)
_DOCS_HOST = "docs.expectedparrot.com"


def _compact_search_results(results: list | dict, limit: int, snippet_length: int = 360) -> list[dict]:
    """Extract a small list of linked pages and excerpts from MCP text blocks."""
    if isinstance(results, dict):
        results = results.get("content", [results])
    compacted = []
    seen_urls = set()
    text_blocks = [
        str(item.get("text", "")) if isinstance(item, dict) and item.get("type") == "text"
        else item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        for item in results
    ]
    for text in text_blocks:
        labeled_chunks = re.split(r"(?=^\s*Search result\s*$)", text, flags=re.MULTILINE)
        found_labeled_result = False
        for chunk in labeled_chunks:
            match = _LABELED_RESULT.search(chunk)
            if match:
                found_labeled_result = True
                url = match.group("url").rstrip(".,)")
                if _DOCS_HOST not in url:
                    continue
                snippet = " ".join(match.group("content").split())
                compacted.append({
                    "title": match.group("title").strip(),
                    "url": url,
                    "page": match.group("page").strip(),
                    "snippet": snippet[:snippet_length],
                })
                if len(compacted) >= limit:
                    return compacted
        if found_labeled_result:
            continue

        links = list(_MARKDOWN_LINK.finditer(text))
        if not links:
            excerpt = " ".join(text.split())
            if excerpt:
                compacted.append({"title": "Search result", "url": None, "snippet": excerpt[:snippet_length]})
            continue
        for index, link in enumerate(links):
            url = link.group(2)
            if _DOCS_HOST not in url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            end = links[index + 1].start() if index + 1 < len(links) else len(text)
            section = text[link.end():end]
            snippet = re.sub(r"[`*_>#]", "", section)
            snippet = " ".join(snippet.split()).strip(" :-–—")
            compacted.append({
                "title": link.group(1).strip(),
                "url": url,
                "snippet": snippet[:snippet_length],
            })
            if len(compacted) >= limit:
                return compacted
    return compacted[:limit]


def _render_human_search_results(results: list[dict]) -> str:
    """Render compact search results for a terminal."""
    if not results:
        return "No documentation results found."
    rendered = []
    for item in results:
        title = item["title"]
        if item.get("url"):
            title = f"{title} — {item['url']}"
        rendered.append(title)
        if item.get("snippet"):
            rendered.append(f"  {item['snippet']}")
    return "\n".join(rendered)


def _rpc(
    client: httpx.Client,
    method: str,
    params: dict | None = None,
    *,
    session_id: str | None = None,
) -> tuple[dict | None, str | None]:
    """Send one MCP Streamable HTTP request and parse its JSON/SSE response."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if not method.startswith("notifications/"):
        message["id"] = next(_request_ids)
    response = client.post(MCP_URL, headers=headers, json=message)
    response.raise_for_status()
    new_session_id = response.headers.get("Mcp-Session-Id") or session_id
    body = response.text.strip()
    if not body:
        return None, new_session_id
    if "text/event-stream" in response.headers.get("content-type", ""):
        data_lines = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
        body = data_lines[-1] if data_lines else ""
    if not body:
        return None, new_session_id
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        content_type = response.headers.get("content-type", "unknown")
        snippet = body[:200].replace("\n", " ")
        raise RuntimeError(
            f"Mintlify MCP returned non-JSON content (HTTP {response.status_code}, "
            f"{content_type}): {snippet or '<empty>'}"
        ) from exc
    if "error" in payload:
        raise RuntimeError(payload["error"].get("message", "Mintlify MCP request failed"))
    return payload.get("result"), new_session_id


def _mcp_search(query: str) -> tuple[list | dict, str]:
    """Discover Mintlify's site-specific search tool and call it anonymously."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        _, session_id = _rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "ep", "version": "1"},
            },
        )
        _rpc(client, "notifications/initialized", session_id=session_id)
        tools_result, session_id = _rpc(client, "tools/list", session_id=session_id)
        available_tools = (tools_result or {}).get("tools", [])
        search_tool = next(
            (
                tool
                for tool in available_tools
                if "search" in (tool.get("name", "") + " " + tool.get("description", "")).lower()
                and "query" in tool.get("inputSchema", {}).get("properties", {})
            ),
            None,
        )
        if search_tool is None:
            raise RuntimeError("Mintlify MCP did not advertise a documentation search tool")
        result, _ = _rpc(
            client,
            "tools/call",
            {"name": search_tool["name"], "arguments": {"query": query}},
            session_id=session_id,
        )
    result = result or {}
    if result.get("isError"):
        raise RuntimeError("Mintlify documentation search returned an error")
    content = result.get("content", [])
    return content, search_tool["name"]


def register(app: click.Group) -> None:
    @app.group("docs", invoke_without_command=True)
    @click.pass_context
    def docs_group(ctx):
        """Search the published EDSL documentation."""
        if ctx.invoked_subcommand is None:
            output({"commands": ["search", "index", "page"], "help": "Use 'ep docs <command> --help' for details."})

    @docs_group.command("search")
    @click.argument("query", nargs=-1, required=True)
    @click.option("--limit", type=click.IntRange(min=1, max=20), default=5, show_default=True,
                  help="Maximum number of page results to print.")
    @click.option("--human", is_flag=True, help="Print search results as readable text instead of JSON.")
    def search_docs(query: tuple[str, ...], limit: int, human: bool) -> None:
        """Search published EDSL docs using Mintlify's public search MCP."""
        try:
            results, tool_name = _mcp_search(" ".join(query))
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            error("REMOTE_ERROR", f"Documentation search failed: {exc}",
                  suggestion=f"Check connectivity to {MCP_URL} and try again.", exit_code=EXIT_REMOTE)
        compacted = _compact_search_results(results, limit)
        if human:
            click.echo(_render_human_search_results(compacted))
        else:
            output({"query": " ".join(query), "results": compacted, "tool": tool_name, "source": MCP_URL})

    @docs_group.command("index")
    @click.option("--human", is_flag=True, help="Print the documentation index as Markdown.")
    def docs_index(human: bool) -> None:
        """List published documentation pages."""
        try:
            response = httpx.get(f"{DOCS_URL}/llms.txt", timeout=30, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            error("REMOTE_ERROR", f"Could not fetch documentation index: {exc}",
                  suggestion=f"Check connectivity to {DOCS_URL} and try again.", exit_code=EXIT_REMOTE)
        if human:
            click.echo(response.text)
        else:
            output({"index": response.text, "source": f"{DOCS_URL}/llms.txt"})

    @docs_group.command("page")
    @click.argument("slug", required=True)
    @click.option("--human", is_flag=True, help="Print page Markdown directly to the terminal.")
    def docs_page(slug: str, human: bool) -> None:
        """Fetch one published docs page as Markdown (for example, scenarios)."""
        slug = slug.strip("/")
        if slug.endswith(".md"):
            slug = slug[:-3]
        if not slug or ".." in slug.split("/"):
            error("USAGE_ERROR", "Page slug must be a non-empty documentation path.", exit_code=EXIT_USAGE)
        url = f"{DOCS_URL}/en/latest/{slug}.md"
        try:
            response = httpx.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = "FILE_NOT_FOUND" if exc.response.status_code == 404 else "REMOTE_ERROR"
            exit_code = 3 if code == "FILE_NOT_FOUND" else EXIT_REMOTE
            error(code, f"Could not fetch documentation page '{slug}': HTTP {exc.response.status_code}",
                  suggestion="Use 'ep docs index' to find a published page slug.", exit_code=exit_code)
        except httpx.HTTPError as exc:
            error("REMOTE_ERROR", f"Could not fetch documentation page '{slug}': {exc}",
                  suggestion=f"Check connectivity to {url} and try again.", exit_code=EXIT_REMOTE)
        if human:
            click.echo(response.text)
        else:
            output({"slug": slug, "markdown": response.text, "source": url})
