"""Model commands for the EDSL CLI."""

from __future__ import annotations

import json
import os
import re
import time
from hashlib import sha256
from pathlib import Path

import click
from platformdirs import user_cache_path

from edsl.cli_shared import EXIT_ERROR, EXIT_REMOTE, EXIT_USAGE, error, output, raw_output_written, save_edsl_object


MODEL_CATALOG_CACHE_TTL_SECONDS = 3600

MODEL_PROFILES = {
    "report-review": {
        "description": "Vision-capable frontier reviewers from distinct providers.",
        "providers": [
            {"service": "anthropic", "include": ("claude-", "sonnet", "opus"), "exclude": ()},
            {"service": "openai", "include": ("gpt-",), "exclude": ("mini", "nano", "codex", "chat", "sol", "terra", "luna")},
            {"service": "google", "include": ("gemini", "pro"), "exclude": ("image", "robotics", "customtools")},
            {"service": "deep_infra", "include": ("qwen", "vl"), "exclude": ()},
        ],
    },
}


def _model_version_key(name: str) -> tuple[bool, tuple[int, ...], str]:
    """Sort versioned model names newest-first without depending on one vendor."""
    has_date_snapshot = bool(re.search(r"(?:19|20)\d{6}|(?:19|20)\d{2}-\d{2}-\d{2}", name))
    return not has_date_snapshot, tuple(int(value) for value in re.findall(r"\d+", name)), name


def _select_model_profile(
    available: list[dict], profile: str, count: int,
) -> list[dict]:
    """Select one capable model per ranked provider for a named workflow."""
    definition = MODEL_PROFILES[profile]
    selected: list[dict] = []
    for provider in definition["providers"]:
        candidates = []
        for item in available:
            name = str(item.get("model") or "")
            lower = name.lower()
            if item.get("service") != provider["service"]:
                continue
            if item.get("works_with_images") is not True:
                continue
            if not all(token in lower for token in provider["include"][:1]):
                continue
            if len(provider["include"]) > 1 and not any(
                token in lower for token in provider["include"][1:]
            ):
                continue
            if any(token in lower for token in provider["exclude"]):
                continue
            candidates.append(item)
        if candidates:
            candidates.sort(
                key=lambda item: _model_version_key(str(item.get("model") or "")),
                reverse=True,
            )
            selected.append(candidates[0])
        if len(selected) == count:
            break
    return selected


def _model_catalog_cache_path(api_url: str) -> Path:
    cache_root = Path(
        os.environ.get("EDSL_MODEL_CATALOG_CACHE_DIR")
        or user_cache_path("edsl") / "model-catalog"
    )
    endpoint = sha256(api_url.encode("utf-8")).hexdigest()[:16]
    return cache_root / f"working-models-{endpoint}.json"


def _read_model_catalog_cache(path: Path) -> tuple[list[dict] | None, float | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        models = payload["models"]
        fetched_at = float(payload["fetched_at"])
        if not isinstance(models, list):
            return None, None
        return models, max(0.0, time.time() - fetched_at)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None, None


def _write_model_catalog_cache(path: Path, models: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"fetched_at": time.time(), "models": models}),
        encoding="utf-8",
    )
    temporary.replace(path)


def _working_models(coop, *, refresh: bool, ttl_seconds: int) -> tuple[list[dict], dict]:
    api_url = getattr(coop, "api_url", None)
    if api_url is None:
        return coop.fetch_working_models(), {
            "hit": False,
            "age_seconds": 0.0,
            "ttl_seconds": ttl_seconds,
        }

    path = _model_catalog_cache_path(str(api_url))
    cached, age = _read_model_catalog_cache(path)
    if not refresh and cached is not None and age is not None and age <= ttl_seconds:
        return cached, {
            "hit": True,
            "age_seconds": round(age, 3),
            "ttl_seconds": ttl_seconds,
        }
    models = coop.fetch_working_models()
    try:
        _write_model_catalog_cache(path, models)
    except OSError:
        pass
    return models, {
        "hit": False,
        "age_seconds": 0.0,
        "ttl_seconds": ttl_seconds,
    }


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep models
    # ---------------------------------------------------------------------------

    @app.group("models", invoke_without_command=True)
    @click.pass_context
    @click.option("--service", default=None, help="Filter by service name.")
    @click.option("--search", default=None, help="Case-insensitive model-name substring.")
    @click.option("--text/--no-text", "works_with_text", default=None, help="Filter by text capability.")
    @click.option("--vision/--no-vision", "works_with_images", default=None, help="Filter by image/vision capability.")
    @click.option("--sort", "sort_by", type=click.Choice(["name", "service", "input-price", "output-price"]), default="service", show_default=True)
    @click.option("--limit", type=click.IntRange(1, 100), default=None, help="Return at most this many models.")
    @click.option("--refresh", is_flag=True, help="Bypass the one-hour model-catalog cache.")
    def models(ctx, service, search, works_with_text, works_with_images, sort_by, limit, refresh):
        """List and create model lists.

        \b
        Examples:
          ep models
          ep models --service openai
          ep models --search gpt --text --sort input-price --limit 10
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
        cache = None
        try:
            from edsl.coop import Coop

            available, cache = _working_models(
                Coop(), refresh=refresh,
                ttl_seconds=MODEL_CATALOG_CACHE_TTL_SECONDS,
            )
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
        total_count = len(model_list)
        if limit is not None:
            model_list = model_list[:limit]
        output(
            {
                "models": model_list,
                "source": source,
                "cache": cache,
                "filters": {
                    "service": service,
                    "search": search,
                    "text": works_with_text,
                    "vision": works_with_images,
                    "sort": sort_by,
                    "limit": limit,
                },
                "count": len(model_list),
                "total_count": total_count,
            },
            warnings=warnings,
        )

    @models.command("create")
    @click.option("--model", "models", multiple=True, help="Model name. Repeat for multiple models.")
    @click.option(
        "--model-spec",
        "model_specs",
        multiple=True,
        help='Per-model JSON object with "model", optional "service", and optional "parameters". Repeat for multiple models.',
    )
    @click.option("--service", default=None, help="Service name to use for all models.")
    @click.option(
        "--profile", type=click.Choice(sorted(MODEL_PROFILES)), default=None,
        help="Select a bounded workflow-specific model panel from the cached working-model catalog.",
    )
    @click.option("--count", type=click.IntRange(1, 4), default=3, show_default=True, help="Number of models selected by --profile.")
    @click.option("--refresh", is_flag=True, help="Bypass the one-hour model-catalog cache used by --profile.")
    @click.option("--base-url", default=None, help="Base URL for an OpenAI-compatible endpoint.")
    @click.option("--api-key-env", default=None, help="Environment variable containing the endpoint API key.")
    @click.option("--canned-response", default=None, help="Canned response for offline test models.")
    @click.option("--temperature", default=None, type=float, help="Sampling temperature for all models.")
    @click.option("--max-tokens", default=None, type=int, help="Maximum output tokens for all models.")
    @click.option("--top-p", default=None, type=float, help="Nucleus sampling top-p for all models.")
    @click.option("--parameter", "parameters", multiple=True, help="Extra model parameter as KEY=JSON. Repeat for multiple parameters.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def models_create(models, model_specs, service, profile, count, refresh, base_url, api_key_env, canned_response, temperature, max_tokens, top_p, parameters, output_path):
        """Create a ModelList file.

        \b
        Examples:
          ep models create --model gpt-4o --output models.ep
          ep models create --model gpt-4o --model gpt-4o-mini --output models.ep
          ep models create --model gpt-4o --temperature 0.2 --max-tokens 500 --top-p 0.9 --output models.ep
          ep models create --model gpt-4o --parameter presence_penalty=0.1 --output models.ep
          ep models create --service openai --model gpt-4o --output models.json
          ep models create --service anthropic --model claude-sonnet-4-5 --output models.ep
          ep models create --profile report-review --count 3 --output review-models.ep
          ep models create --model-spec '{"model":"claude-opus-4-8","service":"anthropic"}' --model-spec '{"model":"gpt-5.4","service":"openai","parameters":{"reasoning_effort":"high"}}' --output models.ep
          ep models create --model test --canned-response ok --output test-models.ep

        \b
        Next:
          ep inspect models.ep
          ep run --survey survey.ep --model_list models.ep
        """
        try:
            from edsl.language_models import Model, ModelList

            model_kwargs = {}
            if base_url is not None:
                model_kwargs["base_url"] = base_url
            if api_key_env is not None:
                model_kwargs["api_key_env"] = api_key_env
            if canned_response is not None:
                model_kwargs["canned_response"] = canned_response
            if temperature is not None:
                model_kwargs["temperature"] = temperature
            if max_tokens is not None:
                model_kwargs["max_tokens"] = max_tokens
            if top_p is not None:
                model_kwargs["top_p"] = top_p
            model_kwargs.update(_parse_model_parameters(parameters))

            if profile and (models or model_specs or service or canned_response):
                error(
                    "USAGE_ERROR",
                    "--profile cannot be combined with --model, --model-spec, --service, or --canned-response.",
                    suggestion="Use the profile by itself; shared generation parameters such as --max-tokens remain supported.",
                    exit_code=EXIT_USAGE,
                )

            profile_selection = None
            catalog_cache = None
            if profile:
                from edsl.coop import Coop

                available, catalog_cache = _working_models(
                    Coop(), refresh=refresh,
                    ttl_seconds=MODEL_CATALOG_CACHE_TTL_SECONDS,
                )
                selected = _select_model_profile(available, profile, count)
                if len(selected) != count:
                    error(
                        "MODEL_PROFILE_UNAVAILABLE",
                        f"Profile {profile!r} found {len(selected)} of {count} required distinct-provider models.",
                        suggestion="Run `ep models --vision --refresh` to inspect the current catalog, or request a smaller --count.",
                        exit_code=EXIT_REMOTE,
                    )
                profile_selection = [
                    {"model": item["model"], "service": item["service"]}
                    for item in selected
                ]
                models = tuple(item["model"] for item in selected)

            if not models and not model_specs:
                error(
                    "USAGE_ERROR",
                    "Provide at least one --model or --model-spec.",
                    suggestion="Use --model NAME for shared settings or repeat --model-spec with a JSON object for per-model settings.",
                    exit_code=EXIT_USAGE,
                )

            if profile_selection is not None:
                created_models = [
                    _create_model(Model, item["model"], item["service"], model_kwargs)
                    for item in profile_selection
                ]
            else:
                created_models = [
                    _create_model(Model, model_name, service, model_kwargs)
                    for model_name in models
                ]
            for raw_spec in model_specs:
                spec = _parse_model_spec(raw_spec)
                spec_kwargs = dict(model_kwargs)
                spec_kwargs.update(spec["parameters"])
                spec_kwargs.update(spec["connection"])
                created_models.append(
                    _create_model(
                        Model,
                        spec["model"],
                        spec["service"] or service,
                        spec_kwargs,
                    )
                )

            model_list = ModelList(created_models)
            saved = save_edsl_object(model_list, output_path, object_type="ModelList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "ModelList",
                    "model_count": len(model_list),
                    "profile": profile,
                    "catalog_cache": catalog_cache,
                    "models": [
                        {
                            "model_name": getattr(model, "model", str(model)),
                            "service_name": getattr(model, "_inference_service_", None),
                            "canned_response": getattr(model, "parameters", {}).get("canned_response"),
                            "parameters": getattr(model, "parameters", {}),
                            "connection": getattr(model, "to_dict")().get("connection", {}),
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


def _parse_model_spec(raw_spec: str) -> dict:
    try:
        spec = json.loads(raw_spec)
    except json.JSONDecodeError as exc:
        error(
            "USAGE_ERROR",
            f"Invalid --model-spec JSON: {exc.msg}.",
            suggestion='Use an object such as \'{"model":"gpt-5.4","service":"openai","parameters":{"reasoning_effort":"high"}}\'.',
            exit_code=EXIT_USAGE,
        )

    if not isinstance(spec, dict):
        error("USAGE_ERROR", "--model-spec must be a JSON object.", exit_code=EXIT_USAGE)

    allowed_keys = {"model", "service", "service_name", "parameters", "connection"}
    unknown_keys = sorted(set(spec) - allowed_keys)
    if unknown_keys:
        error(
            "USAGE_ERROR",
            f"Unknown --model-spec field(s): {', '.join(unknown_keys)}.",
            suggestion="Allowed fields are model, service, service_name, parameters, and connection.",
            exit_code=EXIT_USAGE,
        )

    model_name = spec.get("model")
    if not isinstance(model_name, str) or not model_name.strip():
        error("USAGE_ERROR", '--model-spec requires a non-empty string "model".', exit_code=EXIT_USAGE)

    if "service" in spec and "service_name" in spec:
        error(
            "USAGE_ERROR",
            '--model-spec cannot contain both "service" and "service_name".',
            exit_code=EXIT_USAGE,
        )
    service = spec.get("service", spec.get("service_name"))
    if service is not None and (not isinstance(service, str) or not service.strip()):
        error("USAGE_ERROR", '--model-spec "service" must be a non-empty string.', exit_code=EXIT_USAGE)

    parameters = spec.get("parameters", {})
    if not isinstance(parameters, dict):
        error("USAGE_ERROR", '--model-spec "parameters" must be a JSON object.', exit_code=EXIT_USAGE)

    connection = spec.get("connection", {})
    if not isinstance(connection, dict):
        error("USAGE_ERROR", '--model-spec "connection" must be a JSON object.', exit_code=EXIT_USAGE)
    unknown_connection = sorted(set(connection) - {"base_url", "api_key_env"})
    if unknown_connection:
        error("USAGE_ERROR", f"Unknown connection field(s): {', '.join(unknown_connection)}.", exit_code=EXIT_USAGE)

    return {"model": model_name, "service": service, "parameters": parameters, "connection": connection}


def _create_model(model_cls, model_name: str, service: str | None, model_kwargs: dict):
    model = (
        model_cls(model_name, service_name=service, **model_kwargs)
        if service
        else model_cls(model_name, **model_kwargs)
    )
    if hasattr(model, "parameters"):
        model.parameters.update(
            {k: v for k, v in model_kwargs.items() if k not in {"base_url", "api_key_env"}}
        )
    return model


def _price_sort_value(value):
    if value is None:
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")
