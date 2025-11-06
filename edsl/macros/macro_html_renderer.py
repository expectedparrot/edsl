from __future__ import annotations
from typing import Any
from html import escape
import re


class MacroHTMLRenderer:
    def __init__(self, macro: Any) -> None:
        self.macro = macro

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
        # Extract name and description (now simple strings)
        macro_name = self.macro.display_name
        macro_desc = self.macro.long_description

        title_html = f'<h2 style="margin-bottom:0.25rem;">{escape(macro_name)}</h2>'
        desc_html = self._convert_markdown_to_html(macro_desc)

        rows_html: list[str] = []
        for param in self.macro.parameters_scenario_list:
            rows_html.append(
                """
                <tr>
                  <td>{name}</td>
                  <td><code>{qtype}</code></td>
                  <td>{prompt}</td>
                </tr>
                """.format(
                    name=escape(str(param["question_name"])),
                    qtype=escape(str(param["question_type"])),
                    prompt=escape(str(param["question_text"])),
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
                return '["item1", "item2"]'
            if "date" in qt:
                return '"2025-01-01"'
            if "file" in qt or "path" in qt:
                return '"/path/to/file.txt"'
            return '"..."'

        example_kv_lines: list[str] = []
        for param in self.macro.parameters_scenario_list:
            value_literal = _example_value_for_type(str(param["question_type"]))
            example_kv_lines.append(
                f"    {repr(str(param['question_name']))}: {value_literal}"
            )
        params_body = (
            ",\n".join(example_kv_lines) if example_kv_lines else "    # no parameters"
        )
        usage_code = f"macro.output(params={{\n{params_body}\n}})"
        usage_block = f'<pre style="background:#f6f8fa; padding:10px; border-radius:6px; overflow:auto;"><code class="language-python">{escape(usage_code)}</code></pre>'

        # Build output formatters table
        formatter_rows_html: list[str] = []
        try:
            formatters_mapping = self.macro.output_formatters.mapping
            default_formatter_name = self.macro.output_formatters.default

            for formatter_name, formatter in formatters_mapping.items():
                # Determine if this is the default formatter
                is_default = formatter_name == default_formatter_name
                name_display = (
                    f"<strong>{escape(str(formatter_name))}</strong>"
                    if is_default
                    else escape(str(formatter_name))
                )
                if is_default:
                    name_display += ' <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-size:0.75rem; font-weight:600;">DEFAULT</span>'

                # Get output type
                output_type = getattr(formatter, "output_type", "auto")
                output_type_display = escape(str(output_type))

                # Get command chain summary
                stored_commands = getattr(formatter, "_stored_commands", [])
                if stored_commands:
                    command_names = [
                        cmd[0] for cmd in stored_commands[:5]
                    ]  # First 5 commands
                    commands_display = " → ".join(command_names)
                    if len(stored_commands) > 5:
                        commands_display += " → ..."
                    commands_display = escape(commands_display)
                else:
                    commands_display = "<em>pass-through</em>"

                formatter_rows_html.append(
                    """
                    <tr>
                      <td style="padding:8px;">{name}</td>
                      <td style="padding:8px;"><code>{output_type}</code></td>
                      <td style="padding:8px; font-family:ui-monospace, monospace; font-size:0.875rem;">{commands}</td>
                    </tr>
                    """.format(
                        name=name_display,
                        output_type=output_type_display,
                        commands=commands_display,
                    )
                )
        except Exception:
            # If there's any error getting formatters, just skip the section
            formatter_rows_html = []

        formatters_table_html = ""
        if formatter_rows_html:
            formatters_table_html = (
                """
                <table style="border-collapse:collapse; width:100%; margin-top:0.75rem;">
                  <thead>
                    <tr>
                      <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Formatter Name</th>
                      <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Output Type</th>
                      <th style="text-align:left; border-bottom:1px solid #ccc; padding:6px 8px;">Transformation Pipeline</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows}
                  </tbody>
                </table>
                """
            ).format(rows="\n".join(formatter_rows_html))

        container = (
            """
            <div class="edsl-macro" style="font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Noto Sans, sans-serif; line-height:1.5;">
              {title}
              <div class="edsl-macro-description" style="color:#333; margin-top:0.5rem;">{desc}</div>
              <h3 style="margin-top:1.25rem;">Parameters</h3>
              {table}
              {formatters_section}
              <h3 style="margin-top:1.25rem;">Usage</h3>
              {usage}
            </div>
            """
        ).format(
            title=title_html,
            desc=desc_html,
            table=table_html,
            formatters_section=(
                f'<h3 style="margin-top:1.25rem;">Output Formatters</h3>\n{formatters_table_html}'
                if formatters_table_html
                else ""
            ),
            usage=usage_block,
        )

        return container
