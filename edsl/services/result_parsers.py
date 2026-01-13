"""
Generic result parsers for service results.

These parsers handle converting raw result dicts from remote services
into EDSL objects without requiring the service class to be installed.

This enables clients to work with remote service runners without having
edsl-services installed locally.
"""

from typing import Any, Dict, Optional


class ResultParser:
    """
    Parses service results based on declared patterns.

    This enables clients to work without edsl-services installed,
    by using generic parsing logic based on the result_pattern field.

    Example:
        >>> result = {"rows": [{"name": "Alice"}, {"name": "Bob"}]}
        >>> parsed = ResultParser.parse(result, "scenario_list")
        >>> # Returns ScenarioList with 2 items
    """

    # Registry of pattern parsers
    _parsers: Dict[str, callable] = {}

    @classmethod
    def register_parser(cls, pattern: str):
        """Decorator to register a parser for a pattern."""

        def decorator(func):
            cls._parsers[pattern] = func
            return func

        return decorator

    @classmethod
    def parse(
        cls,
        result: Dict[str, Any],
        pattern: str,
        result_field: Optional[str] = None,
    ) -> Any:
        """
        Parse a result dict using the specified pattern.

        Args:
            result: Raw result dict from service
            pattern: Pattern name (e.g., "scenario_list")
            result_field: Optional field to extract from result

        Returns:
            Parsed EDSL object
        """
        parser = cls._parsers.get(pattern)
        if parser is None:
            # Unknown pattern - return raw dict
            return result
        return parser(result, result_field)

    @classmethod
    def available_patterns(cls) -> list:
        """List available pattern names."""
        return list(cls._parsers.keys())


# =========================================================================
# Pattern implementations
# =========================================================================


@ResultParser.register_parser("scenario_list")
def parse_scenario_list(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as ScenarioList from list of dicts.

    Expected format: {"rows": [{"key": "value"}, ...]}
    """
    from edsl.scenarios import ScenarioList

    data_field = field or "rows"
    rows = result.get(data_field, [])
    return ScenarioList.from_list_of_dicts(rows)


@ResultParser.register_parser("scenario_list_data")
def parse_scenario_list_data(
    result: Dict[str, Any], field: Optional[str] = None
) -> Any:
    """
    Parse result as ScenarioList from 'data' field.

    Expected format: {"data": [{"key": "value"}, ...]}
    """
    from edsl.scenarios import ScenarioList

    rows = result.get("data", [])
    return ScenarioList.from_list_of_dicts(rows)


@ResultParser.register_parser("filestore_base64")
def parse_filestore_base64(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as FileStore from base64 data.

    Expected format: {
        "base64_data": "...",
        "suffix": "xlsx",
        "mime_type": "application/...",
    }
    """
    from edsl.scenarios import FileStore

    return FileStore(
        path=result.get("filename"),
        base64_string=result.get("base64_data") or result.get("base64_string"),
        suffix=result.get("suffix", "bin"),
        mime_type=result.get("mime_type", "application/octet-stream"),
        binary=True,
    )


@ResultParser.register_parser("filestore_image")
def parse_filestore_image(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as FileStore from image_base64 field.

    Expected format: {"image_base64": "...", "suffix": "png"}
    """
    from edsl.scenarios import FileStore

    return FileStore(
        path=None,
        base64_string=result.get("image_base64"),
        suffix=result.get("suffix", "png"),
        mime_type=result.get("mime_type", "image/png"),
        binary=True,
    )


@ResultParser.register_parser("dict_passthrough")
def parse_dict_passthrough(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """Return result dict unchanged."""
    return result


@ResultParser.register_parser("string_field")
def parse_string_field(result: Dict[str, Any], field: Optional[str] = None) -> str:
    """
    Extract a string field from result.

    If field is specified, extracts that field.
    Otherwise tries common field names: answer, code, text, content.
    """
    if field:
        return result.get(field, "")
    # Try common fields
    for key in ["answer", "code", "text", "content"]:
        if key in result:
            return result[key]
    return str(result)


@ResultParser.register_parser("results_from_dict")
def parse_results_from_dict(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as Results object.

    Expected format: {"result": {"results_dict": {...}}}
    or {"results_dict": {...}}
    """
    from edsl.results import Results

    inner = result.get("result", result)
    results_dict = inner.get("results_dict", inner)
    return Results.from_dict(results_dict)


@ResultParser.register_parser("scenario_single")
def parse_scenario_single(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as a single Scenario.

    Expected format: {"result": {"key": "value", ...}}
    """
    from edsl.scenarios import Scenario

    inner = result.get("result", result)
    return Scenario(inner)


@ResultParser.register_parser("question_from_dict")
def parse_question_from_dict(
    result: Dict[str, Any], field: Optional[str] = None
) -> Any:
    """
    Parse result as a Question object.

    Expected format: {"question_data": {"question_type": "...", ...}}
    """
    from edsl.questions import Question

    question_data = dict(result.get("question_data", {}))
    question_type = question_data.pop("question_type", "free_text")
    return Question(question_type, **question_data)


@ResultParser.register_parser("survey_from_dict")
def parse_survey_from_dict(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as a Survey object.

    Expected format: {"questions": [...], "rules": [...], ...}

    Uses QuestionBase.from_dict() which defines the canonical question format.
    """
    from edsl.surveys import Survey
    from edsl.questions import QuestionBase

    questions = []
    for q in result.get("questions", []):
        # QuestionBase.from_dict() handles the canonical format
        questions.append(QuestionBase.from_dict(q))

    # Build survey from questions
    survey = Survey(questions=questions)

    # TODO: Apply rules if present in result

    return survey


@ResultParser.register_parser("agent_list")
def parse_agent_list(result: Dict[str, Any], field: Optional[str] = None) -> Any:
    """
    Parse result as an AgentList object.

    Expected format: {"agents": [...]} or list of agent dicts
    """
    from edsl.agents import AgentList

    data_field = field or "agents"
    agents = result.get(data_field, result if isinstance(result, list) else [])
    return AgentList.from_list(agents)
