import requests
import json
import textwrap

from rich import print as print
from edsl.config import CONFIG


SERVER_URL = CONFIG.get("EDSL_PASTEBIN_URL")

from edsl.utilities.SystemInfo import SystemInfo


def post(
    object,
    *,
    username: str = None,
    description: str = None,
    system_info: str = None,
    public=True,
    ask=True,
):
    """Uploads an object to the server with additional metadata."""

    info = SystemInfo("edsl")
    if ask:
        print(
            f"OK to send the folloing info to community server (info will be public)?"
        )
        print(info)
        inp = input("Enter y/n: ")
        if inp != "y":
            print("Canceled posting")
            return
    object_type = object.__class__.__name__
    object_data = json.dumps(object.to_dict()).encode("utf-8")
    # Prepare the metadata for the POST request
    username = username or info.username
    system_info = system_info or (info.system_info + ";" + info.release_info)
    edsl_version = info.package_version
    data = {
        "username": username,
        "system_info": system_info,
        "edsl_version": edsl_version,
        "object_type": object_type,
        "description": description,
        "public": str(public).lower(),  # Convert boolean to lowercase string
    }

    # Send the POST request with the object data and metadata
    response = requests.post(
        f"{SERVER_URL}/upload",
        files={"file": ("file", object_data, "application/json")},
        data=data,
    )

    # Process the response
    if response.status_code == 200:
        key = response.json()["key"]
        print(
            textwrap.dedent(
                f"""\
        EDSL object of type {object_type} uploaded successfully, with key `{key}`
        You can share this key with others to allow them to retrieve the object.
        To retrieve the object: 

        >>> from edsl import get
        >>> object = get('{key}')
        
        To view all community objects, go to {SERVER_URL}.
        To view this object, go to {SERVER_URL}/view/{key}.
        WARNING: This object is stored on a public server and can be accessed by anyone with the key.
        """
            )
        )
        return response.json()["key"]
    else:
        print(f"Error during file upload: {response.text}")
        return None


def get(key):
    """Retrieves an object and its type from the server using a key."""
    response = requests.get(f"{SERVER_URL}/retrieve/{key}")

    if response.status_code == 200:
        response_data = response.json()
        object_data = response_data.get(
            "object_data"
        )  # Assuming the object data is under "object_data"
        object_type = response_data.get("object_type")
        if object_type and object_data:
            object_dict = json.loads(object_data)

            from edsl import Agent
            from edsl.results import Results
            from edsl.jobs import Jobs
            from edsl.surveys import Survey
            from edsl.questions import Question

            mapping = {
                "Agent": Agent,
                "Question": Question,
                "Survey": Survey,
                "Results": Results,
                "Jobs": Jobs,
            }

            if object_type in mapping:
                object_type = mapping[object_type]
                object = object_type.from_dict(object_dict)
                return object
            else:
                print(f"Object type {object_type} is not supported.")
    else:
        print(f"Error during file retrieval: {response.text}")
        return None


def community():
    response = requests.get(f"{SERVER_URL}/community")
    if response.status_code == 200:
        return response.json()
    else:
        return f"Error: {response.status_code}"


if __name__ == "__main__":
    from edsl import Survey
    from edsl.results import Results

    msg = post(Survey.example())

    print(msg)
    new_obj = get(msg)
    print(new_obj)

    msg = post(Results.example())
    new_obj = get(msg)
    print(new_obj)
    new_obj.select("answer.*").print()
