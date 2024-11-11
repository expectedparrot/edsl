import re
import textwrap


class ScenarioError(Exception):
    documentation = "https://docs.expectedparrot.com/en/latest/scenarios.html#module-edsl.scenarios.Scenario"

    def __init__(self, message: str):
        self.message = message + "\n" + "Documentation: " + self.documentation
        super().__init__(self.message)

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
