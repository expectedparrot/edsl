import shutil

import pytest

from edsl import QuestionBase, QuestionDiagram, Scenario


def _requires_graphviz():
    pytest.importorskip("pydot")
    if shutil.which("dot") is None:
        pytest.skip("Graphviz dot executable is not installed")


def test_question_diagram_serialization():
    question = QuestionDiagram(
        question_name="flow",
        question_text="digraph { A -> B }",
        output_format="svg",
        engine="dot",
    )

    restored = QuestionBase.from_dict(question.to_dict())

    assert isinstance(restored, QuestionDiagram)
    assert restored.question_name == "flow"
    assert restored.question_text == "digraph { A -> B }"
    assert restored.output_format == "svg"
    assert restored.engine == "dot"


def test_question_diagram_rejects_unknown_output_format():
    with pytest.raises(ValueError, match="output_format"):
        QuestionDiagram(
            question_name="flow",
            question_text="digraph { A -> B }",
            output_format="pdf",
        )


def test_question_diagram_renders_svg_directly():
    _requires_graphviz()
    question = QuestionDiagram(
        question_name="flow",
        question_text="digraph { {{ start }} -> {{ finish }} }",
    )

    answer = question.answer_question_directly(
        Scenario({"start": "Start", "finish": "Done"})
    )

    assert answer["answer"].mime_type == "image/svg+xml"
    assert answer["answer"].suffix == "svg"
    assert answer["answer"].base64_string
    assert "Start -> Done" in answer["generated_tokens"]


def test_question_diagram_runs_as_filestore_answer():
    _requires_graphviz()
    question = QuestionDiagram(
        question_name="flow",
        question_text="digraph { {{ start }} -> {{ finish }} }",
    )

    results = question.by(Scenario({"start": "Start", "finish": "Done"})).run(
        disable_remote_inference=True,
        stop_on_exception=True,
    )

    answer = results.select("answer.flow").to_list()[0]

    assert answer.mime_type == "image/svg+xml"
    assert answer.base64_string
    assert hash(results)
