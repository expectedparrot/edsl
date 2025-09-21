from typing import Any, Dict, Optional, Type
from abc import ABC, abstractmethod


class OutputABC(ABC):
    """Abstract base class for controlling `App` outputs.

    Subclasses encapsulate how an application's `results` should be converted
    into a final output artifact, whether that is a raw `results` object,
    a generated report file, or another representation.

    Implementations must be serializable via `to_dict` and reconstructable via
    `load_output_from_dict`.
    """

    @abstractmethod
    def render(self, results: Any) -> Any:
        """Produce the final output given a `results` object."""

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize the output formatter configuration.

        The `add_edsl_version` parameter is accepted for API consistency with
        other components but is not used here.
        """
        return {
            "type": self.__class__.__name__,
            "config": self._export_config(),
        }

    def _export_config(self) -> Dict[str, Any]:
        """Return subclass configuration as a plain dict. Default is empty."""
        return {}

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "OutputABC":
        """Construct an instance from a config dict. Default is no-arg init."""
        return cls()  # type: ignore[call-arg]


OUTPUT_REGISTRY: Dict[str, Type[OutputABC]] = {}


def register_output(cls: Type[OutputABC]) -> Type[OutputABC]:
    """Class decorator to register output formatter types for deserialization."""
    OUTPUT_REGISTRY[cls.__name__] = cls
    return cls


def load_output_from_dict(data: Optional[Dict[str, Any]]) -> Optional[OutputABC]:
    """Factory to reconstruct an OutputABC from its serialized form.

    Returns None if `data` is None.
    """
    if data is None:
        return None
    output_type = data.get("type")
    config = data.get("config", {})
    cls = OUTPUT_REGISTRY.get(output_type)
    if cls is None:
        raise ValueError(f"Unknown output formatter type: {output_type}")
    return cls._from_config(config)


@register_output
class RawResultsOutput(OutputABC):
    """Return the raw `results` object unchanged."""

    def render(self, results: Any) -> Any:
        return results


@register_output
class PassThroughOutput(OutputABC):
    """Return the input object unchanged (Survey, ScenarioList, Results, etc.)."""

    def render(self, results: Any) -> Any:
        return results


@register_output
class ReportFromTemplateOutput(OutputABC):
    """Generate a report file from a `results` template and return its path."""

    def __init__(
        self,
        template: str,
        save_as: str = "report.docx",
        format: str = "docx",
        return_path: bool = True,
    ) -> None:
        self.template = template
        self.save_as = save_as
        self.format = format
        self.return_path = return_path

    def render(self, results: Any) -> Optional[str]:
        report = results.report_from_template(template=self.template, format=self.format)
        report.save(self.save_as)
        return self.save_as if self.return_path else None

    def _export_config(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "save_as": self.save_as,
            "format": self.format,
            "return_path": self.return_path,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "ReportFromTemplateOutput":
        return cls(
            template=config["template"],
            save_as=config.get("save_as", "report.docx"),
            format=config.get("format", "docx"),
            return_path=config.get("return_path", True),
        )


@register_output
class AnswersListOutput(OutputABC):
    """Return the first list from selecting all answers: results.select('answer.*').to_list()[0].

    If there are no rows, returns an empty list.
    """

    def render(self, results: Any) -> Any:
        selected = results.select('answer.*').to_list()
        return selected[0] if selected else []


@register_output
class TableOutput(OutputABC):
    """Render a results table for selected columns via results.select(...).table().

    columns should be a list of selection strings, e.g.,
    ["scenario.tweet", "answer.tweet_sentiment"].
    """

    def __init__(self, columns):
        self.columns = list(columns)

    def render(self, results: Any) -> Any:
        return results.select(*self.columns).table()

    def _export_config(self) -> Dict[str, Any]:
        return {"columns": self.columns}

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "TableOutput":
        return cls(columns=config.get("columns", []))


@register_output
class MarkdownSelectOutput(OutputABC):
    """Render selected result columns to a markdown FileStore via to_markdown().

    Example usage:
        MarkdownSelectOutput([
            'answer.meal_plan_table',
            'answer.shopping_list',
            'answer.recipes',
        ])

    Optional parameters:
        - filename: explicit path for the markdown file
        - to_markdown_kwargs: extra keyword arguments forwarded to Dataset.to_markdown
          (e.g., include_row_headers=False, include_column_headers=False)
    """

    def __init__(self, columns, filename: str | None = None, to_markdown_kwargs: dict | None = None):
        self.columns = list(columns)
        self.filename = filename
        self.to_markdown_kwargs = dict(to_markdown_kwargs or {})

    def render(self, results: Any) -> Any:
        dataset = results.select(*self.columns)
        return dataset.to_markdown(filename=self.filename, **(self.to_markdown_kwargs or {}))

    def _export_config(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "filename": self.filename,
            "to_markdown_kwargs": self.to_markdown_kwargs,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "MarkdownSelectOutput":
        return cls(
            columns=config.get("columns", []),
            filename=config.get("filename"),
            to_markdown_kwargs=config.get("to_markdown_kwargs", {}),
        )

