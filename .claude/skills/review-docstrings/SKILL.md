---
name: review-docstrings
description: >
  Review a Python module's docstrings for completeness and quality. Checks Google-style
  docstring conventions, suggests missing docstrings, and adds doctests where useful.
  TRIGGER: when the user asks to review, audit, or improve docstrings for a module or file.
---

## Instructions

The user will provide a Python module path (file path or dotted module name). Review every class and function in that module for docstring quality.

### Steps

1. **Read the module** in full.
2. **For each public function/method and class**, check:
   - Has a docstring (skip `__init__` if the class docstring covers it).
   - Uses **Google-style** format: `Args:`, `Returns:`, `Raises:`, `Example:` sections as appropriate.
   - The one-line summary is accurate and concise.
   - `Args:` lists every parameter with type and description. Omit `self`/`cls`.
   - `Returns:` describes what is returned (with type).
   - `Raises:` lists exceptions if the function explicitly raises.
   - `Example:` section contains a runnable doctest (`>>>` lines) when the method is easily testable. Prioritize public API methods — private/underscore methods need doctests only if non-obvious.
3. **For private methods** (`_name`): a one-liner docstring is sufficient. Add a doctest only if the behavior is non-obvious or the method is complex.
4. **Report findings** as a checklist grouped by class/function:
   - Missing docstring
   - Missing or incomplete sections
   - Suggested doctests
5. **Apply fixes** directly to the file. Write the improved docstrings in place. Do not rewrite function bodies — only touch docstrings.
6. **Add new doctests** proactively to public methods that are missing them, whenever the method is easily testable (pure logic, returns a value, no network/external resources needed). Use the class's `.example()` factory when available to keep tests short. Verify the expected output by running the expression first, then write the doctest. Aim for short, illustrative examples — even a simple `>>> len(Survey.example())` or `>>> 'key' in obj.some_method()` is valuable.
7. **Verify doctests** by running: `python -m doctest <file_path> -v` (or `pytest --doctest-modules <file_path>`). Fix any failures.

### Google-style docstring template

```python
def example(arg1: str, arg2: int = 0) -> bool:
    """One-line summary of what this function does.

    Longer description if needed, explaining behavior,
    edge cases, or important notes.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 0.

    Returns:
        True if the operation succeeded, False otherwise.

    Raises:
        ValueError: If arg1 is empty.

    Example:
        >>> example("hello", 2)
        True
    """
```

### Rules

- Do NOT add type annotations in docstring `Args:` if they are already in the function signature — just describe the parameter.
- Keep docstrings factual. Do not add filler like "This method is used to...". Start with a verb: "Return", "Compute", "Parse", etc.
- If a doctest requires imports or setup, include them in the `>>>` block.
- If a doctest output is non-deterministic (e.g., UUIDs, timestamps), use `# doctest: +SKIP` or `# doctest: +ELLIPSIS`.
- Prefer short, illustrative examples that show the user how to call the method and what to expect.
