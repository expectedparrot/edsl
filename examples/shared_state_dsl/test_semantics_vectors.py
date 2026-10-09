"""Keep the normative semantics vectors in the ordinary test suite."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SPEC_ROOT = Path(__file__).resolve().parents[2] / "docs" / "shared_state_semantics"
module_spec = spec_from_file_location("shared_state_semantics_vectors", SPEC_ROOT / "run_vectors.py")
assert module_spec is not None and module_spec.loader is not None
vectors = module_from_spec(module_spec)
module_spec.loader.exec_module(vectors)


@pytest.mark.parametrize("path", sorted((SPEC_ROOT / "test-vectors").glob("*.json")), ids=lambda path: path.stem)
def test_normative_semantics_vector(path):
    vectors.run_vector(path)
