from __future__ import annotations

from typing import Optional, Union
from pathlib import Path

from .app import App
from .output_formatter import OutputFormatter


def create_person_simulator(
    persona_context: str,
    application_name: Optional[str] = None,
    display_name: Optional[str] = None,
    short_description: Optional[str] = None,
    long_description: Optional[str] = None,
    agent_name: Optional[str] = None,
    output_formatters: Optional[dict[str, OutputFormatter]] = None,
) -> App:
    """Create an App that answers questions in character using a provided persona context.

    Args:
        persona_context: Descriptive text about the person/persona to simulate.
        application_name: Valid Python identifier for the app (defaults to 'person_simulator').
        display_name: Human-readable name (defaults to 'Person Simulator').
        short_description: One sentence description.
        long_description: Longer description.
        agent_name: Optional name for the simulated persona.
        output_formatters: Optional output formatters dict. Defaults to a persona answers formatter.

    Returns:
        App: Configured app instance for persona simulation.
    """
    from ..surveys import Survey
    from ..agents import Agent
    from ..questions import QuestionEDSLObject

    # Create the persona agent with context
    instruction = (
        "You are answering questions fully in character as the following person.\n"
        "Context:\n" + persona_context + "\n"
        "Stay strictly in character and do not break persona."
    )
    persona_agent = Agent(name=agent_name or "Persona", instruction=instruction)

    # Initial survey accepts a Survey of questions to answer
    initial_survey = Survey([
        QuestionEDSLObject(
            question_name="survey",
            question_text="Provide the survey questions to answer in character",
            expected_object_type="Survey",
        )
    ])

    # Jobs object: empty survey bound to the persona agent
    # Will be populated via params when app runs
    jobs_object = Survey([]).by(persona_agent)

    # Default output formatter
    default_formatter = (
        OutputFormatter(description="Persona Answers")
        .select("answer.*")
        .to_list()
    )

    # Prepare output formatters
    if output_formatters is None:
        output_formatters = {"persona_answers": default_formatter}
    elif isinstance(output_formatters, list):
        # Convert list to dict using description as key
        output_formatters = {
            f.description or f"formatter_{i}": f 
            for i, f in enumerate(output_formatters)
        }

    # Create and return the App
    return App(
        application_name=application_name or "person_simulator",
        display_name=display_name or "Person Simulator",
        short_description=short_description or "Answer questions in character as a persona.",
        long_description=long_description or "Answer questions fully in character using a provided persona context. The app maintains character consistency throughout all responses.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters=output_formatters,
        default_formatter_name=list(output_formatters.keys())[0],
    )


def create_person_simulator_from_directory(
    directory_path: Union[str, Path],
    *,
    agent_name: Optional[str] = None,
    application_name: Optional[str] = None,
    display_name: Optional[str] = None,
    short_description: Optional[str] = None,
    long_description: Optional[str] = None,
    output_formatters: Optional[dict[str, OutputFormatter]] = None,
    recursive: bool = False,
    glob_pattern: Optional[str] = None,
) -> App:
    """Create a PersonSimulator App by extracting text from files in a directory.

    Each file is loaded via FileStore and its extracted text is wrapped in XML-like tags
    to preserve source separation in the assembled persona context.

    Args:
        directory_path: Directory containing files to build the persona from.
        agent_name: Optional agent name.
        application_name: Valid Python identifier for the app.
        display_name: Human-readable name.
        short_description: One sentence description.
        long_description: Longer description.
        output_formatters: Optional output formatters dict.
        recursive: If True, recurse into subdirectories.
        glob_pattern: Optional custom glob (e.g., "**/*.pdf"); overrides recursive flag.

    Returns:
        App: Configured app instance with aggregated context from directory.
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
    return create_person_simulator(
        persona_context=persona_context,
        agent_name=agent_name or base.name,
        application_name=application_name or f"person_simulator_{base.name}",
        display_name=display_name or f"Person Simulator: {base.name}",
        short_description=short_description,
        long_description=long_description,
        output_formatters=output_formatters,
    )


def create_person_simulator_from_firecrawl(
    person_name: str,
    *,
    fallback_bio: str = "",
    agent_name: Optional[str] = None,
    application_name: Optional[str] = None,
    display_name: Optional[str] = None,
    short_description: Optional[str] = None,
    long_description: Optional[str] = None,
    output_formatters: Optional[dict[str, OutputFormatter]] = None,
    max_pages: int = 3,
) -> App:
    """Create a PersonSimulator App by attempting to fetch context via Firecrawl.

    If Firecrawl is unavailable or yields no usable text, falls back to the provided
    fallback_bio.

    Args:
        person_name: Name to search (e.g., "John Horton economist MIT").
        fallback_bio: Used if Firecrawl is not configured or returns no content.
        agent_name: Optional agent name.
        application_name: Valid Python identifier for the app.
        display_name: Human-readable name.
        short_description: One sentence description.
        long_description: Longer description.
        output_formatters: Optional output formatters dict.
        max_pages: Maximum pages to aggregate if Firecrawl returns multiple results.
        
    Returns:
        App: Configured app instance with context from web search or fallback.
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

    return create_person_simulator(
        persona_context=persona_context,
        agent_name=agent_name or person_name,
        application_name=application_name or f"person_simulator_{person_name.lower().replace(' ', '_')}",
        display_name=display_name or f"Person Simulator: {person_name}",
        short_description=short_description,
        long_description=long_description,
        output_formatters=output_formatters,
    )


# Backward-compatible wrapper class
class PersonSimulator:
    """Factory class for creating PersonSimulator Apps.
    
    This class provides a backward-compatible interface to the factory functions.
    It returns App instances rather than inheriting from App.
    """
    
    def __new__(
        cls,
        persona_context: str,
        application_name: Optional[str] = None,
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        agent_name: Optional[str] = None,
        output_formatters: Optional[dict[str, OutputFormatter]] = None,
    ) -> App:
        """Create an App that answers questions in character using a provided persona context.

        Args:
            persona_context: Descriptive text about the person/persona to simulate.
            application_name: Valid Python identifier for the app (defaults to 'person_simulator').
            display_name: Human-readable name (defaults to 'Person Simulator').
            short_description: One sentence description.
            long_description: Longer description.
            agent_name: Optional name for the simulated persona.
            output_formatters: Optional output formatters dict.

        Returns:
            App: Configured app instance for persona simulation.
        """
        return create_person_simulator(
            persona_context=persona_context,
            application_name=application_name,
            display_name=display_name,
            short_description=short_description,
            long_description=long_description,
            agent_name=agent_name,
            output_formatters=output_formatters,
        )
    
    @staticmethod
    def from_directory(
        directory_path: Union[str, Path],
        *,
        agent_name: Optional[str] = None,
        application_name: Optional[str] = None,
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        output_formatters: Optional[dict[str, OutputFormatter]] = None,
        recursive: bool = False,
        glob_pattern: Optional[str] = None,
    ) -> App:
        """Create a PersonSimulator App by extracting text from files in a directory.

        Args:
            directory_path: Directory containing files to build the persona from.
            agent_name: Optional agent name.
            application_name: Valid Python identifier for the app.
            display_name: Human-readable name.
            short_description: One sentence description.
            long_description: Longer description.
            output_formatters: Optional output formatters dict.
            recursive: If True, recurse into subdirectories.
            glob_pattern: Optional custom glob (e.g., "**/*.pdf"); overrides recursive flag.

        Returns:
            App: Configured app instance with aggregated context from directory.
        """
        return create_person_simulator_from_directory(
            directory_path=directory_path,
            agent_name=agent_name,
            application_name=application_name,
            display_name=display_name,
            short_description=short_description,
            long_description=long_description,
            output_formatters=output_formatters,
            recursive=recursive,
            glob_pattern=glob_pattern,
        )
    
    @staticmethod
    def from_firecrawl(
        person_name: str,
        *,
        fallback_bio: str = "",
        agent_name: Optional[str] = None,
        application_name: Optional[str] = None,
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        output_formatters: Optional[dict[str, OutputFormatter]] = None,
        max_pages: int = 3,
    ) -> App:
        """Create a PersonSimulator App by attempting to fetch context via Firecrawl.

        Args:
            person_name: Name to search (e.g., "John Horton economist MIT").
            fallback_bio: Used if Firecrawl is not configured or returns no content.
            agent_name: Optional agent name.
            application_name: Valid Python identifier for the app.
            display_name: Human-readable name.
            short_description: One sentence description.
            long_description: Longer description.
            output_formatters: Optional output formatters dict.
            max_pages: Maximum pages to aggregate if Firecrawl returns multiple results.
            
        Returns:
            App: Configured app instance with context from web search or fallback.
        """
        return create_person_simulator_from_firecrawl(
            person_name=person_name,
            fallback_bio=fallback_bio,
            agent_name=agent_name,
            application_name=application_name,
            display_name=display_name,
            short_description=short_description,
            long_description=long_description,
            output_formatters=output_formatters,
            max_pages=max_pages,
        )
