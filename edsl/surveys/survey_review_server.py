"""Local web review server for Survey git packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def create_review_app(package_path: str | Path):
    """Create a FastAPI app for reviewing and commenting on a Survey package."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Survey review server requires FastAPI. Install with: "
            "pip install 'edsl[services]' or pip install fastapi uvicorn."
        ) from exc

    from edsl.surveys import Survey

    path = Path(package_path)
    app = FastAPI(title="EDSL Survey Review")

    def load_survey():
        try:
            local_head = Survey.git.open(path).status()["commit"]
            return Survey.git.load(path, ref=local_head)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def snapshot() -> dict[str, Any]:
        survey = load_survey()
        comments = survey.git.comments.list()
        comments_by_question = _comments_by_question(comments)
        questions = []
        for index, question in enumerate(survey.questions):
            name = getattr(question, "question_name", f"q{index}")
            questions.append(
                {
                    "index": index,
                    "name": name,
                    "type": getattr(question, "question_type", type(question).__name__),
                    "text": getattr(question, "question_text", ""),
                    "comments": comments_by_question.get(name, []),
                }
            )
        return {
            "path": str(path),
            "questions": questions,
            "comments": comments,
            "history": survey.git.history(),
        }

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return REVIEW_HTML

    @app.get("/api/survey")
    async def api_survey():
        return JSONResponse(snapshot())

    @app.post("/api/comments")
    async def add_comment(payload: dict[str, Any]):
        body = str(payload.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=400, detail="Comment body is required.")
        survey = load_survey()
        result = survey.git.comments.add(
            question_name=payload.get("question_name"),
            path=payload.get("path"),
            body=body,
            author=payload.get("author") or "reviewer",
        )
        return JSONResponse({"result": result, "snapshot": snapshot()})

    @app.post("/api/comments/{thread_id}/reply")
    async def reply_comment(thread_id: str, payload: dict[str, Any]):
        body = str(payload.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=400, detail="Reply body is required.")
        survey = load_survey()
        result = survey.git.comments.reply(
            thread_id,
            body=body,
            author=payload.get("author") or "reviewer",
        )
        return JSONResponse({"result": result, "snapshot": snapshot()})

    @app.post("/api/comments/{thread_id}/resolve")
    async def resolve_comment(thread_id: str):
        survey = load_survey()
        result = survey.git.comments.resolve(thread_id)
        return JSONResponse({"result": result, "snapshot": snapshot()})

    @app.post("/api/comments/{thread_id}/reopen")
    async def reopen_comment(thread_id: str):
        survey = load_survey()
        result = survey.git.comments.reopen(thread_id)
        return JSONResponse({"result": result, "snapshot": snapshot()})

    return app


def _comments_by_question(comments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for comment in comments:
        target = comment.get("target") or {}
        question_name = target.get("question_name")
        if question_name:
            grouped.setdefault(str(question_name), []).append(comment)
    return grouped


REVIEW_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EDSL Survey Review</title>
<style>
:root {
  --bg: #f6f8f6;
  --panel: #ffffff;
  --ink: #17201b;
  --muted: #66706b;
  --line: #d9e0dc;
  --accent: #2d6cdf;
  --comment: #8a5b00;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
header { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
h1 { margin: 0; font-size: 26px; }
.sub { color: var(--muted); margin-top: 4px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.toolbar { padding: 12px 14px; border-bottom: 1px solid var(--line); font-weight: 700; }
.questions { display: grid; }
.question { padding: 14px; border-bottom: 1px solid var(--line); }
.question:last-child { border-bottom: 0; }
.q-head { display: flex; justify-content: space-between; gap: 12px; }
.q-name { font-weight: 700; }
.q-type { color: var(--muted); font-size: 12px; }
.q-text { margin-top: 8px; line-height: 1.4; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  background: #fff;
}
.chip.open { border-color: #e0c36d; background: #fff8dc; color: var(--comment); }
.comment-box {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
textarea, input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px;
  font: inherit;
  background: #fff;
}
textarea { min-height: 80px; resize: vertical; }
button {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  background: #fff;
  cursor: pointer;
}
button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.threads { display: grid; gap: 10px; padding: 12px; }
.thread { border: 1px solid var(--line); border-radius: 7px; padding: 10px; background: #fff; }
.thread.resolved { opacity: .7; }
.thread-head { display: flex; justify-content: space-between; gap: 8px; }
.thread-target { color: var(--muted); font-size: 12px; margin-top: 2px; }
.message { margin-top: 8px; white-space: pre-wrap; }
.reply { border-left: 3px solid var(--line); padding-left: 8px; margin-top: 8px; }
.row { display: flex; gap: 8px; align-items: center; }
.history { padding: 12px; display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
@media (max-width: 860px) { .grid { grid-template-columns: 1fr; } header { display: block; } }
</style>
</head>
<body>
<div class="shell">
  <header>
    <div>
      <h1>Survey Review</h1>
      <div class="sub" id="path"></div>
    </div>
    <button id="refresh">Refresh</button>
  </header>
  <div class="grid">
    <main class="panel">
      <div class="toolbar">Questions</div>
      <div class="questions" id="questions"></div>
    </main>
    <aside class="panel">
      <div class="toolbar">Comment Threads</div>
      <div class="threads" id="threads"></div>
      <div class="toolbar">Recent Versions</div>
      <div class="history" id="history"></div>
    </aside>
  </div>
</div>
<script>
let state = null;
const esc = value => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function load() {
  const res = await fetch("/api/survey");
  state = await res.json();
  render();
}

function render() {
  document.getElementById("path").textContent = state.path;
  document.getElementById("questions").innerHTML = state.questions.map(questionHtml).join("");
  document.getElementById("threads").innerHTML = state.comments.length
    ? state.comments.map(threadHtml).join("")
    : "<div class='thread'>No comments yet.</div>";
  document.getElementById("history").innerHTML = state.history.slice(0, 8).map(entry => `
    <div><code>${esc((entry.commit || "").slice(0, 8))}</code> ${esc(entry.message || "")}</div>
  `).join("");
}

function questionHtml(q) {
  const open = q.comments.filter(thread => thread.status === "open").length;
  const resolved = q.comments.length - open;
  return `
    <section class="question">
      <div class="q-head">
        <div>
          <div class="q-name">${esc(q.index + 1)}. ${esc(q.name)}</div>
          <div class="q-type">${esc(q.type)}</div>
        </div>
        <div class="chips">
          ${open ? `<span class="chip open">${open} open</span>` : ""}
          ${resolved ? `<span class="chip">${resolved} resolved</span>` : ""}
        </div>
      </div>
      <div class="q-text">${esc(q.text)}</div>
      <div class="comment-box">
        <textarea id="body-${esc(q.name)}" placeholder="Comment on this question"></textarea>
        <div class="row">
          <input id="author-${esc(q.name)}" placeholder="Author" value="reviewer">
          <button class="primary" onclick="addComment('${esc(q.name)}')">Add comment</button>
        </div>
      </div>
    </section>
  `;
}

function threadHtml(thread) {
  const first = (thread.messages || [])[0] || {};
  const replies = (thread.messages || []).slice(1);
  return `
    <div class="thread ${esc(thread.status)}">
      <div class="thread-head">
        <strong>${esc(targetLabel(thread.target || {}))}</strong>
        <span class="chip ${thread.status === "open" ? "open" : ""}">${esc(thread.status)}</span>
      </div>
      <div class="thread-target">${esc(first.author?.name || "unknown")} · ${esc(first.created_at || "")}</div>
      <div class="message">${esc(first.body || "")}</div>
      ${replies.map(reply => `
        <div class="reply">
          <div class="thread-target">${esc(reply.author?.name || "unknown")} · ${esc(reply.created_at || "")}</div>
          <div class="message">${esc(reply.body || "")}</div>
        </div>
      `).join("")}
      <div class="comment-box">
        <textarea id="reply-${esc(thread.id)}" placeholder="Reply"></textarea>
        <div class="row">
          <button onclick="reply('${esc(thread.id)}')">Reply</button>
          ${thread.status === "open"
            ? `<button onclick="resolveThread('${esc(thread.id)}')">Resolve</button>`
            : `<button onclick="reopenThread('${esc(thread.id)}')">Reopen</button>`}
        </div>
      </div>
    </div>
  `;
}

function targetLabel(target) {
  if (target.question_name) return target.path ? `${target.question_name} · ${target.path}` : target.question_name;
  return target.kind || "survey";
}

async function addComment(questionName) {
  const body = document.getElementById(`body-${questionName}`).value;
  const author = document.getElementById(`author-${questionName}`).value || "reviewer";
  await mutate("/api/comments", { question_name: questionName, path: "question_text", body, author });
}

async function reply(threadId) {
  const body = document.getElementById(`reply-${threadId}`).value;
  await mutate(`/api/comments/${threadId}/reply`, { body, author: "reviewer" });
}

async function resolveThread(threadId) {
  await mutate(`/api/comments/${threadId}/resolve`, {});
}

async function reopenThread(threadId) {
  await mutate(`/api/comments/${threadId}/reopen`, {});
}

async function mutate(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const data = await res.json();
  state = data.snapshot;
  render();
}

document.getElementById("refresh").addEventListener("click", load);
load();
</script>
</body>
</html>
"""
