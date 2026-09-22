from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from edsl.scenarios import FileStore, ScenarioList
from edsl.scenarios.exceptions import ScenarioError
from edsl.scenarios.scenario_source import ScenarioSource
from edsl.scenarios.sources.wikipedia_source import WikipediaSource


def _response(body=b"<table><tr><th>name</th></tr><tr><td>A</td></tr></table>"):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.encoding = "utf-8"
    response.iter_content.return_value = [body]
    return response


@patch("requests.get")
def test_scenario_list_url_timeouts(mock_get):
    mock_get.return_value = MagicMock(text="content")

    ScenarioList.from_urls(["https://example.com"])
    ScenarioSource._from_urls(["https://example.org"], timeout=7)

    assert mock_get.call_args_list[0].kwargs["timeout"] == 30.0
    assert mock_get.call_args_list[1].kwargs["timeout"] == 7.0


@patch("requests.get")
def test_filestore_url_timeout_and_validation(mock_get, tmp_path):
    response = MagicMock()
    response.iter_content.return_value = [b"hello"]
    mock_get.return_value = response
    path = tmp_path / "download.txt"

    result = FileStore.from_url(
        "https://example.com/download.txt", download_path=str(path), timeout=5
    )

    mock_get.assert_called_once_with(
        "https://example.com/download.txt", stream=True, timeout=5.0
    )
    assert result.text == "hello"
    response.close.assert_called_once()

    mock_get.reset_mock()
    with pytest.raises(ValueError, match="positive finite"):
        FileStore.from_url("https://example.com/file", timeout=0)
    mock_get.assert_not_called()


@patch("pandas.read_html")
@patch("requests.get")
def test_wikipedia_fetch_is_bounded_and_parses_fetched_html(mock_get, read_html):
    mock_get.return_value = _response()
    read_html.return_value = [pd.DataFrame([{"name": "A"}])]

    result = WikipediaSource(
        "https://en.wikipedia.org/wiki/Test", timeout=6
    ).to_scenario_list()

    mock_get.assert_called_once_with(
        "https://en.wikipedia.org/wiki/Test",
        stream=True,
        allow_redirects=False,
        timeout=6.0,
    )
    assert hasattr(read_html.call_args.args[0], "read")
    assert result[0]["name"] == "A"
    mock_get.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    "url",
    [
        "http://en.wikipedia.org/wiki/Test",
        "https://example.com/wiki/Test",
        "https://en.wikipedia.org:444/wiki/Test",
        "https://wikipedia.org.evil.test/wiki/Test",
    ],
)
def test_wikipedia_rejects_urls_outside_trust_boundary(url):
    with pytest.raises(ScenarioError, match="Wikipedia URLs"):
        WikipediaSource(url)


def test_wikipedia_normalizes_malformed_port_error():
    with pytest.raises(ScenarioError, match="Wikipedia URLs"):
        WikipediaSource("https://en.wikipedia.org:not-a-port/wiki/Test")


@patch("requests.get")
def test_wikipedia_rejects_off_domain_redirect(mock_get):
    response = _response()
    response.status_code = 302
    response.headers = {"Location": "https://example.com/large.html"}
    mock_get.return_value = response

    with pytest.raises(ScenarioError, match="Wikipedia URLs"):
        WikipediaSource("https://en.wikipedia.org/wiki/Test").to_scenario_list()

    response.close.assert_called_once()


@patch("requests.get")
def test_wikipedia_rejects_oversized_response(mock_get):
    response = _response()
    response.iter_content.return_value = [
        b"x" * (WikipediaSource.MAX_RESPONSE_BYTES + 1)
    ]
    mock_get.return_value = response

    with pytest.raises(ScenarioError, match="size limit"):
        WikipediaSource("https://en.wikipedia.org/wiki/Test").to_scenario_list()

    response.close.assert_called_once()
