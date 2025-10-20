import inspect
from jinja2 import Template, StrictUndefined

from typing import Any, Optional
from collections import UserList

from ..results import Results
from ..dataset import Dataset
from ..dataset.display.table_display import TableDisplay
from ..scenarios import ScenarioList, FileStore
from ..scenarios import Scenario
from ..scenarios.agent_blueprint import AgentBlueprint
from ..surveys import Survey

relevant_classes = {
    Results: [
        "to_scenario_list",
        "select",
        "table",
        "report_from_template",
        "long_view",
        "augment_agents",
    ],
    Dataset: ["table", "expand", "to_markdown", "to_list"],
    TableDisplay: ["flip", "to_string"],
    FileStore: ["view", "to_docx", "save"],
    Survey: ["to_scenario_list", "table", "add_weighted_linear_scale_sum"],
    ScenarioList: [
        "slice",
        "to_survey",
        "rename",
        "zip",
        "string_cat",
        "string_cat_if",
        "if_",
        "when",
        "add_value",
        "to_ranked_scenario_list",
        "to_true_skill_ranked_list",
        "to_agent_blueprint",
        "__getitem__",
        "add_scenario_reference",
        "choose_k",
        "full_replace",
        "then",
        "else_",
        "otherwise",
        "end",
    ],
    Scenario: ["chunk_text", "replace_value", "to_scenario_list", "to_agent_list"],
    list: ["__getitem__"],
    AgentBlueprint: ["create_agent_list", "table"],
}

white_list_methods = []
for cls, methods in relevant_classes.items():
    for method in methods:
        try:
            white_list_methods.append(getattr(cls, method))
        except AttributeError:
            # Some methods may not be available at import time due to import order/cycles
            # Skip missing ones; unknown commands won't be whitelisted
            continue


def _get_return_annotation_safe(func: Any) -> Any:
    try:
        return inspect.signature(func).return_annotation
    except (ValueError, TypeError):
        # Builtins like list.__getitem__ raise here; treat as unknown
        return inspect._empty


white_list_commands = [f.__name__ for f in white_list_methods]
return_types = {f.__name__: _get_return_annotation_safe(f) for f in white_list_methods}

parent_class = {f.__name__: f.__qualname__.split(".")[0] for f in white_list_methods}

from abc import ABC

# Build disambiguated maps keyed by (owner_class_name, method_name)
# This avoids collisions for methods that share the same name across classes
owner_to_methods: dict[str, set[str]] = {}
return_types_by_owner_method: dict[tuple[str, str], Any] = {}
for f in white_list_methods:
    owner_name = f.__qualname__.split(".")[0]
    method_name = f.__name__
    owner_to_methods.setdefault(owner_name, set()).add(method_name)
    ann = _get_return_annotation_safe(f)
    return_types_by_owner_method[(owner_name, method_name)] = ann

# Map known formatter targets to their root class names
_target_to_root_class_name: dict[str, str] = {
    "results": Results.__name__,
    "scenario": Scenario.__name__,
    # Best-effort placeholders for targets not imported here
    "survey": "Survey",
    "agent_list": "AgentList",
}


def _normalize_annotation_to_name(
    annotation: Any, current_type_name: Optional[str]
) -> str:
    """Convert a return annotation or class object to a readable type name.

    - If annotation is empty or unknown, returns 'Unknown'.
    - If it represents Self, resolve to current_type_name.
    - Otherwise return a best-effort class/type name string.
    """
    if annotation is inspect._empty:
        return "Unknown"
    # Handle typing.Self and 'Self' style
    if isinstance(annotation, str):
        if annotation in {"Self", "typing.Self"}:
            return current_type_name or "Unknown"
        return annotation
    # typing.Self may appear as object without __name__
    try:
        from typing import Self as TypingSelf  # type: ignore

        if annotation is TypingSelf:
            return current_type_name or "Unknown"
    except Exception:
        pass
    # Class-like
    name = getattr(annotation, "__name__", None)
    if isinstance(name, str):
        return name
    # Fallback
    text = str(annotation)
    # Strip typing prefixes if present
    if text.startswith("typing."):
        text = text[len("typing.") :]
    return text


class ObjectFormatter(ABC):
    """Declarative, chainable renderer that applies whitelisted methods to a target type.

    Instances record a sequence of method calls and arguments. When `render` is invoked,
    those methods are applied to the provided object. Templates in recorded args/kwargs
    are resolved lazily against a `params` context.
    """

    target = None
    _subclass_registry: dict[str, "ObjectFormatter"] = {}
    # (owner_class_name, method_name) -> override return annotation/type
    _return_type_overrides: dict[tuple[str, str], Any] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        target = getattr(cls, "target", None)
        if target is not None:
            # Last definition wins if duplicates occur
            ObjectFormatter._subclass_registry[target] = cls  # type: ignore[assignment]

    def copy(self):
        """Return a copy of the formatter.

        This is useful for creating a new formatter with the same configuration but a different target.
        """
        return self.__class__.from_dict(self.to_dict())

    def set_description(self, description: str):
        """Set the description of the formatter.

        This is useful for creating a new formatter with the same configuration but a different description.
        """
        self.description = description
        return self

    def breakpoint(self):
        """Set a breakpoint in the formatter.

        This is useful for debugging the formatter.
        """
        if True:
            # breakpoint()
            pass
        return self

    def set_output_type(self, output_type: str):
        """Set the output type of the formatter.

        This is useful for creating a new formatter with the same configuration but a different output type.
        """
        self.output_type = output_type
        return self

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        allowed_commands: Optional[list[str]] = None,
        params: Optional[Any] = None,
        output_type: str = "auto",
        _stored_commands: Optional[list[tuple[str, tuple, dict]]] = None,
    ) -> None:
        # Treat "name" as a legacy alias for description. If only name is provided,
        # store it in description; keep a .name attribute for backwards references.
        final_description = description if description is not None else name
        self.description = final_description
        self.name = final_description
        if allowed_commands is None:
            allowed_commands = white_list_commands
        self.allowed_commands = allowed_commands

        self._stored_commands = (
            list(_stored_commands) if _stored_commands is not None else []
        )
        # Optional declarative params spec (names or defaults) supplied by user
        self.params = params
        # Output type hint for frontend rendering: "markdown", "html", "file", "json", "auto"
        self.output_type = output_type

    def __getattr__(self, name: str) -> Any:
        if name in self.allowed_commands:

            def method_proxy(*args, **kwargs):
                self._stored_commands.append((name, args, kwargs))
                return self

            return method_proxy

        # For unknown methods, raise AttributeError immediately
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'. "
            f"Use .then('{name}', ...) for post-run method chaining."
        )

    def render(self, results: Any, params: Optional[dict] = None) -> Any:
        """Apply recorded operations to `results`, resolving templates via `params`."""
        if not self._stored_commands:
            return results

        def _render_template_string(value: str, ctx: dict) -> str:
            # Render only if it looks like a jinja2 template AND references a key present in ctx
            if (("{{" in value) or ("{%" in value)) and ctx:
                # If none of the provided context keys appear in the template, skip rendering
                # to avoid accidentally resolving placeholders intended for later stages (e.g., results fields)
                try:
                    keys = list(ctx.keys())
                except Exception:
                    keys = []
                if keys and any(
                    ("{{" + k in value) or ("{{ " + k in value) for k in keys
                ):
                    return Template(value, undefined=StrictUndefined).render(**ctx)
            return value

        def _resolve_templates(value: Any, ctx: dict) -> Any:
            if isinstance(value, str):
                return _render_template_string(value, ctx)
            if isinstance(value, (list, tuple)):
                resolved = [_resolve_templates(v, ctx) for v in value]
                return type(value)(resolved)
            if isinstance(value, dict):
                return {k: _resolve_templates(v, ctx) for k, v in value.items()}
            return value

        context = params or {}

        for command, args, kwargs in self._stored_commands:
            resolved_args = _resolve_templates(args, context)
            resolved_kwargs = _resolve_templates(kwargs, context)
            results = getattr(results, command)(*resolved_args, **resolved_kwargs)

        return results

    # --- end of public API ---

    @classmethod
    def set_return_type_override(
        cls, owner_class_name: str, method_name: str, return_type: Any
    ) -> None:
        """Override the inferred return type for a given (owner, method).

        Example: ObjectFormatter.set_return_type_override('list', '__getitem__', 'Unknown')
        """
        cls._return_type_overrides[(owner_class_name, method_name)] = return_type

    @classmethod
    def clear_return_type_override(
        cls, owner_class_name: str, method_name: str
    ) -> None:
        cls._return_type_overrides.pop((owner_class_name, method_name), None)

    def _starting_type_name(self) -> str:
        """Resolve the readable starting type name from this formatter's target.

        Returns a class-like name such as 'Results' or 'Scenario' when
        recognizable, otherwise a best-effort string for the target.
        """
        if isinstance(self.target, str):
            mapped = _target_to_root_class_name.get(self.target)
            if mapped is not None:
                return mapped
            return self.target
        return "Unknown"

    def type_flow(self) -> list[tuple[str, str, str]]:
        """Return a list of (start_type, command, end_type) for each queued command.

        Uses method owner information and return annotations gathered from the
        whitelisted methods to infer the type transitions.
        """
        flow: list[tuple[str, str, str]] = []
        current_type_name = self._starting_type_name()

        for method_name, _args, _kwargs in self._stored_commands:
            # Prefer the current type as owner if it has this method
            candidate_owner_names = [
                owner_name
                for owner_name, methods in owner_to_methods.items()
                if method_name in methods
            ]

            if current_type_name in candidate_owner_names:
                owner_name = current_type_name
            elif len(candidate_owner_names) == 1:
                owner_name = candidate_owner_names[0]
            else:
                owner_name = current_type_name  # best-effort; may be Unknown

            # Overrides take precedence over inferred annotations
            ann = ObjectFormatter._return_type_overrides.get((owner_name, method_name))
            if ann is None:
                ann = return_types_by_owner_method.get(
                    (owner_name, method_name), inspect._empty
                )
            end_type_name = _normalize_annotation_to_name(ann, current_type_name)
            flow.append((current_type_name, method_name, end_type_name))
            current_type_name = end_type_name

        return flow

    def expected_return_type(self) -> str:
        """Return the expected final type name after all queued commands are applied.

        If there are no queued commands, returns the starting type name.
        """
        flow = self.type_flow()
        if not flow:
            return self._starting_type_name()
        return flow[-1][2]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the formatter configuration and queued commands to a dict.

        Doctest:

        >>> of = OutputFormatter(name='calculator', description='demo', allowed_commands=['inc', 'mul']).inc(3).mul(2)
        >>> data = of.to_dict()
        >>> set(['name','description','allowed_commands','stored_commands','target']).issubset(set(data.keys()))
        True
        >>> data['name'], data['description']
        ('calculator', 'demo')
        >>> data['allowed_commands']
        ['inc', 'mul']
        >>> data['target']
        'results'
        >>> data['stored_commands'][0]['name']
        'inc'
        >>> isinstance(data['stored_commands'][0]['args'], list)
        True
        """
        return {
            # Prefer description as the canonical field; include name for legacy readers
            "description": self.description,
            "name": self.description,
            "allowed_commands": list(self.allowed_commands),
            "target": self.target,
            "params": self.params,
            "output_type": getattr(self, "output_type", "auto"),
            "stored_commands": [
                {"name": name, "args": list(args), "kwargs": kwargs}
                for name, args, kwargs in self._stored_commands
            ],
        }

    def __repr__(self) -> str:
        # Return a compact, constructor-style string that can recreate this instance.
        cls_name = self.__class__.__name__
        parts: list[str] = []
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        # Only include allowed_commands if it differs from the default
        try:
            if self.allowed_commands != white_list_commands:
                parts.append(f"allowed_commands={self.allowed_commands!r}")
        except Exception:
            parts.append(f"allowed_commands={self.allowed_commands!r}")
        if self.params is not None:
            parts.append(f"params={self.params!r}")
        if getattr(self, "output_type", "auto") != "auto":
            parts.append(f"output_type={self.output_type!r}")
        if self._stored_commands:
            parts.append(f"_stored_commands={self._stored_commands!r}")
        return f"{cls_name}({', '.join(parts)})"

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ObjectFormatter.

        This representation can be used with eval() to recreate the ObjectFormatter object.
        Used primarily for doctests and debugging.

        The __repr__ method already returns an eval-able representation, so we just
        delegate to it.
        """
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputFormatter":
        """Create a formatter from a dict produced by to_dict.

        Doctest:

        >>> data = {
        ...     'name': 'calculator',
        ...     'description': 'demo',
        ...     'allowed_commands': ['inc', 'mul'],
        ...     'target': 'results',
        ...     'stored_commands': [
        ...         {'name': 'inc', 'args': [3], 'kwargs': {}},
        ...         {'name': 'mul', 'args': [2], 'kwargs': {}},
        ...     ],
        ... }
        >>> of = ObjectFormatter.from_dict(data)
        >>> of.name, of.description
        ('calculator', 'demo')
        >>> class Dummy:
        ...     def __init__(self):
        ...         self.value = 1
        ...     def inc(self, n):
        ...         self.value += n
        ...         return self
        ...     def mul(self, n):
        ...         self.value *= n
        ...         return self
        >>> d = Dummy()
        >>> of.render(d)
        <...Dummy object at ...>
        >>> d.value
        8
        """
        target_value = data.get("target")
        subclass = ObjectFormatter._subclass_registry.get(target_value, cls)
        allowed = data.get("allowed_commands")
        # Accept either 'description' or legacy 'name'
        description_value = data.get("description", data.get("name"))
        stored = []
        for item in data.get("stored_commands", []):
            name = item["name"]
            args = tuple(item.get("args", []))
            kwargs = dict(item.get("kwargs", {}))
            stored.append((name, args, kwargs))
        instance = subclass(
            description=description_value,
            allowed_commands=allowed,
            params=data.get("params"),
            output_type=data.get("output_type", "auto"),
            _stored_commands=stored,
        )
        return instance


class OutputFormatter(ObjectFormatter):
    target = "results"


class OutputFormatters(UserList):
    """Container for named output formatters with a default selection.

    Accepts initialization from either a dict mapping names to `OutputFormatter`
    instances, or a list of `OutputFormatter` instances (legacy). Ensures a
    pass-through `raw_results` formatter is always present.
    """

    def __init__(
        self,
        data: dict[str, OutputFormatter] | list[OutputFormatter] | None = None,
        default: Optional[str] = None,
    ):
        # Support dict-based initialization as the primary API. List remains for legacy paths.
        if isinstance(data, dict):
            mapping: dict[str, OutputFormatter] = dict(data)
            data_list: list[OutputFormatter] = list(mapping.values())
        else:
            data_list = list(data) if data is not None else []
            # Derive mapping keys from description (or legacy name) when constructed from list
            mapping = {}
            for f in data_list:
                key = getattr(f, "description", None) or getattr(f, "name", None)
                if not key:
                    raise ValueError(
                        "Each formatter must have a non-empty description to be keyed."
                    )
                if key in mapping:
                    raise ValueError(f"Duplicate formatter key '{key}' detected")
                mapping[key] = f

        super().__init__(data_list)

        self.mapping = mapping
        self.default: Optional[str] = default

        # Ensure a pass-through 'raw_results' exists by default
        self._ensure_raw_results()

    def __repr__(self) -> str:
        return f"OutputFormatters({self.data})"

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the OutputFormatters object.

        This representation can be used with eval() to recreate the OutputFormatters object.
        Used primarily for doctests and debugging.
        """
        # Build a dictionary representation for eval
        mapping_repr = "{"
        items = []
        for name, formatter in self.mapping.items():
            # Use the formatter's _eval_repr_ if available, otherwise repr()
            if hasattr(formatter, "_eval_repr_"):
                formatter_repr = formatter._eval_repr_()
            else:
                formatter_repr = repr(formatter)
            items.append(f"{repr(name)}: {formatter_repr}")
        mapping_repr += ", ".join(items) + "}"

        default_repr = repr(self.default)
        return f"OutputFormatters(data={mapping_repr}, default={default_repr})"

    def set_default(self, name: str) -> None:
        if name not in self.mapping:
            raise ValueError(f"Formatter {name} not found")
        self.default = name

    def get_default(self) -> OutputFormatter:
        if self.default is not None and self.default in self.mapping:
            return self.mapping[self.default]
        if "raw_results" in self.mapping:
            return self.mapping["raw_results"]
        # Fallback to first available
        return next(iter(self.mapping.values()))

    def get_formatter(self, name: str) -> OutputFormatter:
        """Get a formatter by name."""
        if name not in self.mapping:
            raise ValueError(
                f"Formatter '{name}' not found. Available formatters: {list(self.mapping.keys())}"
            )
        return self.mapping[name]

    def register(
        self,
        formatter: OutputFormatter,
        key: str | None = None,
        *,
        set_default: bool = False,
    ) -> None:
        """Add a formatter to the collection, updating mapping and optional default.

        Args:
            formatter: The OutputFormatter to add.
            key: Optional explicit key to register under. If None, uses
                 formatter.description or legacy formatter.name.
            set_default: If True, set this formatter as the default.
        """
        if not isinstance(formatter, OutputFormatter):
            raise TypeError("formatter must be an OutputFormatter")
        name = (
            key
            or getattr(formatter, "description", None)
            or getattr(formatter, "name", None)
        )
        if not name:
            raise ValueError("formatter must have a unique, non-empty description")
        if name in self.mapping:
            raise ValueError(f"Formatter with name '{name}' already exists")
        # Append and update mapping
        self.data.append(formatter)
        self.mapping[name] = formatter
        if set_default:
            self.set_default(name)

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
        """Serialize the collection of formatters and default selection to a dict.

        Doctest:

        >>> of1 = OutputFormatter(name='a', description=None, allowed_commands=['table']).table()
        >>> of2 = OutputFormatter(name='b', description=None, allowed_commands=['flip'])
        >>> ofs = OutputFormatters([of1, of2])
        >>> ofs.set_default('a')
        >>> data = ofs.to_dict()
        >>> set(['formatters','default']).issubset(set(data.keys()))
        True
        >>> data['default']
        'a'
        >>> len(data['formatters'])
        2
        """
        # Serialize to a dict keyed by formatter names (descriptions)
        return {
            "formatters": {
                name: formatter.to_dict() for name, formatter in self.mapping.items()
            },
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputFormatters":
        """Create an OutputFormatters instance from a dict produced by to_dict.

        Doctest:

        >>> payload = {
        ...   'formatters': [
        ...       {'name': 'a', 'description': None, 'allowed_commands': ['table'], 'target': 'results', 'stored_commands': [{'name':'table','args': [], 'kwargs': {}}]},
        ...       {'name': 'b', 'description': None, 'allowed_commands': ['flip'], 'target': 'results', 'stored_commands': []},
        ...   ],
        ...   'default': 'a',
        ... }
        >>> ofs = OutputFormatters.from_dict(payload)
        >>> isinstance(ofs, OutputFormatters)
        True
        >>> ofs.get_default().name
        'a'
        >>> len(ofs)
        2
        """
        payload = data.get("formatters", {})
        # Accept both new dict-shaped and legacy list-shaped payloads
        mapping: dict[str, OutputFormatter]
        if isinstance(payload, dict):
            mapping = {
                name: ObjectFormatter.from_dict(fd) for name, fd in payload.items()
            }
        else:
            # Legacy: list of formatter dicts; key by description/name
            mapping = {}
            for fd in payload or []:
                of = ObjectFormatter.from_dict(fd)
                key = getattr(of, "description", None) or getattr(of, "name", None)
                if not key:
                    raise ValueError(
                        "Formatter entry missing description/name for keying"
                    )
                mapping[key] = of
        default_name = data.get("default")
        instance = cls(mapping, default=default_name)
        # Ensure the selected default exists if provided
        if default_name is not None:
            instance.set_default(default_name)
        return instance

    def _ensure_raw_results(self) -> None:
        if "raw_results" not in self.mapping:
            self.mapping["raw_results"] = OutputFormatter(description="Raw results")
            # Keep underlying list in sync for any legacy accesses
            self.data.append(self.mapping["raw_results"])


class ScenarioAttachmentFormatter(ObjectFormatter):
    target = "scenario"


class SurveyAttachmentFormatter(ObjectFormatter):
    target = "survey"


class AgentAttachmentFormatter(ObjectFormatter):
    target = "agent_list"


class AttachmentsFormatter(ObjectFormatter):
    target = "attachments"

    def render(self, attachments: Any, params: Optional[dict] = None) -> Any:
        # attachments here is a HeadAttachments instance when applied
        # Execute stored named ops via AttachmentOps
        from .attachments_ops import AttachmentOps

        if attachments is None:
            # Import here to avoid cycle
            from .head_attachments import HeadAttachments

            attachments = HeadAttachments()
        for command, args, kwargs in self._stored_commands:
            # Support either .op(name='...') or .then('op', name='...') shapes
            if command != "op":
                raise ValueError(
                    "AttachmentsFormatter only supports op(name=..., **kwargs) steps"
                )
            op_name = kwargs.pop("name", None)
            if not isinstance(op_name, str) or not op_name:
                raise ValueError(".op requires a 'name' keyword argument")
            fn = AttachmentOps.get(op_name)
            attachments = fn(attachments, params or {}, **kwargs)
        return attachments

    # Provide a fluent helper for clarity and serialization friendliness
    def op(self, **kwargs) -> "AttachmentsFormatter":
        # Record an op step; name is required and validated in render
        self._stored_commands.append(("op", (), dict(kwargs)))
        return self


if __name__ == "__main__":
    # Provide a sensible default override for built-in list.__getitem__
    # Without this, inspect.signature fails and leaves Unknown, which is fine,
    # but the override makes intent explicit.
    ObjectFormatter.set_return_type_override("list", "__getitem__", "Unknown")

    of = OutputFormatter().table().flip()
    from edsl.results import Results

    results = Results.example()
    print(of.render(results))
