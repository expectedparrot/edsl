"""Generate chili concept images and rate excitement from the image.

Run from the repo root:

    uv run python scripts/chili_image_rating_demo.py
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from edsl import (
    Agent,
    Model,
    QuestionImageGeneration,
    QuestionLinearScale,
    ScenarioList,
    Survey,
)


def load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
        return
    except Exception:
        pass

    env_path = Path(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def scenarios() -> ScenarioList:
    return ScenarioList.from_list_of_dicts(
        [
            {
                "concept_name": "Texas Red",
                "protein": "beef chuck",
                "chile": "ancho and guajillo",
                "sauce": "no-tomato broth",
            },
            {
                "concept_name": "Stout Brisket",
                "protein": "brisket and short rib",
                "chile": "chipotle",
                "sauce": "beer and stout",
            },
            {
                "concept_name": "Coconut Curry Fusion",
                "protein": "chicken",
                "chile": "fresh green chile",
                "sauce": "coconut curry",
            },
        ]
    )


def save_images(results, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    concepts = results.select("scenario.concept_name").to_list()
    images = results.select("answer.chili_image").to_list()

    for concept, image in zip(concepts, images):
        filename = concept.lower().replace(" ", "_").replace("/", "_")
        path = output_dir / f"{filename}.{image.suffix}"
        path.write_bytes(base64.b64decode(image.base64_string))


def main() -> None:
    load_env()

    image_prompt = QuestionImageGeneration(
        question_name="chili_image",
        question_text=(
            "Create an appetizing editorial food photograph of a chili dish named "
            "{{ concept_name }}. The chili uses {{ protein }}, {{ chile }} chile, "
            "and a {{ sauce }} sauce. Show a finished bowl of chili with visible "
            "ingredients, natural light, realistic texture, no text or labels."
        ),
        service_name="google",
        model="gemini-3.1-flash-image",
    )

    excitement = QuestionLinearScale(
        question_name="excitement",
        question_text=(
            "You are evaluating this generated image of the chili concept "
            "{{ concept_name }}: {{ chili_image.answer }}\n\n"
            "Based on the image, how excited would you be to try this dish?"
        ),
        question_options=list(range(11)),
        option_labels={0: "not excited", 10: "extremely excited"},
    )

    chili_consumer = Agent(
        traits={
            "persona": (
                "You are an adventurous chili consumer. You care about visual appeal, "
                "heartiness, chile flavor, and whether the dish looks craveable."
            )
        }
    )

    rating_model = Model(
        "gemini-2.5-flash",
        service_name="google",
        temperature=0.2,
        max_output_tokens=500,
    )

    results = (
        Survey([image_prompt, excitement])
        .by(scenarios())
        .by(chili_consumer)
        .by(rating_model)
        .run(disable_remote_inference=True, stop_on_exception=True)
    )

    output_dir = Path("temp/chili_image_rating_demo")
    save_images(results, output_dir)

    print(results.select("scenario.concept_name", "answer.excitement", "comment.excitement_comment"))
    print(f"Saved generated images to {output_dir}")


if __name__ == "__main__":
    main()
