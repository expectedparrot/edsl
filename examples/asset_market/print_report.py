"""Render the self-contained full HTML report to a PDF using Chromium."""

import argparse
import json
from pathlib import Path


def print_report(path: Path):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(path.resolve().as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        # Check the real rendered controls against the embedded source records.
        expected_count = page.evaluate(
            "REPORT.sessions.reduce((n,s) => n+s.rows.length,0)"
        )
        assert str(f"{expected_count:,}") in page.locator("#ledger-count").inner_text()
        assert page.locator("#period-table tbody tr").count() == 12
        for i in range(page.locator("#session-select option").count()):
            page.select_option("#session-select", str(i))
            for period in (1, 2, 3, 30):
                page.locator("#period-range").evaluate(
                    "(el, value) => {el.value = value; el.dispatchEvent(new Event('input', {bubbles:true}));}",
                    str(period),
                )
                actual = page.locator("#period-table tbody tr").evaluate_all(
                    "rows => rows.map(r => Number(r.cells[4].textContent))"
                )
                expected = page.evaluate(
                    "({i,t}) => REPORT.sessions[i].rows.filter(r=>r.period===t).map(r=>r.signed_fill)",
                    {"i": i, "t": period},
                )
                assert actual == expected
        page.locator("#fills-only").check()
        expected_fills = page.evaluate(
            "REPORT.sessions.flatMap(s=>s.rows).filter(r=>r.signed_fill!==0).length"
        )
        assert page.locator("#ledger-table tbody tr").count() == expected_fills
        page.locator("#fills-only").uncheck()
        page.locator("#ledger-search").fill("trader-08")
        assert "90 of" in page.locator("#ledger-count").inner_text()
        page.locator("#ledger-search").fill("")
        page.select_option("#session-select", "1")
        page.locator("#period-range").evaluate(
            "el => {el.value = '3'; el.dispatchEvent(new Event('input', {bubbles:true}));}"
        )
        page.locator('#period-table tr[data-trader="trader-08"]').click()
        assert "trader-08" in page.locator("#trader-heading").inner_text()
        page.locator("#replay").screenshot(path=str(path.parent / "replay-preview.png"))
        assert not errors, errors
        (path.parent / "browser-checks.json").write_text(
            json.dumps(
                {
                    "javascript_errors": errors,
                    "ledger_rows": expected_count,
                    "filled_decision_rows": expected_fills,
                    "replay_cases_checked": 12,
                    "search_and_trader_selection": "passed",
                },
                indent=2,
            )
            + "\n"
        )
        page.locator("#personas details").evaluate_all(
            "items => items.forEach(d => d.open = true)"
        )
        page.pdf(
            path=str(path.parent / "full-report.pdf"),
            prefer_css_page_size=True,
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#5d707b">Building Traders · EDSL pilot · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
        )
        browser.close()
    return path.parent / "full-report.pdf"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(print_report(args.path))
