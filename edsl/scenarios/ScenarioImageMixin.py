import base64
import os
import requests
import tempfile
import mimetypes
from urllib.parse import urlparse


class ScenarioImageMixin:
    def add_image(self, image_path: str):
        """Add an image to a scenario.

        >>> from edsl.scenarios.Scenario import Scenario
        >>> s = Scenario({"food": "wood chips"})
        >>> s.add_image(Scenario.example_image())
        Scenario({'food': 'wood chips', 'logo': ...})
        """
        new_scenario = self.from_image(image_path)
        return self + new_scenario

    @staticmethod
    def example_image():
        """Return an example image path."""
        import os

        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, "../../static/logo.png")

    @classmethod
    def from_image(cls, image_path: str) -> "Scenario":
        """Creates a scenario with a base64 encoding of an image.

        >>> from edsl.scenarios.Scenario import Scenario
        >>> s = Scenario.from_image(Scenario.example_image())
        >>> s
        Scenario({'logo': ...})
        """

        if image_path.startswith("http://") or image_path.startswith("https://"):
            return cls._from_url_image(image_path)
        else:
            return cls._from_filepath_image(image_path)

    @classmethod
    def _from_url_image(cls, image_url: str) -> "Scenario":
        """Handles downloading and encoding an image from a URL."""
        response = requests.get(image_url)
        if response.status_code == 200:
            # Try to extract the file extension from the URL
            parsed_url = urlparse(image_url)
            file_name = parsed_url.path.split("/")[-1]
            file_extension = file_name.split(".")[-1] if "." in file_name else None

            # If the file extension is not found in the URL, use the content type
            if not file_extension:
                content_type = response.headers.get("Content-Type")
                file_extension = mimetypes.guess_extension(content_type)

            # If still no file extension, use a generic binary extension
            if not file_extension:
                file_extension = ".bin"

            # Create a temporary file with the appropriate extension
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as temp_file:
                # Write the image content to the temporary file
                temp_file.write(response.content)
                temp_file_name = temp_file.name
        else:
            raise ValueError("Failed to download the image.")

        scenario = cls._from_filepath_image(temp_file_name)
        os.remove(temp_file_name)
        return scenario

    @classmethod
    def _from_filepath_image(cls, image_path: str) -> "Scenario":
        """Handles encoding an image from a local file path."""
        with open(image_path, "rb") as image_file:
            s = cls(
                {
                    "file_path": image_path,
                    "encoded_image": base64.b64encode(image_file.read()).decode(
                        "utf-8"
                    ),
                }
            )
            s._has_image = True
            return s

    def __repr__(self):
        return f"Scenario({self.data})"


if __name__ == "__main__":
    import doctest
    from edsl.scenarios.Scenario import Scenario

    doctest.testmod(extraglobs={"Scenario": Scenario}, optionflags=doctest.ELLIPSIS)
