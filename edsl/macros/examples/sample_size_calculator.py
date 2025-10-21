from edsl.macros import Macro
from edsl.surveys import Survey
from edsl.questions import (
    QuestionCompute,
    QuestionNumerical,
    QuestionLinearScale,
    QuestionMultipleChoice,
)
from edsl.macros import OutputFormatter
from edsl import Scenario

# Initial survey to gather parameters
initial_survey = Survey(
    [
        QuestionMultipleChoice(
            question_name="calculation_type",
            question_text="What would you like to calculate?",
            question_options=[
                "Sample size needed",
                "Margin of error for existing sample",
                "Number to invite for target sample size",
            ],
        ),
        QuestionNumerical(
            question_name="margin_of_error",
            question_text="What is your desired margin of error? (e.g., 0.05 for ±5%)",
        ),
        QuestionLinearScale(
            question_name="confidence_level",
            question_text="What confidence level do you want?",
            question_options=[80, 85, 90, 95, 99],
            option_labels={80: "80%", 85: "85%", 90: "90%", 95: "95%", 99: "99%"},
        ),
        QuestionNumerical(
            question_name="expected_response_rate",
            question_text="What is your expected response rate or proportion? (e.g., 0.5 for 50%)",
        ),
        QuestionNumerical(
            question_name="population_size",
            question_text="What is your population size? (Enter 0 or leave blank for infinite population)",
        ),
        QuestionNumerical(
            question_name="existing_sample_size",
            question_text="If calculating margin of error, what is your existing sample size? (Otherwise enter 0)",
        ),
        QuestionNumerical(
            question_name="target_sample_size",
            question_text="If calculating number to invite, what is your target sample size? (Otherwise enter 0)",
        ),
    ]
)

# Question to calculate sample size
q_sample_size = QuestionCompute(
    question_name="sample_size",
    question_text="""
{# Sample Size Calculator Jinja2 Macros #}

{# Macro to get Z-score based on confidence level #}
{% macro get_z_score(confidence_level) -%}
  {%- if confidence_level == 80 -%}1.282
  {%- elif confidence_level == 85 -%}1.440
  {%- elif confidence_level == 90 -%}1.645
  {%- elif confidence_level == 95 -%}1.960
  {%- elif confidence_level == 99 -%}2.576
  {%- else -%}1.960{# Default to 95% confidence #}
  {%- endif -%}
{%- endmacro %}

{# Macro to calculate sample size #}
{% macro calculate_sample_size(scenario) -%}
  {%- set margin_of_error = scenario.margin_of_error | default(0.05) -%}
  {%- set confidence_level = scenario.confidence_level | default(95) -%}
  {%- set expected_response_rate = scenario.expected_response_rate | default(0.5) -%}
  {%- set z_score = get_z_score(confidence_level) | float -%}

  {# Calculate sample size for infinite population #}
  {%- set numerator = (z_score ** 2) * expected_response_rate * (1 - expected_response_rate) -%}
  {%- set denominator = margin_of_error ** 2 -%}
  {%- set n0 = (numerator / denominator) -%}

  {# Apply finite population correction if population size is given #}
  {%- if scenario.population_size and scenario.population_size > 0 -%}
    {%- set n = n0 / (1 + ((n0 - 1) / scenario.population_size)) -%}
    {{- n | round(0, 'ceil') | int -}}
  {%- else -%}
    {{- n0 | round(0, 'ceil') | int -}}
  {%- endif -%}
{%- endmacro %}

{{ calculate_sample_size(scenario) }}
""",
)

# Question to calculate margin of error
q_margin_of_error = QuestionCompute(
    question_name="margin_of_error_calc",
    question_text="""
{# Macro to get Z-score based on confidence level #}
{% macro get_z_score(confidence_level) -%}
  {%- if confidence_level == 80 -%}1.282
  {%- elif confidence_level == 85 -%}1.440
  {%- elif confidence_level == 90 -%}1.645
  {%- elif confidence_level == 95 -%}1.960
  {%- elif confidence_level == 99 -%}2.576
  {%- else -%}1.960{# Default to 95% confidence #}
  {%- endif -%}
{%- endmacro %}

{# Macro to calculate margin of error #}
{% macro calculate_margin_of_error(scenario) -%}
  {%- set sample_size = scenario.existing_sample_size | default(100) -%}
  {%- set confidence_level = scenario.confidence_level | default(95) -%}
  {%- set observed_proportion = scenario.expected_response_rate | default(0.5) -%}
  {%- set z_score = get_z_score(confidence_level) | float -%}

  {%- if sample_size > 0 -%}
    {# Calculate standard error #}
    {%- set se_squared = (observed_proportion * (1 - observed_proportion)) / sample_size -%}
    {%- set se = (se_squared ** 0.5) -%}

    {# Apply finite population correction if needed #}
    {%- if scenario.population_size and scenario.population_size > 0 -%}
      {%- set fpc_squared = (scenario.population_size - sample_size) / (scenario.population_size - 1) -%}
      {%- set fpc = (fpc_squared ** 0.5) -%}
      {%- set se_adjusted = se * fpc -%}
      {%- set margin_of_error = z_score * se_adjusted -%}
    {%- else -%}
      {%- set margin_of_error = z_score * se -%}
    {%- endif -%}

    {{- (margin_of_error * 100) | round(2) -}}
  {%- else -%}
    0
  {%- endif -%}
{%- endmacro %}

{{ calculate_margin_of_error(scenario) }}
""",
)

# Question to calculate number to invite
q_number_to_invite = QuestionCompute(
    question_name="number_to_invite",
    question_text="""
{% macro calculate_number_to_invite(scenario) -%}
  {%- set required_sample_size = scenario.target_sample_size | default(0) -%}
  {%- set expected_response_rate = scenario.expected_response_rate | default(0.20) -%}

  {%- if expected_response_rate > 0 -%}
    {{- (required_sample_size / expected_response_rate) | round(0, 'ceil') | int -}}
  {%- else -%}
    0
  {%- endif -%}
{%- endmacro %}

{{ calculate_number_to_invite(scenario) }}
""",
)

# Create scenario for computation
s = Scenario({})

# Create survey with all calculation questions
survey = Survey([q_sample_size, q_margin_of_error, q_number_to_invite])

# Output formatter
output_formatter = OutputFormatter(
    description="Sample Size Calculator Results", output_type="docx"
).to_docx("sample_size_results.docx")

# Create the macro
macro = Macro(
    application_name="sample_size_calculator",
    display_name="Sample Size Calculator",
    short_description="Calculate required sample sizes for research studies.",
    long_description="This application helps you determine the sample size needed for your study, the margin of error for an existing sample, or how many people to invite to reach your target sample size. It accounts for confidence levels, expected response rates, and finite population corrections to provide accurate statistical estimates.",
    initial_survey=initial_survey,
    jobs_object=survey.by(s),
    output_formatters={"results": output_formatter},
)

if __name__ == "__main__":
    # Example 1: Calculate sample size needed
    print("=" * 60)
    print("Example 1: Calculate Required Sample Size")
    print("=" * 60)
    result1 = macro.output(
        {
            "calculation_type": "Sample size needed",
            "margin_of_error": 0.05,
            "confidence_level": 95,
            "expected_response_rate": 0.5,
            "population_size": 1000,
            "existing_sample_size": 0,
            "target_sample_size": 0,
        }
    )
    # MacroRunOutput cannot be subscripted - need to get actual data
    print(f"Result: {result1}")

    # Example 2: Calculate margin of error for existing sample
    print("\n" + "=" * 60)
    print("Example 2: Calculate Margin of Error")
    print("=" * 60)
    result2 = macro.output(
        {
            "calculation_type": "Margin of error for existing sample",
            "margin_of_error": 0.05,
            "confidence_level": 95,
            "expected_response_rate": 0.5,
            "population_size": 1000,
            "existing_sample_size": 278,
            "target_sample_size": 0,
        }
    )
    print(f"Result: {result2}")

    # Example 3: Calculate number to invite
    print("\n" + "=" * 60)
    print("Example 3: Calculate Number to Invite")
    print("=" * 60)
    result3 = macro.output(
        {
            "calculation_type": "Number to invite for target sample size",
            "margin_of_error": 0.05,
            "confidence_level": 95,
            "expected_response_rate": 0.3,
            "population_size": 0,
            "existing_sample_size": 0,
            "target_sample_size": 300,
        }
    )
    print(f"Result: {result3}")
    print("=" * 60)
