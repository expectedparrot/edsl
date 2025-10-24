from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import NormalizedSurvey
from .profiles import CsvFormat, CsvProfile, detect_csv_profile
from .normalizers.base import SurveyNormalizer
from .normalizers.flat import FlatCsvNormalizer
from .normalizers.qualtrics import QualtricsThreeRowNormalizer


def normalize_survey_file(
    path: Path,
    profile: Optional[CsvProfile] = None,
) -> NormalizedSurvey:
    """
    Detect the survey layout, normalize it, and return a NormalizedSurvey.
    """
    resolved = Path(path).expanduser().resolve()

    detected_profile = profile or detect_csv_profile(resolved)

    normalizer = _get_normalizer(detected_profile)
    return normalizer.normalize(resolved, detected_profile)


def _get_normalizer(profile: CsvProfile) -> SurveyNormalizer:
    if profile.format == CsvFormat.QUALTRICS_THREE_ROW:
        return QualtricsThreeRowNormalizer()
    return FlatCsvNormalizer()
