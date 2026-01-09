"""
Event validation with dry-run support.

Provides:
- Validate events before applying
- Dry-run mode to preview changes
- Schema validation
- Business rule validation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import copy


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    ERROR = "error"      # Event will fail
    WARNING = "warning"  # Event will succeed but may have issues
    INFO = "info"        # Informational note


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: ValidationSeverity
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of validating an event."""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    preview: Optional[Dict[str, Any]] = None  # State after applying (for dry-run)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


@dataclass
class DryRunResult:
    """Result of a dry-run execution."""
    success: bool
    events_valid: int
    events_invalid: int
    final_state: Optional[Dict[str, Any]]
    validation_results: List[Tuple[str, Dict[str, Any], ValidationResult]]
    summary: Dict[str, Any]


class EventValidator:
    """
    Validates events before they are applied.

    Provides schema validation, business rules, and dry-run capability.
    """

    def __init__(self, strict: bool = False):
        """
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict

    def validate_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate a single event against current state.

        Args:
            event_name: Name of the event
            payload: Event payload
            current_state: Current state of the store

        Returns:
            ValidationResult with any issues found
        """
        issues = []
        entries = current_state.get("entries", [])
        meta = current_state.get("meta", {})

        # Schema validation based on event type
        if event_name == "append_row":
            row = payload.get("row")
            if row is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_row",
                    message="append_row requires 'row' in payload",
                    field="row"
                ))
            elif not isinstance(row, dict):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="invalid_row_type",
                    message="row must be a dictionary",
                    field="row"
                ))

        elif event_name == "update_row":
            index = payload.get("index")
            row = payload.get("row")
            if index is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_index",
                    message="update_row requires 'index' in payload",
                    field="index"
                ))
            elif not isinstance(index, int):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="invalid_index_type",
                    message="index must be an integer",
                    field="index"
                ))
            elif index < 0 or index >= len(entries):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="index_out_of_bounds",
                    message=f"index {index} is out of bounds (0-{len(entries)-1})",
                    field="index",
                    details={"index": index, "entries_count": len(entries)}
                ))
            if row is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_row",
                    message="update_row requires 'row' in payload",
                    field="row"
                ))

        elif event_name == "remove_rows":
            indices = payload.get("indices", [])
            if not indices:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="empty_indices",
                    message="remove_rows with empty indices has no effect"
                ))
            for idx in indices:
                if not isinstance(idx, int):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="invalid_index_type",
                        message=f"index {idx} is not an integer",
                        field="indices"
                    ))
                elif idx < 0 or idx >= len(entries):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="index_out_of_bounds",
                        message=f"index {idx} is out of bounds",
                        field="indices",
                        details={"index": idx, "entries_count": len(entries)}
                    ))

        elif event_name == "insert_row":
            index = payload.get("index")
            if index is not None and (index < 0 or index > len(entries)):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="index_out_of_bounds",
                    message=f"insert index {index} is out of bounds",
                    field="index"
                ))

        elif event_name == "rename_fields":
            rename_map = payload.get("rename_map", [])
            if not rename_map:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="empty_rename_map",
                    message="rename_fields with empty rename_map has no effect"
                ))
            else:
                # Check for existing fields
                existing_fields = set()
                for entry in entries:
                    existing_fields.update(entry.keys())
                for old_name, new_name in rename_map:
                    if old_name not in existing_fields:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            code="field_not_found",
                            message=f"field '{old_name}' not found in any entry",
                            field="rename_map",
                            details={"field": old_name}
                        ))
                    if new_name in existing_fields:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            code="field_exists",
                            message=f"field '{new_name}' already exists, will be overwritten",
                            field="rename_map",
                            details={"field": new_name}
                        ))

        elif event_name == "drop_fields":
            fields = payload.get("fields", [])
            if not fields:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="empty_fields",
                    message="drop_fields with empty fields has no effect"
                ))
            else:
                existing_fields = set()
                for entry in entries:
                    existing_fields.update(entry.keys())
                for field in fields:
                    if field not in existing_fields:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            code="field_not_found",
                            message=f"field '{field}' not found in any entry",
                            field="fields",
                            details={"field": field}
                        ))

        elif event_name == "keep_fields":
            fields = payload.get("fields", [])
            if not fields:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="empty_fields",
                    message="keep_fields with empty fields will clear all fields"
                ))

        elif event_name == "set_meta":
            key = payload.get("key")
            if key is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_key",
                    message="set_meta requires 'key' in payload",
                    field="key"
                ))
            if "value" not in payload:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_value",
                    message="set_meta requires 'value' in payload",
                    field="value"
                ))

        elif event_name == "remove_meta_key":
            key = payload.get("key")
            if key is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_key",
                    message="remove_meta_key requires 'key' in payload",
                    field="key"
                ))
            elif key not in meta:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="key_not_found",
                    message=f"meta key '{key}' does not exist",
                    field="key"
                ))

        # Determine overall validity
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        valid = not has_errors and (not has_warnings if self.strict else True)

        return ValidationResult(valid=valid, issues=issues)

    def dry_run(
        self,
        events: List[Tuple[str, Dict[str, Any]]],
        initial_state: Dict[str, Any],
        apply_event_fn: callable
    ) -> DryRunResult:
        """
        Perform a dry-run of events without committing.

        Args:
            events: List of (event_name, payload) tuples
            initial_state: Starting state
            apply_event_fn: Function to apply event (event, state) -> new_state

        Returns:
            DryRunResult with validation and preview
        """
        state = copy.deepcopy(initial_state)
        results = []
        events_valid = 0
        events_invalid = 0
        all_issues = []

        for event_name, payload in events:
            # Validate
            validation = self.validate_event(event_name, payload, state)
            results.append((event_name, payload, validation))

            if validation.valid:
                events_valid += 1
                # Try to apply
                try:
                    state = apply_event_fn(event_name, payload, state)
                except Exception as e:
                    events_invalid += 1
                    validation.issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="apply_error",
                        message=f"Error applying event: {str(e)}"
                    ))
                    validation.valid = False
            else:
                events_invalid += 1

            all_issues.extend(validation.issues)

        success = events_invalid == 0
        error_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.WARNING)

        return DryRunResult(
            success=success,
            events_valid=events_valid,
            events_invalid=events_invalid,
            final_state=state if success else None,
            validation_results=results,
            summary={
                "total_events": len(events),
                "valid": events_valid,
                "invalid": events_invalid,
                "errors": error_count,
                "warnings": warning_count,
                "entries_before": len(initial_state.get("entries", [])),
                "entries_after": len(state.get("entries", [])) if success else None,
            }
        )


# Convenience functions

def validate_event(
    event_name: str,
    payload: Dict[str, Any],
    current_state: Dict[str, Any],
    strict: bool = False
) -> ValidationResult:
    """Validate a single event."""
    return EventValidator(strict=strict).validate_event(event_name, payload, current_state)


def dry_run(
    events: List[Tuple[str, Dict[str, Any]]],
    initial_state: Dict[str, Any],
    apply_event_fn: callable,
    strict: bool = False
) -> DryRunResult:
    """Perform a dry-run of events."""
    return EventValidator(strict=strict).dry_run(events, initial_state, apply_event_fn)
