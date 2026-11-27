"""Local edits to individual items in the three lists used to build a job."""

import click

from edsl.cli_shared import (
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_any_object,
    load_json_object,
    output,
    raw_output_written,
    save_edsl_object,
)


def register(group, object_type):
    @group.command("edit-item")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option(
        "--index",
        type=click.IntRange(min=0),
        help="Zero-based item position. Defaults to the end for --insert.",
    )
    @click.option(
        "--patch",
        help="JSON object or file. Change only the supplied fields, merging nested objects.",
    )
    @click.option("--insert", help="Insert an item from a JSON object or file.")
    @click.option("--remove", is_flag=True, help="Remove the item at --index.")
    @click.option(
        "--output",
        "-o",
        "destination",
        type=click.Path(dir_okay=False),
        help="Write a separate file. Defaults to the input.",
    )
    def edit_item(path, index, patch, insert, remove, destination):
        """Insert, update, or remove one item in a local package."""
        if sum((patch is not None, insert is not None, remove)) != 1:
            error(
                "USAGE_ERROR",
                "Choose one of --patch, --insert, or --remove.",
                exit_code=EXIT_USAGE,
            )
        if index is None and insert is None:
            error(
                "USAGE_ERROR",
                "--index is required when updating or removing an item.",
                exit_code=EXIT_USAGE,
            )
        try:
            items = load_any_object(path, preview=True)
            if type(items).__name__ != object_type:
                raise ValueError(f"Expected {object_type}, got {type(items).__name__}.")
            if index is None:
                index = len(items)
            last_index = len(items) if insert is not None else len(items) - 1
            if index > last_index:
                raise ValueError(
                    f"Index {index} is out of bounds for {len(items)} items."
                )
            if remove:
                del items[index]
            else:
                fields = load_json_object(insert if insert is not None else patch)
                original = (
                    {}
                    if insert is not None
                    else items[index].to_dict(add_edsl_version=False)
                )
                merged = _merge_fields(original, fields)
                item = _item_from_dict(object_type, merged.copy())
                # Some native deserializers silently ignore unrecognized fields.
                # Verify requested values before committing the package.
                recorded = item.to_dict(add_edsl_version=False)
                if _merge_fields(recorded, fields) != recorded:
                    raise ValueError(
                        f"The supplied fields cannot be stored on this {object_type} item."
                    )
                if insert is not None:
                    items.insert(index, item)
                else:
                    items[index] = item
            saved = save_edsl_object(items, destination or path, sync_coop=False)
            if not raw_output_written(saved):
                output(
                    {
                        "object_type": object_type,
                        "index": index,
                        "item_count": len(items),
                        "saved": saved,
                    }
                )
        except Exception as exc:
            error("VALIDATION_ERROR", str(exc), exit_code=EXIT_VALIDATION)


def _merge_fields(original, patch):
    result = original.copy()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            value = _merge_fields(result[key], value)
        result[key] = value
    return result


def _item_from_dict(object_type, data):
    if object_type == "AgentList":
        from edsl import Agent

        return Agent.from_dict(data)
    if object_type == "ScenarioList":
        from edsl import Scenario

        return Scenario.from_dict(data)
    from edsl.language_models.model_list_serializer import model_from_dict

    return model_from_dict(data)
