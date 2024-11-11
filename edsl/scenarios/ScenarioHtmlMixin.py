import requests
from typing import Optional
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class ScenarioHtmlMixin:
    @classmethod
    def from_html(cls, url: str, field_name: Optional[str] = None) -> "Scenario":
        """Create a scenario from HTML content.

        :param html: The HTML content.
        :param field_name: The name of the field containing the HTML content.


        """
        html = cls.fetch_html(url)
        text = cls.extract_text(html)
        if not field_name:
            field_name = "text"
        return cls({"url": url, "html": html, field_name: text})

    def fetch_html(url):
        # Define the user-agent to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Create a session to manage cookies and retries
        session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))

        try:
            # Make the request
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    def extract_text(html):
        # Extract text from HTML using BeautifulSoup
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        return text


if __name__ == "__main__":
    # Usage example
    url = "https://example.com"
    html = ScenarioHtmlMixin.fetch_html(url)
    if html:
        print("Successfully fetched the HTML content.")
    else:
        print("Failed to fetch the HTML content.")

    print(html)
