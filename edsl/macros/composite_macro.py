"""Composite macro that orchestrates two `Macro` instances with explicit wiring.

This module defines `CompositeMacro`, which:
- runs a first `Macro` (macro1)
- binds selected macro1 outputs (via its named `output_formatters`) or macro1 input
  params to the second `Macro` (macro2) input params. Bindings are declared as
  source->target mappings.
- allows fixing (pre-filling) survey input values for macro1 and/or macro2

The effective "initial survey" of the composite is computed dynamically as the
union of required, unfixed parameters from macro1 and macro2 that are not satisfied
by the bindings.

Serialization is supported via `to_dict`/`from_dict` for the explicit-wiring
shape only.
"""

from typing import Any, Optional

from .macro import Macro
from ..surveys import Survey


class CompositeMacro:
    """Compose two `Macro` instances with explicit param wiring.

    Users explicitly specify how macro2 input params are obtained, either from
    macro1 `output_formatters` (by name) or by reusing macro1 input
    params. Users may also provide fixed values for either macro1 or macro2 params.
    """

    # Align with Macro naming: expose an application_type for dispatch
    application_type: str = "composite"

    def __init__(
        self,
        first_macro: Macro,
        second_macro: Optional[Macro] = None,
        bindings: Optional[dict[str, Any]] = None,
        fixed: Optional[dict[str, dict[str, Any]]] = None,
        application_name: Optional[str] = None,
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
    ):
        """Initialize the composite macro.

        Args:
            first_macro: The first macro to run (macro1).
            second_macro: The second macro to run (macro2). May be set later via >>.
            bindings: An explicit dict describing how to populate macro2 params.
                Keys are sources; values are macro2 param names:
                  - Key "param:macro1_param" maps that macro1 param to the target param name (value)
                  - Key "formatter_name" renders macro1 with that named formatter and maps the result to the target param name (value)
                  - Key dict {"formatter": "name", "path": "a.b"} maps the resolved value to the target param name (value)
            fixed: Optional fixed/pre-filled values for surveys:
                {"macro1": {name: value}, "macro2": {name: value}}
            application_name: Python identifier for the composite macro.
            display_name: Human-readable name for the composite macro.
            short_description: One sentence description.
            long_description: Longer description.
        """
        self.first_macro = first_macro
        self.second_macro = second_macro
        self.bindings = dict(bindings or {})
        self.fixed: dict[str, dict[str, Any]] = {
            "macro1": dict((fixed or {}).get("macro1", {})),
            "macro2": dict((fixed or {}).get("macro2", {})),
        }

        # Generate names from component macros if not provided
        if application_name is None or display_name is None:
            first_display = self._extract_macro_display_name(first_macro)
            second_display = (
                self._extract_macro_display_name(second_macro) if second_macro else "?"
            )
            generated_display = f"{first_display} >> {second_display}"

        self.application_name = application_name or self._name_to_alias(
            generated_display if display_name is None else display_name
        )
        self.display_name = display_name or generated_display
        self.short_description = (
            short_description or f"Composite macro: {self.display_name}."
        )
        self.long_description = (
            long_description or f"Composite macro: {self.display_name}."
        )

    def __rshift__(self, macro: "Macro") -> "CompositeMacro":
        """Chain a second macro to this composite using the >> operator."""
        self.second_macro = macro
        return self

    def show(self, filename: Optional[str] = None) -> None:
        """Show a visualization of the composite macro flow.

        Args:
            filename: Optional path to save the image. If None, displays in notebook or opens viewer.
        """
        from .composite_macro_visualization import CompositeMacroVisualization

        CompositeMacroVisualization(self).show(filename=filename)

    # --- Public API -------------------------------------------------------

    @property
    def output_formatters(self):
        """Return the second macro's output formatters (or empty if not set)."""
        if self.second_macro is None:
            from .output_formatter import OutputFormatters

            return OutputFormatters()
        return self.second_macro.output_formatters

    @property
    def initial_survey(self) -> Survey:
        """Compute union of unfixed questions from macro1 and macro2.

        - Include macro1 questions not fixed by self.fixed["macro1"].
        - Include macro2 questions not fixed by self.fixed["macro2"] AND not
          satisfied by bindings (either via formatter outputs or by reusing macro1 params).
        """
        if self.second_macro is None:
            # Only macro1 questions (minus fixed)
            q_needed = self._filter_questions(
                list(self.first_macro.initial_survey),
                exclude_names=set(self.fixed["macro1"].keys()),
            )
            return Survey(q_needed)

        macro1_needed = self._filter_questions(
            list(self.first_macro.initial_survey),
            exclude_names=set(self.fixed["macro1"].keys()),
        )

        macro2_exclusions = (
            set(self.fixed["macro2"].keys()) | self._bound_target_param_names()
        )
        macro2_needed = self._filter_questions(
            list(self.second_macro.initial_survey),
            exclude_names=macro2_exclusions,
        )

        # De-duplicate by question_name, prefer macro1 definitions on conflict
        seen: set[str] = set()
        combined = []
        for q in macro1_needed + macro2_needed:
            if getattr(q, "question_name", None) in seen:
                continue
            seen.add(getattr(q, "question_name", None))
            combined.append(q)
        return Survey(combined)

    def output(
        self,
        params: dict[str, Any] | None,
        formatter_name: Optional[str] = None,
        **kwargs,
    ):
        """Execute the composite flow.

        Steps:
        1) Build macro1 params from provided `params` merged with fixed["macro1"].
        2) Build macro2 params from fixed["macro2"], bindings, and user `params` for
           any remaining required questions.
        4) Run macro2 with constructed params and return its formatted output.

        Args:
            params: Parameters for the composite macro
            formatter_name: Optional formatter to use for the final output (passed to macro2)
            **kwargs: Additional arguments passed through to macro2.output()
        """
        if self.second_macro is None:
            raise ValueError("CompositeMacro requires a second_macro to run.")

        provided = dict(params or {})

        # 1) Resolve macro1 params (fixed overrides take precedence over provided)
        macro1_param_names = {q.question_name for q in self.first_macro.initial_survey}
        macro1_params: dict[str, Any] = {}
        # from user
        for name in macro1_param_names:
            if name in provided:
                macro1_params[name] = provided[name]
        # apply fixed overrides last
        macro1_params.update(self.fixed["macro1"])  # fixed values win

        # 2) Build macro2 params
        macro2_param_names = {q.question_name for q in self.second_macro.initial_survey}
        macro2_params: dict[str, Any] = {}
        # Start with fixed
        macro2_params.update(self.fixed["macro2"])  # fixed first

        # Apply bindings declared as source->target
        for source_spec, target_param in self.bindings.items():
            if target_param not in macro2_param_names:
                # Ignore bindings for unknown params; user may target attachments or legacy keys
                continue
            value = self._resolve_binding_source(source_spec, macro1_params)
            macro2_params[target_param] = value

        # Fill any remaining required params from user-provided composite params
        # that correspond to unfixed/unmapped macro2 questions
        already_set = set(macro2_params.keys())
        for name in macro2_param_names:
            if name in already_set:
                continue
            if name in provided:
                macro2_params[name] = provided[name]

        # 4) Run macro2 with formatter_name and other kwargs
        return self.second_macro.output(
            params=macro2_params, formatter_name=formatter_name, **kwargs
        )

    def deploy(
        self,
        server_url: str = "http://localhost:8000",
        owner: str = "johnjhorton",
        source_available: bool = False,
        force: bool = False,
    ) -> str:
        """Deploy this composite macro to a FastAPI server.

        Args:
            server_url: URL of the FastAPI server (default: http://localhost:8000)
            owner: Required owner string used for global uniqueness (default: 'johnjhorton').
            source_available: If True, the source code is available to future users.
            force: If True, overwrite any existing macro with the same owner/alias.

        Returns:
            The macro_id assigned by the server.

        Example:
            >>> composite = CompositeMacro(first_macro=macro1, second_macro=macro2)
            >>> macro_id = composite.deploy()  # doctest: +SKIP
        """
        from .macro_server_client import MacroServerClient

        return MacroServerClient.deploy(
            self,
            server_url=server_url,
            owner=owner,
            source_available=source_available,
            force=force,
        )

    # --- Serialization ----------------------------------------------------

    def to_dict(self):
        """Serialize this composite macro to a dictionary.

        Includes first_macro, second_macro, bindings, and fixed values.
        """
        data = {
            "application_type": self.application_type,
            "application_name": self.application_name,
            "display_name": self.display_name,
            "short_description": self.short_description,
            "long_description": self.long_description,
            "first_macro": self.first_macro.to_dict(),
            "second_macro": self.second_macro.to_dict()
            if self.second_macro is not None
            else None,
        }
        if self.bindings:
            data["bindings"] = self.bindings
        if any(self.fixed.values()):
            data["fixed"] = self.fixed
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a `CompositeMacro` from a dictionary."""

        def _deserialize_macro_or_composite(payload: dict):
            if not isinstance(payload, dict):
                raise TypeError(
                    "Expected dict for macro payload during deserialization"
                )
            if payload.get("application_type") == "composite":
                return cls.from_dict(payload)
            if "application_type" in payload:
                return Macro.from_dict(payload)
            return Macro.from_dict(payload)

        first = (
            _deserialize_macro_or_composite(data["first_macro"])
            if "first_macro" in data
            else None
        )
        second = (
            _deserialize_macro_or_composite(data["second_macro"])
            if "second_macro" in data and data["second_macro"] is not None
            else None
        )
        bindings = data.get("bindings") or {}
        fixed = data.get("fixed") or {}
        application_name = data.get("application_name")
        display_name = data.get("display_name")
        short_description = data.get("short_description")
        long_description = data.get("long_description")
        if first is None:
            raise ValueError("CompositeMacro.from_dict missing 'first_macro'")
        return cls(
            first_macro=first,
            second_macro=second,
            bindings=bindings,
            fixed=fixed,
            application_name=application_name,
            display_name=display_name,
            short_description=short_description,
            long_description=long_description,
        )

    # --- Internals --------------------------------------------------------

    @staticmethod
    def _filter_questions(questions, *, exclude_names: set[str]):
        """Return questions excluding any whose names appear in `exclude_names`."""
        return [
            q
            for q in questions
            if getattr(q, "question_name", None) not in exclude_names
        ]

    def _bound_target_param_names(self) -> set[str]:
        """Return the set of target parameter names bound by the composite `bindings`."""
        return {v for v in self.bindings.values()}

    @staticmethod
    def _get_by_dotted_path(obj: Any, path: str) -> Any:
        """Resolve a dotted path within nested dicts/objects/lists; returns None on missing."""
        current = obj
        if path is None or path == "":
            return current
        for part in str(path).split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
                continue
            try:
                current = getattr(current, part)
                continue
            except Exception:
                pass
            try:
                index = int(part)
                current = current[index]
                continue
            except Exception:
                pass
            # Not found; return None to indicate missing
            return None
        return current

    def _resolve_binding_source(
        self, source_spec: Any, macro1_params: dict[str, Any]
    ) -> Any:
        """Resolve a binding source spec to a concrete value.

        - dict with {"formatter": name, "path": dotted}: run macro1 formatter and extract by path
        - string "param:<name>": take from macro1 params
        - string <formatter_name>: run macro1 with that formatter
        - any other value: returned as-is
        """
        # Dict form (formatter with optional path)
        if isinstance(source_spec, dict):
            if "formatter" in source_spec:
                formatted = self.first_macro.output(
                    macro1_params, formatter_name=source_spec.get("formatter")
                )
                path = source_spec.get("path")
                return self._get_by_dotted_path(formatted, path) if path else formatted
            # Unknown dict spec; return as-is
            return source_spec
        # String forms
        if isinstance(source_spec, str):
            if source_spec.startswith("param:"):
                return macro1_params.get(source_spec[len("param:") :])
            # Otherwise treat as a macro1 formatter name
            return self.first_macro.output(macro1_params, formatter_name=source_spec)
        # Literal value
        return source_spec

    @staticmethod
    def _extract_macro_display_name(macro: Macro) -> str:
        """Extract the display name from a Macro."""
        return macro.display_name

    @staticmethod
    def _name_to_alias(name: str) -> str:
        """Convert a pretty name to a valid Python identifier alias."""
        import re

        alias = name.lower()
        alias = re.sub(r"[\s\-]+", "_", alias)
        alias = re.sub(r"[^\w]", "", alias)
        if alias and alias[0].isdigit():
            alias = f"macro_{alias}"
        if not alias:
            alias = "macro"
        return alias


if __name__ == "__main__":
    print(
        "This module defines CompositeMacro. See example at edsl/macros/examples/telephone_macro.py"
    )
