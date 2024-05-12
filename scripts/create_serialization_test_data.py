import itertools
import logging
import json
import os
from edsl import __version__ as edsl_version
from edsl.Base import RegisterSubclassesMeta
from edsl.questions import RegisterQuestionsMeta

logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s")


def create_serialization_test_data():
    global edsl_version
    if ".dev" in edsl_version:
        version = edsl_version.split(".dev")[0]
    else:
        version = edsl_version

    data = []
    path = f"tests/serialization/data/{version}.json"

    # A. check if the file already exists
    if os.path.exists(path):
        logging.info(f"`{path}` already exists.")
        return

    # B. Collect all registered classes
    combined_items = itertools.chain(
        RegisterSubclassesMeta.get_registry().items(),
        RegisterQuestionsMeta.get_registered_classes().items(),
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

    # Add anything else you'd like here

    #
    #
    #

    logging.info(f"Found {len(data)} classes")

    # C. Check if all classes have edsl_version in the dict
    for item in data:
        if "edsl_version" not in item["dict"]:
            logging.warning(
                f"Class: {item['class_name']} does not have edsl_version in the dict"
            )

    # D. Write data to the file
    data_to_write = [
        {"class_name": item["class_name"], "dict": item["dict"]} for item in data
    ]
    with open(path, "w") as f:
        json.dump(data_to_write, f)
    logging.info(f"Serialization test data written to `{path}`.")
    logging.info("!!! DO NOT FORGET TO FORCE PUSH IT TO THE REPO !!!")


if __name__ == "__main__":
    create_serialization_test_data()
