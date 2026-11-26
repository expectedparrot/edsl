"""Render a static questionnaire without evaluating survey expressions."""

import ast
import re
from operator import eq, ne
from collections import defaultdict

from ..questions.markdown_layout import text
from ..questions.question_multiple_choice import QuestionMultipleChoice
from .base import EndOfSurvey


def destination(target, size):
    if target == EndOfSurvey or target >= size:
        return "End survey"
    return f"Go to question {target + 1}"


def answer_comparison(expression):
    """Recognize a single piped answer compared with a scalar literal."""
    match = re.fullmatch(
        r"\s*\{\{\s*(\w+)\.answer\s*\}\}\s*(==|!=)\s*(.+?)\s*", expression
    )
    if not match:
        return None
    try:
        value = ast.literal_eval(match[3])
    except (ValueError, SyntaxError):
        return None
    if not isinstance(value, (str, float, int, bool)):
        return None
    return match[1], match[2], value


def inline_choice_route(survey, rule):
    """Move an unambiguous route beside its triggering single-choice answer."""
    # A pre-question skip can annotate the answer immediately before the skipped question.
    index = rule.current_q - 1 if rule.before_rule else rule.current_q
    if index < 0 or (rule.before_rule and rule.next_q != rule.current_q + 1):
        return None
    source = survey.questions[index]
    if not isinstance(source, QuestionMultipleChoice):
        return None
    if source.permissive or source.probabilistic_response is not None:
        return None
    values = source.question_options
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        return None
    comparison = answer_comparison(rule.expression)
    if comparison is None:
        return None
    question_name, operator, answer = comparison
    if question_name != source.question_name:
        return None
    if answer not in values or any("{{" in v or "{%" in v for v in values):
        return None
    target = destination(rule.next_q, len(survey.questions))
    matches = eq if operator == "==" else ne
    notes = {i: target for i, value in enumerate(values) if matches(value, answer)}
    return index, notes


def describe_condition(survey, expression):
    comparison = answer_comparison(expression)
    if comparison is not None:
        name, operator, value = comparison
        if name in survey.question_name_to_index:
            number = survey.question_name_to_index[name] + 1
            verb = "is" if operator == "==" else "is not"
            return f"the answer to question {number} {verb} “{text(value)}”"

    # A code span with a longer delimiter also preserves expressions with backticks.
    delimiter = "`" * (
        1 + max((len(run) for run in re.findall(r"`+", expression)), default=0)
    )
    return f"{delimiter} {expression} {delimiter}"


def rule_note(survey, rule):
    condition = describe_condition(survey, rule.expression)
    if rule.before_rule and rule.next_q == rule.current_q + 1:
        return f"Skip this question if {condition}."
    when = "Before answering" if rule.before_rule else "After answering"
    return (
        f"{when}, if {condition} → {destination(rule.next_q, len(survey.questions))}."
    )


def questionnaire(survey, *, with_question_names, with_question_types, expand_options):
    items = questionnaire_items(
        survey,
        range(len(survey.questions)),
        with_question_names=with_question_names,
        with_question_types=with_question_types,
        expand_options=expand_options,
    )
    return ("# " + text(survey.name or "Survey") + "\n\n" + items).rstrip()


def questionnaire_items(
    survey,
    indices,
    *,
    with_question_names=False,
    with_question_types=False,
    expand_options=False,
):
    """Render a window of questions with numbering and routing from the full survey."""
    rules = survey.rule_collection.non_default_rules
    notes = defaultdict(list)
    option_notes = {}
    # With competing or intersecting routes, keep the rules at their evaluation sites.
    inline = inline_choice_route(survey, rules[0]) if len(rules) == 1 else None
    if inline:
        index, routes = inline
        option_notes[index] = routes
    else:
        for rule in sorted(rules, key=lambda r: (not r.before_rule, -r.priority)):
            notes[rule.current_q].append(rule_note(survey, rule))

    sections = []
    for i in indices:
        question = survey.questions[i]
        sections.append(
            question.to_markdown(
                number=i + 1,
                option_notes=option_notes.get(i),
                with_question_names=with_question_names,
                with_question_types=with_question_types,
                expand_options=expand_options,
            )
        )
        sections.extend(notes.get(i, ()))
    return "\n\n".join(sections)
