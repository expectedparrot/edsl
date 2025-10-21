"""
Synthetic Data Generator

This macro generates synthetic datasets as ScenarioLists based on user descriptions.
Users specify what kind of dataset they want, optionally including desired columns,
and the macro generates appropriate synthetic data.

The output is a ScenarioList where each scenario represents one row of data.

Example usage:
    macro.output(params={
        "dataset_description": "Customer data for an e-commerce company",
        "desired_columns": "customer_id, age, purchase_amount, product_category",
        "num_rows": 50
    })
"""

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText, QuestionNumerical
from edsl import Scenario
import textwrap


# Single question that generates the entire dataset
q_generate_dataset = QuestionList(
    question_name="dataset_rows",
    question_text=textwrap.dedent(
        """\
        Generate {{ scenario.num_rows }} rows of synthetic data for the following dataset:

        <dataset_description>
        {{ scenario.dataset_description }}
        </dataset_description>

        {% if scenario.desired_columns %}
        Include these columns in the dataset: {{ scenario.desired_columns }}
        You may add additional relevant columns if they would enhance the dataset.
        {% endif %}

        Requirements:
        - Generate exactly {{ scenario.num_rows }} complete rows of data
        - Each row should be a dictionary with column names as keys and realistic values
        - Make the values realistic and appropriate for the dataset context
        - Ensure variety across rows but maintain internal consistency within each row
        - For ID columns, use sequential or unique identifiers
        - For numeric columns, use appropriate ranges and distributions
        - For categorical columns, use a realistic set of categories
        - For date columns, use ISO format (YYYY-MM-DD)

        Return a list of {{ scenario.num_rows }} dictionaries, one per row.

        Example format for a customer dataset with 3 rows:
        [
            {"customer_id": 1001, "name": "Alice Smith", "age": 32, "city": "Seattle", "purchase_amount": 245.50},
            {"customer_id": 1002, "name": "Bob Jones", "age": 45, "city": "Portland", "purchase_amount": 189.99},
            {"customer_id": 1003, "name": "Carol White", "age": 28, "city": "Denver", "purchase_amount": 412.25}
        ]

        Return ONLY the list of dictionaries, nothing else.
        """
    ),
)

# Build the jobs pipeline - very simple, just one question
jobs_object = q_generate_dataset.by(Scenario.example())

# Initial survey to collect user input
initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="dataset_description",
            question_text="Describe the kind of dataset you want to generate (e.g., 'customer records for a retail company', 'experiment results with measurements', 'employee data for a tech company')",
        ),
        QuestionFreeText(
            question_name="desired_columns",
            question_text="(Optional) List specific columns you want included, comma-separated (e.g., 'name, age, email'). Leave blank to let the AI decide.",
        ),
        QuestionNumerical(
            question_name="num_rows",
            question_text="How many rows of data should be generated?",
            min_value=1,
            max_value=500,
        ),
    ]
)

# Output formatter to create ScenarioList
# Takes the list of row dictionaries and expands them into a ScenarioList
# The expand creates scenarios with 'dataset_rows' field containing the dict
# We use unpack_dict to flatten the nested dict into top-level scenario fields
output_formatter = (
    OutputFormatter(description="Synthetic Dataset", output_type="edsl_object")
    .select("answer.dataset_rows")
    .expand("answer.dataset_rows")
    .to_scenario_list()
    .unpack_dict(field="dataset_rows", drop_field=True)
)

# Markdown table preview
markdown_table = (
    OutputFormatter(description="Dataset Preview (Markdown)", output_type="markdown")
    .select("answer.dataset_rows")
    .expand("answer.dataset_rows")
    .to_scenario_list()
    .unpack_dict(field="dataset_rows", drop_field=True)
    .table(tablefmt="github")
    .to_string()
)

# Rich table for terminal display
rich_table = (
    OutputFormatter(description="Dataset Preview (Rich)", output_type="rich")
    .select("answer.dataset_rows")
    .expand("answer.dataset_rows")
    .to_scenario_list()
    .unpack_dict(field="dataset_rows", drop_field=True)
    .table(tablefmt="rich")
)

# Debug formatter to see raw output
debug_raw = OutputFormatter(
    description="Debug: Raw Output", output_type="edsl_object"
).select("answer.dataset_rows")

# Excel FileStore output
# Note: Don't provide filename parameter - it will write to disk and return None
# Without filename, to_excel returns a FileStore object that can be manipulated
excel_output = (
    OutputFormatter(description="Excel FileStore", output_type="edsl_object")
    .select("answer.dataset_rows")
    .expand("answer.dataset_rows")
    .to_scenario_list()
    .unpack_dict(field="dataset_rows", drop_field=True)
    .to_excel()
)

macro = Macro(
    application_name="synthetic_data",
    display_name="Synthetic Data Generator",
    short_description="Generate synthetic datasets from natural language descriptions.",
    long_description="This application generates synthetic datasets as ScenarioLists. Users describe the kind of data they want, optionally specify columns, and receive a ScenarioList where each scenario represents a row of realistic synthetic data.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "scenario_list": output_formatter,
        "markdown": markdown_table,
        "rich": rich_table,
        "excel": excel_output,
        "debug_raw": debug_raw,
    },
    default_formatter_name="scenario_list",
    default_params={
        "num_rows": 20,
        "desired_columns": "",
    },
)

if __name__ == "__main__":
    output = macro.output(
        params={
            "dataset_description": "Defense startups in a recent YC batch",
            "desired_columns": [
                "startup_name",
                "startup_description",
                "initial_customer_profile",
            ],
            "num_rows": 25,
        }
    )
