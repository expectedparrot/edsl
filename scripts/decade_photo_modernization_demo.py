"""Generate decade-by-decade versions of a reference photo.

Run from the repo root:

    uv run python scripts/decade_photo_modernization_demo.py
"""

from __future__ import annotations

import base64
import html
import os
from pathlib import Path

from edsl import FileStore, Model, QuestionImageGeneration, ScenarioList


OUTPUT_DIR = Path("temp/decade_photo_modernization_demo")
REFERENCE_YEAR = 1910
TARGET_YEARS = list(range(1920, 2030, 10))


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


def find_reference_image() -> Path:
    candidates = sorted(
        Path.home().joinpath("Desktop").glob("Screenshot 2026-07-11 at 10.03.52*AM.png")
    )
    if not candidates:
        raise FileNotFoundError(
            "Could not find the reference screenshot on the Desktop. "
            "Expected a file matching 'Screenshot 2026-07-11 at 10.03.52*AM.png'."
        )
    return candidates[0]


def scenarios(source_image: FileStore) -> ScenarioList:
    rows = []
    for year in TARGET_YEARS:
        decade = f"{year}s"
        if year == 2020:
            decade = "2020s / present day"
        rows.append(
            {
                "source_image": source_image,
                "reference_year": REFERENCE_YEAR,
                "target_year": year,
                "target_decade": decade,
                "era_context": era_context(year),
            }
        )
    return ScenarioList.from_list_of_dicts(rows)


def era_context(year: int) -> str:
    context = {
        1920: "early mechanized farm life, practical workwear, period tools and rural backdrop",
        1930: "Depression-era farm setting, durable overalls, dust-bowl realism, modest rural context",
        1940: "wartime agricultural production, sturdy work clothes, farm equipment, documentary photo style",
        1950: "postwar family farm, cleaner denim workwear, pickup truck or improved barn setting",
        1960: "modernizing farm, short-sleeve work shirt, newer equipment, Kodachrome color feel",
        1970: "independent farmer aesthetic, weathered denim, longer hair or sideburns if natural, warm film look",
        1980: "rural workwear with trucker cap or plaid shirt, practical farmyard context, color snapshot style",
        1990: "contemporary small farm, baseball cap, work jacket, pickup or livestock pen, realistic color photo",
        2000: "modern sustainable farm context, casual rugged clothes, updated fencing and equipment",
        2010: "local organic farm setting, practical outdoor clothing, smartphone-era documentary photography",
        2020: "present-day regenerative farm or homestead, modern outdoor workwear, natural color photography",
    }
    return context[year]


def save_images(results, output_dir: Path) -> dict[int, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    years = results.select("scenario.target_year").to_list()
    images = results.select("answer.decade_image").to_list()
    filenames = {}

    for year, image in zip(years, images):
        path = output_dir / f"farmer_{year}s.{image.suffix}"
        path.write_bytes(base64.b64decode(image.base64_string))
        filenames[year] = path.name

    return filenames


def write_report(reference_path: Path, image_files: dict[int, str], output_dir: Path) -> Path:
    reference_copy = output_dir / reference_path.name
    reference_copy.write_bytes(reference_path.read_bytes())

    cards = [
        f"""
      <article class="card">
        <img src="{html.escape(reference_copy.name)}" alt="Reference image from {REFERENCE_YEAR}">
        <div class="card-body">
          <div class="year">{REFERENCE_YEAR}</div>
          <p>Original reference image.</p>
        </div>
      </article>
"""
    ]
    for year in TARGET_YEARS:
        cards.append(
            f"""
      <article class="card">
        <img src="{html.escape(image_files[year])}" alt="Generated {year}s version">
        <div class="card-body">
          <div class="year">{year}s</div>
          <p>{html.escape(era_context(year))}</p>
        </div>
      </article>
"""
        )

    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Decade Photo Modernization</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #121722;
      background: #f5f2eb;
      line-height: 1.45;
    }}
    header {{
      padding: 32px 40px 22px;
      background: #fffdf8;
      border-bottom: 1px solid #d9d3c6;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 980px;
      color: #5d6470;
      font-size: 16px;
    }}
    main {{
      padding: 28px 40px 48px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .card {{
      background: white;
      border: 1px solid #d9d3c6;
      border-radius: 8px;
      overflow: hidden;
    }}
    .card img {{
      display: block;
      width: 100%;
      aspect-ratio: 4 / 3;
      object-fit: cover;
      background: #e7dfd2;
    }}
    .card-body {{
      padding: 14px 15px 16px;
    }}
    .year {{
      font-size: 20px;
      font-weight: 750;
      margin-bottom: 6px;
    }}
    p {{
      margin: 0;
      color: #525a66;
      font-size: 14px;
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
    <h1>Decade Photo Modernization</h1>
    <div class="subtitle">
      The 1910 reference photo is used as the identity anchor. Each generated image modernizes
      dress, setting, photographic style, and farm context for the target decade while asking
      the model to keep the person clearly recognizable.
    </div>
  </header>
  <main>
    <section class="grid">
      {"".join(cards)}
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
    reference_path = find_reference_image()
    source_image = FileStore(str(reference_path))

    question = QuestionImageGeneration(
        question_name="decade_image",
        question_text=(
            "Use this reference photo from {{ reference_year }} as the identity anchor: "
            "{{ source_image }}\n\n"
            "Generate a realistic version of the same person in {{ target_decade }}. "
            "Keep the person clearly recognizable: preserve facial structure, expression, "
            "body type, stance, and relationship to cattle or farm work. Modernize the "
            "clothing, context, setting, photography style, and farm environment for the "
            "target decade. Era context: {{ era_context }}. Do not add text, labels, or captions."
        ),
        service_name="google",
        model="gemini-3.1-flash-image",
    )

    results = (
        question.by(scenarios(source_image))
        .by(Model("test"))
        .run(disable_remote_inference=True, stop_on_exception=True)
    )

    image_files = save_images(results, OUTPUT_DIR)
    report_path = write_report(reference_path, image_files, OUTPUT_DIR)

    print(f"Reference image: {reference_path}")
    print(f"Saved generated images and report to {OUTPUT_DIR}")
    print(report_path)


if __name__ == "__main__":
    main()
