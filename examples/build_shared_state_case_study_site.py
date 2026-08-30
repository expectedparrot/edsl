"""Build the browsable HTML companion to the shared-state Gemini case studies."""

from __future__ import annotations

import ast
import copy
import html
import inspect
import json
import re
from pathlib import Path

import black
from examples.shared_state_gemini_game_smoke import GAMES
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "shared_state_case_studies"
REPORT = ROOT / "docs" / "shared_state_case_studies.md"
AUDIT = ROOT / "examples" / "shared_state_gemini_complete_audit.json"
RERUNS = ROOT / "examples" / "shared_state_gemini_case_study_reruns.json"
FORECAST_RESULTS = ROOT / "examples" / "shared_state_forecast_results.json"

GAME_ORDER = [
    "dictator", "ultimatum", "trust", "bilateral_trade", "negotiation",
    "matrix", "repeated_matrix", "centipede", "nash_demand", "money_request",
    "beauty", "market_entry", "common_pool", "cheap_talk", "signaling",
    "principal_agent", "sealed_auction", "ascending_auction", "double_auction",
    "binary_market", "deferred_acceptance", "serial_matching", "voting",
    "coalition", "resource_allocation", "budget", "register", "counter",
    "delphi", "forecast", "private_signal", "agenda", "document", "log",
    "message_board", "work_pool",
]

CSS = """
:root{--ink:#17211b;--muted:#637168;--paper:#fafbf7;--card:#fff;--line:#dce5dd;
--green:#176b4d;--deep:#113d2d;--mint:#e8f4ed;--amber:#b56518;--code:#14201a}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);
color:var(--ink);font:16.5px/1.62 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--green)}header{padding:72px 24px 56px;color:#fff;background:linear-gradient(125deg,#123c2d,#176b4d 60%,#347b61)}
.wrap,main{width:min(1120px,calc(100% - 40px));margin:auto}h1{max-width:900px;margin:0 0 14px;
font:750 clamp(2.4rem,6vw,4.8rem)/1.02 Georgia,serif;letter-spacing:-.035em}header p{max-width:820px;margin:0;color:#dcece3;font-size:1.18rem}
main{padding:42px 0 88px}.eyebrow{margin:0 0 8px;color:#bce2cc;text-transform:uppercase;letter-spacing:.12em;font-size:.78rem;font-weight:800}
h2{margin:52px 0 17px;font:700 2rem/1.16 Georgia,serif}h3{margin:0 0 8px;font-size:1.08rem}.lede{font-size:1.12rem;max-width:830px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}.stat{min-width:135px;padding:13px 17px;border:1px solid #ffffff35;border-radius:12px;background:#ffffff12}.stat b{display:block;font-size:1.5rem}.stat span{color:#dcece3;font-size:.82rem}
.toolbar{position:sticky;top:0;z-index:5;padding:13px 0;background:#fafbf7ee;backdrop-filter:blur(9px);border-bottom:1px solid var(--line)}
.toolbar .wrap{display:flex;gap:14px;align-items:center;justify-content:space-between}.toolbar a{text-decoration:none;font-weight:700}.toolbar input{width:min(430px,55vw);padding:10px 13px;border:1px solid var(--line);border-radius:9px;background:white;font:inherit}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}.card,.panel,.callout{border:1px solid var(--line);border-radius:14px;background:var(--card)}
.card{display:block;padding:20px;color:inherit;text-decoration:none;transition:.15s transform,.15s box-shadow}.card:hover{transform:translateY(-2px);box-shadow:0 9px 24px #123c2d16}.card small{color:var(--green);font-weight:800}.card h3{margin:5px 0 8px}.card p{margin:0;color:var(--muted);font-size:.94rem}.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.tag{padding:3px 8px;border-radius:999px;background:var(--mint);color:var(--green);font-size:.75rem;font-weight:750}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{padding:22px}.panel p:last-child{margin-bottom:0}.result{border-left:5px solid var(--green);background:var(--mint)}
.callout{padding:18px 22px;border-left:5px solid var(--amber);background:#fff8ec}.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:20px 0}.fact{padding:14px 16px;border:1px solid var(--line);border-radius:11px;background:white}.fact small{display:block;color:var(--muted)}
table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:11px 13px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#eef4ef}td code{font-size:.85rem}.scroll{overflow:auto;border-radius:12px}
.prompt-table{min-width:1500px}.prompt-table .prompt-cell{min-width:430px}.prompt-table .comment-cell{min-width:300px}.prompt-table td pre{margin:0;max-height:330px;padding:14px;white-space:pre-wrap;overflow:auto;font-size:12px}
pre{overflow:auto;padding:21px 23px;border-radius:12px;background:var(--code);color:#e8f2eb;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}.key{color:#78c8ff}.str{color:#a8d989}.num{color:#f6c177}.bool{color:#ff7ab2}
.highlight{margin:16px 0 24px}.highlight pre{margin:0}.highlight .k,.highlight .kn,.highlight .kc{color:#ff7ab2;font-weight:650}.highlight .s,.highlight .s1,.highlight .s2,.highlight .sd{color:#a8d989}.highlight .c,.highlight .c1{color:#7f9689;font-style:italic}.highlight .mi,.highlight .mf{color:#f6c177}.highlight .nf,.highlight .nc{color:#62d6b1}.highlight .nb{color:#78c8ff}.highlight .o{color:#c5a3ff}
details{margin:18px 0}summary{cursor:pointer;color:var(--green);font-weight:750}.navlinks{display:flex;justify-content:space-between;gap:14px;margin:56px 0 0;padding-top:22px;border-top:1px solid var(--line)}footer{margin-top:62px;color:var(--muted);font-size:.9rem}
@media(max-width:720px){.two{grid-template-columns:1fr}.toolbar .wrap{align-items:stretch;flex-direction:column}.toolbar input{width:100%}header{padding-top:54px}}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def highlight_json(value: object) -> str:
    raw = html.escape(json.dumps(value, indent=2, ensure_ascii=False))
    raw = re.sub(r'(&quot;.*?&quot;)(\s*:)', r'<span class="key">\1</span>\2', raw)
    raw = re.sub(r'(:\s*)(&quot;.*?&quot;)', r'\1<span class="str">\2</span>', raw)
    raw = re.sub(r'(?<![\w;])(true|false|null)(?!\w)', r'<span class="bool">\1</span>', raw)
    return re.sub(r'(?<![\w;])(-?\d+(?:\.\d+)?)(?!\w)', r'<span class="num">\1</span>', raw)


def highlight_python(source: str) -> str:
    return highlight(source, PythonLexer(), HtmlFormatter())


class _TutorialTransformer(ast.NodeTransformer):
    """Remove case-study harness conveniences from displayed programs."""

    def __init__(self, game: str, machine_name: str):
        self.game = game
        self.machine_name = machine_name

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if (node.module or "").startswith("examples.shared_state_dsl"):
            return None
        return node

    def visit_Name(self, node: ast.Name):
        if node.id == "SPEC":
            return ast.copy_location(ast.Name(self.machine_name, node.ctx), node)
        return node

    def visit_Call(self, node: ast.Call):
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "_agent":
            if not node.args:
                raise ValueError("_agent call requires a name")
            traits = ast.Dict(
                keys=[ast.Constant(keyword.arg) for keyword in node.keywords],
                values=[keyword.value for keyword in node.keywords],
            )
            return ast.copy_location(
                ast.Call(
                    func=ast.Name("Agent", ast.Load()),
                    args=[],
                    keywords=[
                        ast.keyword(arg="name", value=node.args[0]),
                        ast.keyword(arg="traits", value=traits),
                    ],
                ),
                node,
            )
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name != self.game:
            self.generic_visit(node)
            return node
        node.name = "build_experiment"
        self.generic_visit(node)
        expanded = []
        for statement in node.body:
            if (
                isinstance(statement, ast.Return)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "_simultaneous"
            ):
                expanded.extend(self._expand_simultaneous(statement.value))
            else:
                expanded.append(statement)
        node.body = expanded
        return node

    def _expand_simultaneous(self, call: ast.Call) -> list[ast.stmt]:
        machine, target, question, writer, agents = call.args
        if not isinstance(target, ast.Constant) or not isinstance(target.value, str):
            raise ValueError("tutorial generator requires a literal state target")
        if not isinstance(writer, ast.Lambda):
            raise ValueError("tutorial generator requires a declarative write lambda")
        target_name = target.value

        class ReplaceLambdaNames(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name):
                if node.id == writer.args.args[0].arg:
                    return ast.copy_location(ast.Name(target_name, node.ctx), node)
                if node.id == writer.args.args[1].arg:
                    return ast.copy_location(copy.deepcopy(question), node)
                return node

        write = ReplaceLambdaNames().visit(copy.deepcopy(writer.body))
        shared_keyword = ast.keyword(arg=target_name, value=copy.deepcopy(machine))
        states = ast.Assign(
            targets=[ast.Name("states", ast.Store())],
            value=ast.Call(
                func=ast.Name("SharedStateMap", ast.Load()),
                args=[ast.Call(func=ast.Name("SharedState", ast.Load()), args=[], keywords=[shared_keyword])],
                keywords=[ast.keyword(arg="state_id", value=ast.JoinedStr(values=[
                    ast.Constant(f"tutorial-{self.game}-"),
                    ast.FormattedValue(ast.Call(ast.Name("uuid4", ast.Load()), [], []), -1),
                ]))],
            ),
        )
        handle = ast.Assign(
            targets=[ast.Name(target_name, ast.Store())],
            value=ast.Attribute(
                ast.Call(
                    ast.Attribute(ast.Name("states", ast.Load()), "by", ast.Load()),
                    [ast.Constant("game")], [],
                ),
                target_name, ast.Load(),
            ),
        )
        survey = ast.Assign(
            targets=[ast.Name("survey", ast.Store())],
            value=ast.Call(ast.Name("Survey", ast.Load()), [ast.List([
                ast.Call(ast.Attribute(ast.Name(target_name, ast.Load()), "read", ast.Load()), [], []),
                copy.deepcopy(question), write,
            ], ast.Load())], []),
        )
        people = ast.Assign(
            targets=[ast.Name("people", ast.Store())],
            value=ast.Call(ast.Name("AgentList", ast.Load()), [copy.deepcopy(agents)], []),
        )
        schedule = ast.Assign(
            targets=[ast.Name("schedule", ast.Store())],
            value=ast.Call(
                ast.Attribute(ast.Name("InterviewSchedule", ast.Load()), "rounds", ast.Load()),
                [],
                [
                    ast.keyword(arg="count", value=ast.Constant(1)),
                    ast.keyword(arg="within_round", value=ast.Constant("concurrent")),
                    ast.keyword(arg="state_visibility", value=ast.Constant("snapshot")),
                    ast.keyword(
                        arg="finalize_when",
                        value=ast.Call(ast.Attribute(ast.Name(target_name, ast.Load()), "is_complete", ast.Load()), [], []),
                    ),
                ],
            ),
        )
        result = ast.Return(ast.Tuple([
            ast.Name("survey", ast.Load()), ast.Name("people", ast.Load()),
            ast.Name("schedule", ast.Load()),
        ], ast.Load()))
        return [states, handle, survey, people, schedule, result]


def standalone_source(game: str, machine_source: str, experiment_source: str) -> str:
    """Produce and validate one dependency-free tutorial program."""
    machine_name = f"{game}_machine"
    machine_tree = ast.parse(machine_source)
    experiment_tree = ast.parse(experiment_source)
    transformer = _TutorialTransformer(game, machine_name)
    machine_tree = transformer.visit(machine_tree)
    experiment_tree = transformer.visit(experiment_tree)
    machine_tree.body = [
        node for node in machine_tree.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str))
    ]
    imports = ast.parse("""\
from uuid import uuid4

from edsl import (
    Agent, AgentList, InterviewSchedule, Model, QuestionFreeText,
    QuestionMultipleChoice, QuestionNumerical, QuestionRank, Survey,
)
""").body
    machine_tree.body = [
        node for node in machine_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "edsl.sharedstate"
        or not isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    public_import = next(
        node for node in machine_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "edsl.sharedstate"
    )
    imported = {alias.name for alias in public_import.names}
    public_import.names.extend(
        ast.alias(name)
        for name in ("SharedState", "SharedStateMap", "current")
        if name not in imported
    )
    experiment_tree.body = [node for node in experiment_tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    runner = ast.parse("""
if __name__ == "__main__":
    survey, agents, schedule = build_experiment()
    results = (
        survey.by(agents)
        .by(Model("gemini-2.5-flash", service_name="google"))
        .run(
            cache=False,
            disable_remote_cache=True,
            disable_remote_inference=True,
            interview_schedule=schedule,
            max_concurrency=5,
        )
    )
    print(results)
""").body
    tree = ast.Module(imports + machine_tree.body + experiment_tree.body + runner, [])
    tree = ast.fix_missing_locations(tree)
    source = black.format_str(ast.unparse(tree) + "\n", mode=black.Mode())
    compiled = compile(source, f"<tutorial:{game}>", "exec")
    exec(compiled, {"__name__": "tutorial_import_check"})
    forbidden = ("_agent(", "_simultaneous(", "SPEC", "from examples.")
    if any(token in source for token in forbidden):
        raise RuntimeError(f"{game} tutorial retained a private dependency")
    return source


def parse_report() -> list[dict]:
    text = REPORT.read_text()
    category = ""
    found = []
    for block in re.split(r"(?=^### \d+\.)", text, flags=re.M):
        before = text[: text.find(block)] if block in text else ""
        cats = re.findall(r"^## (.+)$", before, flags=re.M)
        if cats:
            category = cats[-1]
        title = re.search(r"^### \d+\. (.+)$", block, flags=re.M)
        if not title:
            continue
        def field(label: str) -> str:
            match = re.search(rf"\*\*{re.escape(label)}\.\*\*\s+(.+?)(?=\n\n|\Z)", block, re.S)
            return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
        found.append({"title": title.group(1), "category": category,
                      "scenario": field("Scenario"), "result": field("Result"),
                      "lesson": field("What it showed")})
    if len(found) != len(GAME_ORDER):
        raise RuntimeError(f"Expected 36 report cases, found {len(found)}")
    for game, case in zip(GAME_ORDER, found):
        case["game"] = game
    return found


def machine_and_experiment(game: str) -> tuple[dict, dict, str, str, str]:
    survey, agents, schedule = GAMES[game]()
    survey_data = survey.to_dict()
    state_steps = survey_data["state_steps"]
    steps = []
    for phase in ("before_writes", "reads", "writes"):
        for question, entries in state_steps.get(phase, {}).items():
            for item in entries:
                steps.append((phase, question, item))
    definition = next(item["definition"] for _, _, item in steps if "definition" in item)
    machines = definition["machines"]
    machine = machines.get("game") or next(iter(machines.values()))
    schedule_data = {
        "kind": schedule.kind, "group_by": schedule.group_by,
        "order_by": schedule.order_by, "rounds": schedule.count,
        "within_round": schedule.within_round,
        "state_visibility": schedule.state_visibility,
        "round_order": schedule.round_order,
        "finalize_when_complete": schedule.finalize_when is not None,
    }
    experiment = {
        "questions": [{"name": q.question_name, "type": q.question_type,
                       "text": str(q.question_text),
                       "options": getattr(q, "question_options", None)} for q in survey.questions],
        "agents": [{"name": a.name, "traits": dict(a.traits)} for a in agents],
        "schedule": schedule_data,
        "survey_state_steps": [{"phase": p, "question": q,
                                "operation": i.get("command", i.get("kind", p))}
                               for p, q, i in steps],
    }
    source = inspect.getsource(GAMES[game])
    match = re.search(r"from examples\.shared_state_dsl\.([\w_]+) import", source)
    module = f"{match.group(1)}.py" if match else "shared_state_gemini_game_smoke.py"
    machine_path = ROOT / "examples" / "shared_state_dsl" / module
    machine_source = machine_path.read_text() if machine_path.exists() else ""
    experiment_source = inspect.getsource(GAMES[game])
    return machine, experiment, module, machine_source, experiment_source


def shell(title: str, body: str, description: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(description)}"><title>{esc(title)}</title><style>{CSS}</style></head><body>{body}</body></html>'''


def contribution_rows(run: dict, agents: list[dict]) -> str:
    answers = run.get("answers", [])
    versions = run.get("read_versions", [])
    count = len(agents)
    if count and len(answers) > count and len(answers) % count == 0:
        rounds = len(answers) // count
        records = []
        for agent_index, agent in enumerate(agents):
            for round_index in range(rounds):
                answer_index = agent_index * rounds + round_index
                version_index = round_index * count + agent_index
                records.append((
                    agent, round_index + 1, answers[answer_index],
                    versions[version_index] if version_index < len(versions) else "—",
                ))
    else:
        records = [
            (agent, None, answers[index] if index < len(answers) else {},
             versions[index] if index < len(versions) else "—")
            for index, agent in enumerate(agents)
        ]
    return "".join(
        f"<tr><td>{index + 1}</td><td>{esc(agent['name'])}</td>"
        f"<td>{esc(round_number or '—')}</td>"
        f"<td><code>{esc(json.dumps(agent['traits'], ensure_ascii=False))}</code></td>"
        f"<td><code>{esc(json.dumps(answer, ensure_ascii=False))}</code></td>"
        f"<td>{esc(version)}</td></tr>"
        for index, (agent, round_number, answer, version) in enumerate(records)
    )


def forecast_results_table() -> str:
    if not FORECAST_RESULTS.exists():
        return ""
    captured = json.loads(FORECAST_RESULTS.read_text())
    rows = "".join(
        f"<tr><td>{esc(row['agent'])}</td><td>{esc(row['round'])}</td>"
        f"<td class=\"prompt-cell\"><pre>{esc(row['user_prompt'])}</pre></td>"
        f"<td class=\"prompt-cell\"><pre>{esc(row['system_prompt'])}</pre></td>"
        f"<td><code>{esc(row['answer'])}</code></td>"
        f"<td class=\"comment-cell\">{esc(row.get('comment', ''))}</td></tr>"
        for row in captured["rows"]
    )
    return f'''<h3 style="margin-top:30px">The complete Results rows</h3><p>This is the prompt data retained by the actual six-row EDSL <code>Results</code> object. Nothing in these cells has been reconstructed or abbreviated. The durable package is <a href="../shared_state_forecast_results.ep"><code>shared_state_forecast_results.ep</code></a>.</p><div class="scroll"><table class="prompt-table"><thead><tr><th>Agent</th><th>Round</th><th>User prompt</th><th>System prompt</th><th>Answer</th><th>Comment</th></tr></thead><tbody>{rows}</tbody></table></div>'''


def page(case: dict, run: dict, number: int, prev_case: dict | None, next_case: dict | None) -> str:
    machine, experiment, module, machine_source, experiment_source = machine_and_experiment(case["game"])
    tutorial_source = standalone_source(case["game"], machine_source, experiment_source)
    fields = machine.get("fields", {})
    commands = machine.get("commands", {})
    schedule = experiment["schedule"]
    questions = experiment["questions"]
    agents = experiment["agents"]
    rows = contribution_rows(run, agents)
    results_table = forecast_results_table() if case["game"] == "forecast" else ""
    qrows = "".join(f"<tr><td><code>{esc(q['name'])}</code></td><td>{esc(q['type'])}</td><td>{esc(q['text'])}</td></tr>" for q in questions)
    steps = experiment["survey_state_steps"]
    srows = "".join(f"<tr><td>{i+1}</td><td>{esc(s['phase'].replace('_',' '))}</td><td><code>{esc(s['question'])}</code></td><td><code>{esc(s['operation'])}</code></td></tr>" for i,s in enumerate(steps))
    prev_link = f'<a href="{prev_case["game"]}.html">← {esc(prev_case["title"])}</a>' if prev_case else "<span></span>"
    next_link = f'<a href="{next_case["game"]}.html">{esc(next_case["title"])} →</a>' if next_case else "<span></span>"
    body = f'''
<header><div class="wrap"><p class="eyebrow">Case study {number:02d} · {esc(case['category'])}</p><h1>{esc(case['title'])}</h1><p>{esc(case['scenario'])}</p><div class="stats"><div class="stat"><b>{len(agents)}</b><span>agents</span></div><div class="stat"><b>{len(commands)}</b><span>machine commands</span></div><div class="stat"><b>{len(run.get('read_versions',[]))}</b><span>recorded reads</span></div></div></div></header>
<div class="toolbar"><div class="wrap"><a href="index.html">← All case studies</a><span>Gemini 2.5 Flash · local inference</span></div></div>
<main>
<p class="lede">This page connects one concrete social-science experiment to the state machine that enforced it and the real Gemini responses that changed its state.</p>
<section><h2>1. The machine</h2><div class="two"><div class="panel"><h3>What it stores</h3><p><b>{esc(machine.get('name','Machine'))}</b> has {len(fields)} durable field{'s' if len(fields)!=1 else ''}: {', '.join(f'<code>{esc(x)}</code>' for x in fields) or 'none'}.</p><p>Its public view exposes {', '.join(f'<code>{esc(x)}</code>' for x in machine.get('view',{})) or 'no fields'}.</p></div><div class="panel"><h3>How it changes</h3><p>Survey interviews can issue {', '.join(f'<code>{esc(x)}</code>' for x in commands) or 'no commands'}. Inputs are validated and each accepted command is applied atomically.</p><p>Completion predicate: <b>{'defined' if machine.get('complete_when') else 'none'}</b>. Close effects: <b>{len(machine.get('close_effects',[]))}</b>.</p></div></div>
<details><summary>Inspect the complete serialized Machine</summary><pre>{highlight_json(machine)}</pre></details></section>
<section><h2>2. Complete, standalone Python</h2><p>This is one copyable program: it defines the machine, creates the agents and Survey, selects the schedule, runs Gemini locally, and prints the Results. It uses only public EDSL imports—there are no repository-local imports or private helper functions.</p>{highlight_python(tutorial_source)}</section>
<section><h2>3. The experiment</h2><div class="facts"><div class="fact"><small>Schedule</small><b>{esc(schedule['kind'])}</b></div><div class="fact"><small>Within round</small><b>{esc(schedule['within_round'] or 'serial')}</b></div><div class="fact"><small>State visibility</small><b>{esc(schedule['state_visibility'] or 'live')}</b></div><div class="fact"><small>Rounds</small><b>{esc(schedule['rounds'] or 'until complete')}</b></div></div><div class="scroll"><table><thead><tr><th>Question</th><th>Type</th><th>Prompt</th></tr></thead><tbody>{qrows}</tbody></table></div><h3 style="margin-top:28px">Survey state sequence</h3><p>These explicit read and write steps determine when interviews observe shared state and when their answers become commands.</p><div class="scroll"><table><thead><tr><th>#</th><th>Phase</th><th>Question boundary</th><th>Operation</th></tr></thead><tbody>{srows}</tbody></table></div></section>
<section><h2>4. What happened</h2><div class="two"><div class="panel result"><h3>Observed result</h3><p>{esc(case['result'])}</p></div><div class="panel"><h3>Final shared state</h3><pre>{highlight_json(run.get('final_state',{}))}</pre></div></div><h3 style="margin-top:28px">What each agent contributed</h3><div class="scroll"><table><thead><tr><th>#</th><th>Agent</th><th>Round</th><th>Private traits</th><th>Answer</th><th>Read version</th></tr></thead><tbody>{rows}</tbody></table></div>{results_table}</section>
<section><h2>5. State evolution</h2><p>The recorded read versions were <code>{esc(run.get('read_versions',[]))}</code>. The committed command sequence was <code>{esc(run.get('commands',[]))}</code>.</p><div class="callout"><b>How to read this:</b> agents sharing a version decided from the same snapshot; increasing versions mean later interviews could observe earlier commits. Command order is commit order, not necessarily interview launch order.</div><details><summary>Inspect raw run summary</summary><pre>{highlight_json(run)}</pre></details></section>
<section><h2>6. What this example teaches us</h2><p class="lede">{esc(case['lesson'])}</p><p>This is one behavioral realization, not an estimate of Gemini's average behavior. Its main purpose is to test whether the machine, survey, visibility, and schedule jointly express the intended experiment.</p></section>
<div class="navlinks">{prev_link}<a href="index.html">Index</a>{next_link}</div><footer>Generated from the runnable Survey, serialized Machine, Gemini audit, and case-study report. No result was invented for this page.</footer></main>'''
    return shell(case["title"], body, case["scenario"])


def index_page(cases: list[dict], runs: dict[str, dict]) -> str:
    sections = []
    for category in dict.fromkeys(c["category"] for c in cases):
        subset = [c for c in cases if c["category"] == category]
        cards = "".join(f'''<a class="card" href="{c['game']}.html" data-search="{esc((c['title']+' '+c['scenario']+' '+c['lesson']).lower())}"><small>{GAME_ORDER.index(c['game'])+1:02d}</small><h3>{esc(c['title'])}</h3><p>{esc(c['scenario'])}</p><div class="tags"><span class="tag">{len(runs[c['game']].get('answers',[]))} responses</span><span class="tag">{len(runs[c['game']].get('commands',[]))} commits</span></div></a>''' for c in subset)
        sections.append(f'<section><h2>{esc(category)}</h2><div class="grid">{cards}</div></section>')
    body = f'''<header><div class="wrap"><p class="eyebrow">Expected Parrot · EDSL shared state</p><h1>Thirty-six machines, thirty-six real experiments</h1><p>A linked field guide to the new shared-state DSL. Every case study describes the machine, Survey design, Gemini responses, read visibility, command history, final state, and what the run exposed.</p><div class="stats"><div class="stat"><b>36</b><span>state machines</span></div><div class="stat"><b>36</b><span>completed Gemini cases</span></div><div class="stat"><b>4</b><span>research domains</span></div></div></div></header><div class="toolbar"><div class="wrap"><a href="../economic_games_lab.html">Simulation laboratory</a><input id="filter" type="search" placeholder="Filter machines, mechanisms, or findings…" aria-label="Filter case studies"></div></div><main><p class="lede">These pages are not toy descriptions detached from code. Each combines the actual serialized Machine and Survey with the saved output of a local <code>gemini-2.5-flash</code> run.</p><div class="callout"><b>Reading the collection:</b> start with the scenario, then compare the schedule's visibility rule with the read versions. That relationship tells you what information each agent could actually use.</div>{''.join(sections)}<footer>Source: <a href="../shared_state_gemini_game_smoke.py">runnable experiments</a> · <a href="../../docs/shared_state_case_studies.md">case-study analysis</a> · generated by <a href="../build_shared_state_case_study_site.py">build script</a></footer></main><script>const q=document.querySelector('#filter');q.addEventListener('input',()=>{{const s=q.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>c.hidden=!c.dataset.search.includes(s));}});</script>'''
    return shell("EDSL Shared-State Case Studies", body, "Thirty-six real Gemini experiments built with the EDSL shared-state DSL.")


def main() -> None:
    cases = parse_report()
    audit = json.loads(AUDIT.read_text())
    reruns = json.loads(RERUNS.read_text())
    runs = {run["game"]: run for run in audit["runs"]}
    runs.update({run["game"]: run for run in reruns["runs"]})
    if FORECAST_RESULTS.exists():
        captured = json.loads(FORECAST_RESULTS.read_text())
        binding = captured["shared_state"]["bindings"][0]
        events = binding["events"]
        runs["forecast"] = {
            "game": "forecast",
            "answers": [
                {"probability": row["answer"]} for row in captured["rows"]
            ],
            "commands": [
                event["command"] for event in events if event["kind"] == "write"
            ],
            "final_state": binding["exit_snapshots"][0]["state"],
            "read_versions": [
                event["version"] for event in events if event["kind"] == "read"
            ],
        }
        forecast_case = next(case for case in cases if case["game"] == "forecast")
        forecast_case["result"] = (
            "In the prompt-capture run, A revised 30% to 45%, B remained at "
            "50%, and C revised 70% to 54%. All second-round estimates used "
            "the same version-3 snapshot."
        )
    missing = set(GAME_ORDER) - runs.keys()
    if missing:
        raise RuntimeError(f"Missing run data: {sorted(missing)}")
    OUT.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(cases):
        previous = cases[i - 1] if i else None
        following = cases[i + 1] if i + 1 < len(cases) else None
        (OUT / f"{case['game']}.html").write_text(page(case, runs[case["game"]], i + 1, previous, following))
    (OUT / "index.html").write_text(index_page(cases, runs))
    print(f"Wrote {len(cases) + 1} pages to {OUT}")


if __name__ == "__main__":
    main()
