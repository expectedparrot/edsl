"""ModelList JSONL serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator, Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..language_models import LanguageModel
    from .model_list import ModelList


class ModelListSerializer:
    """JSONL serialization for ModelList objects.

    JSONL format:
      - Line 1: metadata header (``__header__: true``, class name, count)
      - Lines 2+: one Model per line (``to_dict(add_edsl_version=False)``)
    """

    def __init__(self, model_list: "ModelList") -> None:
        self._model_list = model_list

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def _build_metadata(self, add_edsl_version: bool = True) -> dict:
        meta: dict = {
            "__header__": True,
            "edsl_class_name": "ModelList",
            "n_models": len(self._model_list),
        }
        if add_edsl_version:
            from edsl import __version__

            meta["edsl_version"] = __version__
        return meta

    def to_jsonl_rows(self, add_edsl_version: bool = True) -> Generator[str, None, None]:
        """Yield one JSON string per line — header then one Model per line."""
        yield json.dumps(self._build_metadata(add_edsl_version))
        for model in self._model_list:
            yield json.dumps(model.to_dict(add_edsl_version=False))

    def to_jsonl(self, filename: Union[str, Path, None] = None) -> Optional[str]:
        """Export as JSONL string or write to *filename*.

        Examples:
            >>> from edsl.language_models.model_list import ModelList
            >>> ml = ModelList.example()
            >>> text = ml.to_jsonl()
            >>> lines = text.strip().splitlines()
            >>> len(lines)
            4
            >>> import json; json.loads(lines[0])['n_models']
            3
        """
        if filename is not None:
            with open(filename, "w") as f:
                for row in self.to_jsonl_rows():
                    f.write(row + "\n")
            return None
        return "\n".join(self.to_jsonl_rows()) + "\n"

    # ------------------------------------------------------------------
    # import (static — no instance needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
        """Normalise *source* into an iterable of lines."""
        if isinstance(source, Path):
            with open(source, "r") as fh:
                yield from fh
            return

        if isinstance(source, str):
            if "\n" not in source.rstrip("\n"):
                candidate = Path(source)
                try:
                    if candidate.is_file():
                        with open(candidate, "r") as fh:
                            yield from fh
                        return
                except OSError:
                    pass
            yield from source.splitlines()
        else:
            yield from source

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]]) -> "ModelList":
        """Create a ModelList from a JSONL source.

        Examples:
            >>> from edsl.language_models.model_list import ModelList
            >>> ml = ModelList.example()
            >>> ml2 = ModelList.from_jsonl(ml.to_jsonl())
            >>> ml == ml2
            True
        """
        from ..language_models import LanguageModel
        from .model_list import ModelList

        lines = ModelListSerializer._open_lines(source)
        line_iter = iter(lines)
        next(line_iter)  # skip header
        models = [
            LanguageModel.from_dict(json.loads(line))
            for line in line_iter
            if line.strip()
        ]
        return ModelList(models)

    @staticmethod
    def iter_models_from_jsonl(
        source: Union[str, Path, Iterable[str]],
    ) -> Generator["LanguageModel", None, None]:
        """Lazily yield Model objects from a JSONL source."""
        from ..language_models import LanguageModel

        lines = ModelListSerializer._open_lines(source)
        line_iter = iter(lines)
        next(line_iter)  # skip header
        for line in line_iter:
            if line.strip():
                yield LanguageModel.from_dict(json.loads(line))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
