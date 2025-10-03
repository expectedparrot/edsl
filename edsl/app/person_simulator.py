from __future__ import annotations

from typing import Optional, Union
from pathlib import Path

from .app import App
from .head_attachments import HeadAttachments
from .output_formatter import OutputFormatter


class PersonSimulator(App):
    application_type: str = "person_simulator"
    default_output_formatter: OutputFormatter = (
        OutputFormatter(description="Persona Answers").select("answer.*").to_list()
    )

    input_type: "Survey"
    modified_jobs_component: "Survey"

    def __init__(
        self,
        persona_context: str,
        application_name: Optional[str] = None,
        description: Optional[str] = None,
        agent_name: Optional[str] = None,
        output_formatters: Optional[list[OutputFormatter]] = None,
    ):
        """Answer free-text questions in character using a provided persona context.

        Args:
            persona_context: Descriptive text about the person/persona to simulate.
            application_name: Optional human-readable name.
            description: Optional description.
            agent_name: Optional name for the simulated persona.
            output_formatters: Optional output formatters. Defaults to a pass-through formatter.
        """
        from ..surveys import Survey
        from ..agents import Agent

        instruction = (
            "You are answering questions fully in character as the following person.\n"
            "Context:\n" + persona_context + "\n"
            "Stay strictly in character and do not break persona."
        )
        self.persona_agent = Agent(
            name=agent_name or "Persona", instruction=instruction
        )

        # Minimal jobs object for base constructor
        jobs_object = Survey([]).by(self.persona_agent)

        # Provide a minimal required initial_survey per new contract
        from ..surveys import Survey as _Survey

        super().__init__(
            jobs_object=jobs_object,
            output_formatters=output_formatters,
            description=description,
            application_name=application_name or "Person Simulator",
            initial_survey=_Survey([]),
        )

    def _prepare_from_params(self, params: dict) -> "HeadAttachments":
        from ..surveys import Survey
        from ..questions import QuestionFreeText

        # Normalize params into a Survey of free-text questions
        input_obj = params.get("survey") or params.get("questions")
        if isinstance(input_obj, Survey):
            survey = input_obj
        elif isinstance(input_obj, list) and all(isinstance(q, str) for q in input_obj):
            questions = [
                QuestionFreeText(question_name=f"q_{i}", question_text=text)
                for i, text in enumerate(input_obj)
            ]
            survey = Survey(questions)
        else:
            raise TypeError(
                "PersonSimulator requires params dict with key 'survey' (Survey) or 'questions' (list[str])"
            )
        return HeadAttachments(survey=survey)

    @classmethod
    def from_directory(
        cls,
        directory_path: Union[str, Path],
        *,
        agent_name: Optional[str] = None,
        application_name: Optional[str] = None,
        description: Optional[str] = None,
        output_formatters: Optional[list[OutputFormatter]] = None,
        recursive: bool = False,
        glob_pattern: Optional[str] = None,
    ) -> "PersonSimulator":
        """Construct a PersonSimulator by extracting text from files in a directory.

        Each file is loaded via FileStore and its extracted text is wrapped in XML-like tags
        to preserve source separation in the assembled persona context.

        Args:
            directory_path: Directory containing files to build the persona from.
            agent_name: Optional agent name.
            application_name: Optional app name.
            description: Optional app description.
            output_formatters: Optional output formatters.
            recursive: If True, recurse into subdirectories.
            glob_pattern: Optional custom glob (e.g., "**/*.pdf"); overrides recursive flag.

        Returns:
            PersonSimulator: Instance configured with aggregated context from directory.
        """
        from ..scenarios import FileStore
        from pathlib import Path as _Path

        base = _Path(directory_path)
        if not base.exists() or not base.is_dir():
            raise ValueError(
                f"Directory not found or not a directory: {directory_path}"
            )

        if glob_pattern is not None:
            paths = sorted(base.glob(glob_pattern))
        else:
            pattern = "**/*" if recursive else "*"
            paths = sorted(base.glob(pattern))

        sections: list[str] = []
        for p in paths:
            if not p.is_file():
                continue
            try:
                fs = FileStore(path=str(p))
                text = fs.extract_text()
                if isinstance(text, str) and text.strip():
                    sections.append(f'<source path="{p}">\n{text.strip()}\n</source>')
            except Exception:
                # Skip files that cannot be processed
                continue

        persona_context = "\n\n".join(sections)
        return cls(
            persona_context=persona_context,
            agent_name=agent_name or base.name,
            application_name=application_name or f"Person Simulator: {base.name}",
            description=description,
            output_formatters=output_formatters,
        )

    @classmethod
    def from_firecrawl(
        cls,
        person_name: str,
        *,
        fallback_bio: str = "",
        agent_name: Optional[str] = None,
        application_name: Optional[str] = None,
        description: Optional[str] = None,
        output_formatters: Optional[list[OutputFormatter]] = None,
        max_pages: int = 3,
    ) -> "PersonSimulator":
        """Construct a PersonSimulator by attempting to fetch context via Firecrawl.

        If Firecrawl is unavailable or yields no usable text, falls back to the provided
        fallback_bio.

        Args:
            person_name: Name to search (e.g., "John Horton economist MIT").
            fallback_bio: Used if Firecrawl is not configured or returns no content.
            agent_name: Optional agent name.
            application_name: Optional app name.
            description: Optional app description.
            output_formatters: Optional output formatters.
            max_pages: Maximum pages to aggregate if Firecrawl returns multiple results.
        """
        persona_context = fallback_bio or person_name
        try:
            # Prefer high-level convenience; fall back gracefully if unavailable
            from ..scenarios.firecrawl_scenario import search_web, scrape_url

            # Step 1: Search for top results with URLs
            search_result = search_web(person_name, limit=max_pages)
            search_scenarios = (
                search_result[0] if isinstance(search_result, tuple) else search_result
            )

            urls: list[str] = []
            for scenario in search_scenarios:
                try:
                    if (
                        "url" in scenario
                        and isinstance(scenario["url"], str)
                        and scenario["url"].strip()
                    ):
                        urls.append(scenario["url"].strip())
                except Exception:
                    continue

            # Step 2: Scrape the found URLs for full content (markdown)
            if urls:
                scrape_result = scrape_url(
                    urls,
                    formats=["markdown"],
                    only_main_content=True,
                    limit=max_pages,
                )
                scraped = (
                    scrape_result[0]
                    if isinstance(scrape_result, tuple)
                    else scrape_result
                )

                text_chunks: list[str] = []
                count = 0
                for scenario in scraped:
                    if count >= max_pages:
                        break
                    # Prefer full content/markdown fields
                    if (
                        "content" in scenario
                        and isinstance(scenario["content"], str)
                        and scenario["content"].strip()
                    ):
                        text_chunks.append(scenario["content"].strip())
                    elif (
                        "markdown" in scenario
                        and isinstance(scenario["markdown"], str)
                        and scenario["markdown"].strip()
                    ):
                        text_chunks.append(scenario["markdown"].strip())
                    count += 1

                aggregated = "\n\n".join(text_chunks).strip()
                if aggregated:
                    persona_context = aggregated
        except Exception:
            # Firecrawl not configured/failed; keep fallback persona_context
            pass

        return cls(
            persona_context=persona_context,
            agent_name=agent_name or person_name,
            application_name=application_name or f"Person Simulator: {person_name}",
            description=description,
            output_formatters=output_formatters,
        )


