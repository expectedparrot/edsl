from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from ..models import NormalizedSurvey
from ..profiles import CsvProfile


class SurveyNormalizer(ABC):
    """Base class for survey normalizers."""

    @abstractmethod
    def normalize(self, path: Path, profile: CsvProfile) -> NormalizedSurvey:
        raise NotImplementedError

    def load_dataframe(self, path: Path, profile: CsvProfile) -> pd.DataFrame:
        """Shared helper for reading simple CSV files."""
        return pd.read_csv(
            path,
            delimiter=profile.delimiter,
            dtype=str,
            keep_default_na=False,
        )
