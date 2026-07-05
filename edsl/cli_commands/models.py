"""Model commands for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_REMOTE, error, output, save_edsl_object


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # edsl models
    # ---------------------------------------------------------------------------

    @app.group("models", invoke_without_command=True)
    @click.pass_context
    @click.option("--service", default=None, help="Filter by service name.")
    @click.option("--search", default=None, help="Wildcard search pattern.")
    @click.option("--text/--no-text", "works_with_text", default=None, help="Filter by text capability.")
    @click.option("--vision/--no-vision", "works_with_images", default=None, help="Filter by image/vision capability.")
    @click.option("--sort", "sort_by", type=click.Choice(["name", "service", "input-price", "output-price"]), default="service", show_default=True)
    def models(ctx, service, search, works_with_text, works_with_images, sort_by):
        """List and create model lists."""
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
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def models_create(models, service, output_path):
        """Create a ModelList file."""
        try:
            from edsl.language_models import Model, ModelList

            model_list = ModelList(
                [
                    Model(model_name, service_name=service) if service else Model(model_name)
                    for model_name in models
                ]
            )
            saved = save_edsl_object(model_list, output_path, object_type="ModelList")
            output(
                {
                    "object_type": "ModelList",
                    "model_count": len(model_list),
                    "models": [
                        {
                            "model_name": getattr(model, "model", str(model)),
                            "service_name": getattr(model, "_inference_service_", None),
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


def _price_sort_value(value):
    if value is None:
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")
