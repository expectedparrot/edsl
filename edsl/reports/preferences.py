from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class ReportPreferences:
    """User-selected preferences determining what appears in a Reports report."""

    # Question filtering
    include_questions: List[str] = field(default_factory=list)
    exclude_questions: List[str] = field(default_factory=list)

    # Custom analysis list (each element is a list of question names)
    analyses: Optional[List[List[str]]] = None

    # Mapping from analysis (tuple of question names) to list of allowed output names
    analysis_output_filters: Dict[Tuple[str, ...], List[str]] = field(
        default_factory=dict
    )

    # Control whether writeups are generated for each analysis
    analysis_writeup_filters: Dict[Tuple[str, ...], bool] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "include_questions": self.include_questions,
            "exclude_questions": self.exclude_questions,
            "analyses": self.analyses,
            "analysis_output_filters": {
                "|".join(k): v for k, v in self.analysis_output_filters.items()
            },
            "analysis_writeup_filters": {
                "|".join(k): v for k, v in self.analysis_writeup_filters.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ReportPreferences":
        filters = data.get("analysis_output_filters", {})
        converted = {tuple(k.split("|")): v for k, v in filters.items()}
        writeup_filters = data.get("analysis_writeup_filters", {})
        writeup_converted = {tuple(k.split("|")): v for k, v in writeup_filters.items()}
        return cls(
            include_questions=data.get("include_questions", []),
            exclude_questions=data.get("exclude_questions", []),
            analyses=data.get("analyses"),
            analysis_output_filters=converted,
            analysis_writeup_filters=writeup_converted,
        )
