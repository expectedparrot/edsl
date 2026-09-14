"""Local SSTI regression checks; no remote inference or real credentials.

Run in isolation from the repository's service/cleanup hooks:
python -m pytest -q --confcutdir=tests/security tests/security/test_ssti.py
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch
from uuid import uuid4

import pytest
from jinja2 import Template
from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from edsl import (
    Agent,
    Model,
    QuestionFreeText,
    QuestionMultipleChoice,
    Scenario,
    Survey,
)
from edsl.invigilators.question_item_processor import QuestionItemProcessor
from edsl.invigilators.question_numerical_processor import QuestionNumericalProcessor
from edsl.invigilators.question_option_processor import QuestionOptionProcessor
from edsl.prompts import Prompt
from edsl.questions import QuestionCheckBox, QuestionMatrix, QuestionRank
from edsl.questions.question_compute import QuestionCompute
from edsl.questions.question_image_generation import QuestionImageGeneration
from edsl.runner.service import JobService


@pytest.fixture
def canary(monkeypatch):
    key = "EDSL_SSTI_TEST_" + uuid4().hex
    value = "synthetic-" + uuid4().hex
    monkeypatch.setenv(key, value)
    getter = Mock(wraps=os.getenv)
    monkeypatch.setattr(os, "getenv", getter)
    expression = "cycler.__init__.__globals__.os.getenv(" + repr(key) + ")"
    return SimpleNamespace(
        key=key,
        value=value,
        getter=getter,
        expression=expression,
        text="{{ " + expression + " }}",
        options="{{ [" + expression + ", 'safe'] }}",
        number="{{ " + expression + " | length }}",
    )


def assert_blocked(canary, operation):
    # Rendering may reject the template or preserve it literally. Either way,
    # the getter must never be reached, even if a later fallback raises.
    try:
        operation()
    except SecurityError:
        pass
    assert not any(
        call.args and call.args[0] == canary.key
        for call in canary.getter.call_args_list
    ), "Template accessed the synthetic environment variable"


def test_probe_detects_an_unrestricted_jinja_environment(canary):
    assert Template(canary.text).render() == canary.value
    canary.getter.assert_called_once_with(canary.key)


def test_prompt_blocks_python_internals(canary):
    # Nonempty context prevents Prompt's no-variable fast path.
    with pytest.raises(SecurityError):
        Prompt(canary.text).render({"unused": 1})
    canary.getter.assert_not_called()


@pytest.mark.parametrize("shape", ["string", "list", "from", "add"])
def test_dynamic_options_block_python_internals(canary, shape):
    options = {
        "string": canary.options,
        "list": [canary.text, "safe"],
        "from": {"from": canary.options, "add": ["other"]},
        "add": {"from": "{{ scenario.options }}", "add": [canary.text]},
    }[shape]
    processor = QuestionOptionProcessor(Scenario({"options": ["safe"]}), {})
    assert_blocked(
        canary, lambda: processor.get_question_options({"question_options": options})
    )


def test_matrix_items_block_python_internals(canary):
    processor = QuestionItemProcessor(Scenario({}), {})
    assert_blocked(
        canary, lambda: processor.get_question_items({"question_items": canary.options})
    )


@pytest.mark.parametrize("bound", ["min_value", "max_value"])
def test_numerical_bounds_block_python_internals(canary, bound):
    processor = QuestionNumericalProcessor(Scenario({}), {})
    assert_blocked(
        canary,
        lambda: processor.get_question_numerical_value({bound: canary.number}, bound),
    )


@pytest.mark.parametrize("shape", ["string", "list", "from"])
def test_runner_options_block_python_internals(canary, shape):
    options = {
        "string": canary.options,
        "list": [canary.text, "safe"],
        "from": {"from": canary.options, "add": ["other"]},
    }[shape]
    assert_blocked(
        canary, lambda: JobService._resolve_question_options(options, {}, {})
    )


def test_question_text_blocks_python_internals(canary):
    question = QuestionFreeText(question_name="q", question_text=canary.text)
    assert_blocked(canary, lambda: question.render({}))


@pytest.mark.parametrize("field", ["question_options", "question_items"])
@pytest.mark.parametrize("explicit_sandbox", [False, True])
def test_native_question_rendering_preserves_sandbox(canary, field, explicit_sandbox):
    if field == "question_options":
        question = QuestionMultipleChoice(
            question_name="q", question_text="Pick", question_options=canary.options
        )
    else:
        question = QuestionMatrix(
            question_name="q",
            question_text="Rate",
            question_items=canary.options,
            question_options=[1, 2],
        )
    kwargs = {"jinja_env": SandboxedEnvironment()} if explicit_sandbox else {}
    assert_blocked(canary, lambda: question.render({}, **kwargs))


def test_compute_question_blocks_python_internals(canary):
    question = QuestionCompute(question_name="q", question_text=canary.text)
    assert_blocked(canary, lambda: question.answer_question_directly({}))


@pytest.mark.parametrize("surface", ["text", "option"])
def test_html_blocks_python_internals(canary, surface):
    question = (
        QuestionFreeText(question_name="q", question_text=canary.text)
        if surface == "text"
        else QuestionMultipleChoice(
            question_name="q",
            question_text="Pick",
            question_options=[canary.text, "safe"],
        )
    )
    assert_blocked(canary, question.html)


@pytest.mark.parametrize(
    "question_type", [QuestionMultipleChoice, QuestionCheckBox, QuestionRank]
)
def test_answer_translation_blocks_python_internals(canary, question_type):
    question = question_type(
        question_name="q",
        question_text="Pick",
        question_options=[canary.text, "safe"],
        use_code=True,
    )
    code = 0 if question_type is QuestionMultipleChoice else [0]
    assert_blocked(canary, lambda: question._translate_answer_code_to_answer(code, {}))


def test_survey_rule_blocks_python_internals(canary):
    from edsl.surveys.rules.rule import Rule
    from edsl.surveys.exceptions import SurveyRuleCannotEvaluateError

    # Quoted template is valid both for rule construction and Python evaluation.
    rule = Rule(
        current_q=0,
        next_q=1,
        question_name_to_index={"q": 0},
        priority=0,
        expression='"' + canary.text + '" != ""',
    )

    def evaluate():
        try:
            rule.evaluate({})
        except SurveyRuleCannotEvaluateError:
            pass

    assert_blocked(canary, evaluate)


def test_job_filter_blocks_python_internals(canary):
    from edsl.jobs.interview_tuple_filter import InterviewTupleFilter

    expression = "{{ " + canary.expression + " is not none }}"
    tuples = InterviewTupleFilter([{}], [{}], [{}], expression)
    assert_blocked(canary, lambda: list(iter(tuples)))


def test_interview_filter_blocks_python_internals(canary):
    from edsl.interviews import Interview

    interview = Interview(
        agent=Agent(),
        scenario=Scenario({}),
        model=Model("test"),
        survey=Survey([QuestionFreeText(question_name="q", question_text="Hi")]),
    )
    assert_blocked(
        canary, lambda: interview.include("{{ " + canary.expression + " is not none }}")
    )


def test_image_question_blocks_python_internals_before_provider_call(canary):
    generated = Mock()
    generator = SimpleNamespace(async_generate=AsyncMock(return_value=generated))
    question = QuestionImageGeneration(question_name="q", question_text=canary.text)
    with patch.object(
        QuestionImageGeneration,
        "image_generator",
        new_callable=PropertyMock,
        return_value=generator,
    ):
        assert_blocked(
            canary, lambda: asyncio.run(question.answer_question_directly({}))
        )
    generator.async_generate.assert_not_awaited()


def test_report_blocks_python_internals(canary):
    from edsl import Dataset
    from edsl.results.report import Report

    report = Report(Dataset([{"answer.q": ["safe"]}]), template=canary.text)
    assert_blocked(canary, report.generate)


def test_formatter_arguments_block_python_internals(canary):
    from edsl.macros.output_formatter import OutputFormatter

    # A real context key satisfies the existing substring check.
    formatter = OutputFormatter(output_type="markdown", allowed_commands=["echo"])
    formatter.echo("{{ prefix }}" + canary.text)
    target = SimpleNamespace(echo=lambda text: text)
    assert_blocked(canary, lambda: formatter.render(target, params={"prefix": ""}))


def test_fixed_html_template_does_not_execute_option_data(canary):
    question = QuestionMultipleChoice(
        question_name="q", question_text="Pick", question_options=[canary.text, "safe"]
    )
    assert canary.text in question.question_html_content
    canary.getter.assert_not_called()


def test_legitimate_native_values_and_substitution():
    scenario = Scenario({"options": ["Alpha", "Beta"], "minimum": 2, "name": "Ada"})
    assert QuestionOptionProcessor(scenario, {}).get_question_options(
        {"question_options": "{{ scenario.options }}"}
    ) == ["Alpha", "Beta"]
    assert (
        QuestionNumericalProcessor(scenario, {}).get_question_numerical_value(
            {"min_value": "{{ scenario.minimum }}"}, "min_value"
        )
        == 2
    )
    assert JobService._resolve_question_options(
        "{{ scenario.options }}", {}, scenario
    ) == ["Alpha", "Beta"]
    question = QuestionMultipleChoice(
        question_name="q",
        question_text="Hello {{ scenario.name }}",
        question_options="{{ scenario.options }}",
    )
    for kwargs in ({}, {"jinja_env": SandboxedEnvironment()}):
        rendered = question.render(scenario, **kwargs)
        assert rendered.question_options == ["Alpha", "Beta"]
        assert rendered.question_text == "Hello Ada"


def test_native_environment_retains_custom_sandbox_policy():
    from edsl.utilities.jinja import make_native_environment

    class RestrictedSandbox(SandboxedEnvironment):
        def is_safe_attribute(self, obj, attr, value):
            return attr != "secret" and super().is_safe_attribute(obj, attr, value)

    environment = RestrictedSandbox()
    environment.filters["double"] = lambda n: n * 2
    native = make_native_environment(environment)
    assert native.from_string("{{ [3 | double, 7] }}").render() == [6, 7]
    with pytest.raises(SecurityError):
        native.from_string("{{ obj.secret.upper() }}").render(
            obj=SimpleNamespace(secret="private")
        )
    assert environment.from_string("{{ [1, 2] }}").render() == "[1, 2]"


def test_question_rejects_unrestricted_environment_override():
    from jinja2 import Environment

    question = QuestionFreeText(question_name="q", question_text="{{ name }}")
    with pytest.raises(ValueError, match="SandboxedEnvironment"):
        question.render({"name": "Ada"}, jinja_env=Environment())


def test_html_preserves_explicitly_literal_template_syntax():
    question = QuestionMultipleChoice(
        question_name="q",
        question_text="Pick {{ scenario.name }}",
        question_options=["{% raw %}{{ 7 * 7 }}{% endraw %}", "{{ previous.answer }}"],
    )
    html = question.html(scenario={"name": "Ada"}, answers={"previous": "Beta"})
    assert "Pick Ada" in html
    assert "Beta" in html
    assert "{{ 7 * 7 }}" in html
    # Rendering must not mutate the source survey.
    assert question.question_text == "Pick {{ scenario.name }}"


@pytest.mark.parametrize("long_loop", [False, True])
def test_looped_option_labels_do_not_execute_python(canary, long_loop):
    from edsl import QuestionLinearScale, ScenarioList
    from edsl.questions.loop_processor import LongSurveyLoopProcessor

    # The comment makes this a valid dynamic-label input to the real constructor.
    # The expression only reads the test's synthetic key if eval is used.
    labels = (
        "{1: __import__('os').getenv("
        + repr(canary.key)
        + "), 2: 'safe'} # {{ marker }}"
    )
    question = QuestionLinearScale(
        question_name="q",
        question_text="Rate {{ scenario.name }}",
        question_options=[1, 2],
        option_labels=labels,
    )
    scenarios = ScenarioList([Scenario({"name": "Ada"})])
    with pytest.raises((ValueError, SyntaxError)):
        if long_loop:
            LongSurveyLoopProcessor(
                Survey([question]), scenarios
            ).process_templates_for_all_questions()
        else:
            question.loop(scenarios)
    canary.getter.assert_not_called()


def test_looped_option_labels_preserve_valid_mapping():
    from edsl import QuestionLinearScale, ScenarioList

    question = QuestionLinearScale(
        question_name="q",
        question_text="Rate",
        question_options=[1, 2],
        option_labels="{{ labels }}",
    )
    labels = {1: "Low", 2: "High"}
    result = question.loop(ScenarioList([Scenario({"labels": labels})]))
    assert result[0].option_labels == labels


def test_interview_filter_cannot_mutate_live_survey():
    from edsl.interviews import Interview

    survey = Survey(
        [
            QuestionFreeText(question_name="first", question_text="First?"),
            QuestionFreeText(question_name="second", question_text="Second?"),
        ]
    )
    interview = Interview(
        agent=Agent(traits={"age": 22}),
        scenario=Scenario({"city": "Boston"}),
        model=Model("test"),
        survey=survey,
    )
    before = survey.to_dict()
    with pytest.raises(SecurityError):
        interview.include("{% set _ = survey.delete_question(0) %}true")
    assert survey.to_dict() == before
    assert interview.include(
        "{{ agent.age == 22 and scenario.city == 'Boston' "
        "and model.model == 'test' and survey.questions | length == 2 }}"
    )


@pytest.mark.parametrize(
    "surface",
    [
        "string",
        "native",
        "native_override",
        "question",
        "question_override",
        "native_options",
        "prompt",
        "runner",
        "job_filter",
    ],
)
def test_public_callables_are_blocked_across_renderers(surface):
    from edsl.jobs.interview_tuple_filter import InterviewTupleFilter
    from edsl.utilities.jinja import make_environment, make_native_environment

    mutate = Mock(return_value="changed", unsafe_callable=False, alters_data=False)
    context = {"nested": {"obj": SimpleNamespace(mutate=mutate)}}
    template = "{{ nested.obj.mutate() }}"
    with pytest.raises(SecurityError):
        if surface == "string":
            make_environment().from_string(template).render(context)
        elif surface == "native":
            make_native_environment().from_string(template).render(context)
        elif surface == "native_override":
            make_native_environment(SandboxedEnvironment()).from_string(
                template
            ).render(context)
        elif surface in ("question", "question_override"):
            question = QuestionFreeText(question_name="q", question_text=template)
            kwargs = (
                {"jinja_env": SandboxedEnvironment()}
                if surface == "question_override"
                else {}
            )
            question.render(context, **kwargs)
        elif surface == "native_options":
            question = QuestionMultipleChoice(
                question_name="q",
                question_text="Pick",
                question_options="{{ [nested.obj.mutate(), 'safe'] }}",
            )
            question.render(context, jinja_env=SandboxedEnvironment())
        elif surface == "prompt":
            Prompt(template).render(context)
        elif surface == "runner":
            JobService._resolve_template_string(template, {}, context)
        elif surface == "job_filter":
            list(
                InterviewTupleFilter(
                    [{}], [context], [{}], "{{ scenario.nested.obj.mutate() }}"
                )
            )
    mutate.assert_not_called()


@pytest.mark.parametrize(
    "template",
    [
        "{{ data.clear() }}",
        "{{ data.update({'new': 1}) }}",
        "{{ data['values'].append(3) }}",
        "{{ action() }}",
    ],
)
def test_context_functions_and_container_mutations_are_denied(template):
    from edsl.utilities.jinja import make_environment

    data = {"values": [1, 2]}
    action = Mock(return_value="changed", unsafe_callable=False, alters_data=False)
    with pytest.raises(SecurityError):
        make_environment().from_string(template).render(data=data, action=action)
    assert data == {"values": [1, 2]}
    action.assert_not_called()


def test_read_only_method_names_do_not_allow_custom_implementations():
    from edsl.utilities.jinja import make_environment

    called = Mock()

    class CustomDict(dict):
        def get(self, key):
            called()

    with pytest.raises(SecurityError):
        make_environment().from_string("{{ obj.get('x') }}").render(obj=CustomDict())
    called.assert_not_called()


def test_allowed_template_helpers_and_capture_still_work():
    from edsl.utilities.jinja import make_environment, make_native_environment

    source = (
        "{% macro label(x) %}{{ x.strip().upper() }}{% endmacro %}"
        "{% set ns = namespace(total=0) %}"
        "{% for i in range(3) %}{% set ns.total = ns.total + i %}{% endfor %}"
        "{{ label(data.get('name')) }}:{{ ns.total }}:"
        "{{ dict(data.items()).keys() | list | join(',') }}"
    )
    assert (
        make_environment().from_string(source).render(data={"name": " Ada "})
        == "ADA:3:name"
    )
    assert make_native_environment().from_string("{{ data.get('values') }}").render(
        data={"values": [1, 2]}
    ) == [1, 2]
    prompt = Prompt("{{ vars.set('x', 5) }}{{ vars.get('x') }}").render({})
    assert str(prompt) == "5"
    assert prompt.captured_variables == {"x": 5}


def test_custom_callable_policy_is_preserved_without_mutating_override():
    from edsl.utilities.jinja import make_native_environment, require_sandbox

    class NoCalls(SandboxedEnvironment):
        def is_safe_callable(self, obj):
            return False

    for environment in (require_sandbox(NoCalls()), make_native_environment(NoCalls())):
        with pytest.raises(SecurityError):
            environment.from_string("{{ data.get('x') }}").render(data={"x": 1})
    original = SandboxedEnvironment()
    mutate = Mock(return_value="changed", unsafe_callable=False, alters_data=False)
    restricted = require_sandbox(original)
    assert original.is_safe_callable(mutate)
    assert not restricted.is_safe_callable(mutate)
