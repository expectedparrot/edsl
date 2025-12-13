"""
Change tracking system for vibe processing.
"""

from typing import List, Dict, Any
from ..config import VibeChange


class ChangeTracker:
    """Tracks and manages changes made during vibe processing."""

    def __init__(self):
        self._changes: List[VibeChange] = []

    def record_change(self, change: VibeChange) -> None:
        """Record a change made during processing."""
        self._changes.append(change)

    def get_changes(self) -> List[VibeChange]:
        """Get all recorded changes."""
        return self._changes.copy()

    def get_changes_for_question(self, question_name: str) -> List[VibeChange]:
        """Get all changes for a specific question."""
        return [
            change for change in self._changes if change.question_name == question_name
        ]

    def has_changes_for_question(self, question_name: str) -> bool:
        """Check if any changes were made for a specific question."""
        return any(change.question_name == question_name for change in self._changes)

    def get_change_log(self) -> List[Dict[str, Any]]:
        """Get a list of all changes as dictionaries for serialization."""
        return [change.to_dict() for change in self._changes]

    def get_change_summary(self) -> Dict[str, Any]:
        """Get a summary of changes made during processing."""
        if not self._changes:
            return {
                "total_changes": 0,
                "changes_by_type": {},
                "questions_modified": 0,
                "average_confidence": 0.0,
            }

        changes_by_type = {}
        questions_modified = set()
        total_confidence = 0.0

        for change in self._changes:
            # Count by type
            change_type = change.change_type
            changes_by_type[change_type] = changes_by_type.get(change_type, 0) + 1

            # Track questions modified
            questions_modified.add(change.question_name)

            # Sum confidence scores
            total_confidence += change.confidence

        return {
            "total_changes": len(self._changes),
            "changes_by_type": changes_by_type,
            "questions_modified": len(questions_modified),
            "average_confidence": (
                total_confidence / len(self._changes) if self._changes else 0.0
            ),
        }

    def clear(self) -> None:
        """Clear all recorded changes."""
        self._changes.clear()

    def __len__(self) -> int:
        """Return the number of changes recorded."""
        return len(self._changes)
