import itertools
import logging
import json
import os
import sys
from edsl import __version__ as edsl_version
from edsl.base import RegisterSubclassesMeta
from edsl.coop.utils import ObjectRegistry
from edsl.questions import *
from tests.serialization.cases.RegisterSerializationCasesMeta import (
    RegisterSerializationCasesMeta,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s")

def create_serialization_test_data(start_new_version=False):
    if ".dev" in edsl_version:
        version = edsl_version.split(".dev")[0]
    else:
        version = edsl_version

    current_path = f"tests/serialization/data/{version}.json"

    # A. Handle `start_new_version` logic
    if start_new_version:
        logging.info("Starting a new version based on the last version.")

        # Find the latest version file
        data_dir = "tests/serialization/data"
        version_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
        if not version_files:
            logging.error("No existing version files found to copy from.")
            return

        version_files.sort(reverse=True)
        last_version_file = os.path.join(data_dir, version_files[0])

        logging.info(f"Copying content from `{last_version_file}` to `{current_path}`.")

        # Read the last version's content and write it to the current version file
        with open(last_version_file, "r") as src, open(current_path, "w") as dest:
            dest.write(src.read())

        logging.info(f"New version created at `{current_path}`.")
        return

    # B. Proceed with creating serialization test data
    data = []


    # Collect all registered classes
    subclass_registry = RegisterSubclassesMeta.get_registry()
    questions_registry = RegisterQuestionsMeta.get_registered_classes()
    object_registry = ObjectRegistry.get_registry(
        subclass_registry=subclass_registry, exclude_classes=["QuestionBase", "Study"]
    )

    combined_items = itertools.chain(
        subclass_registry.items(),
        questions_registry.items(),
        object_registry.items(),
    )

    for subclass_name, subclass in combined_items:
        example = subclass.example()
        data.append(
            {
                "class_name": subclass_name,
                "class": subclass,
                "example": example,
                "dict": example.to_dict(),
            }
        )

    logging.info(f"Found {len(data)} registered classes")
    # Check if all registered have edsl_version in the dict
    for item in data:
        if "edsl_version" not in item["dict"]:
            logging.warning(
                f"Class: {item['class_name']} does not have edsl_version in the dict"
            )

    # Create custom / more complex examples
    RegisterSerializationCasesMeta.generate_custom_example_data(container=data)

    # Write data to the file
    data_to_write = [
        {"class_name": item["class_name"], "dict": item["dict"]} for item in data
    ]
    with open(current_path, "w") as f:
        json.dump(data_to_write, f)
    logging.info(f"Serialization test data written to `{current_path}`.")
    logging.info("!!! DO NOT FORGET TO FORCE PUSH IT TO THE REPO !!!")

if __name__ == "__main__":
    start_new_version = "--start_new_version" in sys.argv
    create_serialization_test_data(start_new_version=start_new_version)
