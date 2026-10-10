"""Lazy imports with an actionable installation hint."""

import importlib


def require(module):
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            f"Hugging Face interchange requires {module}. Install with: pip install 'edsl[hf]'"
        ) from exc
