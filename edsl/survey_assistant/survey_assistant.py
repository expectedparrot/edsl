#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "claude-agent-sdk",
#     "anyio>=3.6.0",
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "edsl>=0.1.0",
#     "PyYAML>=6.0.0",
#     "pandas>=2.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
EDSL Survey Generator using Claude Agent SDK
Processes any document type and creates EDSL survey objects via YAML

Supported formats with smart handling:
- QSF: Pre-parsed to extract Qualtrics question structure
- CSV/TSV: Sampled (first 20 rows) for large files
- XLSX/XLS: Sampled (first 20 rows) for large files
- JSON: Sent as-is
- Text files: Sent as-is

Usage:
    uv run edsl_survey_generator.py file1.txt file2.csv file3.qsf file4.xlsx
"""

import anyio
import gzip
import json
import os
import sys
import io
import logging
import re
from html import unescape
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import yaml
import typer
from dotenv import load_dotenv
import csv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich.columns import Columns

# Load environment variables from .env file
load_dotenv()

# Try to import claude_agent_sdk with helpful error message
try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        UserMessage,
        query,
    )
except ImportError:
    print("\n" + "=" * 70)
    print("ERROR: claude-agent-sdk is not installed")
    print("=" * 70)
    print("\nTo install it, run:")
    print("  pip install claude-agent-sdk")
    print("\nOr if using uv:")
    print("  uv pip install claude-agent-sdk")
    print("\nFor more information, visit:")
    print("  https://github.com/anthropics/claude-agent-sdk-python")
    print("=" * 70 + "\n")
    raise

from edsl import QuestionBase, Survey
from edsl.questions import *  # Import all question types

app = typer.Typer()
console = Console()


class SuppressOutput:
    """Context manager to suppress stdout temporarily."""

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._original_stdout


def sample_csv_file(
    csv_content: str, max_rows: int = 10, delimiter: str = ","
) -> Dict[str, Any]:
    """Sample a CSV/TSV file to provide structure without sending all data.

    Args:
        csv_content: Raw CSV/TSV file content
        max_rows: Maximum number of data rows to include (default: 10)
        delimiter: Field delimiter (default: ',')

    Returns:
        Dictionary with CSV structure and sample data
    """
    try:
        lines = csv_content.strip().split("\n")
        total_rows = len(lines) - 1  # Exclude header

        # Parse CSV/TSV
        csv_reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
        rows = list(csv_reader)

        if not rows:
            return {"error": "Empty file"}

        header = rows[0]
        data_rows = rows[1:]

        # Sample data
        sample_rows = data_rows[:max_rows]

        return {
            "columns": header,
            "column_count": len(header),
            "total_rows": len(data_rows),
            "sample_rows": sample_rows,
            "sampled": len(data_rows) > max_rows,
            "delimiter": delimiter,
        }
    except Exception as e:
        return {"error": f"Failed to parse file: {e}"}


def sample_xlsx_file(file_path: Path, max_rows: int = 10) -> Dict[str, Any]:
    """Sample an XLSX file to provide structure without sending all data.

    Args:
        file_path: Path to XLSX file
        max_rows: Maximum number of data rows to include (default: 10)

    Returns:
        Dictionary with XLSX structure and sample data
    """
    try:
        try:
            import openpyxl

            use_openpyxl = True
        except ImportError:
            use_openpyxl = False

        if use_openpyxl:
            # Use openpyxl (lighter weight)
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet = wb.active

            rows = list(sheet.iter_rows(values_only=True))
            wb.close()
        else:
            # Fall back to pandas
            try:
                import pandas as pd

                df = pd.read_excel(file_path, nrows=max_rows + 1)  # +1 for header
                header = df.columns.tolist()
                data_rows = df.values.tolist()
                rows = [header] + data_rows
            except ImportError:
                return {
                    "error": "Neither openpyxl nor pandas is available for reading XLSX files"
                }

        if not rows:
            return {"error": "Empty XLSX file"}

        header = [str(cell) if cell is not None else "" for cell in rows[0]]
        data_rows = [
            [str(cell) if cell is not None else "" for cell in row] for row in rows[1:]
        ]

        # Sample data
        sample_rows = data_rows[:max_rows]

        return {
            "columns": header,
            "column_count": len(header),
            "total_rows": len(data_rows),
            "sample_rows": sample_rows,
            "sampled": len(data_rows) > max_rows,
            "sheet_name": sheet.title if use_openpyxl else "Sheet1",
        }
    except Exception as e:
        return {"error": f"Failed to parse XLSX: {e}"}


def parse_qsf_file(qsf_content: str) -> Dict[str, Any]:
    """Parse a QSF (Qualtrics Survey Format) file and extract questions.

    Args:
        qsf_content: Raw QSF file content (JSON string)

    Returns:
        Dictionary with parsed survey structure including questions
    """

    def strip_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        text = unescape(text)
        # Clean up whitespace
        text = " ".join(text.split())
        return text

    try:
        data = json.loads(qsf_content)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}

    parsed = {
        "survey_name": data.get("SurveyEntry", {}).get("SurveyName", "Unknown"),
        "questions": [],
    }

    # Extract questions from SurveyElements
    if "SurveyElements" in data:
        for element in data["SurveyElements"]:
            if element.get("Element") == "SQ":  # Survey Question
                payload = element.get("Payload", {})

                question = {
                    "question_id": payload.get("QuestionID", ""),
                    "question_text": strip_html(payload.get("QuestionText", "")),
                    "question_type": payload.get("QuestionType", ""),
                    "selector": payload.get("Selector", ""),
                    "sub_selector": payload.get("SubSelector", ""),
                    "choices": {},
                    "answers": {},
                    "validation": payload.get("Validation", {}),
                }

                # Extract choices
                if "Choices" in payload and isinstance(payload["Choices"], dict):
                    for choice_id, choice_data in payload["Choices"].items():
                        if isinstance(choice_data, dict):
                            question["choices"][choice_id] = strip_html(
                                choice_data.get("Display", "")
                            )

                # Extract answers (for matrix questions)
                if "Answers" in payload and isinstance(payload["Answers"], dict):
                    for ans_id, ans_data in payload["Answers"].items():
                        if isinstance(ans_data, dict):
                            question["answers"][ans_id] = strip_html(
                                ans_data.get("Display", "")
                            )

                parsed["questions"].append(question)

    return parsed


# Check for Anthropic API key
def check_api_key():
    """Check if Anthropic API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("\n[bold red]WARNING: No Anthropic API key found![/bold red]")
        console.print(
            "\n[yellow]The SurveyAssistant requires an Anthropic API key to function.[/yellow]"
        )
        console.print("\nPlease set your API key in one of these ways:")
        console.print("  1. Create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        console.print(
            "  2. Export it in your shell: export ANTHROPIC_API_KEY=your_key_here"
        )
        console.print("  3. Set it in your environment variables")
        console.print(
            "\nGet your API key from: [link]https://console.anthropic.com/[/link]\n"
        )
        return False
    return True


class SurveyAssistant:
    """Generates EDSL surveys from uploaded documents using Claude.

    Args:
        *file_paths: File paths to process
        spec_file: Path to EDSL specification file
        verbose_logs: If True, prints detailed debug logs during generation
        max_turns: Maximum number of turns for Claude's agent loop (default: 10)
    """

    def __init__(
        self,
        *file_paths,
        spec_file: Path = Path("EDSL_SPECIFICATION.md"),
        verbose_logs: bool = False,
        max_turns: int = 30,
    ):
        # Check for API key
        if not check_api_key():
            raise ValueError(
                "Anthropic API key is required. Please set ANTHROPIC_API_KEY environment variable."
            )

        self.spec_file = spec_file
        self.edsl_spec = self._load_specification()
        self.output_dir = Path("edsl_output")
        self.output_dir.mkdir(exist_ok=True)
        self.file_paths = [Path(fp) for fp in file_paths] if file_paths else []
        self._survey = None  # Will store the generated survey
        self._console = Console()  # Console for progress updates
        self.max_turns = max_turns  # Maximum turns for Claude agent

        # Setup logging
        self.verbose_logs = verbose_logs
        self.logger = logging.getLogger(f"SurveyAssistant.{id(self)}")
        if verbose_logs:
            self.logger.setLevel(logging.DEBUG)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
                self.logger.addHandler(handler)
        else:
            self.logger.setLevel(logging.WARNING)

    def _load_specification(self) -> str:
        """Load EDSL specification from markdown file."""
        if not self.spec_file.exists():
            console.print(
                f"[yellow]Warning: {self.spec_file} not found. Using basic EDSL knowledge.[/yellow]"
            )
            return ""

        with open(self.spec_file, "r") as f:
            return f.read()

    def _create_status_display(
        self, emoji: str, message: str, spinner: bool = False, style: str = "cyan"
    ):
        """Create a status display with optional spinner for Live display.

        Args:
            emoji: Emoji to display before the message
            message: The message to display
            spinner: Whether to show a spinner
            style: Rich style to apply

        Returns:
            Columns with spinner and text if spinner=True, otherwise just Text
        """
        text = Text(f"{emoji} {message}", style=style)
        if spinner:
            return Columns([Spinner("dots", style=style), text], padding=(0, 1))
        return text

    @property
    def survey(self) -> Optional[Survey]:
        """Get the generated Survey object. Generates it if not already created.

        Returns:
            The Survey object, generating it if necessary. Returns None if generation fails.
        """
        if self._survey is None:
            result = self.generate_survey()
            if not result.get("success", False):
                return None
        return self._survey

    def generate_survey(
        self,
        file_paths: Optional[List[Path]] = None,
        verbose: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Process multiple files and generate EDSL survey.

        Args:
            file_paths: Optional list of file paths. If not provided, uses the file paths
                       passed to the constructor.
            verbose: If True, returns detailed results dictionary. If False, returns simplified summary.
            debug: If True, streams Claude's responses to stdout in real-time for debugging.

        Returns:
            Dictionary with generation results and status. If verbose=False, returns simplified summary.
        """
        try:
            return anyio.run(self._generate_survey_async, file_paths, verbose, debug)
        except KeyboardInterrupt:
            self._console.print(
                "\n[yellow]⚠ Survey generation interrupted by user[/yellow]"
            )
            return {"error": "Interrupted by user", "success": False}

    async def _generate_survey_async(
        self,
        file_paths: Optional[List[Path]] = None,
        verbose: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Async implementation of survey generation.

        Args:
            file_paths: Optional list of file paths to process
            verbose: If True, returns detailed results dictionary
            debug: If True, streams Claude's responses to stdout
        """
        # Use provided file_paths or fall back to instance file_paths
        if file_paths is None:
            file_paths = self.file_paths

        if not file_paths:
            return {
                "error": "No files provided. Pass file paths to constructor or to generate_survey()"
            }

        # Initialize Live display for progress updates
        live = Live(Text(""), console=self._console, refresh_per_second=10)
        live.start()

        try:
            # Read all files
            file_contents = {}
            for i, file_path in enumerate(file_paths, 1):
                live.update(
                    self._create_status_display(
                        "📖",
                        f"Reading files... ({i}/{len(file_paths)}) {file_path.name}",
                        spinner=True,
                    )
                )

                # Try to read file directly first if it exists locally
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content_str = f.read()
                        file_contents[str(file_path)] = content_str
                        self.logger.debug(
                            f"Successfully read {file_path.name} directly: {len(content_str)} characters"
                        )
                        if debug:
                            self._console.print(
                                f"[green]✓[/green] Read {file_path.name} directly ({len(content_str)} chars)"
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to read {file_path.name} directly: {e}, trying Claude..."
                        )
                        # Fall back to Claude if direct read fails
                        content = await self._read_file(file_path)
                        if "error" not in content:
                            file_contents[str(file_path)] = content["content"]
                            self.logger.debug(
                                f"Successfully read {file_path.name} via Claude: {len(content['content'])} characters"
                            )
                        else:
                            self.logger.warning(
                                f"Failed to read {file_path.name}: {content.get('error')}"
                            )
                else:
                    # File doesn't exist locally, try Claude
                    content = await self._read_file(file_path)
                    if "error" not in content:
                        file_contents[str(file_path)] = content["content"]
                        self.logger.debug(
                            f"Successfully read {file_path.name}: {len(content['content'])} characters"
                        )
                    else:
                        self.logger.warning(
                            f"Failed to read {file_path.name}: {content.get('error')}"
                        )

            if not file_contents:
                live.stop()
                self.logger.error("No valid files could be read")
                return {"error": "No valid files could be read"}

            self.logger.debug(f"Total files read: {len(file_contents)}")

            # Generate YAML for survey questions
            if debug:
                live.stop()
                self._console.print(
                    "\n[bold cyan]🤖 Generating survey questions with Claude...[/bold cyan]"
                )
                self._console.print("[dim]" + "─" * 70 + "[/dim]")
            else:
                live.update(
                    self._create_status_display(
                        "🤖", "Generating survey questions with Claude...", spinner=True
                    )
                )

            yaml_questions = await self._generate_survey_yaml(
                file_contents, debug=debug
            )

            if debug:
                self._console.print("\n[dim]" + "─" * 70 + "[/dim]")
                self._console.print("[dim]Claude response complete.[/dim]\n")
                live.start()

            if "error" in yaml_questions:
                if not debug:
                    live.stop()
                self.logger.error(f"YAML generation error: {yaml_questions['error']}")
                self._console.print(f"\n[red]Error:[/red] {yaml_questions['error']}")
                if not debug:
                    self._console.print(f"[dim]Debug files saved to:[/dim]")
                    self._console.print(
                        f"  [dim]- {self.output_dir}/last_prompt.txt[/dim]"
                    )
                    self._console.print(
                        f"  [dim]- {self.output_dir}/last_claude_response.txt[/dim]\n"
                    )
                return yaml_questions

            self.logger.debug(
                f"Generated {len(yaml_questions.get('questions', []))} questions from Claude"
            )
            if self.verbose_logs and yaml_questions.get("questions"):
                for q in yaml_questions["questions"]:
                    self.logger.debug(f"  - {q.get('name', 'unnamed')}")

            # Process each question individually
            questions = []
            errors = []
            question_results = []
            total_questions = len(yaml_questions["questions"])

            for idx, question_data in enumerate(yaml_questions["questions"], 1):
                question_name = question_data.get("name", "unnamed")
                yaml_content = question_data.get("yaml", "")

                live.update(
                    self._create_status_display(
                        "⚙️",
                        f"Processing questions... ({idx}/{total_questions}) {question_name}",
                        spinner=False,
                    )
                )

                # Save individual YAML file
                yaml_file = self.output_dir / f"{question_name}.yaml"
                with open(yaml_file, "w") as f:
                    f.write(yaml_content)

                # Try to instantiate the question
                result = self._create_question_from_yaml(yaml_content, question_name)

                if result["success"]:
                    questions.append(result["question"])
                    question_results.append(
                        {
                            "name": question_name,
                            "type": result["question"].__class__.__name__,
                            "status": "✓ Success",
                            "file": yaml_file.name,
                        }
                    )
                else:
                    errors.append(
                        {
                            "question_name": question_name,
                            "error": result["error"],
                            "yaml_file": yaml_file.name,
                        }
                    )
                    question_results.append(
                        {
                            "name": question_name,
                            "type": "Unknown",
                            "status": f"✗ Failed: {result['error']}",
                            "file": yaml_file.name,
                        }
                    )

            # Create survey if we have any valid questions
            survey = None
            survey_yaml = None

            if questions:
                try:
                    live.update(
                        self._create_status_display(
                            "📝", "Creating survey object...", spinner=False
                        )
                    )
                    survey = Survey(questions=questions)
                    self._survey = survey  # Store the survey in the instance

                    # Save survey YAML
                    live.update(
                        self._create_status_display(
                            "💾", "Saving survey files...", spinner=False
                        )
                    )
                    survey_yaml = survey.to_yaml()
                    survey_yaml_file = self.output_dir / "survey.yaml"
                    with open(survey_yaml_file, "w") as f:
                        f.write(survey_yaml)

                    # Save survey as JSON.gz (suppress the "Saved to..." message)
                    output_file = self.output_dir / "survey.json.gz"
                    with SuppressOutput():
                        survey.save(str(output_file))

                except Exception as e:
                    live.stop()
                    self._console.print(f"[red]Error creating survey: {e}[/red]")
                    return {
                        "error": f"Failed to create survey: {e}",
                        "questions_processed": question_results,
                        "errors": errors,
                    }

            live.update(
                self._create_status_display(
                    "✅",
                    "Survey generation complete!",
                    spinner=False,
                    style="green bold",
                )
            )
            live.stop()

            # Print a concise summary
            self._console.print(
                f"\n[green]✓[/green] Generated survey with {len(questions)}/{len(questions) + len(errors)} questions"
            )
            if errors:
                self._console.print(
                    f"[yellow]⚠[/yellow]  {len(errors)} question(s) failed to process:"
                )
                for error in errors:
                    # Extract just the first line of the error message for brevity
                    error_msg = error["error"].split("\n")[0]
                    if error_msg.startswith("Failed to create question: "):
                        error_msg = error_msg.replace("Failed to create question: ", "")
                    self._console.print(
                        f"   [red]✗[/red] [bold]{error['question_name']}[/bold]: {error_msg}"
                    )
                    self._console.print(
                        f"      [dim]Check: {self.output_dir}/{error['yaml_file']}[/dim]"
                    )
            self._console.print(f"[dim]Output: {self.output_dir}/[/dim]\n")

            # Build detailed results
            detailed_results = {
                "success": len(questions) > 0,
                "output_dir": str(self.output_dir),
                "output_file": str(self.output_dir / "survey.json.gz")
                if survey
                else None,
                "survey_yaml_file": str(self.output_dir / "survey.yaml")
                if survey
                else None,
                "questions_processed": question_results,
                "errors": errors,
                "survey_summary": {
                    "total_questions": len(questions) + len(errors),
                    "successful_questions": len(questions),
                    "failed_questions": len(errors),
                    "question_types": list(
                        set([q.__class__.__name__ for q in questions])
                    )
                    if questions
                    else [],
                    "question_names": [q.question_name for q in questions]
                    if questions
                    else [],
                },
            }

            # Return simplified summary if not verbose
            if not verbose:
                return {
                    "success": len(questions) > 0,
                    "total_questions": len(questions) + len(errors),
                    "successful_questions": len(questions),
                    "failed_questions": len(errors),
                    "output_dir": str(self.output_dir),
                    "output_file": str(self.output_dir / "survey.json.gz")
                    if survey
                    else None,
                }

            return detailed_results
        except Exception as e:
            live.stop()
            self._console.print(f"[red]Error during survey generation: {e}[/red]")
            raise

    async def _read_file(self, file_path: Path) -> Dict[str, str]:
        """Read content from any file type."""
        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            system_prompt="You are a file reading assistant. Extract all text content from any file type (PDF, DOC, TXT, CSV, JSON, QSF, etc.).",
            max_turns=5,  # Give Claude enough turns to read large files
        )

        prompt = f"Read the file at {file_path} and extract all content. For structured data (CSV, JSON, QSF), preserve the structure."

        content = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content += block.text

        return (
            {"content": content}
            if content
            else {"error": f"Could not read {file_path}"}
        )

    async def _generate_survey_yaml(
        self, file_contents: Dict[str, str], debug: bool = False
    ) -> Dict[str, Any]:
        """Generate YAML representation of EDSL survey from document contents.

        Args:
            file_contents: Dictionary mapping filenames to their contents
            debug: If True, streams Claude's response to stdout in real-time
        """
        system_prompt = f"""You are an expert in EDSL (Expected Parrot Domain Specific Language) for creating surveys.

{self.edsl_spec}

Your task is to:
1. Analyze the provided documents (including CSV/TSV/Excel data, JSON/QSF survey files, etc.)
2. For QSF files: The file will be pre-parsed for you with structured question data including:
   - question_text: The question text (HTML stripped)
   - question_type: Qualtrics question type (MC, TE, Matrix, etc.)
   - selector: Question selector (SAVR, FORM, Likert, etc.)
   - choices: Dictionary of answer choices
   - answers: Dictionary of answers (for matrix questions)
3. For CSV/TSV/Excel files: Large files are sampled (first 20 rows) to show structure. You can infer the pattern from the sample.
4. Map Qualtrics question types to appropriate EDSL question types
5. Generate YAML representations of EDSL questions
6. Output each question's YAML separately

Important rules:
- Each question must have: question_name, question_text, question_type
- question_name must be a valid Python identifier (lowercase, underscores, no spaces)
- Output each question in a separate YAML block

Common Qualtrics to EDSL mappings:
- MC (Multiple Choice) with SAVR selector → QuestionMultipleChoice
- MC with MAVR/MAHR selector → QuestionCheckBox
- TE (Text Entry) with FORM/SL selector → QuestionFreeText
- Matrix with Likert → QuestionMatrix
- Slider → QuestionLinearScale or QuestionNumerical
- Rank → QuestionRankQuestion or QuestionTopK

Format your response as:
QUESTION_NAME: [the question_name]
```yaml
[complete yaml for this question]
```

Repeat for each question. Be sure to use appropriate question types based on the context.

You do not need to use any tools - all necessary data is provided in the prompt above."""

        options = ClaudeAgentOptions(
            system_prompt=system_prompt, max_turns=self.max_turns
        )

        # Build the prompt with all file contents
        prompt = (
            "Please analyze these documents and generate YAML for an EDSL survey:\n\n"
        )
        for filename, content in file_contents.items():
            # Check if file appears to be QSF
            file_ext = filename.lower().split(".")[-1] if "." in filename else ""

            if file_ext == "qsf":
                # Parse QSF file and provide structured data
                parsed_qsf = parse_qsf_file(content)

                if "error" in parsed_qsf:
                    # Parsing failed, send raw content to Claude
                    self.logger.warning(f"QSF parsing failed: {parsed_qsf['error']}")
                    if debug:
                        self._console.print(
                            f"[yellow]⚠[/yellow] QSF parsing failed: {parsed_qsf['error']}"
                        )
                        self._console.print(
                            f"[dim]Sending raw file content to Claude instead[/dim]"
                        )

                    prompt += f"=== {filename} (Qualtrics QSF - Raw JSON, parsing failed) ===\n"
                    prompt += f"Note: Automatic parsing failed with error: {parsed_qsf['error']}\n"
                    prompt += f"Please parse this QSF JSON manually to extract survey questions.\n\n"
                    prompt += f"{content}\n\n"
                else:
                    prompt += f"=== {filename} (Qualtrics QSF - Pre-parsed) ===\n"
                    prompt += f"Survey Name: {parsed_qsf['survey_name']}\n"
                    prompt += f"Total Questions: {len(parsed_qsf['questions'])}\n\n"
                    prompt += "Parsed Questions:\n"
                    prompt += json.dumps(parsed_qsf["questions"], indent=2)
                    prompt += "\n\n"

                    if debug:
                        self._console.print(
                            f"[green]✓[/green] Pre-parsed QSF: {len(parsed_qsf['questions'])} questions found"
                        )

            elif file_ext == "csv":
                # Sample CSV file for large files
                csv_sample = sample_csv_file(content, max_rows=20, delimiter=",")

                if "error" in csv_sample:
                    # Sampling failed, send raw content
                    prompt += (
                        f"=== {filename} (CSV - sampling failed) ===\n{content}\n\n"
                    )
                else:
                    prompt += f"=== {filename} (CSV - Sampled) ===\n"
                    prompt += f"Columns: {csv_sample['column_count']} | Total Rows: {csv_sample['total_rows']}\n"
                    prompt += f"Column Headers: {', '.join(csv_sample['columns'])}\n\n"

                    if csv_sample["sampled"]:
                        prompt += f"Sample Data (first 20 of {csv_sample['total_rows']} rows):\n"
                    else:
                        prompt += f"Complete Data ({csv_sample['total_rows']} rows):\n"

                    # Reconstruct CSV for sample
                    csv_sample_text = ",".join(csv_sample["columns"]) + "\n"
                    for row in csv_sample["sample_rows"]:
                        csv_sample_text += ",".join(str(cell) for cell in row) + "\n"

                    prompt += csv_sample_text + "\n"

                    if debug:
                        self._console.print(
                            f"[green]✓[/green] Sampled CSV: {csv_sample['column_count']} columns, {csv_sample['total_rows']} total rows"
                        )

            elif file_ext == "tsv":
                # Sample TSV file for large files
                tsv_sample = sample_csv_file(content, max_rows=20, delimiter="\t")

                if "error" in tsv_sample:
                    # Sampling failed, send raw content
                    prompt += (
                        f"=== {filename} (TSV - sampling failed) ===\n{content}\n\n"
                    )
                else:
                    prompt += f"=== {filename} (TSV - Sampled) ===\n"
                    prompt += f"Columns: {tsv_sample['column_count']} | Total Rows: {tsv_sample['total_rows']}\n"
                    prompt += f"Column Headers: {', '.join(tsv_sample['columns'])}\n\n"

                    if tsv_sample["sampled"]:
                        prompt += f"Sample Data (first 20 of {tsv_sample['total_rows']} rows):\n"
                    else:
                        prompt += f"Complete Data ({tsv_sample['total_rows']} rows):\n"

                    # Reconstruct TSV for sample
                    tsv_sample_text = "\t".join(tsv_sample["columns"]) + "\n"
                    for row in tsv_sample["sample_rows"]:
                        tsv_sample_text += "\t".join(str(cell) for cell in row) + "\n"

                    prompt += tsv_sample_text + "\n"

                    if debug:
                        self._console.print(
                            f"[green]✓[/green] Sampled TSV: {tsv_sample['column_count']} columns, {tsv_sample['total_rows']} total rows"
                        )

            elif file_ext in ["xlsx", "xls"]:
                # Sample Excel file
                xlsx_sample = sample_xlsx_file(Path(filename), max_rows=20)

                if "error" in xlsx_sample:
                    prompt += f"=== {filename} (Excel - {xlsx_sample['error']}) ===\n"
                    prompt += "Could not parse Excel file. Please convert to CSV or provide in another format.\n\n"
                else:
                    prompt += f"=== {filename} (Excel - Sampled) ===\n"
                    prompt += f"Sheet: {xlsx_sample.get('sheet_name', 'Unknown')}\n"
                    prompt += f"Columns: {xlsx_sample['column_count']} | Total Rows: {xlsx_sample['total_rows']}\n"
                    prompt += f"Column Headers: {', '.join(xlsx_sample['columns'])}\n\n"

                    if xlsx_sample["sampled"]:
                        prompt += f"Sample Data (first 20 of {xlsx_sample['total_rows']} rows):\n"
                    else:
                        prompt += f"Complete Data ({xlsx_sample['total_rows']} rows):\n"

                    # Reconstruct as CSV for sample
                    xlsx_sample_text = ",".join(xlsx_sample["columns"]) + "\n"
                    for row in xlsx_sample["sample_rows"]:
                        xlsx_sample_text += ",".join(str(cell) for cell in row) + "\n"

                    prompt += xlsx_sample_text + "\n"

                    if debug:
                        self._console.print(
                            f"[green]✓[/green] Sampled Excel: {xlsx_sample['column_count']} columns, {xlsx_sample['total_rows']} total rows"
                        )

            elif file_ext == "json" or (
                content.strip().startswith("{") or content.strip().startswith("[")
            ):
                prompt += f"=== {filename} (JSON format) ===\n{content}\n\n"
            else:
                prompt += f"=== {filename} ===\n{content}\n\n"

        # Save prompt for debugging (only if not in debug mode)
        if not debug:
            prompt_file = self.output_dir / "last_prompt.txt"
            with open(prompt_file, "w") as f:
                f.write(prompt)
            self.logger.debug(f"Saved prompt to {prompt_file}")
        else:
            # In debug mode, show the prompt
            self._console.print("\n[bold yellow]📄 File Contents Summary:[/bold yellow]")
            self._console.print("[dim]" + "─" * 70 + "[/dim]")
            # Show info about each file
            for filename, content in file_contents.items():
                file_ext = filename.lower().split(".")[-1] if "." in filename else ""
                if file_ext == "qsf":
                    parsed_qsf = parse_qsf_file(content)
                    if "error" not in parsed_qsf:
                        self._console.print(f"[cyan]{filename}[/cyan] (QSF)")
                        self._console.print(f"  Survey: {parsed_qsf['survey_name']}")
                        self._console.print(
                            f"  Questions: {len(parsed_qsf['questions'])}"
                        )
                    else:
                        self._console.print(
                            f"[cyan]{filename}[/cyan] (QSF - parse error)"
                        )
                elif file_ext == "csv":
                    csv_sample = sample_csv_file(content, max_rows=20, delimiter=",")
                    if "error" not in csv_sample:
                        self._console.print(f"[cyan]{filename}[/cyan] (CSV)")
                        self._console.print(f"  Columns: {csv_sample['column_count']}")
                        self._console.print(f"  Rows: {csv_sample['total_rows']}")
                        if csv_sample["sampled"]:
                            self._console.print(f"  [dim](showing first 20 rows)[/dim]")
                    else:
                        self._console.print(
                            f"[cyan]{filename}[/cyan] (CSV - parse error)"
                        )
                elif file_ext == "tsv":
                    tsv_sample = sample_csv_file(content, max_rows=20, delimiter="\t")
                    if "error" not in tsv_sample:
                        self._console.print(f"[cyan]{filename}[/cyan] (TSV)")
                        self._console.print(f"  Columns: {tsv_sample['column_count']}")
                        self._console.print(f"  Rows: {tsv_sample['total_rows']}")
                        if tsv_sample["sampled"]:
                            self._console.print(f"  [dim](showing first 20 rows)[/dim]")
                    else:
                        self._console.print(
                            f"[cyan]{filename}[/cyan] (TSV - parse error)"
                        )
                elif file_ext in ["xlsx", "xls"]:
                    xlsx_sample = sample_xlsx_file(Path(filename), max_rows=20)
                    if "error" not in xlsx_sample:
                        self._console.print(f"[cyan]{filename}[/cyan] (Excel)")
                        self._console.print(
                            f"  Sheet: {xlsx_sample.get('sheet_name', 'Unknown')}"
                        )
                        self._console.print(f"  Columns: {xlsx_sample['column_count']}")
                        self._console.print(f"  Rows: {xlsx_sample['total_rows']}")
                        if xlsx_sample["sampled"]:
                            self._console.print(f"  [dim](showing first 20 rows)[/dim]")
                    else:
                        self._console.print(
                            f"[cyan]{filename}[/cyan] (Excel - {xlsx_sample['error']})"
                        )
                else:
                    self._console.print(
                        f"[cyan]{filename}[/cyan] ({len(content)} chars)"
                    )
                    preview = content[:300] + ("..." if len(content) > 300 else "")
                    self._console.print(f"[dim]{preview}[/dim]")
                self._console.print()
            self._console.print("[dim]" + "─" * 70 + "[/dim]\n")

        questions = []
        all_text = []  # Collect all text for debugging

        try:
            async for message in query(prompt=prompt, options=options):
                if debug:
                    # Show message type for debugging
                    print(f"\n{'='*70}", flush=True)
                    print(f"[Message: {type(message).__name__}]", flush=True)

                # Handle ResultMessage (tool results)
                if isinstance(message, ResultMessage):
                    if debug:
                        print(f"[Tool result being sent back to Claude]", flush=True)
                    continue

                # Handle UserMessage (system messages back to Claude)
                if isinstance(message, UserMessage):
                    if debug:
                        print(f"[System message to Claude]", flush=True)
                    continue

                if isinstance(message, AssistantMessage):
                    if debug and message.content:
                        print(f"[{len(message.content)} content block(s)]", flush=True)

                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            # Show tool usage details
                            if debug:
                                print(f"\n[TOOL USE]:", flush=True)
                                print(f"  Tool: {block.name}", flush=True)
                                print(f"  ID: {block.id}", flush=True)
                                if hasattr(block, "input") and block.input:
                                    print(
                                        f"  Input: {json.dumps(block.input, indent=2)}",
                                        flush=True,
                                    )
                            self.logger.debug(f"Tool use: {block.name}")

                        elif isinstance(block, TextBlock):
                            # Parse the response to extract individual questions
                            text = block.text
                            all_text.append(text)

                            # Stream to stdout if debug mode
                            if debug:
                                print(f"\n[TEXT]:", flush=True)
                                print(text, flush=True)

                            self.logger.debug(f"Claude response chunk: {text[:200]}...")
                            lines = text.split("\n")

                            current_name = None
                            in_yaml_block = False
                            yaml_lines = []

                            for line in lines:
                                if line.startswith("QUESTION_NAME:"):
                                    # Save previous question if exists
                                    if current_name and yaml_lines:
                                        questions.append(
                                            {
                                                "name": current_name,
                                                "yaml": "\n".join(yaml_lines),
                                            }
                                        )
                                        yaml_lines = []

                                    current_name = line.split(":", 1)[1].strip()
                                    in_yaml_block = False
                                elif line.strip() == "```yaml":
                                    in_yaml_block = True
                                elif line.strip() == "```" and in_yaml_block:
                                    in_yaml_block = False
                                elif in_yaml_block:
                                    yaml_lines.append(line)

                            # Don't forget the last question
                            if current_name and yaml_lines:
                                questions.append(
                                    {
                                        "name": current_name,
                                        "yaml": "\n".join(yaml_lines),
                                    }
                                )

                        else:
                            # Unknown block type
                            if debug:
                                print(
                                    f"\n[UNKNOWN BLOCK TYPE: {type(block).__name__}]",
                                    flush=True,
                                )
                                print(f"  {repr(block)}", flush=True)
        except KeyboardInterrupt:
            if debug:
                print("\n[INTERRUPTED BY USER]", flush=True)
            raise

        # Save Claude's full response for debugging (only if not in debug mode)
        if all_text and not debug:
            response_file = self.output_dir / "last_claude_response.txt"
            with open(response_file, "w") as f:
                f.write("\n".join(all_text))
            self.logger.debug(f"Saved Claude response to {response_file}")

        if not questions:
            self.logger.error("No questions generated from Claude response")
            if not debug:
                self.logger.error(
                    f"Check {self.output_dir}/last_prompt.txt and {self.output_dir}/last_claude_response.txt for details"
                )
            if self.verbose_logs and all_text:
                self.logger.debug(f"Full Claude response:\n{''.join(all_text)}")
            return {"error": "No questions generated"}

        self.logger.debug(
            f"Successfully parsed {len(questions)} questions from Claude response"
        )
        return {"questions": questions}

    def _create_question_from_yaml(
        self, yaml_str: str, question_name: str
    ) -> Dict[str, Any]:
        """Create EDSL Question from YAML representation."""
        try:
            # First validate the YAML
            yaml_data = yaml.safe_load(yaml_str)
            if not yaml_data or "question_type" not in yaml_data:
                return {
                    "success": False,
                    "error": "Missing required field 'question_type'",
                }

            # Create question using from_yaml
            question = QuestionBase.from_yaml(yaml_str)

            return {"success": True, "question": question}

        except yaml.YAMLError as e:
            return {"success": False, "error": f"Invalid YAML: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to create question: {str(e)}"}

    def to_survey(self) -> Optional[Survey]:
        """Return the generated Survey object.

        Returns:
            The Survey object if one has been generated, None otherwise.
            Note: Use the .survey property instead for automatic generation.
        """
        return self._survey


@app.command()
def generate(
    files: List[Path] = typer.Argument(
        ..., help="List of files relevant to survey generation"
    ),
    spec_file: Optional[Path] = typer.Option(
        Path("EDSL_SPECIFICATION.md"),
        "--spec",
        "-s",
        help="Path to EDSL specification markdown file",
    ),
    output_dir: Optional[Path] = typer.Option(
        Path("edsl_output"),
        "--output-dir",
        "-o",
        help="Output directory for generated files",
    ),
):
    """Generate EDSL survey from document files."""
    console.print(f"[bold]EDSL Survey Generator[/bold]")

    # Check for API key early
    if not check_api_key():
        raise typer.Exit(1)

    console.print(f"Processing {len(files)} files...")

    # Validate files exist
    valid_files = []
    for file in files:
        if file.exists():
            valid_files.append(file)
            console.print(f"  ✓ {file}")
        else:
            console.print(f"  [red]✗ {file} (not found)[/red]")

    if not valid_files:
        console.print("[red]No valid files found![/red]")
        raise typer.Exit(1)

    # Run async generation
    async def run_generation():
        generator = SurveyAssistant(spec_file=spec_file)
        generator.output_dir = output_dir
        generator.output_dir.mkdir(exist_ok=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating survey...", total=None)

            result = await generator._generate_survey_async(valid_files)

            progress.stop()

            # Display results table
            console.print(f"\n[bold]Generation Results[/bold]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Question Name", style="cyan", no_wrap=True)
            table.add_column("Type", style="blue")
            table.add_column("Status", style="green")
            table.add_column("YAML File", style="dim")

            for q_result in result.get("questions_processed", []):
                status_style = "green" if "Success" in q_result["status"] else "red"
                table.add_row(
                    q_result["name"],
                    q_result["type"],
                    q_result["status"],
                    q_result["file"],
                )

            console.print(table)

            # Summary
            summary = result.get("survey_summary", {})
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(
                f"  Total questions attempted: {summary.get('total_questions', 0)}"
            )
            console.print(
                f"  Successfully created: [green]{summary.get('successful_questions', 0)}[/green]"
            )
            console.print(f"  Failed: [red]{summary.get('failed_questions', 0)}[/red]")

            if result.get("success"):
                console.print(f"\n[green]✓ Survey generated successfully![/green]")
                console.print(f"Output directory: [bold]{result['output_dir']}[/bold]")
                console.print(f"  - Individual YAMLs: {result['output_dir']}/*.yaml")
                console.print(
                    f"  - Survey YAML: {result.get('survey_yaml_file', 'N/A')}"
                )
                console.print(f"  - Survey object: {result.get('output_file', 'N/A')}")
            else:
                console.print(f"\n[red]✗ Survey generation failed![/red]")
                if result.get("errors"):
                    console.print(f"\n[bold]Errors:[/bold]")
                    for error in result["errors"]:
                        console.print(f"  - {error['question_name']}: {error['error']}")
                        console.print(f"    Check: {error['yaml_file']}")

    anyio.run(run_generation)


@app.command()
def validate(
    yaml_file: Path = typer.Argument(..., help="YAML file to validate"),
):
    """Validate a single YAML question file."""
    if not yaml_file.exists():
        console.print(f"[red]File not found: {yaml_file}[/red]")
        raise typer.Exit(1)

    with open(yaml_file, "r") as f:
        yaml_content = f.read()

    console.print(f"[bold]Validating: {yaml_file}[/bold]\n")
    console.print("[dim]YAML Content:[/dim]")
    console.print(yaml_content)
    console.print("\n[dim]Validation Result:[/dim]")

    generator = SurveyAssistant()
    result = generator._create_question_from_yaml(yaml_content, yaml_file.stem)

    if result["success"]:
        question = result["question"]
        console.print(f"[green]✓ Valid EDSL question![/green]")
        console.print(f"  Type: {question.__class__.__name__}")
        console.print(f"  Name: {question.question_name}")
        console.print(f"  Text: {question.question_text}")
    else:
        console.print(f"[red]✗ Invalid: {result['error']}[/red]")


@app.command()
def example():
    """Show example usage and create sample files."""
    console.print("[bold]EDSL Survey Generator - Example Usage[/bold]\n")

    # Create example survey specification
    example_content = """Customer Satisfaction Survey

We need to measure satisfaction with our new product launch.

Questions needed:
1. Overall satisfaction rating (5-point scale)
2. Which features do you use? (multiple choice, select all that apply: Analytics, Reports, API)
3. Would you recommend to others? (0-10 scale)
4. Any additional feedback? (open text)
5. Would you renew? (Yes/No)
"""

    example_file = Path("example_survey_spec.txt")
    with open(example_file, "w") as f:
        f.write(example_content)

    # Create example CSV with responses
    csv_content = """question_name,response,respondent_id
satisfaction,4,001
features_used,Analytics,001
recommend,8,001
satisfaction,5,002
features_used,Reports,002
recommend,10,002
"""

    csv_file = Path("example_responses.csv")
    with open(csv_file, "w") as f:
        f.write(csv_content)

    console.print(f"Created example files:")
    console.print(f"  - {example_file}")
    console.print(f"  - {csv_file}")
    console.print(f"\nExample command:")
    console.print(
        f"  [bold]uv run edsl_survey_generator.py {example_file} {csv_file}[/bold]"
    )


if __name__ == "__main__":
    app()
