"""Client-side validation for a human survey's agent-access config patch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Dict, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
    model_validator,
)

from .exceptions import AgentAccessValidationError

if TYPE_CHECKING:
    from ..surveys import Survey


class QuestionAgentSettings(BaseModel):
    """One question's agent settings, as the server stores them."""

    model_config = ConfigDict(extra="forbid")

    instructions: Optional[
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
        ]
    ] = None


class AgentAccessPatch(BaseModel):
    """
    A partial agent-access config, as ``patch_human_survey_agent_access`` sends it.

    Mirrors the server's rules for each field. Fields left out are unchanged on the
    server; ``instructions`` may be null (to clear it), and a question may be null in
    ``question_settings`` (to remove its settings). ``enabled``,
    ``participation_mode`` and ``question_settings`` itself can't be null.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: Optional[bool] = None
    participation_mode: Optional[
        Literal["human_assisted", "authorized_context", "autonomous"]
    ] = None
    instructions: Optional[
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
        ]
    ] = None
    question_settings: Optional[Dict[str, Optional[QuestionAgentSettings]]] = None

    @model_validator(mode="after")
    def _no_null_where_a_value_is_required(self) -> "AgentAccessPatch":
        for name in ("enabled", "participation_mode", "question_settings"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self


def validate_agent_access_patch(
    partial_config: Dict[str, Any],
    survey: Optional["Survey"] = None,
) -> None:
    """
    Validate an agent-access config patch before it's sent.

    Checks the patch's keys and values against the server's rules. With ``survey``,
    also checks that every question given settings in ``question_settings`` is a
    question in it; removing a question's settings (null) is allowed for any name, so
    a misspelled one can be cleared. Raises ``AgentAccessValidationError``.
    """
    if not isinstance(partial_config, dict):
        raise AgentAccessValidationError("An agent-access patch must be a JSON object.")
    try:
        patch = AgentAccessPatch.model_validate(partial_config)
    except ValidationError as e:
        raise AgentAccessValidationError(str(e)) from e

    if survey is None or not patch.question_settings:
        return
    question_names = set(survey.question_names)
    unknown = sorted(
        name
        for name, settings in patch.question_settings.items()
        if settings is not None and name not in question_names
    )
    if unknown:
        raise AgentAccessValidationError(
            f"question_settings names questions that aren't in the survey: {unknown}."
        )
