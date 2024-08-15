import re
from textwrap import dedent


class GeneralErrors(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return self.make_urls_clickable(self.message)

    @staticmethod
    def make_urls_clickable(text):
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        for url in urls:
            clickable_url = f"\033]8;;{url}\007{url}\033]8;;\007"
            text = text.replace(url, clickable_url)
        return text


class MissingAPIKeyError(GeneralErrors):
    def __init__(self, full_message=None, model_name=None, inference_service=None):
        if model_name and inference_service:
            full_message = dedent(
                f"""
            An API Key for model `{model_name}` is missing from the .env file.
            This key is associated with the inference service `{inference_service}`.
            Please see https://docs.expectedparrot.com/en/latest/api_keys.html for more information.
            """
            )

        super().__init__(full_message)
