"""Composite application that orchestrates two `App` instances with explicit wiring.

This module defines `CompositeApp`, which:
- runs a first `App` (app1)
- binds selected app1 outputs (via its named `output_formatters`) or app1 input
  params to the second `App` (app2) input params. Bindings are declared as
  source->target mappings.
- allows fixing (pre-filling) survey input values for app1 and/or app2

The effective "initial survey" of the composite is computed dynamically as the
union of required, unfixed parameters from app1 and app2 that are not satisfied
by the bindings.

Serialization is supported via `to_dict`/`from_dict` for the explicit-wiring
shape only.
"""

from typing import Any, Optional

from .app import App
from ..surveys import Survey


class CompositeApp:
    """Compose two `App` instances with explicit param wiring.

    Users explicitly specify how app2 input params are obtained, either from
    app1 `output_formatters` (by name) or by reusing app1 input
    params. Users may also provide fixed values for either app1 or app2 params.
    """

    # Align with App naming: expose an application_type for dispatch
    application_type: str = "composite"

    def __init__(
        self,
        first_app: App,
        second_app: Optional[App] = None,
        bindings: Optional[dict[str, Any]] = None,
        fixed: Optional[dict[str, dict[str, Any]]] = None,
        application_name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize the composite application.

        Args:
            first_app: The first app to run (app1).
            second_app: The second app to run (app2). May be set later via >>.
            bindings: An explicit dict describing how to populate app2 params.
                Keys are sources; values are app2 param names:
                  - Key "param:app1_param" maps that app1 param to the target param name (value)
                  - Key "formatter_name" renders app1 with that named formatter and maps the result to the target param name (value)
                  - Key dict {"formatter": "name", "path": "a.b"} maps the resolved value to the target param name (value)
            fixed: Optional fixed/pre-filled values for surveys:
                {"app1": {name: value}, "app2": {name: value}}
        """
        self.first_app = first_app
        self.second_app = second_app
        self.bindings = dict(bindings or {})
        self.fixed: dict[str, dict[str, Any]] = {
            "app1": dict((fixed or {}).get("app1", {})),
            "app2": dict((fixed or {}).get("app2", {})),
        }
        # Generate application_name from component apps if not provided
        self.application_name = application_name or f"{first_app.application_name} >> {second_app.application_name if second_app else '?'}"
        self.description = description or f"Composite app: {self.application_name}"

    def __rshift__(self, app: "App") -> "CompositeApp":
        """Chain a second app to this composite using the >> operator."""
        self.second_app = app
        return self

    # --- Public API -------------------------------------------------------

    @property
    def output_formatters(self):
        """Return the second app's output formatters (or empty if not set)."""
        if self.second_app is None:
            from .output_formatter import OutputFormatters
            return OutputFormatters()
        return self.second_app.output_formatters

    @property
    def initial_survey(self) -> Survey:
        """Compute union of unfixed questions from app1 and app2.

        - Include app1 questions not fixed by self.fixed["app1"].
        - Include app2 questions not fixed by self.fixed["app2"] AND not
          satisfied by bindings (either via formatter outputs or by reusing app1 params).
        """
        if self.second_app is None:
            # Only app1 questions (minus fixed)
            q_needed = self._filter_questions(
                list(self.first_app.initial_survey),
                exclude_names=set(self.fixed["app1"].keys()),
            )
            return Survey(q_needed)

        app1_needed = self._filter_questions(
            list(self.first_app.initial_survey),
            exclude_names=set(self.fixed["app1"].keys()),
        )

        app2_exclusions = set(self.fixed["app2"].keys()) | self._bound_target_param_names()
        app2_needed = self._filter_questions(
            list(self.second_app.initial_survey),
            exclude_names=app2_exclusions,
        )

        # De-duplicate by question_name, prefer app1 definitions on conflict
        seen: set[str] = set()
        combined = []
        for q in app1_needed + app2_needed:
            if getattr(q, "question_name", None) in seen:
                continue
            seen.add(getattr(q, "question_name", None))
            combined.append(q)
        return Survey(combined)

    def output(self, params: dict[str, Any] | None, formatter_name: Optional[str] = None, **kwargs):
        """Execute the composite flow.

        Steps:
        1) Build app1 params from provided `params` merged with fixed["app1"].
        2) Build app2 params from fixed["app2"], bindings, and user `params` for
           any remaining required questions.
        4) Run app2 with constructed params and return its formatted output.

        Args:
            params: Parameters for the composite app
            formatter_name: Optional formatter to use for the final output (passed to app2)
            **kwargs: Additional arguments passed through to app2.output()
        """
        if self.second_app is None:
            raise ValueError("CompositeApp requires a second_app to run.")

        provided = dict(params or {})

        # 1) Resolve app1 params (fixed overrides take precedence over provided)
        app1_param_names = {q.question_name for q in self.first_app.initial_survey}
        app1_params: dict[str, Any] = {}
        # from user
        for name in app1_param_names:
            if name in provided:
                app1_params[name] = provided[name]
        # apply fixed overrides last
        app1_params.update(self.fixed["app1"])  # fixed values win

        # 2) Build app2 params
        app2_param_names = {q.question_name for q in self.second_app.initial_survey}
        app2_params: dict[str, Any] = {}
        # Start with fixed
        app2_params.update(self.fixed["app2"])  # fixed first

        # Apply bindings declared as source->target
        for source_spec, target_param in self.bindings.items():
            if target_param not in app2_param_names:
                # Ignore bindings for unknown params; user may target attachments or legacy keys
                continue
            value = self._resolve_binding_source(source_spec, app1_params)
            app2_params[target_param] = value

        # Fill any remaining required params from user-provided composite params
        # that correspond to unfixed/unmapped app2 questions
        already_set = set(app2_params.keys())
        for name in app2_param_names:
            if name in already_set:
                continue
            if name in provided:
                app2_params[name] = provided[name]

        # 4) Run app2 with formatter_name and other kwargs
        return self.second_app.output(params=app2_params, formatter_name=formatter_name, **kwargs)

    # --- Serialization ----------------------------------------------------

    def to_dict(self):
        """Serialize this composite app to a dictionary.

        Includes first_app, second_app, bindings, and fixed values.
        """
        data = {
            "application_type": self.application_type,
            "application_name": self.application_name,
            "description": self.description,
            "first_app": self.first_app.to_dict(),
            "second_app": self.second_app.to_dict() if self.second_app is not None else None,
        }
        if self.bindings:
            data["bindings"] = self.bindings
        if any(self.fixed.values()):
            data["fixed"] = self.fixed
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a `CompositeApp` from a dictionary."""
        def _deserialize_app_or_composite(payload: dict):
            if not isinstance(payload, dict):
                raise TypeError("Expected dict for app payload during deserialization")
            if payload.get("application_type") == "composite":
                return cls.from_dict(payload)
            if "application_type" in payload:
                return App.from_dict(payload)
            return App.from_dict(payload)

        first = _deserialize_app_or_composite(data["first_app"]) if "first_app" in data else None
        second = _deserialize_app_or_composite(data["second_app"]) if "second_app" in data and data["second_app"] is not None else None
        bindings = data.get("bindings") or {}
        fixed = data.get("fixed") or {}
        application_name = data.get("application_name")
        description = data.get("description")
        if first is None:
            raise ValueError("CompositeApp.from_dict missing 'first_app'")
        return cls(first_app=first, second_app=second, bindings=bindings, fixed=fixed, application_name=application_name, description=description)

    # --- Internals --------------------------------------------------------

    @staticmethod
    def _filter_questions(questions, *, exclude_names: set[str]):
        """Return questions excluding any whose names appear in `exclude_names`."""
        return [q for q in questions if getattr(q, "question_name", None) not in exclude_names]

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

    def _resolve_binding_source(self, source_spec: Any, app1_params: dict[str, Any]) -> Any:
        """Resolve a binding source spec to a concrete value.

        - dict with {"formatter": name, "path": dotted}: run app1 formatter and extract by path
        - string "param:<name>": take from app1 params
        - string <formatter_name>: run app1 with that formatter
        - any other value: returned as-is
        """
        # Dict form (formatter with optional path)
        if isinstance(source_spec, dict):
            if "formatter" in source_spec:
                formatted = self.first_app.output(app1_params, formatter_name=source_spec.get("formatter"))
                path = source_spec.get("path")
                return self._get_by_dotted_path(formatted, path) if path else formatted
            # Unknown dict spec; return as-is
            return source_spec
        # String forms
        if isinstance(source_spec, str):
            if source_spec.startswith("param:"):
                return app1_params.get(source_spec[len("param:"):])
            # Otherwise treat as an app1 formatter name
            return self.first_app.output(app1_params, formatter_name=source_spec)
        # Literal value
        return source_spec


if __name__ == "__main__":
    print("This module defines CompositeApp. See example at edsl/app/examples/telephone_app.py")
