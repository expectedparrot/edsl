"""Read an approved draft without changing the package under review."""

import json

from click.testing import CliRunner

from edsl import QuestionFreeText, Survey
from edsl.__main__ import app


def test_inspect_and_list_questions_at_an_earlier_commit(tmp_path):
    path = tmp_path / "walk.ep"
    for text in ("Approved wording", "Field test wording"):
        Survey([QuestionFreeText(question_name="walk", question_text=text)]).git.save(
            path, message=text, sync_coop=False
        )
    package = path.read_bytes()
    sha = Survey.git.load(path, sync_coop=False).git.log()[1]["commit"]
    runner = CliRunner()
    for command, key in [(["inspect"], "sample_questions"), (["surveys", "questions"], "questions")]:
        result = runner.invoke(app, [*command, str(path), "--ref", sha[:9]])
        assert result.exit_code == 0, result.output
        info = json.loads(result.output)["data"]
        assert info["commit"] == sha
        assert info[key][0]["question_text"] == "Approved wording"
    md = runner.invoke(app, ["inspect", str(path), "--commit", "HEAD~1", "--markdown"])
    assert md.exit_code == 0 and "Approved wording" in md.output
    output = tmp_path / "draft.json"
    export = runner.invoke(app, ["inspect", str(path), "--ref", sha, "--save", str(output)])
    assert export.exit_code == 0, export.output
    assert Survey.from_dict(json.loads(output.read_text())).get("walk").question_text == "Approved wording"
    for target, flags in [(path, ["--save", str(path)]), (output, []), ("-", []), ("owner/alias", [])]:
        bad = runner.invoke(app, ["inspect", str(target), "--ref", sha, *flags])
        assert bad.exit_code == 2, bad.output
    missing = runner.invoke(app, ["inspect", str(path), "--ref", "missing-draft"])
    assert missing.exit_code != 0 and "ep log" in missing.output
    assert path.read_bytes() == package
