"""Generate landing-page image concepts for expectedparrot.com and rate them.

Run from the repo root:

    uv run python scripts/landing_page_image_concept_demo.py
"""

from __future__ import annotations

import base64
import html
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


OUTPUT_DIR = Path("temp/landing_page_image_concept_demo")


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
                "concept_name": "Research Control Room",
                "target_user": "academic and policy researchers",
                "core_promise": "run structured AI interviews and experiments at scale",
                "hero_visual": (
                    "a polished research command center with interview cards, "
                    "agent personas, and survey results arranged on large displays"
                ),
                "visual_style": "premium SaaS product photography with realistic UI surfaces",
                "palette": "warm white, charcoal, tomato red, and fresh green accents",
                "energy": "credible, focused, analytical",
            },
            {
                "concept_name": "Synthetic Respondent Studio",
                "target_user": "product teams testing messaging and concepts",
                "core_promise": "simulate audience reactions before launching real studies",
                "hero_visual": (
                    "a studio table with concept cards, generated respondent profiles, "
                    "and image-based survey artifacts flowing into a clean dashboard"
                ),
                "visual_style": "editorial tabletop scene mixed with subtle interface overlays",
                "palette": "soft daylight, cream, slate, coral, and blue accents",
                "energy": "creative, fast, practical",
            },
            {
                "concept_name": "Expected Parrot Signal",
                "target_user": "research leaders and data teams",
                "core_promise": "turn qualitative conversations into decision-ready evidence",
                "hero_visual": (
                    "an abstract but recognizable parrot-shaped signal made from "
                    "conversation bubbles, data points, and research notebooks"
                ),
                "visual_style": "sophisticated brand illustration rendered as realistic mixed media",
                "palette": "white, deep ink, leaf green, crimson, and golden highlights",
                "energy": "distinctive, memorable, trustworthy",
            },
        ]
    )


def save_images(results, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    concepts = results.select("scenario.concept_name").to_list()
    images = results.select("answer.hero_image").to_list()
    filenames = {}

    for concept, image in zip(concepts, images):
        filename = concept.lower().replace(" ", "_").replace("/", "_")
        path = output_dir / f"{filename}.{image.suffix}"
        path.write_bytes(base64.b64decode(image.base64_string))
        filenames[concept] = path.name

    return filenames


def write_report(results, image_files: dict[str, str], output_dir: Path) -> Path:
    concepts = results.select("scenario.concept_name").to_list()
    target_users = results.select("scenario.target_user").to_list()
    promises = results.select("scenario.core_promise").to_list()
    styles = results.select("scenario.visual_style").to_list()
    palettes = results.select("scenario.palette").to_list()
    ratings = results.select("answer.appeal").to_list()
    comments = results.select("comment.appeal_comment").to_list()
    script_source = Path(__file__).read_text()

    cards = []
    for concept, target_user, promise, style, palette, rating, comment in zip(
        concepts, target_users, promises, styles, palettes, ratings, comments
    ):
        cards.append(
            f"""
      <article class="card">
        <img src="{html.escape(image_files[concept])}" alt="{html.escape(concept)} generated landing-page concept">
        <div class="card-body">
          <div class="name-row">
            <div class="name">{html.escape(concept)}</div>
            <div class="rating">{html.escape(str(rating))}/10</div>
          </div>
          <p class="meta"><strong>Audience:</strong> {html.escape(target_user)}</p>
          <p class="meta"><strong>Promise:</strong> {html.escape(promise)}</p>
          <p class="meta"><strong>Style:</strong> {html.escape(style)}</p>
          <p class="meta"><strong>Palette:</strong> {html.escape(palette)}</p>
          <p class="comment">{html.escape(comment or "")}</p>
        </div>
      </article>
"""
        )

    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Expected Parrot Landing Page Image Concepts</title>
  <style>
    :root {{
      --bg: #f5f7f4;
      --ink: #121722;
      --muted: #586170;
      --panel: #fff;
      --line: #d8ddd3;
      --accent: #be2f24;
      --code: #111827;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.45;
    }}
    header {{
      padding: 34px 42px 24px;
      background: #fffef9;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 980px;
      color: var(--muted);
      font-size: 16px;
    }}
    main {{
      padding: 28px 42px 52px;
    }}
    h2 {{
      margin: 0 0 16px;
      font-size: 22px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 34px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .card img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      background: #e7ebe4;
    }}
    .card-body {{
      padding: 16px;
    }}
    .name-row {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .name {{
      font-size: 19px;
      font-weight: 750;
    }}
    .rating {{
      min-width: 54px;
      text-align: center;
      color: #fff;
      background: var(--accent);
      border-radius: 999px;
      padding: 4px 10px;
      font-weight: 750;
    }}
    .meta {{
      margin: 0 0 7px;
      color: var(--muted);
      font-size: 14px;
    }}
    .comment {{
      margin: 12px 0 0;
      font-size: 15px;
    }}
    .code-section {{
      background: var(--code);
      color: #eef2ff;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #2c3448;
    }}
    .code-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 16px;
      background: #182033;
      border-bottom: 1px solid #2c3448;
      color: #cbd5e1;
      font-size: 14px;
    }}
    pre {{
      margin: 0;
      padding: 18px;
      overflow-x: auto;
      font-size: 13px;
      line-height: 1.45;
      tab-size: 4;
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }}
    @media (max-width: 1000px) {{
      header, main {{
        padding-left: 20px;
        padding-right: 20px;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Expected Parrot Landing Page Image Concepts</h1>
    <div class="subtitle">
      Three hero-image directions for expectedparrot.com, varied by target user, product promise,
      visual metaphor, style, palette, and energy. A prospective research-tool user rated each image.
    </div>
  </header>
  <main>
    <h2>Concept Images And Ratings</h2>
    <section class="grid">
      {"".join(cards)}
    </section>
    <h2>Generated Script</h2>
    <section class="code-section">
      <div class="code-header">
        <span>scripts/landing_page_image_concept_demo.py</span>
        <span>Local inference: Google image generation + Gemini rating</span>
      </div>
      <pre><code>{html.escape(script_source)}</code></pre>
    </section>
  </main>
</body>
</html>
"""

    report_path = output_dir / "report.html"
    report_path.write_text(report)
    return report_path


def main() -> None:
    load_env()

    image_prompt = QuestionImageGeneration(
        question_name="hero_image",
        question_text=(
            "Create a 16:9 landing page hero image concept for expectedparrot.com. "
            "Target user: {{ target_user }}. Product promise: {{ core_promise }}. "
            "Hero visual: {{ hero_visual }}. Visual style: {{ visual_style }}. "
            "Palette: {{ palette }}. Energy: {{ energy }}. Make it polished, modern, "
            "specific to AI research and survey workflows, suitable for the first viewport "
            "of a serious SaaS landing page. Do not include readable text, fake logos, or UI labels."
        ),
        service_name="google",
        model="gemini-3.1-flash-image",
    )

    appeal = QuestionLinearScale(
        question_name="appeal",
        question_text=(
            "You are evaluating a generated landing page hero image concept for expectedparrot.com.\n"
            "Concept: {{ concept_name }}\n"
            "Target user: {{ target_user }}\n"
            "Product promise: {{ core_promise }}\n"
            "Image: {{ hero_image.answer }}\n\n"
            "Based on the image, how effective would this be as a landing page hero for a research software product?"
        ),
        question_options=list(range(11)),
        option_labels={0: "not effective", 10: "extremely effective"},
    )

    evaluator = Agent(
        traits={
            "persona": (
                "You are a pragmatic buyer of research software and a careful landing-page evaluator. "
                "You value credibility, clarity, visual specificity, and whether the hero image makes "
                "the product feel useful for real research workflows."
            )
        }
    )

    rating_model = Model(
        "gemini-2.5-flash",
        service_name="google",
        temperature=0.2,
        max_output_tokens=600,
    )

    results = (
        Survey([image_prompt, appeal])
        .by(scenarios())
        .by(evaluator)
        .by(rating_model)
        .run(disable_remote_inference=True, stop_on_exception=True)
    )

    image_files = save_images(results, OUTPUT_DIR)
    report_path = write_report(results, image_files, OUTPUT_DIR)

    print(results.select("scenario.concept_name", "answer.appeal", "comment.appeal_comment"))
    print(f"Saved generated images and report to {OUTPUT_DIR}")
    print(report_path)


if __name__ == "__main__":
    main()
