# EDSL App Development Guide

A comprehensive guide for building EDSL applications based on analysis of the existing codebase architecture and patterns.

## Overview

EDSL apps follow a consistent pattern: collect user input via an initial survey, process that input through a jobs pipeline, and format the output for consumption. Apps are designed to be self-contained, reusable components that combine survey logic, AI agent interactions, and data transformation.

## Core Architecture

### App Components

Every EDSL app consists of four core components:

1. **Initial Survey** - Collects user input parameters
2. **Jobs Object** - Defines the AI processing logic
3. **Output Formatters** - Transform results for presentation
4. **App Instance** - Orchestrates the entire workflow

### Basic App Structure

```python
from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText

# 1. Define initial survey
initial_survey = Survey([
    QuestionFreeText(
        question_name="user_input",
        question_text="What would you like to analyze?"
    )
])

# 2. Define processing logic
jobs_object = survey_with_ai_logic.to_jobs()

# 3. Define output formatting
output_formatter = (
    OutputFormatter(name="Results")
    .select("answer.key_field")
    .to_markdown()
)

# 4. Create app instance
app = App(
    application_name="My App",
    description="Brief description of what the app does",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters=[output_formatter]
)
```

## App Types

### 1. General Purpose Apps

**Pattern**: Survey input → AI processing → Formatted output

**Examples**: auto_survey.py, meal_planner.py, jeopardy.py

**Key characteristics**:
- Use the base `App` class
- Custom `jobs_object` with Survey and Agent logic
- Multiple output formatters for different presentation formats

```python
# Example: Auto Survey Generator
app = App(
    description="Automatically generate a survey based on user input",
    application_name="auto_survey",
    initial_survey=initial_survey,
    jobs_object=job,
    output_formatters=[output_formatter]
)
```

### 2. Ranking Apps

**Pattern**: Item list → Pairwise comparisons → Ranked results

**Examples**: food_health.py

**Key characteristics**:
- Use specialized `RankingApp` class
- Requires `QuestionMultipleChoice` for comparisons
- Automatically generates pairwise comparison logic

```python
from edsl.app import RankingApp

app = RankingApp(
    ranking_question=comparison_question,
    option_fields=['item_1', 'item_2'],
    application_name="Item Ranker",
    description="Ranks items using pairwise comparisons",
    option_base="item",
    rank_field="rank"
)
```

### 3. TrueSkill Apps

**Pattern**: Item list → Batch comparisons → TrueSkill ratings

**Key characteristics**:
- Use `TrueSkillApp` class
- Implements TrueSkill algorithm for more sophisticated ranking
- Better for larger item sets than simple pairwise ranking

### 4. Persona Generation Apps

**Pattern**: Survey analysis → Dimension extraction → Agent creation

**Examples**: create_personas.py

**Key characteristics**:
- Analyze existing surveys to identify relevant dimensions
- Generate agent blueprints based on dimensional analysis
- Use `SurveyAttachmentFormatter` to process input surveys

## Component Deep Dive

### Initial Surveys

The initial survey collects parameters that drive the app's logic. Common patterns:

**Text Input**:
```python
QuestionFreeText(
    question_name="topic",
    question_text="What topic should we analyze?"
)
```

**Multiple Choice**:
```python
QuestionMultipleChoice(
    question_name="format",
    question_text="What format do you prefer?",
    question_options=["markdown", "html", "pdf"]
)
```

**Checkbox for Multiple Selections**:
```python
QuestionCheckBox(
    question_name="features",
    question_text="Which features do you want?",
    question_options=["feature1", "feature2", "feature3"]
)
```

**EDSL Object Input**:
```python
QuestionEDSLObject(
    question_name="input_survey",
    question_text="Provide the Survey to analyze",
    expected_object_type="Survey"
)
```

### Jobs Objects

Jobs objects define the AI processing logic. They transform user input into AI agent interactions.

**Simple Question Processing**:
```python
question = QuestionFreeText(
    question_name="result",
    question_text="Process this: {{ scenario.user_input }}"
)
jobs_object = question.by(Agent())
```

**Multi-stage Pipeline**:
```python
# Stage 1: Generate ideas
ideas_question = QuestionList(
    question_name="ideas",
    question_text="Generate ideas for: {{ scenario.topic }}"
)

# Stage 2: Evaluate ideas
eval_question = QuestionMultipleChoice(
    question_name="best_idea",
    question_text="Which is the best idea: {{ scenario.ideas }}?",
    question_options="{{ scenario.ideas }}"
)

# Combine into pipeline
jobs_object = (
    Survey([ideas_question])
    .to_jobs()
    .select("ideas", "topic")
    .expand("ideas")
    .to(Survey([eval_question]))
)
```

### Output Formatters

Output formatters transform job results into the desired output format.

New API: pass a dict of named formatters and optionally set a default by name. A reserved `raw_results` formatter is always present and returns the unmodified results.

```python
from edsl.app.output_formatter import OutputFormatter

markdown_formatter = (
    OutputFormatter(description="Markdown Report")
    .to_markdown()
    .view()
)

app = App(
    # ...
    output_formatters={
        "report": markdown_formatter,
        # "raw_results" is available implicitly and returns the raw Results
    },
    default_formatter_name="report",  # optional; falls back to "raw_results"
)
```

**Basic Selection and Formatting**:
```python
formatter = (
    OutputFormatter(name="Basic Results")
    .select("answer.key_field")
    .to_markdown()
)
```

**Complex Transformations**:
```python
formatter = (
    OutputFormatter(name="Survey Generator")
    .select("generated_question_text", "generated_question_type")
    .to_scenario_list()
    .rename({"generated_question_text": "question_text"})
    .to_survey()
)
```

**Multiple Output Formats**:
```python
markdown_formatter = (
    OutputFormatter(name="Markdown View")
    .select("answer.content")
    .to_markdown()
    .view()
)

docx_formatter = (
    OutputFormatter(name="Document Export")
    .select("answer.content")
    .to_markdown()
    .to_docx()
)

app = App(
    # ... other parameters
    output_formatters=[markdown_formatter, docx_formatter]
)
```

### Attachment Formatters

Attachment formatters modify input data before it's processed by the jobs object.

**Text Chunking**:
```python
from edsl.app.output_formatter import ScenarioAttachmentFormatter

chunk_formatter = (
    ScenarioAttachmentFormatter(name="Text Chunker")
    .chunk_text(
        field='input_text',
        chunk_size_field='words_per_chunk',
        unit='word'
    )
)

app = App(
    # ... other parameters
    attachment_formatters=[chunk_formatter]
)
```

**Survey to ScenarioList Conversion**:
```python
from edsl.app.output_formatter import SurveyAttachmentFormatter

survey_formatter = (
    SurveyAttachmentFormatter(name="Survey Processor")
    .to_scenario_list()
)
```

## Advanced Patterns

### Template-Driven Questions

Use Jinja2 templates to create dynamic questions:

```python
question = QuestionFreeText(
    question_name="analysis",
    question_text="""
    Analyze this data for {{ scenario.target_audience }}:
    <data>{{ scenario.input_data }}</data>

    Focus on: {{ scenario.analysis_type }}
    """
)
```

### Conditional Logic

Use skip rules to create conditional survey flows:

```python
survey = Survey([
    choice_question,
    conditional_question
]).add_skip_rule(
    "conditional_question",
    "{{ choice_question.answer }} != 'detailed'"
)
```

### Agent Customization

Create specialized agents with specific traits:

```python
expert_agent = Agent(
    name="domain_expert",
    traits={
        "expertise": "machine learning",
        "communication_style": "technical but accessible"
    }
)

jobs_object = survey.by(expert_agent)
```

## Development Best Practices

### 1. Start Simple

Begin with a basic app structure and add complexity incrementally:

```python
# Minimal viable app
app = App(
    application_name="simple_app",
    description="Does one thing well",
    initial_survey=simple_survey,
    jobs_object=basic_job,
    output_formatters=[basic_formatter]
)
```

### 2. Use Descriptive Names

Make your question names and field names clear and consistent:

```python
# Good
question_name="user_dietary_restrictions"

# Avoid
question_name="q1"
```

### 3. Modular Design

Keep components separate and reusable:

```python
# Define components separately
initial_survey = create_input_survey()
processing_job = create_processing_pipeline()
output_format = create_output_formatter()

# Compose into app
app = App(
    initial_survey=initial_survey,
    jobs_object=processing_job,
    output_formatters=[output_format]
)
```

### 4. Handle Edge Cases

Use validation and error handling in your questions:

```python
QuestionNumerical(
    question_name="quantity",
    question_text="How many items? (1-100)",
    min_value=1,
    max_value=100
)
```

### 5. Test with Real Data

Always test your app with realistic input:

```python
if __name__ == "__main__":
    result = app.output(params={
        "topic": "climate change",
        "audience": "general public"
    }, verbose=True)
    print(result)
```

## Common Pitfalls

### 1. Over-Complex Initial Surveys

Keep initial surveys focused. If you need many questions, consider breaking into multiple apps or using conditional logic.

### 2. Inefficient Job Pipelines

Avoid unnecessary data transformations. Each `.select()` and `.expand()` operation has computational cost.

### 3. Poor Error Handling

Always test edge cases like empty inputs, malformed data, and API failures.

### 4. Inflexible Output Formats

Design output formatters to be reusable across different contexts.

## Example: Complete App Implementation

Here's a complete example showing all components working together:

```python
import textwrap
from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.agents import Agent

# 1. Initial Survey - Collect user requirements
initial_survey = Survey([
    QuestionFreeText(
        question_name="product_name",
        question_text="What product do you want to analyze?"
    ),
    QuestionMultipleChoice(
        question_name="analysis_type",
        question_text="What type of analysis?",
        question_options=["market", "competitor", "feature"]
    )
])

# 2. Processing Agent
analyst = Agent(
    name="product_analyst",
    traits={"expertise": "product management and market research"}
)

# 3. Analysis Question
analysis_question = QuestionFreeText(
    question_name="analysis_result",
    question_text=textwrap.dedent("""
    Perform a {{ scenario.analysis_type }} analysis for {{ scenario.product_name }}.

    Provide a structured analysis including:
    - Key findings
    - Recommendations
    - Next steps
    """)
)

# 4. Jobs Pipeline
jobs_object = Survey([analysis_question]).by(analyst)

# 5. Output Formatters
markdown_output = (
    OutputFormatter(name="Analysis Report")
    .select("answer.analysis_result")
    .to_markdown()
)

summary_output = (
    OutputFormatter(name="Executive Summary")
    .select("answer.analysis_result")
    .to_scenario_list()
    .add_value("report_type", "executive_summary")
)

# 6. Complete App
app = App(
    application_name="Product Analyzer",
    description="Generates product analysis reports",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters=[markdown_output, summary_output]
)

# 7. Usage
if __name__ == "__main__":
    analysis = app.output(params={
        "product_name": "iPhone 15",
        "analysis_type": "competitor"
    })
    print(analysis)
```

## Next Steps

After building your app:

1. **Test thoroughly** with various input combinations
2. **Optimize performance** by profiling job execution times
3. **Add error handling** for edge cases and API failures
4. **Create documentation** explaining the app's purpose and usage
5. **Consider packaging** for distribution if the app is reusable

This guide covers the essential patterns for building EDSL apps. The framework is designed to be flexible, so feel free to experiment and adapt these patterns to your specific use cases.