from __future__ import annotations

"""Utility for loading a saved EDSL object without knowing its exact class.

This module provides a single `load` function that mirrors the behaviour of
`Base.load` but *automatically* figures out which concrete EDSL subclass to use.

How it works
============
A serialised EDSL object produced by :py:meth:`edsl.base.base_class.Base.save` (or
`to_dict`) always includes the key ``"edsl_class_name"``.  That value is the name
of the concrete subclass (e.g. ``"Survey"`` or ``"Results"``).  At import time
all subclasses register themselves with :class:`edsl.base.base_class.RegisterSubclassesMeta`,
so we can look them up dynamically.

The function therefore:
1. Reads the JSON or gzipped JSON file.
2. Extracts the ``edsl_class_name`` value.
3. Retrieves the appropriate class from the registry.
4. Dispatches to ``Class.from_dict`` to construct the instance.

The interface avoids any heavy imports until dispatch time so start-up cost is
minimal.

Example
-------
```python
from edsl.utilities.edsl_load import load
obj = load("my_results.json.gz")
print(type(obj))  # <class 'edsl.results.results.Results'>
```
"""

from pathlib import Path
from typing import Any, Dict
import json
import gzip

from edsl.base.base_class import Base, RegisterSubclassesMeta

__all__ = ["load"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_file(p: Path) -> Dict[str, Any]:
    """Return a parsed dictionary from *p*.

    Handles the four common cases:
    • ``foo.json``
    • ``foo.json.gz``
    • ``foo`` (tries ``foo.json.gz`` then ``foo.json``)
    """
    if p.suffix == ".gz":
        # Expect something like *.json.gz
        return Base.open_compressed_file(str(p))

    if p.suffix == ".json":
        return Base.open_regular_file(str(p))

    # No recognised suffix – try both options, compressed first
    compressed = p.with_suffix(p.suffix + ".json.gz") if p.suffix else Path(str(p) + ".json.gz")
    if compressed.exists():
        return Base.open_compressed_file(str(compressed))

    plain = p.with_suffix(p.suffix + ".json") if p.suffix else Path(str(p) + ".json")
    if plain.exists():
        return Base.open_regular_file(str(plain))

    # Give up – let the caller know
    raise FileNotFoundError(f"Could not locate a .json or .json.gz file for '{p}'.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load(filename: str):
    """Load any EDSL object from *filename*.

    Parameters
    ----------
    filename:
        Path to a ``.json`` or ``.json.gz`` file created by
        :py:meth:`edsl.base.base_class.Base.save`.  If the extension is omitted the
        function will try ``<filename>.json.gz`` first and then ``<filename>.json``.

    Returns
    -------
    Any
        An instance of the appropriate EDSL subclass.

    Raises
    ------
    FileNotFoundError
        If no suitable file is found.
    KeyError
        If the file does not include ``edsl_class_name``.
    ValueError
        If the class cannot be found in the registry.
    """
    path = Path(filename)
    data = _read_file(path)

    try:
        class_name = data["edsl_class_name"]
    except KeyError as e:
        raise KeyError("Missing 'edsl_class_name' key – is this an EDSL serialised file?") from e

    registry = RegisterSubclassesMeta.get_registry()
    if class_name not in registry:
        raise ValueError(f"Unknown EDSL class '{class_name}'.  Is the relevant module imported?")

    cls = registry[class_name]
    return cls.from_dict(data) 