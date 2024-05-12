import itertools
import json
import os
from edsl import __version__ as edsl_version
from edsl.Base import RegisterSubclassesMeta
from edsl.questions import RegisterQuestionsMeta


def test_serialization():
    global edsl_version
    # get all filenames in tests/serialization/data -- just use full path
    path = "tests/serialization/data"
    files = os.listdir(path)

    # if no file starts with edsl_version, throw an error
    version = edsl_version.split(".dev")[0] if ".dev" in edsl_version else edsl_version
    assert any(
        [f.startswith(version) for f in files]
    ), f"No serialization data found for the current EDSL version ({version}). Please run `make test-data`."

    # get all EDSL classes that you'd like to test
    combined_items = itertools.chain(
        RegisterSubclassesMeta.get_registry().items(),
        RegisterQuestionsMeta.get_registered_classes().items(),
    )
    classes = []
    for subclass_name, subclass in combined_items:
        classes.append(
            {
                "class_name": subclass_name,
                "class": subclass,
            }
        )

    for file in files:
        print("\n\n")
        print(f"Testing compatibility of {version} with {file}")
        with open(os.path.join(path, file), "r") as f:
            data = json.load(f)
        for item in data:
            class_name = item["class_name"]
            if class_name == "QuestionFunctional":
                continue
            print(f"- Testing {class_name}")
            try:
                cls = next(c for c in classes if c["class_name"] == class_name)
            except StopIteration:
                raise ValueError(f"Class {class_name} not found in classes")
            try:
                cls["class"].from_dict
            except:
                raise ValueError(f"Class {class_name} does not have from_dict method")
            try:
                _ = cls["class"].from_dict(item["dict"])
            except Exception as e:
                print("The data is:", item["dict"])
                raise ValueError(f"Error in class {class_name}: {e}")
