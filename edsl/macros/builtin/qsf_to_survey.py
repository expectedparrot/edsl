"""
QSF to EDSL Survey Converter Macro

This builtin macro converts Qualtrics Survey Format (QSF) files into EDSL Survey objects.
It leverages the existing Survey.from_qsf() method but provides a macro interface for
batch processing, parameterization, and integration with the EDSL macro ecosystem.

No LLM calls are made - this is pure file parsing and data transformation.
"""

from edsl.macros import Macro
from edsl.questions import QuestionFileUpload, QuestionFreeText
from edsl.surveys import Survey
from edsl.macros import OutputFormatter


class QSFSurveyFormatter(OutputFormatter):
    """Custom formatter that converts QSF files to EDSL Survey objects."""

    def __init__(self, description="QSF to Survey Converter", allowed_commands=None, params=None, output_type="Survey", _stored_commands=None):
        super().__init__(
            description=description,
            allowed_commands=allowed_commands,
            params=params,
            output_type=output_type,
            _stored_commands=_stored_commands
        )

    def render(self, results, params=None):
        """
        Convert QSF file to EDSL Survey using the file path from params.

        Args:
            results: Results object (not used since pseudo_run=True)
            params: Dictionary containing user-provided parameters (nested under "params" key)

        Returns:
            Survey: The converted EDSL Survey object
        """
        if not params:
            raise ValueError("No parameters provided to QSF converter")

        # Parameters are nested under "params" key
        actual_params = params.get("params", {})

        qsf_file_path = actual_params.get("qsf_file")
        encoding = actual_params.get("encoding", "utf-8")

        if not qsf_file_path:
            raise ValueError("No QSF file path provided")

        # Use the existing Survey.from_qsf() method
        try:
            survey = Survey.from_qsf(qsf_file_path, encoding=encoding)
            return survey
        except Exception as e:
            raise RuntimeError(
                f"Failed to convert QSF file '{qsf_file_path}': {str(e)}"
            )


# Define the input survey to collect QSF file and options
initial_survey = Survey(
    [
        QuestionFileUpload(
            question_name="qsf_file",
            question_text="Upload the Qualtrics QSF file to convert to EDSL Survey format (provide local file path or URL)",
        ),
        QuestionFreeText(
            question_name="encoding",
            question_text="File encoding (optional, defaults to 'utf-8' - common encodings: utf-8, latin-1, cp1252)",
        ),
    ]
)

# Create a dummy survey that references the scenario variables to satisfy compatibility
from edsl.questions import QuestionFreeText

dummy_survey = Survey(
    [
        QuestionFreeText(
            question_name="dummy",
            question_text="QSF file path: {{ qsf_file }}, encoding: {{ encoding }}",
        )
    ]
)

# Create the macro
qsf_to_survey_macro = Macro(
    application_name="qsf_to_survey",
    display_name="QSF to EDSL Survey Converter",
    short_description="Convert Qualtrics QSF files to EDSL Survey objects",
    long_description="""
    This macro converts Qualtrics Survey Format (QSF) files into EDSL Survey objects.

    **Features:**
    - Supports both local QSF files and URLs
    - Handles various encoding formats
    - Preserves question structure, logic, and metadata
    - Returns a ready-to-use EDSL Survey object
    - No LLM calls required - pure file conversion

    **Supported QSF Features:**
    - Multiple choice questions
    - Text entry questions
    - Rating scales
    - Question groups/blocks
    - Basic branching logic
    - Question randomization

    **Usage:**
    1. Provide path to your QSF file (or URL)
    2. Optionally specify file encoding
    3. Receive converted EDSL Survey object
    4. Use the Survey with agents, scenarios, and models as normal

    **Example:**
    ```python
    # Convert QSF file
    result = macro.output({
        "qsf_file": "/path/to/survey.qsf",
        "encoding": "utf-8"
    })

    # Use the converted survey
    survey = result.survey
    results = survey.by(Agent()).run()
    ```

    **Note:** Complex QSF features like advanced branching may require manual
    adjustment after conversion. The macro handles most common survey formats.
    """,
    initial_survey=initial_survey,
    jobs_object=dummy_survey.to_jobs(),  # References scenario vars to satisfy compatibility
    output_formatters={"survey": QSFSurveyFormatter()},
    default_formatter_name="survey",
    # Default values for common use cases
    default_params={"encoding": "utf-8"},
    # Enable pseudo_run to avoid LLM calls
    pseudo_run=True,
)


if __name__ == "__main__":
    # Example usage and testing
    print("QSF to Survey Converter Macro")
    print("=" * 40)
    print(f"Application Name: {qsf_to_survey_macro.application_name}")
    print(f"Display Name: {qsf_to_survey_macro.display_name}")
    print(f"Pseudo Run: {qsf_to_survey_macro.pseudo_run}")
    print()

    # Print the questions that will be asked
    print("Input Parameters:")
    for q in qsf_to_survey_macro.initial_survey.questions:
        print(f"- {q.question_name}: {q.question_text}")

    print()
    print("Available Output Formatters:")
    if hasattr(qsf_to_survey_macro.output_formatters, "_data"):
        formatters = qsf_to_survey_macro.output_formatters._data
        for name, formatter in formatters.items():
            print(f"- {name}: {formatter.description}")
    else:
        print("- survey: QSF to Survey Converter")
