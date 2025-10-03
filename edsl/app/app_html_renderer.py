from __future__ import annotations
from typing import Any
from html import escape
import re


class AppHTMLRenderer:
    def __init__(self, app: Any) -> None:
        self.app = app

    def _convert_markdown_to_html(self, md_text: str) -> str:
        if md_text is None:
            return ""
        safe_text = escape(str(md_text))
        try:
            import markdown as md  # type: ignore
            return md.markdown(
                safe_text,
                extensions=["extra", "sane_lists", "tables"],
            )
        except Exception:
            pass

        text = safe_text
        text = re.sub(r"(?m)^######\s+(.+)$", r"<h6>\\1</h6>", text)
        text = re.sub(r"(?m)^#####\s+(.+)$", r"<h5>\\1</h5>", text)
        text = re.sub(r"(?m)^####\s+(.+)$", r"<h4>\\1</h4>", text)
        text = re.sub(r"(?m)^###\s+(.+)$", r"<h3>\\1</h3>", text)
        text = re.sub(r"(?m)^##\s+(.+)$", r"<h2>\\1</h2>", text)
        text = re.sub(r"(?m)^#\s+(.+)$", r"<h1>\\1</h1>", text)
        text = re.sub(r"`([^`]+)`", r"<code>\\1</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\\1</strong>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\\1</em>", text)
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        wrapped = [p if p.startswith("<h") else f"<p>{p}</p>" for p in parts]
        return "\n".join(wrapped)

    def render(self) -> str:
        title_html = f"<h2 style=\"margin-bottom:0.25rem;\">{escape(self.app.application_name)}</h2>"
        desc_html = self._convert_markdown_to_html(self.app.description)

        rows_html: list[str] = []
        for name, qtype, prompt in self.app.parameters:
            rows_html.append(
                """
                <tr>
                  <td>{name}</td>
                  <td><code>{qtype}</code></td>
                  <td>{prompt}</td>
                </tr>
                """.format(
                    name=escape(str(name)),
                    qtype=escape(str(qtype)),
                    prompt=escape(str(prompt)),
                )
            )

        table_html = (
            """
            <table style="border-collapse:collapse; width:100%; margin-top:0.75rem;">
              <thead>
                <tr>
                  <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Parameter</th>
                  <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Type</th>
                  <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Prompt</th>
                </tr>
              </thead>
              <tbody>
                {rows}
              </tbody>
            </table>
            """
        ).format(rows="\n".join(rows_html))

        def _example_value_for_type(question_type: str) -> str:
            qt = (question_type or "").lower()
            if "bool" in qt:
                return "True"
            if "int" in qt:
                return "0"
            if "float" in qt or "number" in qt or "numeric" in qt:
                return "0.0"
            if "list" in qt or "array" in qt:
                return "[\"item1\", \"item2\"]"
            if "date" in qt:
                return "\"2025-01-01\""
            if "file" in qt or "path" in qt:
                return "\"/path/to/file.txt\""
            return "\"...\""

        example_kv_lines: list[str] = []
        for name, qtype, _prompt in self.app.parameters:
            value_literal = _example_value_for_type(str(qtype))
            example_kv_lines.append(f"    {repr(str(name))}: {value_literal}")
        params_body = ",\n".join(example_kv_lines) if example_kv_lines else "    # no parameters"
        usage_code = f"app.output(params={{\n{params_body}\n}})"
        usage_block = f"<pre style=\"background:#f6f8fa; padding:10px; border-radius:6px; overflow:auto;\"><code class=\"language-python\">{escape(usage_code)}</code></pre>"

        container = (
            """
            <div class="edsl-app" style="font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Noto Sans, sans-serif; line-height:1.5;">
              {title}
              <div class="edsl-app-description" style="color:#333; margin-top:0.5rem;">{desc}</div>
              <h3 style="margin-top:1.25rem;">Parameters</h3>
              {table}
              <h3 style="margin-top:1.25rem;">Usage</h3>
              {usage}
            </div>
            """
        ).format(title=title_html, desc=desc_html, table=table_html, usage=usage_block)

        return container


