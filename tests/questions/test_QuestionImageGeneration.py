from edsl import (
    ImageGeneration,
    Model,
    QuestionBase,
    QuestionImageGeneration,
    Scenario,
    Survey,
)


def test_image_generation_test_service_returns_filestore():
    image = ImageGeneration(model="test-image", service_name="test").generate(
        "draw a square"
    )

    assert image.mime_type == "image/png"
    assert image.base64_string


def test_question_image_generation_serialization_preserves_service_settings():
    question = QuestionImageGeneration(
        question_name="img",
        question_text="Create {{ topic }}",
        model="test-image",
        service_name="test",
        aspect_ratio="1:1",
    )

    restored = QuestionBase.from_dict(question.to_dict())

    assert isinstance(restored, QuestionImageGeneration)
    assert restored.model == "test-image"
    assert restored.service_name == "test"
    assert restored.generation_parameters == {"aspect_ratio": "1:1"}
    assert restored._invigilator_class.__name__ == "InvigilatorImageGeneration"


def test_question_image_generation_runs_as_filestore_answer():
    question = QuestionImageGeneration(
        question_name="img",
        question_text="Create an icon for {{ topic }}",
        model="test-image",
        service_name="test",
    )

    results = (
        question.by(Model("test"))
        .by(Scenario({"topic": "surveys"}))
        .run(disable_remote_inference=True, stop_on_exception=True)
    )

    answer = results.select("answer.img").to_list()[0]
    generated_tokens = results.select("generated_tokens.img_generated_tokens").to_list()[
        0
    ]

    assert answer.mime_type == "image/png"
    assert answer.base64_string
    assert generated_tokens == "Create an icon for surveys"


def test_question_image_generation_can_pipe_prior_image_answer():
    original = QuestionImageGeneration(
        question_name="image",
        question_text="Create a portrait image.",
        model="test-image",
        service_name="test",
    )
    edit = QuestionImageGeneration(
        question_name="edit",
        question_text="Edit this image: {{ image.answer }}",
        model="test-image",
        service_name="test",
    )

    results = (
        Survey([original, edit])
        .by(Model("test"))
        .run(disable_remote_inference=True, stop_on_exception=True)
    )

    original_answer = results.select("answer.image").to_list()[0]
    edited_answer = results.select("answer.edit").to_list()[0]

    assert original_answer.mime_type == "image/png"
    assert edited_answer.mime_type == "image/png"
