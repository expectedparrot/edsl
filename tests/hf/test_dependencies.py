"""Base EDSL imports work when HF dependencies are absent."""

import subprocess
import sys

import pytest

from edsl.hf.dependencies import require


@pytest.mark.parametrize("module", ["datasets", "huggingface_hub", "pyarrow"])
def test_install_hint(module, monkeypatch):
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ImportError, match=r"pip install 'edsl\[hf\]'"):
        require(module)


def test_base_import_does_not_import_hf():
    code = """
import sys
import importlib.abc
class BlockHF(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('datasets', 'huggingface_hub', 'pyarrow'):
            raise ImportError('HF extras intentionally unavailable')
sys.meta_path.insert(0, BlockHF())
from edsl import AgentList, ScenarioList
assert callable(AgentList.save_hf) and callable(ScenarioList.from_hf)
"""
    subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
