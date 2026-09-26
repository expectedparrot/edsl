"""ScenarioList creation commands for the EDSL CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, load_any_object, output, raw_output_written, save_edsl_object


def register(scenarios_group: click.Group) -> None:
    @scenarios_group.command("create")
    @click.option("--from-csv", "csv_path", default=None, type=click.Path(exists=True), help="Create from a CSV file.")
    @click.option("--from-xlsx", "xlsx_path", default=None, type=click.Path(exists=True), help="Create from an Excel file.")
    @click.option("--from-image", "image_paths", multiple=True, type=click.Path(exists=True), help="Image file to include. Repeat for multiple images.")
    @click.option("--from-json", "json_source", default=None, help="JSON string or path containing a list of scenario dicts.")
    @click.option("--from-list", "list_values", multiple=True, help="Value for one-field scenarios. Repeat for multiple values.")
    @click.option("--field", "list_field", default="value", show_default=True, help="Field name for --from-list.")
    @click.option("--sheet", default=None, help="Excel sheet name.")
    @click.option("--snakify/--no-snakify", default=True, show_default=True, help="Normalize field names when supported.")
    @click.option("--image-key", default="image", show_default=True, help="Scenario key for image content.")
    @click.option("--filename-key", default="filename", show_default=True, help="Scenario key for image filename metadata.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def create_scenarios(
        csv_path: str | None,
        xlsx_path: str | None,
        image_paths: tuple[str, ...],
        json_source: str | None,
        list_values: tuple[str, ...],
        list_field: str,
        sheet: str | None,
        snakify: bool,
        image_key: str,
        filename_key: str,
        output_path: str,
    ):
        """Create a ScenarioList from tabular data or images.

        \b
        Examples:
          ep scenarios create --from-csv topics.csv --output scenarios.ep
          ep scenarios create --from-csv topics.csv --no-snakify --output scenarios.ep
          ep scenarios create --from-xlsx topics.xlsx --sheet Sheet1 --output scenarios.ep
          ep scenarios create --from-image chart.png --from-image map.png --image-key image --filename-key source_file --output image_scenarios.ep
          ep scenarios create --from-json scenarios.json --output scenarios.ep
          ep scenarios create --from-list AI --from-list Climate --field topic --output scenarios.ep
          ep scenarios create --from-csv topics.csv --output -

        \b
        Next:
          ep inspect scenarios.ep
          ep run --survey survey.ep --scenario_list scenarios.ep --model gpt-4o
        """
        source_count = sum(bool(value) for value in (csv_path, xlsx_path, image_paths, json_source, list_values))
        if source_count != 1:
            error(
                "USAGE_ERROR",
                "Provide exactly one source: --from-csv, --from-xlsx, --from-image, --from-json, or --from-list.",
                exit_code=EXIT_USAGE,
            )

        try:
            from edsl import Scenario, ScenarioList

            if csv_path:
                scenarios = ScenarioList.from_source("csv", csv_path, snakify=snakify)
                source = csv_path
            elif xlsx_path:
                kwargs = {"snakify": snakify}
                if sheet:
                    kwargs["sheet_name"] = sheet
                scenarios = ScenarioList.from_source("excel", xlsx_path, **kwargs)
                source = xlsx_path
            elif json_source:
                scenarios = ScenarioList.from_list_of_dicts(_load_list_of_dicts(json_source))
                source = json_source
            elif list_values:
                scenarios = ScenarioList.from_list(list_field, list(list_values))
                source = list(list_values)
            else:
                scenario_items = []
                for image_path in image_paths:
                    image_scenario = Scenario.from_image(image_path)
                    source_key = next(iter(image_scenario.keys()))
                    scenario_items.append(
                        Scenario(
                            {
                                image_key: image_scenario[source_key],
                                filename_key: str(Path(image_path)),
                            }
                        )
                    )
                scenarios = ScenarioList(scenario_items)
                source = list(image_paths)

            saved = save_edsl_object(scenarios, output_path, object_type="ScenarioList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "ScenarioList",
                    "source": source,
                    "scenario_count": len(scenarios),
                    "keys": sorted(_scenario_keys(scenarios)),
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SCENARIOS_CREATE_ERROR",
                str(e),
                suggestion="Check the input data, field names, image files, and output path.",
                exit_code=EXIT_ERROR,
            )

    @scenarios_group.command("transform")
    @click.argument("scenarios_path")
    @click.option("--select", "select_fields", multiple=True, help="Field to keep. Repeat for multiple fields.")
    @click.option("--drop", "drop_fields", multiple=True, help="Field to drop. Repeat for multiple fields.")
    @click.option("--rename", "renames", multiple=True, help="Rename field as OLD=NEW. Repeat for multiple fields.")
    @click.option("--filter", "filter_expression", default=None, help="Filter expression evaluated against scenario fields.")
    @click.option("--sample", "sample_n", default=None, type=int, help="Sample N scenarios.")
    @click.option("--shuffle", is_flag=True, default=False, help="Shuffle scenarios.")
    @click.option("--seed", default=None, help="Seed for sample/shuffle.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SCENARIOS_PATH.")
    def transform_scenarios(
        scenarios_path: str,
        select_fields: tuple[str, ...],
        drop_fields: tuple[str, ...],
        renames: tuple[str, ...],
        filter_expression: str | None,
        sample_n: int | None,
        shuffle: bool,
        seed: str | None,
        output_path: str | None,
    ):
        """Transform an existing ScenarioList.

        \b
        Examples:
          ep scenarios transform scenarios.ep --select topic --select frame --output slim_scenarios.ep
          ep scenarios transform scenarios.ep --filter "frame == 'urgent'" --sample 5 --seed demo
          ep scenarios transform scenarios.ep --rename frame=tone
        """
        try:
            from edsl import ScenarioList

            scenarios = load_any_object(scenarios_path)
            if not isinstance(scenarios, ScenarioList):
                error("UNSUPPORTED_OBJECT", f"Expected a ScenarioList object, got {type(scenarios).__name__}.", exit_code=EXIT_USAGE)

            if filter_expression:
                scenarios = scenarios.filter(filter_expression)
            if select_fields:
                scenarios = scenarios.select(*select_fields)
            if drop_fields:
                scenarios = scenarios.drop(*drop_fields)
            renames_dict = _parse_renames(renames)
            if renames_dict:
                scenarios = scenarios.rename(renames_dict)
            if shuffle:
                scenarios = scenarios.shuffle(seed=seed)
            if sample_n is not None:
                scenarios = scenarios.sample(sample_n, seed=seed)

            saved = save_edsl_object(scenarios, output_path or scenarios_path, object_type="ScenarioList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "ScenarioList",
                    "scenario_count": len(scenarios),
                    "keys": sorted(_scenario_keys(scenarios)),
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SCENARIOS_TRANSFORM_ERROR",
                str(e),
                suggestion="Check the ScenarioList path, field names, filter expression, and output path.",
                exit_code=EXIT_ERROR,
            )


def _scenario_keys(scenarios) -> set[str]:
    keys = set()
    for scenario in scenarios:
        keys.update(dict(scenario).keys())
    return keys


def _load_list_of_dicts(value: str) -> list[dict]:
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.exists() and path.is_file() else value
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        error("INVALID_JSON", f"Failed to parse JSON: {e}", exit_code=EXIT_USAGE)
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        error("USAGE_ERROR", "Expected a JSON list of objects.", exit_code=EXIT_USAGE)
    return data


def _parse_renames(items: tuple[str, ...]) -> dict[str, str]:
    renames = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid rename {item!r}; expected OLD=NEW.", exit_code=EXIT_USAGE)
        old_name, new_name = item.split("=", 1)
        renames[old_name] = new_name
    return renames
