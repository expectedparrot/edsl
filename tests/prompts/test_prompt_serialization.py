"""Serialization and hashing for Prompt as a standalone Coop object."""

import subprocess
import sys

import pytest

from edsl import Prompt
from edsl.prompts.exceptions import PromptValueError

EDGE_CASE_TEXTS = [
    "",
    "   ",
    "line one\nline two\n",
    "trailing newlines\n\n",
    "\ttabbed\r\nwindows line",
    "Unicode: café, 日本語, emoji 🦜",
    "Explain {{ topic }} for {{ audience }}.",
    "{% for x in items %}{{ x }}{% endfor %}",
    "{{ unclosed",
    "<script>alert('x')</script><b>bold</b>",
]


def test_top_level_import():
    import edsl
    from edsl.prompts import Prompt as PackagePrompt

    assert edsl.Prompt is PackagePrompt


def test_to_dict_without_version_is_the_embedded_shape():
    assert Prompt("Hi {{ x }}").to_dict(add_edsl_version=False) == {
        "text": "Hi {{ x }}",
        "class_name": "Prompt",
    }


def test_default_to_dict_carries_metadata():
    from edsl import __version__

    assert Prompt("Hi").to_dict() == {
        "text": "Hi",
        "class_name": "Prompt",
        "edsl_class_name": "Prompt",
        "edsl_version": __version__,
    }


EMBEDDED_PROMPT_KEYS = {"text", "class_name"}


def test_prompts_embedded_in_results_carry_no_metadata():
    # Adding version metadata here would grow every Result and change its hash.
    from edsl import Results

    for add_edsl_version in (True, False):
        results = Results.example().to_dict(add_edsl_version=add_edsl_version)
        prompts = [
            prompt
            for result in results["data"]
            for prompt in result["prompt"].values()
        ]
        assert prompts
        assert all(set(prompt) == EMBEDDED_PROMPT_KEYS for prompt in prompts)


def test_prompts_in_by_question_data_carry_no_metadata():
    from edsl import Results

    question_data = Results.example()[0].by_question_data()["question_data"]
    prompts = [
        value
        for question in question_data.values()
        for key, value in question.items()
        if key in ("user_prompt", "system_prompt")
    ]
    assert prompts
    assert all(set(prompt) == EMBEDDED_PROMPT_KEYS for prompt in prompts)


@pytest.mark.parametrize("text", EDGE_CASE_TEXTS)
@pytest.mark.parametrize("add_edsl_version", [False, True])
def test_round_trip_preserves_text_exactly(text, add_edsl_version):
    restored = Prompt.from_dict(Prompt(text).to_dict(add_edsl_version=add_edsl_version))
    assert isinstance(restored, Prompt)
    assert str(restored) == text


def test_from_dict_accepts_bare_text():
    assert str(Prompt.from_dict({"text": "just text"})) == "just text"


def test_from_dict_does_not_render():
    restored = Prompt.from_dict({"text": "Hello {{ name }}"})
    assert str(restored) == "Hello {{ name }}"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"class_name": "Prompt"},
        {"text": None},
        {"text": 5},
        {"text": ["a"]},
        {"text": {"nested": "dict"}},
        "a string, not a dict",
        None,
    ],
)
def test_from_dict_rejects_missing_or_non_string_text(data):
    with pytest.raises(PromptValueError):
        Prompt.from_dict(data)


def test_from_dict_rejects_other_classes():
    with pytest.raises(PromptValueError, match="Survey"):
        Prompt.from_dict({"text": "x", "edsl_class_name": "Survey"})


def test_get_hash_is_deterministic_across_processes():
    text = "Explain {{ topic }}."
    in_process = Prompt(text).get_hash()
    other_process = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from edsl import Prompt; print(Prompt({text!r}).get_hash())",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert in_process == other_process


def test_get_hash_depends_only_on_text():
    assert Prompt("a").get_hash() == Prompt.from_dict({"text": "a"}).get_hash()
    assert Prompt("a").get_hash() != Prompt("b").get_hash()
    assert Prompt("").get_hash() != Prompt(" ").get_hash()


def test_str_behaviour_is_unchanged():
    p = Prompt("same")
    assert p == "same"
    assert hash(p) == hash("same")
    assert {"same": 1}[p] == 1
