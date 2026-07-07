"""Model commands for the EDSL CLI."""

from __future__ import annotations

import json

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_REMOTE, EXIT_USAGE, error, output, raw_output_written, save_edsl_object


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep models
    # ---------------------------------------------------------------------------

    @app.group("models", invoke_without_command=True)
    @click.pass_context
    @click.option("--service", default=None, help="Filter by service name.")
    @click.option("--search", default=None, help="Wildcard search pattern.")
    @click.option("--text/--no-text", "works_with_text", default=None, help="Filter by text capability.")
    @click.option("--vision/--no-vision", "works_with_images", default=None, help="Filter by image/vision capability.")
    @click.option("--sort", "sort_by", type=click.Choice(["name", "service", "input-price", "output-price"]), default="service", show_default=True)
    def models(ctx, service, search, works_with_text, works_with_images, sort_by):
        """List and create model lists.

        \b
        Examples:
          ep models
          ep models --service openai
          ep models --search gpt --text --sort input-price
          ep models --vision --sort name
          ep models create --model gpt-4o --output models.ep
        """
        if ctx.invoked_subcommand and ctx.invoked_subcommand != "*":
            return
        from edsl.language_models import Model

        # Determine which services have configured keys
        try:
            key_info = Model.key_info()
            configured_services = set()
            for entry in key_info:
                if hasattr(entry, 'get'):
                    if entry.get('api_key_set'):
                        configured_services.add(entry.get('service_name', ''))
                elif hasattr(entry, 'api_key_set'):
                    if entry.api_key_set:
                        configured_services.add(getattr(entry, 'service_name', ''))
        except Exception:
            configured_services = set()

        warnings = []
        source = "expected_parrot"
        try:
            from edsl.coop import Coop

            available = Coop().fetch_working_models()
            model_list = []
            for item in available:
                model_name = item.get("model")
                service_name = item.get("service")
                if service and service_name != service:
                    continue
                if search and search.lower() not in str(model_name).lower():
                    continue
                if works_with_text is not None and item.get("works_with_text") is not works_with_text:
                    continue
                if works_with_images is not None and item.get("works_with_images") is not works_with_images:
                    continue
                model_list.append({
                    "model_name": model_name,
                    "service_name": service_name,
                    "configured": service_name in configured_services,
                    "works_with_text": item.get("works_with_text"),
                    "works_with_images": item.get("works_with_images"),
                    "usd_per_1M_input_tokens": item.get("usd_per_1M_input_tokens"),
                    "usd_per_1M_output_tokens": item.get("usd_per_1M_output_tokens"),
                })
        except Exception as remote_error:
            if works_with_text is not None or works_with_images is not None:
                error(
                    "MODEL_LIST_ERROR",
                    f"Could not fetch model capabilities from Expected Parrot: {remote_error}",
                    suggestion="Retry without --text/--no-text/--vision/--no-vision, or check your network/API key.",
                    exit_code=EXIT_REMOTE,
                )
            try:
                available = Model.available(
                    search_term=search or None,
                    service_name=service or None,
                    local_only=True,
                )
            except Exception as e:
                error("MODEL_LIST_ERROR", str(e))

            warnings.append(
                f"Could not fetch models from Expected Parrot; returned local models only: {remote_error}"
            )
            source = "local"
            model_list = []
            for m in available:
                model_name = m.model if hasattr(m, 'model') else str(m)
                service_name = getattr(m, '_inference_service_', '') or getattr(m, 'inference_service', '') or ""
                model_list.append({
                    "model_name": model_name,
                    "service_name": service_name,
                    "configured": service_name in configured_services,
                    "works_with_text": None,
                    "works_with_images": None,
                    "usd_per_1M_input_tokens": None,
                    "usd_per_1M_output_tokens": None,
                })

        if sort_by == "name":
            model_list.sort(key=lambda x: (x["model_name"] or "", x["service_name"] or ""))
        elif sort_by == "input-price":
            model_list.sort(key=lambda x: (_price_sort_value(x["usd_per_1M_input_tokens"]), x["service_name"] or "", x["model_name"] or ""))
        elif sort_by == "output-price":
            model_list.sort(key=lambda x: (_price_sort_value(x["usd_per_1M_output_tokens"]), x["service_name"] or "", x["model_name"] or ""))
        else:
            model_list.sort(key=lambda x: (x["service_name"] or "", x["model_name"] or ""))
        output(
            {
                "models": model_list,
                "source": source,
                "filters": {
                    "service": service,
                    "search": search,
                    "text": works_with_text,
                    "vision": works_with_images,
                    "sort": sort_by,
                },
                "count": len(model_list),
            },
            warnings=warnings,
        )

    @models.command("create")
    @click.option("--model", "models", multiple=True, required=True, help="Model name. Repeat for multiple models.")
    @click.option("--service", default=None, help="Service name to use for all models.")
    @click.option("--canned-response", default=None, help="Canned response for offline test models.")
    @click.option("--temperature", default=None, type=float, help="Sampling temperature for all models.")
    @click.option("--max-tokens", default=None, type=int, help="Maximum output tokens for all models.")
    @click.option("--top-p", default=None, type=float, help="Nucleus sampling top-p for all models.")
    @click.option("--parameter", "parameters", multiple=True, help="Extra model parameter as KEY=JSON. Repeat for multiple parameters.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def models_create(models, service, canned_response, temperature, max_tokens, top_p, parameters, output_path):
        """Create a ModelList file.

        \b
        Examples:
          ep models create --model gpt-4o --output models.ep
          ep models create --model gpt-4o --model gpt-4o-mini --output models.ep
          ep models create --model gpt-4o --temperature 0.2 --max-tokens 500 --top-p 0.9 --output models.ep
          ep models create --model gpt-4o --parameter presence_penalty=0.1 --output models.ep
          ep models create --service openai --model gpt-4o --output models.json
          ep models create --service anthropic --model claude-sonnet-4-5 --output models.ep
          ep models create --model test --canned-response ok --output test-models.ep

        \b
        Next:
          ep inspect models.ep
          ep run --survey survey.ep --model_list models.ep
        """
        try:
            from edsl.language_models import Model, ModelList

            model_kwargs = {}
            if canned_response is not None:
                model_kwargs["canned_response"] = canned_response
            if temperature is not None:
                model_kwargs["temperature"] = temperature
            if max_tokens is not None:
                model_kwargs["max_tokens"] = max_tokens
            if top_p is not None:
                model_kwargs["top_p"] = top_p
            model_kwargs.update(_parse_model_parameters(parameters))

            model_list = ModelList(
                [
                    _create_model(Model, model_name, service, model_kwargs)
                    for model_name in models
                ]
            )
            saved = save_edsl_object(model_list, output_path, object_type="ModelList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "ModelList",
                    "model_count": len(model_list),
                    "models": [
                        {
                            "model_name": getattr(model, "model", str(model)),
                            "service_name": getattr(model, "_inference_service_", None),
                            "canned_response": getattr(model, "parameters", {}).get("canned_response"),
                            "parameters": getattr(model, "parameters", {}),
                        }
                        for model in model_list
                    ],
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "MODELS_CREATE_ERROR",
                str(e),
                suggestion="Check model names, service name, and output path.",
                exit_code=EXIT_ERROR,
            )


def _parse_model_parameters(items: tuple[str, ...]) -> dict:
    parameters = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid --parameter {item!r}; expected KEY=JSON.", exit_code=EXIT_USAGE)
        key, raw_value = item.split("=", 1)
        if not key:
            error("USAGE_ERROR", f"Invalid --parameter {item!r}; key is empty.", exit_code=EXIT_USAGE)
        try:
            parameters[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            parameters[key] = raw_value
    return parameters


def _create_model(model_cls, model_name: str, service: str | None, model_kwargs: dict):
    model = (
        model_cls(model_name, service_name=service, **model_kwargs)
        if service
        else model_cls(model_name, **model_kwargs)
    )
    if hasattr(model, "parameters"):
        model.parameters.update(model_kwargs)
    return model


def _price_sort_value(value):
    if value is None:
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")
