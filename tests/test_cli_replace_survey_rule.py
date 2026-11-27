"""Exercise rule replacement on saved packages and verify the resulting routes."""

import json

import pytest
from click.testing import CliRunner

from edsl import Question, Survey
from edsl.__main__ import app


def run(*args, code=0):
    result = CliRunner().invoke(app, ["surveys", *map(str, args)])
    assert result.exit_code == code, result.output
    response = json.loads(result.stdout)
    assert response["status"] == ("ok" if code == 0 else "error")
    return response


@pytest.fixture
def source(tmp_path):
    survey = Survey(
        [
            Question(
                "checkbox",
                question_name="amenities",
                question_text="Choose amenities.",
                question_options=["Seats", "Map", "Other"],
            ),
            Question("free_text", question_name="write_in", question_text="What else?"),
            Question(
                "free_text", question_name="wrap", question_text="Any final thoughts?"
            ),
        ]
    )
    survey.add_skip_rule("write_in", "{{ amenities.answer }} != ['Other']")
    path = tmp_path / "draft.ep"
    survey.git.save(path, sync_coop=False)
    return path


def test_replace_checkbox_rule_and_replay_saved_paths(source, tmp_path):
    final = tmp_path / "final.ep"
    cases = tmp_path / "paths.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "name": "multiple selections",
                        "answers": {"amenities": ["Seats", "Other"]},
                        "expected_path": ["amenities", "write_in", "wrap"],
                    },
                    {
                        "name": "other alone",
                        "answers": {"amenities": ["Other"]},
                        "expected_path": ["amenities", "write_in", "wrap"],
                    },
                    {
                        "name": "no other",
                        "answers": {"amenities": ["Seats"]},
                        "expected_path": ["amenities", "wrap"],
                    },
                ]
            }
        )
    )
    original = source.read_bytes()
    assert (
        run("check-paths", source, "--cases", cases, code=5)["error"]["code"]
        == "PATH_CHECK_FAILED"
    )
    before = run("show", source)["data"]["rules"]
    assert len(before) == 1 and before[0]["question"] == "write_in"
    expression = "'Other' not in {{ amenities.answer }}"
    run(
        "replace-rule",
        source,
        "--question",
        "write_in",
        "--expression",
        expression,
        "-o",
        final,
    )
    assert run("show", final)["data"]["rules"] == [
        {**before[0], "expression": expression}
    ]
    assert run("check-paths", final, "--cases", cases)["data"]["passed"] == 3
    assert source.read_bytes() == original


def test_replace_one_rule_at_original_priority_and_change_destination(source):
    from edsl.surveys.base import EndOfSurvey

    survey = Survey.git.load(source, sync_coop=False)
    survey.add_stop_rule("write_in", "{{ write_in.answer }} == 'done'")
    survey.add_rule("write_in", "{{ write_in.answer }} == 'more'", "wrap")
    survey.git.save(source, sync_coop=False)
    before = run("show", source)["data"]["rules"]
    args = [
        "replace-rule",
        source,
        "--question",
        "write_in",
        "--expression",
        "{{ write_in.answer }} == 'finish'",
    ]
    original = source.read_bytes()
    msg = run(*args, "--priority", "0", code=5)["error"]["message"]
    assert "--when before" in msg and "--when after" in msg
    assert source.read_bytes() == original

    run(*args, "--when", "after", "--priority", "0", "--next", "wrap")
    updated = run("show", source)["data"]["rules"]
    assert updated == [
        before[0],
        {**before[1], "expression": args[-1], "next_q": 2},
        before[2],
    ]
    run(*args, "--match-expression", args[-1], "--next", "EndOfSurvey")
    survey = Survey.git.load(source, sync_coop=False)
    assert (
        survey.next_question("write_in", {"write_in.answer": "finish"}) == EndOfSurvey
    )
    assert (
        survey.next_question("write_in", {"write_in.answer": "done"}).question_name
        == "wrap"
    )


@pytest.mark.parametrize(
    ("question", "expression", "extra"),
    [
        ("wrap", "True", []),  # only a default rule exists
        ("missing", "True", []),
        ("write_in", "(", []),
        ("write_in", "x = 1", []),
        ("write_in", "{{ nowhere.answer }}", []),
        ("write_in", "{{ wrap.answer }}", []),
        ("write_in", "{{ write_in.answer }}", []),
        ("write_in", "True", ["--when", "after"]),
        ("write_in", "True", ["--next", "wrap"]),
        ("write_in", "True", ["--match-expression", "obsolete condition"]),
    ],
)
def test_failed_replacement_leaves_source_intact(source, question, expression, extra):
    original = source.read_bytes()
    response = run(
        "replace-rule",
        source,
        "--question",
        question,
        "--expression",
        expression,
        *extra,
        code=5
    )
    assert response["error"]["code"] == "VALIDATION_ERROR"
    assert source.read_bytes() == original


def test_concurrent_replacement_and_question_edit_both_survive(source):
    from concurrent.futures import ThreadPoolExecutor
    import subprocess
    import sys

    expression = "'Other' not in {{ amenities.answer }}"
    edits = [
        [
            "replace-rule",
            str(source),
            "--question",
            "write_in",
            "--expression",
            expression,
        ],
        ["update-question", str(source), "wrap", "--question-text", "Final comment?"],
    ]

    def edit(arguments):
        reply = subprocess.run(
            [sys.executable, "-m", "edsl", "surveys", *arguments],
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(reply.stdout)["status"] == "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(edit, edits))
    saved = Survey.git.load(source, sync_coop=False)
    assert saved.rule_collection.non_default_rules[0].expression == expression
    assert saved.get("wrap").question_text == "Final comment?"
