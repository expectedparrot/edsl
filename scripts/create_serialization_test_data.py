import itertools
import logging
import json
import os
from edsl import __version__ as edsl_version
from edsl.Base import RegisterSubclassesMeta
from edsl.coop.utils import ObjectRegistry, Study
from edsl.questions import *
from edsl.utilities.utilities import to_camel_case
from tests.serialization.cases.RegisterSerializationCasesMeta import (
    RegisterSerializationCasesMeta,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s")


def create_serialization_test_data():
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

    # B. Study data needs to go up here; otherwise, there is a namespace error
    with Study(name="example_study", verbose=False) as study:
        from edsl import QuestionFreeText

        q = QuestionFreeText.example()

    data.append(
        {
            "class_name": "Study",
            "class": Study,
            "example": study,
            "dict": study.to_dict(),
        }
    )

    # C. Collect all registered classes we want to generate an example for
    subclass_registry = RegisterSubclassesMeta.get_registry()
    # Create an object registry for the classes that are not in the subclass registry
    object_registry = {}
    for object in ObjectRegistry.objects:
        camel_case_name = to_camel_case(object["object_type"])
        classes_to_exclude = ["Question", "Study"]
        # if we don't already have this subclass, register it
        if (
            camel_case_name not in subclass_registry
            and camel_case_name not in classes_to_exclude
        ):
            object_registry[camel_case_name] = object["edsl_class"]

    combined_items = itertools.chain(
        subclass_registry.items(),
        RegisterQuestionsMeta.get_registered_classes().items(),
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
    # check if all registered have edsl_version in the dict
    for item in data:
        if "edsl_version" not in item["dict"]:
            logging.warning(
                f"Class: {item['class_name']} does not have edsl_version in the dict"
            )

    # D. Create custom / more complex examples
    RegisterSerializationCasesMeta.generate_custom_example_data(container=data)

    # E. Write data to the file
    data_to_write = [
        {"class_name": item["class_name"], "dict": item["dict"]} for item in data
    ]
    with open(path, "w") as f:
        json.dump(data_to_write, f)
    logging.info(f"Serialization test data written to `{path}`.")
    logging.info("!!! DO NOT FORGET TO FORCE PUSH IT TO THE REPO !!!")


if __name__ == "__main__":
    create_serialization_test_data()
