from __future__ import annotations

"""Utilities for exposing a ServiceDefinition through a Gradio UI.

This mirrors ``register_service`` (FastAPI) but targets a local/hosted
Gradio application so anyone can try the service from a browser with
zero front-end code.

Typical usage::

    import gradio as gr
    from edsl.extensions import extensions           # {"create_survey": ServiceDefinition, ...}
    from edsl.extensions.gradio_authoring import register_service_gradio

    demo = gr.Blocks()

    @register_service_gradio(demo, "create_survey", extensions["create_survey"])
    async def create_survey_logic(overall_question, population, num_questions, ep_api_token):
        ...
        return {"survey": survey_obj}

    if __name__ == "__main__":
        demo.launch()
"""

from typing import Any, Callable, Dict, List, Optional, Sequence
import inspect

import gradio as gr

from .authoring import (
    ServiceDefinition,
    ParameterDefinition,
)
from .exceptions import (
    ServiceParameterValidationError,
    ServiceOutputValidationError,
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

_TYPE_TO_GRADIO_COMPONENT: Dict[str, Callable[[str, Any], gr.components.Component]] = {
    # fmt: off
    "str":    lambda label, default: gr.Textbox(label=label, value=default or ""),
    "string": lambda label, default: gr.Textbox(label=label, value=default or ""),
    "int":    lambda label, default: gr.Number(label=label, value=default, precision=0),
    "integer":lambda label, default: gr.Number(label=label, value=default, precision=0),
    "float":  lambda label, default: gr.Number(label=label, value=default, precision=2),
    "number": lambda label, default: gr.Number(label=label, value=default, precision=2),
    "bool":   lambda label, default: gr.Checkbox(label=label, value=default or False),
    "boolean":lambda label, default: gr.Checkbox(label=label, value=default or False),
    # fmt: on
}


def _component_for_parameter(
    name: str, param_def: ParameterDefinition
) -> gr.components.Component:
    """Return a *new* Gradio component appropriate for *one* parameter."""
    # We prefer showing the *parameter name* as the visible label so users
    # immediately know which argument they are filling in.  The description,
    # if provided, is shown via the `info` tooltip where supported (Gradio ≥
    # 3.38).

    label = name
    info_kw = {"info": param_def.description} if param_def.description else {}

    type_key = param_def.type.lower()
    default = (
        None
        if param_def.default_value
        is param_def.__class__.__dataclass_fields__["default_value"].default
        else param_def.default_value
    )

    factory = _TYPE_TO_GRADIO_COMPONENT.get(type_key)
    if factory is not None:
        comp = factory(label, default)
    else:
        # Fallback to JSON for list / dict / custom EDSL objects
        comp = gr.JSON(label=label, value=default)

    # Apply tooltip if available (Gradio silently ignores unknown kwargs)
    if info_kw:
        try:
            comp.info = info_kw["info"]  # type: ignore[attr-defined]
        except Exception:
            pass

    return comp


def _output_component_for_returns(
    service_def: ServiceDefinition,
) -> gr.components.Component | Sequence[gr.components.Component]:
    """Return output component(s) for displaying results.

    For simplicity we currently return a single JSON viewer, even if the
    service has multiple return keys.  This can be refined later.
    """
    if len(service_def.service_returns) == 1:
        # If exactly one value, label as that key
        key = next(iter(service_def.service_returns))
        return gr.JSON(label=f"{key} (output)")
    # Multiple keys – show the whole dict
    return gr.JSON(label="Result")


# ---------------------------------------------------------------------------
# Decorator factory
# ---------------------------------------------------------------------------


def register_service_gradio(
    ui: Optional[gr.Blocks],
    service_name: str,
    service_def: ServiceDefinition,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: expose *fn* via a Gradio UI automatically built from *service_def*.

    Parameters
    ----------
    ui:
        A ``gr.Blocks`` object to mount the widgets into.  If ``None`` a
        standalone ``gr.Interface`` is created and attached to the wrapped
        function via the ``gr_interface`` attribute for later launching.
    service_name:
        Human-readable name and also used as the tab / interface title.
    service_def:
        The :class:`~edsl.extensions.authoring.ServiceDefinition` that
        describes parameters, costs and return structure.
    """

    # -------------------------------------------------------------------
    # Combine parameters defined in the ServiceDefinition *and* any extras
    # present in the decorated function signature (helpful when the YAML is
    # out-of-sync with the implementation, e.g. missing optional params).
    # -------------------------------------------------------------------

    # Whether an EP API token is required (evaluated here for outer-scope access)
    requires_token = service_def.cost.uses_client_ep_key if service_def.cost else False

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        # -------------------------------------------------------------------
        # Re-derive parameter lists now that *fn* is known so we can add
        # optional parameters that were not part of the ServiceDefinition.
        # -------------------------------------------------------------------

        merged_param_names: List[str] = list(service_def.parameters.keys())
        merged_param_defs: List[ParameterDefinition] = [
            service_def.parameters[n] for n in merged_param_names
        ]

        # Detect extras via function signature (skip positional varargs etc.)
        for p_name, p in inspect.signature(fn).parameters.items():
            if p_name in ("self", "cls") or p_name in merged_param_names:
                continue

            # Infer simple type string from annotation
            ann = p.annotation
            if ann is inspect._empty:
                type_str = "str"
            else:
                # Handle typing.Optional or unions like int | None
                from typing import get_origin, get_args

                origin = get_origin(ann)
                if origin is None and isinstance(ann, type):
                    type_str = ann.__name__
                elif origin in (list, dict):
                    type_str = origin.__name__
                elif origin is None and str(ann).startswith("typing."):
                    # Fallback for typing constructs without origin
                    type_str = str(ann).split(".")[-1]
                else:
                    # Try to extract first non-None arg from Union/Optional
                    args = [
                        a for a in get_args(ann) if a is not type(None)
                    ]  # noqa: E721
                    if len(args) == 1 and isinstance(args[0], type):
                        type_str = args[0].__name__
                    else:
                        type_str = "str"

            merged_param_names.append(p_name)
            merged_param_defs.append(
                ParameterDefinition(
                    type=type_str,
                    required=p.default is inspect._empty,
                    description="",
                    default_value=None if p.default is inspect._empty else p.default,
                )
            )

        # Helper to convert merged lists into Gradio input components
        def _build_input_components() -> List[gr.components.Component]:
            comps = [
                _component_for_parameter(n, d)
                for n, d in zip(merged_param_names, merged_param_defs)
            ]
            if requires_token:
                comps.append(gr.Textbox(label="EP API Token", type="password"))
            return comps

        # Prepare output component(s) for stand-alone interface (Blocks case will create later)
        output_components = _output_component_for_returns(service_def)

        async def _gradio_handler(*inputs: Any) -> Any:
            try:
                kwargs: Dict[str, Any] = {
                    name: value for name, value in zip(merged_param_names, inputs)
                }

                # Pop token from the end if present
                ep_api_token: Optional[str] = None
                if requires_token:
                    ep_api_token = inputs[-1]
                    # When token is present the parameter list is offset by one
                    kwargs = {
                        name: value
                        for name, value in zip(merged_param_names, inputs[:-1])
                    }

                # Validate call parameters according to the ServiceDefinition
                service_def.validate_call_parameters(kwargs)

                if ep_api_token is not None:
                    kwargs["ep_api_token"] = ep_api_token

                # Execute the user-supplied function (sync or async)
                if inspect.iscoroutinefunction(fn):
                    result = await fn(**kwargs)
                else:
                    # Run synchronous code directly; could also off-load to executor
                    result = fn(**kwargs)

                # Validate the user result against return schema
                service_def.validate_service_output(result)
                return result

            except (ServiceParameterValidationError, ServiceOutputValidationError) as e:
                # Known validation errors: return as dict for JSON component
                return {"error": str(e)}
            except Exception as e:  # noqa: BLE001, S110
                # Unexpected errors – you may want to log these in real apps
                return {"error": f"Unexpected error: {e}"}

        _gradio_handler.__name__ = f"gradio_{service_name}_handler"

        # -------------------------------------------------------------------
        # UI assembly
        # -------------------------------------------------------------------
        if ui is None:
            interface = gr.Interface(
                fn=_gradio_handler,
                inputs=_build_input_components(),
                outputs=output_components,
                title=service_name,
                description=service_def.description,
            )
            # Expose interface for later launching
            setattr(fn, "gr_interface", interface)
        else:
            with ui:
                with gr.Tab(service_name):
                    gr.Markdown(f"### {service_name}\n{service_def.description}")

                    # Re-create *visual* components within the current context so
                    # they appear in the UI.  Keep the logical parameter order.
                    component_refs: List[gr.components.Component] = (
                        _build_input_components()
                    )

                    # Build output component(s) **inside** the context so they render
                    output_refs = _output_component_for_returns(service_def)

                    # Run button – placed after inputs
                    run_button = gr.Button(value="Run")

                    # Wire callback
                    run_button.click(
                        _gradio_handler,
                        inputs=component_refs,
                        outputs=output_refs,
                    )

        # Decorator must return the *original* function unmodified so that
        # application code can still call it programmatically.
        return fn

    return decorator
