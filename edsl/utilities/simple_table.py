"""Plain-text table rendering without external dependencies."""


def simple_table(headers, data, fmt="grid"):
    """Render a table as plain text.

    Supports formats: grid, simple, pipe/markdown.
    """
    if not data:
        return " | ".join(str(h) for h in headers)

    cols = len(headers)
    widths = [len(str(h)) for h in headers]
    for row in data:
        for i in range(cols):
            widths[i] = max(widths[i], len("" if row[i] is None else str(row[i])))

    def _pad(val, w):
        s = "" if val is None else str(val)
        return s.ljust(w)

    if fmt in ("pipe", "markdown"):
        header_line = "| " + " | ".join(_pad(h, widths[i]) for i, h in enumerate(headers)) + " |"
        sep_line = "| " + " | ".join("-" * widths[i] for i in range(cols)) + " |"
        row_lines = [
            "| " + " | ".join(_pad(row[i], widths[i]) for i in range(cols)) + " |"
            for row in data
        ]
        return "\n".join([header_line, sep_line] + row_lines)

    elif fmt == "simple":
        header_line = "  ".join(_pad(h, widths[i]) for i, h in enumerate(headers))
        sep_line = "  ".join("-" * widths[i] for i in range(cols))
        row_lines = [
            "  ".join(_pad(row[i], widths[i]) for i in range(cols))
            for row in data
        ]
        return "\n".join([header_line, sep_line] + row_lines)

    else:  # grid
        hsep = "+-" + "-+-".join("-" * widths[i] for i in range(cols)) + "-+"
        header_line = "| " + " | ".join(_pad(h, widths[i]) for i, h in enumerate(headers)) + " |"
        row_lines = [
            "| " + " | ".join(_pad(row[i], widths[i]) for i in range(cols)) + " |"
            for row in data
        ]
        parts = [hsep, header_line, hsep] + [line for r in row_lines for line in (r, hsep)]
        return "\n".join(parts)
