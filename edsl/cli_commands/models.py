"""Model listing command for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import EXIT_REMOTE, error, output


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # edsl models
    # ---------------------------------------------------------------------------

    @app.command()
    @click.option("--service", default=None, help="Filter by service name.")
    @click.option("--search", default=None, help="Wildcard search pattern.")
    @click.option("--text/--no-text", "works_with_text", default=None, help="Filter by text capability.")
    @click.option("--vision/--no-vision", "works_with_images", default=None, help="Filter by image/vision capability.")
    @click.option("--sort", "sort_by", type=click.Choice(["name", "service", "input-price", "output-price"]), default="service", show_default=True)
    def models(service, search, works_with_text, works_with_images, sort_by):
        """List available models."""
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


def _price_sort_value(value):
    if value is None:
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")
