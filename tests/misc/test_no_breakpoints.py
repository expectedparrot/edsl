import os
import re
from edsl import BASE_DIR


def test_no_breakpoint():
    breakpoint_pattern = re.compile(r"\bbreakpoint\(\)")
    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = list(f)
                    for lineno, line in enumerate(lines, start=1):
                        stripped_line = line.strip()
                        # Skip lines that are comments
                        if stripped_line.startswith("#"):
                            continue
                        # Skip breakpoint() calls inside a def breakpoint method
                        if lineno > 1:
                            prev_line = lines[lineno - 2].strip()
                            if prev_line.startswith("def breakpoint("):
                                continue
                        # Check if the pattern is found in the line
                        if breakpoint_pattern.search(line):
                            assert (
                                False
                            ), f"Found 'breakpoint()' in {file_path} on line {lineno}"
