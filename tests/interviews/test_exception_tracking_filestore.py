from edsl import Agent, FileStore, Model, QuestionMultipleChoice, Scenario, Survey
from edsl.caching import Cache
from edsl.interviews.exception_tracking import InterviewExceptionEntry


def test_filestore_reproduction_sketch_uses_path_without_truncated_payload(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"not-a-real-png-but-valid-file-content")
    file_store = FileStore(str(image_path))
    question = QuestionMultipleChoice(
        question_name="colors",
        question_text="Colors: {{ scenario.image }}",
        question_options=["red", "blue"],
    )
    scenario = Scenario({"image": file_store})
    agent = Agent()
    model = Model("test", throw_exception=True)
    invigilator = agent.create_invigilator(
        question=question,
        cache=Cache(),
        survey=Survey([question]),
        scenario=scenario,
        model=model,
    )
    code = InterviewExceptionEntry(
        exception=RuntimeError("forced"), invigilator=invigilator
    ).code_to_reproduce

    assert "Diagnostic reproduction sketch" in code
    assert "FileStore" in code.splitlines()[1]
    assert "base64_string" not in code
    assert "File contents are not embedded" in code

    definitions = code.rsplit("\nresults =", maxsplit=1)[0]
    namespace = {}
    exec(definitions, namespace)

    restored = namespace["scenario"]["image"]
    assert restored.base64_string == file_store.base64_string
