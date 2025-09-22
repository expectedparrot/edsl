from typing import Any, Dict, Optional, Type, Iterator, Union
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

    label = "Raw results"
    id = "raw_results"

    def render(self, results: Any) -> Any:
        return results


@register_output
class PassThroughOutput(OutputABC):
    """Return the input object unchanged (Survey, ScenarioList, Results, etc.)."""

    label = "Pass through"
    id = "pass_through"

    def render(self, results: Any) -> Any:
        return results


@register_output
class ReportFromTemplateOutput(OutputABC):
    """Generate a report file from a `results` template and return its path."""

    label = "Generate report (DOCX)"
    id = "report_docx"

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

    label = "Table view"
    id = "table"

    def __init__(self, columns):
        self.columns = list(columns)

    def render(self, results: Any) -> Any:
        return results.select(*self.columns).table()

    def _export_config(self) -> Dict[str, Any]:
        return {"columns": self.columns}

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "TableOutput":
        return cls(columns=config.get("columns", []))

    id = "table"


@register_output
class FlippedTableOutput(OutputABC):
    """Render a flipped results table for selected columns via results.select(...).table().flip().

    Example configuration:
        FlippedTableOutput([
            "startup_name",
            "answer.*",
        ])

    Optional parameters:
        - tablefmt: table format (defaults to "rich")
        - pretty_labels: mapping of column keys to display labels
        - print_parameters: parameters forwarded to Dataset.table for rendering
    """

    label = "Flipped table view"
    id = "table_flipped"

    def __init__(
        self,
        columns,
        tablefmt: str | None = "rich",
        pretty_labels: dict | None = None,
        print_parameters: dict | None = None,
    ) -> None:
        self.columns = list(columns)
        self.tablefmt = tablefmt
        self.pretty_labels = dict(pretty_labels or {})
        self.print_parameters = dict(print_parameters or {})

    def render(self, results: Any) -> Any:
        return (
            results.select(*self.columns)
            .table(
                tablefmt=self.tablefmt,
                pretty_labels=self.pretty_labels or None,
                print_parameters=self.print_parameters or None,
            )
            .flip()
        )

    def _export_config(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "tablefmt": self.tablefmt,
            "pretty_labels": self.pretty_labels,
            "print_parameters": self.print_parameters,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "FlippedTableOutput":
        return cls(
            columns=config.get("columns", []),
            tablefmt=config.get("tablefmt", "rich"),
            pretty_labels=config.get("pretty_labels", {}),
            print_parameters=config.get("print_parameters", {}),
        )

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

    label = "Markdown file (save)"
    id = "markdown_save"

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



@register_output
class MarkdownSelectViewOutput(OutputABC):
    """Render selected result columns to markdown and open the file via FileStore.view().

    Same configuration as MarkdownSelectOutput, but after writing the markdown file,
    it invokes `.view()` on the returned FileStore for immediate viewing.
    """

    label = "Open Markdown (view)"
    id = "markdown_view"

    def __init__(self, columns, filename: str | None = None, to_markdown_kwargs: dict | None = None):
        self.columns = list(columns)
        self.filename = filename
        self.to_markdown_kwargs = dict(to_markdown_kwargs or {})

    def render(self, results: Any) -> Any:
        dataset = results.select(*self.columns)
        filestore = dataset.to_markdown(filename=self.filename, **(self.to_markdown_kwargs or {}))
        try:
            filestore.view()
        except Exception:
            # Fallback silently if view is unavailable in environment
            pass
        return filestore

    def _export_config(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "filename": self.filename,
            "to_markdown_kwargs": self.to_markdown_kwargs,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "MarkdownSelectViewOutput":
        return cls(
            columns=config.get("columns", []),
            filename=config.get("filename"),
            to_markdown_kwargs=config.get("to_markdown_kwargs", {}),
        )



@register_output
class MarkdownSelectPDFOutput(OutputABC):
    """Render selected columns to markdown, convert to PDF, and return the PDF FileStore."""

    label = "Export PDF"
    id = "export_pdf"

    def __init__(self, columns, filename: str | None = None, to_markdown_kwargs: dict | None = None, pdf_options: dict | None = None, output_path: str | None = None):
        self.columns = list(columns)
        self.filename = filename
        self.to_markdown_kwargs = dict(to_markdown_kwargs or {})
        self.pdf_options = dict(pdf_options or {})
        self.output_path = output_path

    def render(self, results: Any) -> Any:
        dataset = results.select(*self.columns)
        filestore = dataset.to_markdown(filename=self.filename, **(self.to_markdown_kwargs or {}))
        return filestore.to_pdf(output_path=self.output_path, **(self.pdf_options or {}))

    def _export_config(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "filename": self.filename,
            "to_markdown_kwargs": self.to_markdown_kwargs,
            "pdf_options": self.pdf_options,
            "output_path": self.output_path,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "MarkdownSelectPDFOutput":
        return cls(
            columns=config.get("columns", []),
            filename=config.get("filename"),
            to_markdown_kwargs=config.get("to_markdown_kwargs", {}),
            pdf_options=config.get("pdf_options", {}),
            output_path=config.get("output_path"),
        )


@register_output
class MarkdownSelectDocxOutput(OutputABC):
    """Render selected columns to markdown, convert to DOCX, and return the DOCX FileStore."""

    label = "Export DOCX"
    id = "export_docx"

    def __init__(self, columns, filename: str | None = None, to_markdown_kwargs: dict | None = None, docx_options: dict | None = None, output_path: str | None = None):
        self.columns = list(columns)
        self.filename = filename
        self.to_markdown_kwargs = dict(to_markdown_kwargs or {})
        self.docx_options = dict(docx_options or {})
        self.output_path = output_path

    def render(self, results: Any) -> Any:
        dataset = results.select(*self.columns)
        filestore = dataset.to_markdown(filename=self.filename, **(self.to_markdown_kwargs or {}))
        return filestore.to_docx(output_path=self.output_path, **(self.docx_options or {}))

    def _export_config(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "filename": self.filename,
            "to_markdown_kwargs": self.to_markdown_kwargs,
            "docx_options": self.docx_options,
            "output_path": self.output_path,
        }

    @classmethod
    def _from_config(cls, config: Dict[str, Any]) -> "MarkdownSelectDocxOutput":
        return cls(
            columns=config.get("columns", []),
            filename=config.get("filename"),
            to_markdown_kwargs=config.get("to_markdown_kwargs", {}),
            docx_options=config.get("docx_options", {}),
            output_path=config.get("output_path"),
        )


class OutputFormatters:
    """Ordered collection of output formatter objects with a designated default.

    - Behaves like a list for iteration and index-based access
    - Also supports lookup by formatter "id" via __getitem__(str)
    - If no explicit default is set, the first formatter is considered the default

    Formatter "id" resolution:
    - If a formatter has an attribute `id`, that is used
    - Otherwise the class name is used
    - If duplicates occur, a numeric suffix (e.g., "-2") is appended to ensure uniqueness
    """

    def __init__(self, formatters: Optional[list[OutputABC]] = None, default_index: Optional[int] = None):
        self._formatters: list[OutputABC] = list(formatters or [])
        self._ids: list[str] = []
        self._rebuild_ids()
        if self._formatters:
            if default_index is None:
                self.default_index: Optional[int] = 0
            else:
                if default_index < 0 or default_index >= len(self._formatters):
                    raise IndexError("default_index out of range for OutputFormatters")
                self.default_index = default_index
        else:
            self.default_index = None

    # Basic sequence protocol
    def __iter__(self) -> Iterator[OutputABC]:
        return iter(self._formatters)

    def __len__(self) -> int:
        return len(self._formatters)

    def __getitem__(self, key: Union[int, str]) -> OutputABC:
        if isinstance(key, int):
            return self._formatters[key]
        # string -> id lookup
        idx = self._index_for_id(key)
        return self._formatters[idx]

    # Public API
    def add(self, formatter: OutputABC, make_default: bool = False) -> None:
        self._formatters.append(formatter)
        self._add_id_for(formatter)
        if self.default_index is None:
            self.default_index = 0
        if make_default:
            self.default_index = len(self._formatters) - 1

    def remove(self, key: Union[int, str, OutputABC]) -> None:
        idx = self._coerce_to_index(key)
        del self._formatters[idx]
        del self._ids[idx]
        # Adjust default index
        if self.default_index is not None:
            if idx < self.default_index:
                self.default_index -= 1
            elif idx == self.default_index:
                self.default_index = 0 if self._formatters else None

    def set_default(self, key: Union[int, str, OutputABC]) -> None:
        idx = self._coerce_to_index(key)
        self.default_index = idx

    def get_default(self) -> OutputABC:
        if self.default_index is None or not self._formatters:
            raise ValueError("No output formatters have been configured")
        return self._formatters[self.default_index]

    def get(self, key: Union[int, str]) -> OutputABC:
        return self[key]

    def ids(self) -> list[str]:
        return list(self._ids)

    def labels(self) -> list[str]:
        labels: list[str] = []
        for fmt, fid in zip(self._formatters, self._ids):
            label = getattr(fmt, "label", None)
            labels.append(label if isinstance(label, str) else fid)
        return labels

    def validate(self) -> None:
        if len(set(self._ids)) != len(self._ids):
            raise ValueError("Duplicate formatter ids detected in OutputFormatters")
        if self._formatters and (self.default_index is None or not (0 <= self.default_index < len(self._formatters))):
            raise ValueError("Invalid default index for OutputFormatters")

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        return {
            "formatters": [f.to_dict(add_edsl_version=add_edsl_version) for f in self._formatters],
            "default_index": self.default_index,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["OutputFormatters"]:
        if data is None:
            return None
        items = data.get("formatters", [])
        default_index = data.get("default_index")
        formatters: list[OutputABC] = [load_output_from_dict(item) for item in items]
        return cls(formatters=formatters, default_index=default_index)

    # Internal helpers
    def _rebuild_ids(self) -> None:
        self._ids = []
        for fmt in self._formatters:
            self._add_id_for(fmt)

    def _add_id_for(self, formatter: OutputABC) -> None:
        base = getattr(formatter, "id", None)
        if not isinstance(base, str) or not base:
            base = formatter.__class__.__name__
        candidate = base
        counter = 2
        while candidate in self._ids:
            candidate = f"{base}-{counter}"
            counter += 1
        self._ids.append(candidate)

    def _index_for_id(self, formatter_id: str) -> int:
        try:
            return self._ids.index(formatter_id)
        except ValueError:
            raise KeyError(f"Unknown formatter id: {formatter_id}")

    def _coerce_to_index(self, key: Union[int, str, OutputABC]) -> int:
        if isinstance(key, int):
            return key
        if isinstance(key, str):
            return self._index_for_id(key)
        # assume object instance
        for idx, fmt in enumerate(self._formatters):
            if fmt is key:
                return idx
        raise ValueError("Formatter not found in OutputFormatters")

