"""Coop.push and Coop.patch with git_repo=True: an .ep package's push asks Coop
for its git repo, and Coop's answer carries git_remote_url."""

import pytest

from edsl import Survey
from edsl.coop import Coop
import edsl.coop.coop as coop_module

REMOTE = "https://git.example.test/edsl/alice/obj-x.git"
OBJECT_UUID = "11111111-2222-4333-8444-555555555555"


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def coop(monkeypatch):
    """A Coop whose server returns REMOTE whenever a request carries git_repo."""
    sent = []

    def send(self, uri, method, payload=None, params=None, **kwargs):
        sent.append((method, uri, payload or {}))
        payload = payload or {}
        remote = {"git_remote_url": REMOTE} if payload.get("git_repo") else {}
        if uri == "api/v0/object/push":
            return FakeResponse(
                {"signed_url": "https://gcs.test/put", "object_uuid": OBJECT_UUID,
                 "owner_username": "alice", "visibility": "private"}
            )
        if uri == "api/v0/object/check-format":
            return FakeResponse({"is_new_format": self.new_format})
        if uri == "api/v0/object/upload-url":
            return FakeResponse({"signed_url": "https://gcs.test/put"})
        return FakeResponse({"processing_started": True, **remote})

    class Uploaded:
        status_code = 200

    monkeypatch.setattr(Coop, "_send_server_request", send)
    monkeypatch.setattr(Coop, "_resolve_server_response", lambda self, response: None)
    monkeypatch.setattr(Coop, "_resolve_gcs_response", lambda self, response: None, raising=False)
    monkeypatch.setattr(coop_module.requests, "put", lambda *args, **kwargs: Uploaded())
    client = Coop(api_key="test-key")
    client.new_format = True
    return client, sent


def _confirm_payloads(sent):
    return [payload for method, uri, payload in sent if uri == "api/v0/object/confirm-upload"]


def test_push_of_an_ep_asks_for_its_repo_and_returns_the_url(coop):
    client, sent = coop

    info = client.push(Survey.example(), git_repo=True)
    plain = client.push(Survey.example())

    assert info["git_remote_url"] == REMOTE
    assert "git_remote_url" not in plain
    assert [p.get("git_repo") for p in _confirm_payloads(sent)] == [True, None]


@pytest.mark.parametrize("new_format", [True, False])
def test_patch_of_an_ep_asks_for_its_repo_and_returns_the_url(coop, new_format):
    client, sent = coop
    client.new_format = new_format

    info = client.patch(OBJECT_UUID, value=Survey.example(), git_repo=True)

    assert info["git_remote_url"] == REMOTE
    asked = [p for method, uri, p in sent if p.get("git_repo")]
    assert len(asked) == 1
