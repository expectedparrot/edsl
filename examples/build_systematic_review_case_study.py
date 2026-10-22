"""Build the systematic-review shared-state tutorial from saved Results."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from edsl import Results
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

from examples.shared_state_dsl.shared_review_screening import SPEC


HERE = Path(__file__).resolve().parent
OUT = HERE / "shared_state_case_studies" / "systematic_review.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def code(source: str) -> str:
    return highlight(source, PythonLexer(), HtmlFormatter())


def json_block(value: object) -> str:
    return f"<pre>{esc(json.dumps(value, indent=2, ensure_ascii=False))}</pre>"


def _prompt_rows(results: Results, phase: str, questions: tuple[str, ...]) -> str:
    rows = []
    for result in results:
        for question in questions:
            prompts = result.data["prompt"]
            answer = result.answer.get(question)
            comment = result.data["comments_dict"].get(f"{question}_comment")
            rows.append(
                "<tr>"
                f"<td>{esc(phase)}</td><td>{esc(result.agent.name)}</td>"
                f"<td><code>{esc(question)}</code></td>"
                f'<td class="prompt-cell"><pre>{esc(prompts[f"{question}_user_prompt"].text)}</pre></td>'
                f'<td class="prompt-cell"><pre>{esc(prompts[f"{question}_system_prompt"].text)}</pre></td>'
                f"<td><code>{esc(json.dumps(answer, ensure_ascii=False))}</code></td>"
                f'<td class="comment-cell">{esc(comment)}</td></tr>'
            )
    return "".join(rows)


def _final_state(results: Results) -> dict:
    binding = results.shared_state["bindings"][0]
    return next(
        snapshot["state"]["review"]
        for snapshot in reversed(binding["exit_snapshots"])
        if snapshot.get("state") is not None
    )


def build(*, css: str) -> Path:
    screening = Results.load(HERE / "systematic_review_screening_results.ep")
    adjudication = Results.load(HERE / "systematic_review_adjudication_results.ep")
    state = _final_state(adjudication)
    reviews_by_paper: dict[str, list[dict]] = {}
    for review in state["reviews"]:
        reviews_by_paper.setdefault(review["paper"], []).append(review)
    counts = Counter(review["paper"] for review in state["reviews"])
    screening_events = screening.shared_state["bindings"][0]["events"]
    adjudication_events = adjudication.shared_state["bindings"][0]["events"]
    screening_reads = [e["version"] for e in screening_events if e["kind"] == "read"]
    adjudication_reads = [e["version"] for e in adjudication_events if e["kind"] == "read"]
    claims = {reviewer: paper["id"] for reviewer, paper in state["claims"].items()}
    prompt_rows = _prompt_rows(
        screening,
        "screening",
        ("screening_decision", "screening_reason"),
    ) + _prompt_rows(
        adjudication,
        "adjudication",
        ("final_decision", "final_reason"),
    )
    machine_source = (
        HERE / "shared_state_dsl" / "shared_review_screening.py"
    ).read_text()
    workflow_source = (HERE / "shared_state_systematic_review.py").read_text()
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Atomic systematic-review screening with EDSL shared state"><title>Systematic-review screening</title><style>{css}</style></head><body>
<header><div class="wrap"><p class="eyebrow">Stress test · atomic work allocation</p><h1>Systematic-review screening</h1><p>Six reviewers concurrently claim blinded abstract-screening assignments. A separate Results run then adjudicates the accumulated reviews using the same shared state.</p><div class="stats"><div class="stat"><b>6</b><span>screeners</span></div><div class="stat"><b>3</b><span>adjudicators</span></div><div class="stat"><b>18</b><span>captured prompts</span></div></div></div></header>
<div class="toolbar"><div class="wrap"><a href="index.html">← All case studies</a><span>Gemini 2.5 Flash · local inference</span></div></div><main>
<p class="lede">This example combines atomic claiming, viewer-specific state, repeated state reads, concurrent execution, phase separation, and state persistence across two independently saved <code>Results</code> objects.</p>
<section><h2>1. Research workflow</h2><div class="facts"><div class="fact"><small>Screening</small><b>6 concurrent interviews</b></div><div class="fact"><small>Allocation</small><b>2 reviewers per paper</b></div><div class="fact"><small>Disclosure</small><b>viewer-specific claim</b></div><div class="fact"><small>Adjudication</small><b>separate Results run</b></div></div><div class="callout"><b>Authoritative-claim contract:</b> <code>claim()</code> commits atomically, but its return is only advisory. Each reviewer performs <code>review.read()</code> and uses <code>shared_state.review.my_claim</code> before answering.</div></section>
<section><h2>2. The state machine</h2><div class="two"><div class="panel"><h3>Durable fields</h3><p><code>available</code>, <code>claims</code>, <code>reviews</code>, and <code>final_decisions</code>.</p><p>The claim command assigns and removes the first queue item in one transition.</p></div><div class="panel"><h3>Viewer-specific views</h3><p><code>my_claim</code> exposes only the current reviewer's assignment. <code>relevant_reviews</code> exposes only the adjudicator's paper.</p><p>This avoids asking an agent to search a large public map or trusting dynamic Jinja indexing.</p></div></div><details><summary>Serialized Machine</summary>{json_block(SPEC.to_dict())}</details><details><summary>Complete Machine source</summary>{code(machine_source)}</details></section>
<section><h2>3. The two-Survey program</h2><p>The first Survey performs concurrent claims and blinded screening. The second Survey reuses the same state reference for adjudication. One explicit read establishes an interview-local snapshot that remains available to later questions until another read refreshes it.</p>{code(workflow_source)}</section>
<section><h2>4. Atomic allocation result</h2><div class="two"><div class="panel result"><h3>Claims</h3>{json_block(claims)}</div><div class="panel"><h3>Invariant checks</h3><p>Remaining assignments: <b>{len(state['available'])}</b></p><p>Reviews per paper: <code>{esc(dict(counts))}</code></p><p>Distinct reviewers: <b>{len(state['claims'])}</b></p></div></div><p>Screening read versions were <code>{esc(screening_reads)}</code>. The early reads advance as concurrent claims commit; the later rationale reads all observe the fully claimed version. The adjudication run entered at version <code>{esc(adjudication_reads[0])}</code>, proving that it read state produced by the earlier Results run.</p></section>
<section><h2>5. Reviews and final decisions</h2><div class="scroll"><table><thead><tr><th>Paper</th><th>Two initial reviews</th><th>Final disposition</th></tr></thead><tbody>{''.join(f'<tr><td><code>{esc(paper)}</code></td><td>{esc([(r["reviewer"], r["decision"]) for r in reviews])}</td><td><b>{esc(state["final_decisions"][paper]["decision"])}</b><br>{esc(state["final_decisions"][paper]["reason"])}</td></tr>' for paper,reviews in sorted(reviews_by_paper.items()))}</tbody></table></div><details><summary>Complete final shared state</summary>{json_block(state)}</details></section>
<section><h2>6. Every retained prompt and answer</h2><p>These 18 rows come directly from the two durable Results packages: <a href="../systematic_review_screening_results.ep"><code>systematic_review_screening_results.ep</code></a> and <a href="../systematic_review_adjudication_results.ep"><code>systematic_review_adjudication_results.ep</code></a>.</p><div class="scroll"><table class="prompt-table"><thead><tr><th>Phase</th><th>Agent</th><th>Question</th><th>User prompt</th><th>System prompt</th><th>Answer</th><th>Comment</th></tr></thead><tbody>{prompt_rows}</tbody></table></div></section>
<section><h2>7. What the stress test exposed</h2><div class="two"><div class="panel"><h3>What worked</h3><p>Atomic queue mutation, exactly two assignments per paper, viewer-specific disclosure, stable interview-local snapshots, and reuse of one state across two runs.</p></div><div class="panel"><h3>What required improvement</h3><p>Snapshot context originally disappeared after one question; reads now persist until explicitly refreshed. Complex Jinja indexing is covered by integration tests, while <code>my_claim</code> remains preferable for information control. Results JSONL initially dropped shared state; serialization now preserves it.</p></div></div></section>
<div class="navlinks"><a href="work_pool.html">← Atomic work pool</a><a href="index.html">Index</a><span></span></div><footer>Generated from the runnable machine, two saved Results packages, and their complete shared-state audits.</footer></main></body></html>'''
    OUT.write_text(body)
    return OUT


def main() -> None:
    from examples.build_shared_state_case_study_site import CSS

    print(f"Wrote {build(css=CSS)}")


if __name__ == "__main__":
    main()
