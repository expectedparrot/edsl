"""Coop push/pull/patch for Prompt.

The server and bucket are mocked, so these tests do not need a running Coop.
"""

import json
from unittest.mock import Mock, patch

import pytest

from edsl import Prompt
from edsl.coop.coop import Coop
from edsl.coop.exceptions import CoopObjectTypeError
from edsl.coop.utils import ObjectRegistry
from edsl.prompts.exceptions import PromptValueError

PROMPT_UUID = "123e4567-e89b-12d3-a456-426614174000"
TEXT = "Explain {{ topic }} for {{ audience }}."


def json_response(content):
    response = Mock()
    response.json.return_value = content
    return response


def fake_server(pulled_object, object_type="prompt", report_type=True):
    """Answer the alias-info and pull requests the way the server does."""
    calls = []

    def send(uri, method, params=None, payload=None):
        calls.append({"uri": uri, "method": method, "params": params, "payload": payload})
        if uri == "api/v0/object/alias/info":
            return json_response(
                {"uuid": PROMPT_UUID, "is_new_format": True, "object_type": object_type}
            )
        if uri == "api/v0/object/pull":
            body = {"signed_url": "https://bucket/signed", "is_legacy_format": False}
            if report_type:
                body["object_type"] = object_type
            return json_response(body)
        raise AssertionError(f"unexpected request {method} {uri}")

    bucket_response = json_response(pulled_object)
    return send, bucket_response, calls


def pull(url_or_uuid, expected_object_type, pulled_object, **server_kwargs):
    send, bucket_response, calls = fake_server(pulled_object, **server_kwargs)
    with patch.object(Coop, "_send_server_request", side_effect=send), patch.object(
        Coop, "_resolve_server_response"
    ), patch.object(Coop, "_resolve_gcs_response"), patch(
        "edsl.coop.coop.requests.get", return_value=bucket_response
    ):
        result = Coop(api_key="b").pull(url_or_uuid, expected_object_type)
    return result, calls


def test_registry_maps_prompt_both_ways():
    assert ObjectRegistry.get_object_type_by_edsl_class(Prompt("x")) == "prompt"
    assert ObjectRegistry.get_object_type_by_edsl_class(Prompt) == "prompt"
    assert ObjectRegistry.get_edsl_class_by_object_type("prompt") is Prompt
    assert ObjectRegistry.get_registry()["Prompt"] is Prompt


def push(obj, **kwargs):
    """Push obj against a mocked server; return the push payload and uploaded JSON."""
    coop = Coop(api_key="b")
    push_response = json_response(
        {
            "object_uuid": PROMPT_UUID,
            "signed_url": "https://bucket/upload",
            "alias": None,
            "url": "u",
            "alias_url": None,
            "visibility": "private",
            "description": None,
        }
    )
    confirm_response = json_response({"status": "success"})
    uploaded = {}

    def put(url, data, headers):
        uploaded["body"] = json.loads(data)
        return Mock(status_code=200)

    with patch.object(
        coop, "_send_server_request", side_effect=[push_response, confirm_response]
    ) as send, patch.object(coop, "_resolve_server_response"), patch.object(
        coop, "_resolve_gcs_response"
    ), patch("edsl.coop.coop.requests.put", side_effect=put):
        coop.push(obj, **kwargs)

    return send.call_args_list[0].kwargs["payload"], uploaded["body"]


def test_push_uploads_the_standalone_form():
    prompt = Prompt(TEXT)
    payload, body = push(prompt, alias="explanation-template", visibility="private")

    assert payload["object_type"] == "prompt"
    assert payload["object_hash"] == prompt.get_hash()
    assert body["text"] == TEXT
    assert body["edsl_class_name"] == "Prompt"
    assert "edsl_version" in body


@pytest.mark.parametrize(
    "cls",
    [
        "edsl.notebooks.Notebook",
        "edsl.macros.composite_macro.CompositeMacro",
    ],
)
def test_push_names_the_class_for_objects_that_used_to_omit_it(cls):
    # Like Prompt, these defaulted to add_edsl_version=False until 1.0.8.
    import importlib

    module_name, class_name = cls.rsplit(".", 1)
    edsl_class = getattr(importlib.import_module(module_name), class_name)

    _, body = push(edsl_class.example())

    assert body["edsl_class_name"] == class_name
    assert "edsl_version" in body


def test_patch_sends_an_empty_prompt():
    coop = Coop(api_key="b")
    format_response = json_response({"is_new_format": False})
    patch_response = json_response({"status": "success"})

    with patch.object(
        coop, "_send_server_request", side_effect=[format_response, patch_response]
    ) as send, patch.object(coop, "_resolve_server_response"):
        coop.patch(PROMPT_UUID, value=Prompt(""))

    json_string = send.call_args_list[1].kwargs["payload"]["json_string"]
    assert json.loads(json_string)["text"] == ""


@pytest.mark.parametrize(
    "ref",
    [
        PROMPT_UUID,
        f"https://www.expectedparrot.com/content/{PROMPT_UUID}",
        "https://www.expectedparrot.com/content/alice/explanation-template",
    ],
)
def test_pull_by_each_reference_form(ref):
    stored = Prompt(TEXT).to_dict(add_edsl_version=True)
    result, _ = pull(ref, "prompt", stored)
    assert isinstance(result, Prompt)
    assert str(result) == TEXT


def test_prompt_pull_expands_owner_alias_shorthand():
    stored = Prompt(TEXT).to_dict(add_edsl_version=True)
    send, bucket_response, calls = fake_server(stored)
    with patch.object(Coop, "_send_server_request", side_effect=send), patch.object(
        Coop, "_resolve_server_response"
    ), patch.object(Coop, "_resolve_gcs_response"), patch(
        "edsl.coop.coop.requests.get", return_value=bucket_response
    ):
        result = Prompt.pull("alice/explanation-template")

    assert str(result) == TEXT
    assert calls[0]["params"] == {
        "owner_username": "alice",
        "alias": "explanation-template",
    }


def test_generic_pull_returns_a_prompt():
    stored = Prompt(TEXT).to_dict(add_edsl_version=True)
    result, _ = pull(PROMPT_UUID, None, stored)
    assert type(result) is Prompt


def test_generic_pull_uses_the_server_type_when_the_payload_has_no_class():
    result, _ = pull(PROMPT_UUID, None, {"text": TEXT, "class_name": "Prompt"})
    assert type(result) is Prompt


def test_generic_pull_of_an_unknown_class_raises_instead_of_guessing():
    # Agent.from_dict accepts any dict, so guessing would return an Agent here.
    from edsl.coop.exceptions import CoopResponseError

    with pytest.raises(CoopResponseError, match="FutureThing"):
        pull(
            PROMPT_UUID,
            None,
            {"edsl_class_name": "FutureThing", "foo": 1},
            report_type=False,
        )


def test_alias_pull_of_another_type_is_rejected():
    with pytest.raises(CoopObjectTypeError):
        pull(
            "https://www.expectedparrot.com/content/alice/my-survey",
            "prompt",
            {"edsl_class_name": "Survey"},
            object_type="survey",
        )


def test_uuid_pull_of_another_type_is_rejected_by_the_server_type():
    with pytest.raises(CoopObjectTypeError):
        pull(PROMPT_UUID, "prompt", {"edsl_class_name": "Survey"}, object_type="survey")


def test_uuid_pull_of_another_type_is_rejected_without_the_server_type():
    # Older servers do not report object_type on pull; the payload still names its class.
    with pytest.raises(PromptValueError, match="Survey"):
        pull(
            PROMPT_UUID,
            "prompt",
            {"text": "x", "edsl_class_name": "Survey"},
            object_type="survey",
            report_type=False,
        )
