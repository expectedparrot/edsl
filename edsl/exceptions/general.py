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
    def __init__(self, model_name, inference_service):
        full_message = dedent(
            f"""
        An API Key for modle `{model_name}` is missing from the .env file.
        This key is assocaited with the inference service `{inference_service}`.
        Please see https://docs.expectedparrot.com/en/latest/starter_tutorial.html#part-1-using-api-keys-for-llms.
        """
        )
        super().__init__(full_message)
