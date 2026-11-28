# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.55.0"]
# ///
"""Record one live response to the coffee demo's three-question survey."""

import argparse
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url", help="Live respondent URL for your coffee demo deployment"
    )
    parser.add_argument("output", type=Path, help="New .webm file")
    parser.add_argument(
        "--brew", default="Espresso", help="Exact label of a brew choice"
    )
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".webm" or output.exists():
        parser.error("choose a new .webm output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    size = {"width": 1100, "height": 722}

    with tempfile.TemporaryDirectory(
        dir=output.parent
    ) as scratch, sync_playwright() as pw:
        browser = pw.chromium.launch(slow_mo=300)
        context = browser.new_context(
            viewport=size, record_video_size=size, record_video_dir=scratch
        )
        try:
            page = context.new_page()
            page.goto(args.url)
            next_question = page.get_by_role("button", name="Next", exact=True)
            for choice in ("Yes", args.brew):
                page.get_by_text(choice, exact=True).click()
                expect(
                    page.get_by_role("radio", name=choice, exact=True)
                ).to_be_checked()
                next_question.click()
            page.get_by_role("textbox").press_sequentially(
                "A flat white and a glass of water.", delay=65
            )
            next_question.click()
            expect(
                page.get_by_role("heading", name="Thank you for completing the survey!")
            ).to_be_visible()
            page.wait_for_timeout(2000)  # Hold the confirmation in the recording.
        finally:
            context.close()
            browser.close()
        output.hardlink_to(page.video.path())
    print(output)


if __name__ == "__main__":
    main()
