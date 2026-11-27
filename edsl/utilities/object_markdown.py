"""Read-only Markdown previews for saved EDSL objects."""

from __future__ import annotations

import json
from collections.abc import Mapping


class MarkdownPageError(ValueError):
    """The requested page does not exist or has an invalid size."""


class MarkdownPreviewMixin:
    def to_markdown(self, *, page: int = 1, page_size: int = 10) -> str:
        """Preview one page of this object without running it."""
        return object_markdown(self, page=page, page_size=page_size)


def _plain(value):
    """Represent values as data, including metadata-only summaries of attachments."""
    if isinstance(value, Mapping):
        if "base64_string" in value and ("path" in value or "mime_type" in value):
            return {k: value[k] for k in ("path", "mime_type") if k in value}
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _text(value):
    from ..questions.markdown_layout import text

    value = _plain(value)
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, default=str)
    return text(value)


def _fields(mapping):
    return "\n\n".join(
        f"**{_text(k)}**  \n{_text(v)}"
        for k, v in sorted(mapping.items(), key=lambda pair: str(pair[0]))
    )


def _agent(agent, number):
    heading = f"### Agent {number}"
    if agent.name:
        heading += f" — {_text(agent.name)}"
    # Reading .traits would execute a dynamic traits function.
    sections = [heading, _fields(agent._traits) or "*No static traits.*"]
    if agent.has_dynamic_traits_function:
        sections.append("*Additional traits are computed at runtime.*")
    if agent.instruction != agent.default_instruction:
        sections.append(_fields({"Instructions": agent.instruction}))
    if agent.codebook:
        sections.append("**Trait descriptions**\n\n" + _fields(agent.codebook))
    return "\n\n".join(sections)


def _rows(title, entries):
    from .simple_table import simple_table

    entries = list(entries)
    keys = sorted({key for _, row in entries for key in row}, key=str)
    # A wide or multiline record is easier to read as stacked fields.
    if keys and len(keys) <= 6:
        headers = [title, *(_text(k).ljust(3) for k in keys)]
        cells = [
            [str(i), *(_text(row[k]) if k in row else "" for k in keys)]
            for i, row in entries
        ]
        if all(
            len(cell.splitlines()) <= 1 for row in [headers, *cells] for cell in row
        ):
            table = simple_table(headers, cells, fmt="pipe")
            if len(table.partition("\n")[0]) <= 100:
                return table
    return "\n\n".join(
        f"### {title} {i}\n\n" + (_fields(row) or "*No fields.*") for i, row in entries
    )


def _model(model, number):
    saved = model.to_dict(add_edsl_version=False)
    details = {"Service": saved["inference_service"], **saved["parameters"]}
    if "connection" in saved:
        details["Connection"] = saved["connection"]
    if "prompt_plan" in saved:
        details["Prompt plan"] = saved["prompt_plan"]
    return f"### Model {number} — {_text(model.model)}\n\n" + _fields(details)


def _result(result, number):
    context = {"Iteration": result.data.get("iteration", 0)}
    if result.model is not None:
        context["Model"] = result.model.model
    if result.agent is not None:
        context["Agent"] = result.agent.name or result.agent._traits
    if result.scenario:
        context["Scenario"] = result.scenario
    return (
        f"### Result {number}\n\n"
        + _fields(context)
        + "\n\n**Answers**\n\n"
        + (_fields(result.answer) or "*No answers.*")
    )


def _groups(obj):
    """Return a heading, optional summary, and ordered (kind, sequence) groups."""
    from .. import (
        Agent,
        AgentList,
        Collection,
        Evaluation,
        Jobs,
        ModelList,
        Prompt,
        Results,
        Scenario,
        ScenarioList,
        Survey,
    )
    from ..language_models.language_model import LanguageModel
    from ..questions.question_base import QuestionBase

    if isinstance(obj, (Jobs, Evaluation)):
        groups = [
            ("Questions", obj.survey.questions),
            ("Agents", obj.agents),
            ("Scenarios", obj.scenarios),
            ("Judgment models" if isinstance(obj, Evaluation) else "Models", obj.models),
        ]
        summary = " · ".join(f"{label} {len(items)}" for label, items in groups)
        if isinstance(obj, Evaluation):
            return "Evaluation", summary, groups
        plan = obj.assignment_summary()
        layout = {"Assignment mode": plan["assignment_mode"]}
        if plan["interviews_per_iteration"] is not None:
            layout["Assigned interviews per iteration"] = plan["interviews_per_iteration"]
        for field, comparison in plan.get("paired_identifier_counts", {}).items():
            layout[f"Paired {field}"] = (
                f"{comparison['mismatched']} of {comparison['compared']} interviews "
                "pair an agent and scenario with different IDs."
            )
        if "interview_filter" in plan:
            layout["Interview filter"] = plan["interview_filter"]
        summary += "\n\n" + _fields(layout)
        if obj.treatment_assignment is not None:
            summary += "\n\n" + _fields(
                {"Treatment design": obj.treatment_assignment.design_id}
            )
        return "Jobs", summary, groups
    if isinstance(obj, Results) and obj.survey is not None:
        questions = obj.survey.questions
        sample = "\n".join(
            f"- **{_text(q.question_name)}** {_text(q.question_text)}" for q in questions[:3]
        )
        summary = f"**Saved survey** ({len(questions)} questions)\n\n{sample}"
        return "Results", summary, [("Results", obj)]
    if isinstance(obj, Survey):
        return obj.name or "Survey", "", [("Questions", obj.questions)]
    if isinstance(obj, Collection):
        summary = "\n\n".join(filter(None, [_text(obj.purpose), _fields(obj.metadata)]))
        if obj.tags:
            summary += "\n\n" + _fields({"Tags": obj.tags})
        return obj.name, summary.strip(), [("Members", obj.items)]
    if isinstance(obj, Scenario) and "base64_string" in obj and "path" in obj:
        return "FileStore", "", [("Files", [_plain(obj)])]
    if isinstance(obj, Prompt):
        return "Prompt", "", [("Lines", str(obj).splitlines())]
    for cls, title, kind in (
        (AgentList, "AgentList", "Agents"),
        (ScenarioList, "ScenarioList", "Scenarios"),
        (ModelList, "ModelList", "Models"),
        (Results, "Results", "Results"),
        (Agent, "Agent", "Agents"),
        (Scenario, "Scenario", "Scenarios"),
        (LanguageModel, "Model", "Models"),
        (QuestionBase, "Question", "Questions"),
    ):
        if isinstance(obj, cls):
            sequence = (
                obj if cls in (AgentList, ScenarioList, ModelList, Results) else [obj]
            )
            return title, "", [(kind, sequence)]
    raise TypeError(f"Markdown preview is unavailable for {type(obj).__name__}.")


def _section(obj, kind, items, indices, question_options):
    if kind == "Questions":
        from ..surveys.survey_markdown import questionnaire_items

        survey = getattr(obj, "survey", obj)
        if hasattr(survey, "questions"):
            return questionnaire_items(survey, indices, **question_options)
        return obj.to_markdown(**question_options)
    entries = ((i + 1, items[i]) for i in indices)
    if kind == "Judgment models":
        return _rows("Model", ((n, {"service": m.service_name, "model": m.model}) for n, m in entries))
    if kind == "Files":
        return _fields(items[0])
    if kind == "Scenarios":
        return _rows("Scenario", ((n, _plain(row)) for n, row in entries))
    if kind == "Members":
        return _rows("Member", ((n, row.to_dict()) for n, row in entries))
    if kind == "Lines":
        # Indented code keeps literal prompt text intact across page boundaries.
        return "\n".join("    " + line for _, line in entries)
    render = {"Agents": _agent, "Models": _model, "Results": _result}[kind]
    return "\n\n".join(render(item, n) for n, item in entries)


def object_markdown(
    obj,
    *,
    page: int = 1,
    page_size: int = 10,
    with_question_names: bool = False,
    with_question_types: bool = False,
    expand_options: bool = False,
) -> str:
    """Render only the requested entries, numbered from their original positions."""
    if any(type(n) is not int or n < 1 for n in (page, page_size)):
        raise MarkdownPageError("Page and page size must be positive integers.")
    from ..questions.markdown_layout import text

    title, summary, groups = _groups(obj)
    total = sum(len(items) for _, items in groups)
    pages = max(1, (total + page_size - 1) // page_size)
    if page > pages:
        raise MarkdownPageError(
            f"Requested page {page}. Choose a page from 1 to {pages}."
        )
    start = (page - 1) * page_size
    stop = min(start + page_size, total)
    sections = ["# " + text(title)]
    if summary:
        sections.append(summary)
    unit = groups[0][0] if len(groups) == 1 else "Components"
    sections.append(
        f"{unit} {start + 1}–{stop} of {total} · Page {page} of {pages}"
        if total
        else f"No {unit.lower()}."
    )
    question_options = dict(
        with_question_names=with_question_names,
        with_question_types=with_question_types,
        expand_options=expand_options,
    )
    offset = 0
    for kind, items in groups:
        indices = range(max(0, start - offset), min(len(items), stop - offset))
        if indices:
            if len(groups) > 1:
                sections.append("## " + kind)
            sections.append(_section(obj, kind, items, indices, question_options))
        offset += len(items)
    return "\n\n".join(sections)
