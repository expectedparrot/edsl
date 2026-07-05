"""ScenarioList creation commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, output, save_edsl_object


def register(scenarios_group: click.Group) -> None:
    @scenarios_group.command("create")
    @click.option("--from-csv", "csv_path", default=None, type=click.Path(exists=True), help="Create from a CSV file.")
    @click.option("--from-xlsx", "xlsx_path", default=None, type=click.Path(exists=True), help="Create from an Excel file.")
    @click.option("--from-image", "image_paths", multiple=True, type=click.Path(exists=True), help="Image file to include. Repeat for multiple images.")
    @click.option("--sheet", default=None, help="Excel sheet name.")
    @click.option("--snakify/--no-snakify", default=True, show_default=True, help="Normalize field names when supported.")
    @click.option("--image-key", default="image", show_default=True, help="Scenario key for image content.")
    @click.option("--filename-key", default="filename", show_default=True, help="Scenario key for image filename metadata.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def create_scenarios(
        csv_path: str | None,
        xlsx_path: str | None,
        image_paths: tuple[str, ...],
        sheet: str | None,
        snakify: bool,
        image_key: str,
        filename_key: str,
        output_path: str,
    ):
        """Create a ScenarioList from tabular data or images."""
        source_count = sum(bool(value) for value in (csv_path, xlsx_path, image_paths))
        if source_count != 1:
            error(
                "USAGE_ERROR",
                "Provide exactly one source: --from-csv, --from-xlsx, or --from-image.",
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


def _scenario_keys(scenarios) -> set[str]:
    keys = set()
    for scenario in scenarios:
        keys.update(dict(scenario).keys())
    return keys
