"""
Synthetic Policy Generator

This macro generates realistic company policy documents based on company details.
Users provide information about their company (industry, size, culture, etc.) and
select a policy type, and the macro generates a comprehensive, company-specific
policy document that's 5-20 pages long.

Example usage:
    macro.output(params={
        "company_name": "TechCorp Inc.",
        "industry": "Software Development",
        "company_size": "50-200 employees",
        "policy_type": "Time Off and Leave",
        "company_culture": "Flexible, remote-friendly, work-life balance focused"
    })
"""

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionList,
    QuestionNumerical,
)
from edsl import Scenario
import textwrap


# Single-level generation: Generate sections with content directly
q_generate_policy = QuestionList(
    question_name="policy_sections",
    question_text=textwrap.dedent(
        """\
        You are creating a {{ scenario.policy_type }} policy for a company
        with the following characteristics:

        <company_details>
        Company: {{ scenario.company_name }}
        Industry: {{ scenario.industry }}
        Size: {{ scenario.company_size }}
        Culture: {{ scenario.company_culture }}
        Location: {{ scenario.location }}
        </company_details>

        Generate a comprehensive policy document with 6-10 major sections.
        For each section, provide:
        1. A section title
        2. 2-4 paragraphs of detailed, professional policy content

        Return a list of dictionaries with this format:
        [
            {
                "section_title": "Section Name",
                "content": "Detailed policy content for this section (2-4 paragraphs)..."
            },
            ...
        ]

        Make the content:
        - Specific to {{ scenario.company_name }} and {{ scenario.industry }}
        - Appropriate for {{ scenario.location }} jurisdiction
        - Reflective of the culture: {{ scenario.company_culture }}
        - Professional and realistic with specific details, numbers, or examples
        - Company-specific, not generic

        Examples of sections for different policy types:
        - Time Off: Overview, PTO Accrual, Sick Leave, Parental Leave, Holidays, Request Process
        - Remote Work: Eligibility, Equipment, Work Hours, Communication, Security, Performance
        - Expense Reimbursement: Eligible Expenses, Approval Process, Submission, Payment Timeline

        Return ONLY the list of dictionaries, nothing else.
        """
    ),
)

# Build the jobs pipeline - much simpler now
jobs_object = Survey([q_generate_policy]).to_jobs()

# Initial survey to collect company information
initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="company_name",
            question_text="What is your company name?",
        ),
        QuestionFreeText(
            question_name="industry",
            question_text="What industry is your company in? (e.g., 'Software Development', 'Healthcare', 'Manufacturing', 'Retail')",
        ),
        QuestionMultipleChoice(
            question_name="company_size",
            question_text="What is your company size?",
            question_options=[
                "1-10 employees (startup)",
                "11-50 employees (small)",
                "51-200 employees (medium)",
                "201-1000 employees (large)",
                "1000+ employees (enterprise)",
            ],
        ),
        QuestionMultipleChoice(
            question_name="policy_type",
            question_text="What type of policy do you want to generate?",
            question_options=[
                "Time Off and Leave",
                "Remote Work and Flexible Schedule",
                "Expense Reimbursement",
                "Professional Development and Training",
                "Health and Wellness Benefits",
                "Code of Conduct and Ethics",
                "Equipment and Technology Use",
                "Travel and Business Expenses",
            ],
        ),
        QuestionFreeText(
            question_name="company_culture",
            question_text="Describe your company culture in a few words (e.g., 'collaborative and innovative', 'traditional and hierarchical', 'startup culture with flexibility')",
        ),
        QuestionMultipleChoice(
            question_name="location",
            question_text="Primary location/jurisdiction for this policy?",
            question_options=[
                "United States (federal)",
                "California, USA",
                "New York, USA",
                "United Kingdom",
                "Canada",
                "European Union",
                "Australia",
            ],
        ),
    ]
)

# Output formatter - expand the list of section dictionaries into individual scenarios
scenario_list_output = (
    OutputFormatter(description="Structured Policy Data", output_type="ScenarioList")
    .select("scenario.*", "answer.policy_sections")
    .expand("answer.policy_sections")
    .to_scenario_list()
    .unpack_dict(field="policy_sections", drop_field=True)
)

# Markdown table preview
markdown_document = (
    OutputFormatter(description="Policy Document (Markdown)", output_type="markdown")
    .select("scenario.*", "answer.policy_sections")
    .expand("answer.policy_sections")
    .to_scenario_list()
    .unpack_dict(field="policy_sections", drop_field=True)
    .table(tablefmt="github")
    .to_string()
)

# Rich table for terminal
rich_preview = (
    OutputFormatter(description="Policy Preview (Rich)", output_type="rich")
    .select("scenario.*", "answer.policy_sections")
    .expand("answer.policy_sections")
    .to_scenario_list()
    .unpack_dict(field="policy_sections", drop_field=True)
    .table(tablefmt="rich")
)

# DOCX FileStore output - note: don't provide filename to get FileStore object
docx_output = (
    OutputFormatter(
        description="Policy Document (DOCX FileStore)", output_type="FileStore"
    )
    .select("scenario.*", "answer.policy_sections")
    .expand("answer.policy_sections")
    .to_scenario_list()
    .unpack_dict(field="policy_sections", drop_field=True)
    .to_docx()
)

# Excel output for data analysis
excel_output = (
    OutputFormatter(description="Policy Data (Excel)", output_type="FileStore")
    .select("scenario.*", "answer.policy_sections")
    .expand("answer.policy_sections")
    .to_scenario_list()
    .unpack_dict(field="policy_sections", drop_field=True)
    .to_excel()
)

macro = Macro(
    application_name="synthetic_policy",
    display_name="Synthetic Policy Generator",
    short_description="Generate realistic, company-specific policy documents.",
    long_description="""This application generates comprehensive company policy documents
    based on company characteristics. Users provide details about their company (name, industry,
    size, culture, location) and select a policy type. The macro then generates a detailed,
    multi-page policy document with company-specific content that reflects the organization's
    culture and industry requirements.""",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "scenario_list": scenario_list_output,
        "markdown": markdown_document,
        "rich": rich_preview,
        "docx": docx_output,
        "excel": excel_output,
    },
    default_formatter_name="scenario_list",
    default_params={
        "company_size": "51-200 employees (medium)",
        "location": "United States (federal)",
    },
)

if __name__ == "__main__":
    output = macro.output(
        params={
            "company_name": "Stellar Innovations",
            "industry": "Software Development",
            "company_size": "51-200 employees (medium)",
            "policy_type": "Remote Work and Flexible Schedule",
            "company_culture": "Remote-first, async communication, results-oriented, global team",
            "location": "United States (federal)",
        }
    )

    print("\n=== Generated Policy Structure ===")
    print(output.rich)

    print("\n=== Policy Data Details ===")
    sl = output.scenario_list
    print(f"Generated {len(sl)} policy sections")

    if len(sl) > 0:
        print(f"\nColumns: {list(sl[0].keys())}")
        print(f"\nFirst section:")
        first = sl[0]
        print(f"  Title: {first.get('section_title', 'N/A')}")
        content_preview = (
            first.get("content", "N/A")[:200] + "..."
            if len(first.get("content", "")) > 200
            else first.get("content", "N/A")
        )
        print(f"  Content: {content_preview}")

    print("\n=== File Outputs ===")
    try:
        docx_fs = output.docx
        print(f"DOCX FileStore: {type(docx_fs)}")
        print(f"  Path: {docx_fs.path if docx_fs else 'None'}")
        print(f"  Save with: docx_fs.save('company_policy.docx')")
    except Exception as e:
        print(f"DOCX Error: {e}")

    try:
        excel_fs = output.excel
        print(f"\nExcel FileStore: {type(excel_fs)}")
        print(f"  Path: {excel_fs.path if excel_fs else 'None'}")
        print(f"  Save with: excel_fs.save('policy_data.xlsx')")
    except Exception as e:
        print(f"Excel Error: {e}")
