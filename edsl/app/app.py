from typing import TYPE_CHECKING, Optional, Any, TypedDict, Union
from pathlib import Path
from abc import ABC, abstractmethod
from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..agents import AgentList
from ..questions import QuestionMultipleChoice
from ..scenarios.ranking_algorithm import results_to_ranked_scenario_list

if TYPE_CHECKING:
    from ..scenarios import ScenarioList
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..scenarios import ScenarioList
    from ..agents import AgentList

from .output_formatter import OutputFormatter, OutputFormatters

from dataclasses import dataclass

class HeadAttachments:
    """A class to attach objects to the head of a jobs object."""

    def __init__(self, *, scenario: Optional[ScenarioList] = None, survey: Optional[Survey] = None, agent_list: Optional[AgentList] = None):
        self.scenario = scenario
        self.survey = survey
        self.agent_list = agent_list

    def attach_to_head(self, jobs: 'Jobs') -> 'Jobs':
        if self.scenario: 
            jobs = jobs.add_scenario_head(self.scenario)
        if self.survey:
            jobs = jobs.add_survey_to_head(self.survey)
        if self.agent_list:
            jobs = jobs.add_agent_list_to_head(self.agent_list)
        return jobs

# class AppDeployment:
#     license_type: str
#     github_repo: str
#     timestamp: str
#     source_available: bool
#     documentation: str
#     thumbnail: str

class App(ABC):
    """
    A class representing an EDSL application.

    An EDSL application requires the user to complete an initial survey. 
    This creates parameters that are used to run a jobs object.
    The jobs object has the logic for the application.
    """
    # Subclass registry: maps application_type -> subclass
    _registry: dict[str, type['App']] = {}

    # Each subclass should set a unique application_type
    application_type: str = "base"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Skip base class itself
        if cls is App:
            return
        app_type = getattr(cls, "application_type", None)
        if not isinstance(app_type, str) or not app_type.strip():
            raise TypeError(f"{cls.__name__} must define a non-empty 'application_type' class attribute.")
        # Enforce uniqueness
        if app_type in App._registry and App._registry[app_type] is not cls:
            existing = App._registry[app_type].__name__
            raise ValueError(f"Duplicate application_type '{app_type}' for {cls.__name__}; already registered by {existing}.")
        App._registry[app_type] = cls

    # Subclasses must define a default_output_formatter used when none is supplied
    default_output_formatter: Optional[OutputFormatter] = None

    def __init__(self, 
        jobs_object: 'Jobs', 
        description: str,
        application_name: str,
        output_formatters: Optional[list[OutputFormatter] | OutputFormatter] = None, 
        initial_survey: Optional[Survey] = None):
        """Instantiate an App object.
        
        Args:
            jobs_object: The jobs object that is the logic of the application.
            output_formatters: The output formatters to use for the application.
            description: The description of the application.
            application_name: Human-readable name for this application. Must be a string if provided.
            initial_survey: The initial survey to use for the application.
        """
        self.jobs_object = jobs_object
        self.description = description
        self.initial_survey = initial_survey
        # Enforce default_output_formatter contract

        if output_formatters is None:
            if getattr(self.__class__, 'default_output_formatter', None) is None:
                raise ValueError("Subclasses of App must define a class-level default_output_formatter or pass output_formatters")
            output_formatters = [self.__class__.default_output_formatter]
        if not isinstance(output_formatters, list):
            output_formatters = [output_formatters]
        if len(output_formatters) == 0:
            raise ValueError("output_formatters must be a non-empty list")
        self.output_formatters: OutputFormatters = OutputFormatters(output_formatters)
        if application_name is not None and not isinstance(application_name, str):
            raise TypeError("application_name must be a string if provided")
        # Default to the class name if not provided
        self.application_name: str = application_name or self.__class__.__name__
        self._validate_parameters()

    @classmethod
    def list(cls) -> list[str]:
        """List all apps."""
        from ..coop.coop import Coop
        coop = Coop()
        return coop.list_apps()

    def _generate_results(self, modified_jobs_object: 'Jobs') -> 'Results':
        """Generate results from a modified jobs object."""
        return modified_jobs_object.run()

    def output(self, params: 'Any', verbose: bool = False, formater_to_use: Optional[str] = None) -> Any:
        head_attachments = self._prepare_from_params(params)
        jobs = head_attachments.attach_to_head(self.jobs_object)
        return self._render(jobs, formater_to_use)

    def _render(self, jobs: 'Jobs', formater_to_use: Optional[str]) -> Any:
        """Render the results of a jobs object by applying the appropriate output formatter."""
        if formater_to_use is not None:
            formatter = self.output_formatters.get_formatter(formater_to_use)
        else:
            formatter = self.output_formatters.get_default()
        results = self._generate_results(jobs)
        return formatter.render(results)

    @abstractmethod
    def _prepare_from_params(self, params: Any) -> 'Jobs':
        """Map external params into a Jobs object ready to run.
        
        Args:
            params: The parameters to use to generate the jobs object.

        Returns:
            A Jobs object ready to run.
        """

    def add_output_formatter(self, formatter: OutputFormatter, set_default: bool = False) -> "App":
        """Add an additional output formatter to this app (fluent).

        Args:
            formatter: An `OutputFormatter` instance to add.
            set_default: If True, set this formatter as the default for subsequent outputs.

        Returns:
            The `App` instance to allow fluent chaining.

        Raises:
            TypeError: If `formatter` is not an `OutputFormatter`.
            ValueError: If the formatter has no name or the name already exists.
        """
        if not isinstance(formatter, OutputFormatter):
            raise TypeError("formatter must be an OutputFormatter")
        if not getattr(formatter, "name", None):
            raise ValueError("formatter must have a unique, non-empty name")
        if formatter.name in self.output_formatters.mapping:
            raise ValueError(f"Formatter with name '{formatter.name}' already exists")

        # Append and keep the mapping in sync
        self.output_formatters.data.append(formatter)
        self.output_formatters.mapping[formatter.name] = formatter

        if set_default:
            self.output_formatters.set_default(formatter.name)

        return self

    @property 
    def parameters(self) -> dict:
        """Returns the parameters of the application.
        
        >>> App.example().parameters
        [('raw_text', 'text', 'What is the text to split into a twitter thread?')]
        """
        if self.initial_survey is None:
            return []
        return [(q.question_name, q.question_type, q.question_text) for q in self.initial_survey]


    def __repr__(self) -> str:
        return f"App: application_name={self.application_name}, description={self.description}"

    def _validate_parameters(self) -> None:

        if self.initial_survey is None: # Some apps do not require a survey
            return
        input_survey_params = [x[0] for x in self.parameters]
        head_params = self.jobs_object.head_parameters
        for param in head_params:
            if "." not in param:
                continue # not a scenario parameter - could be a calculated field, for example
            prefix, param_name = param.split('.')
            if prefix != 'scenario':
                continue
            if param_name not in input_survey_params:
                raise ValueError(f"The parameter {param_name} is not in the input survey."
                f"Input survey parameters: {input_survey_params}, Head job parameters: {head_params}")

        if self.jobs_object.has_post_run_methods:
            print(self.jobs_object._post_run_methods)
            raise ValueError("Cannot have post_run_methods in the jobs object if using output formatters.")

    def _collect_answers_interactively(self) -> dict:
        """Collect answers interactively using Textual if available, else fallback.

        Returns:
            dict: Mapping question_name -> answer, with file uploads normalized to FileStore.
        """
        if self.initial_survey is None:
            raise ValueError("Cannot collect answers interactively without an initial_survey.")

        answers = None
        # Prefer Textual TUI if installed
        try:
            from ..surveys.textual_interactive_survey import run_textual_survey  # type: ignore
            answers = run_textual_survey(self.initial_survey, title=self.application_name)
        except Exception:
            # Fallback to existing Rich-based flow
            try:
                from ..surveys import InteractiveSurvey  # type: ignore
                answers = InteractiveSurvey(self.initial_survey).run()
            except Exception as e:
                raise e

        # Normalize file uploads to FileStore
        try:
            for question_name, answer in list(answers.items()):
                q = self.initial_survey[question_name]
                if getattr(q, 'question_type', None) == "file_upload":
                    from ..scenarios import FileStore  # type: ignore
                    answers[question_name] = FileStore(path=answer)
        except Exception:
            # Best-effort normalization; keep raw answers if anything goes wrong
            pass

        return answers or {}

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Convert the app to a dictionary for serialization.
        
        Args:
            add_edsl_version: Whether to add the E[P] version to the dictionary.
        
        Returns:
            A dictionary representing the app.
        """
        return {
            "initial_survey": self.initial_survey.to_dict(add_edsl_version = add_edsl_version) if self.initial_survey else None,
            "jobs_object": self.jobs_object.to_dict(add_edsl_version = add_edsl_version),
            "application_type": self.application_type,
            "application_name": self.application_name,
            "description": self.description,
            "output_formatters": self.output_formatters.to_dict(add_edsl_version = add_edsl_version),
        }

    @property
    def application_type(self) -> str:  # type: ignore[override]
        return getattr(self.__class__, "application_type", self.__class__.__name__)

    @classmethod
    def from_dict(cls, data: dict) -> 'App':
        """Create an app from a dictionary.
        
        Args:
            data: A dictionary representing the app.
        
        Returns:
            An app object.
        """
        # Choose subclass via registry using application_type (if available)
        from ..jobs import Jobs
        from ..surveys import Survey

        # Prepare constructor kwargs (shared __init__ across subclasses)
        kwargs = {
            "jobs_object": Jobs.from_dict(data.get("jobs_object")),
            "output_formatters": OutputFormatters.from_dict(data.get("output_formatters")),
            "description": data.get("description"),
            "application_name": data.get("application_name"),
            "initial_survey": Survey.from_dict(data.get("initial_survey")),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        app_type = data.get("application_type")
        target_cls: type[App]
        if isinstance(app_type, str) and app_type in App._registry:
            target_cls = App._registry[app_type]
        else:
            target_cls = cls

        return target_cls(**kwargs)


    def push(self, visibility: Optional[str] = "unlisted", description: Optional[str] = None, alias: Optional[str] = None):
        """Pushes the application to the E[P] server."""
        job_info = self.jobs_object.push(visibility = visibility).to_dict()
        if self.initial_survey is not None:
            initial_survey_info = self.initial_survey.push(visibility = visibility).to_dict()
        else:
            initial_survey_info = None

        app_info = Scenario({
            'description': self.description, 
            'application_name': self.application_name,
            'initial_survey_info': initial_survey_info,
            'job_info': job_info,
            'application_type': self.application_type,
            'class_name': self.__class__.__name__,
            'output_formatters_info': self.output_formatters.to_dict(),
        }).push(visibility = visibility, description = description, alias = alias)
        return app_info

    @classmethod
    def pull(cls, edsl_uuid: str) -> 'App':
        """Pulls the application from the E[P]."""
        from ..surveys import Survey
        from ..jobs import Jobs
        from ..scenarios import Scenario

        # Get the information
        app_info = Scenario.pull(edsl_uuid)
        jobs_object = Jobs.pull(app_info['job_info']['uuid'])
        if app_info['initial_survey_info'] is not None:
            initial_survey = Survey.pull(app_info['initial_survey_info']['uuid'])
        else:
            initial_survey = None
        output_formatters = OutputFormatters.from_dict(app_info.get('output_formatters_info'))

        # Prepare kwargs (shared __init__ across subclasses)
        kwargs = {
            'jobs_object': jobs_object,
            'output_formatters': output_formatters,
            'description': app_info.get('description'),
            'application_name': app_info.get('application_name'),
            'initial_survey': initial_survey,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        app_type = app_info.get('application_type')
        target_cls: type[App]
        if isinstance(app_type, str) and app_type in App._registry:
            target_cls = App._registry[app_type]
        else:
            target_cls = cls

        return target_cls(**kwargs)

class SingleScenarioApp(App):
    """This is for the case when the app takes a single scenario as input.
    
    - might make more sense to:
       - find out what it is / declare what it is 
       - have a InputTransformer before it is applied
    
    Input possibilities:
    - A scenario (either as params = {} or from _collect_answers_interactively)
    -- A scenario list (either as params = {} or from _collect_answers_interactively)
  
    -- A agent list (either as params = {} or from _collect_answers_interactively)
    -- A survey (either as params = {} or from _collect_answers_interactively)

    For a survey, we might either run it or turn it to a scenario list first. 

    Three modification possibilities:
    --- adds a scenario / scenario list to head 
    --- adds a agent_list 
    --- adds a survey
    """
    application_type: str = "single_scenario_input"

    def _prepare_from_params(self, params: dict) -> HeadAttachments:
        from ..scenarios import FileStore
        normalized: dict = {}
        for key, value in params.items():
            relevant_question = self.initial_survey[key] if self.initial_survey else None
            if relevant_question is not None and getattr(relevant_question, 'question_type', None) == "file_upload":
                normalized[key] = FileStore(path=value)
            else:
                normalized[key] = value
        scenario = Scenario(normalized)
        return HeadAttachments(scenario=scenario)

    def output(self, params: Optional[dict] = None, verbose: bool = False, formater_to_use: Optional[str] = None) -> Any:
        if params is None:
            params = self._collect_answers_interactively()
        head_attachments = self._prepare_from_params(params)
        jobs = head_attachments.attach_to_head(self.jobs_object)
        return self._render(jobs, formater_to_use)


class SurveyInputApp(App):
    application_type: str = "edsl_survey_as_input"

    def _prepare_from_params(self, params: 'Survey') -> HeadAttachments:
        return HeadAttachments(scenario=params.to_scenario_list())

class AgentsInputApp(App):
    application_type: str = "edsl_agents_as_input"

    def _prepare_from_params(self, params: 'AgentList') -> HeadAttachments:
        return HeadAttachments(agent_list=params)

class GiveToAgentsApp(App):
    application_type: str = "give_to_agents"

    def _prepare_from_params(self, params: 'Survey') -> HeadAttachments:
        return HeadAttachments(survey=params)

class PersonSimulator(App):
    application_type: str = "person_simulator"
    default_output_formatter: OutputFormatter = OutputFormatter(name="Persona Answers").select('answer.*').to_list()

    input_type: Survey
    modified_jobs_component: Survey

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

        # default output_formatters handled by base class via default_output_formatter

        instruction = (
            "You are answering questions fully in character as the following person.\n"
            "Context:\n" + persona_context + "\n"
            "Stay strictly in character and do not break persona."
        )
        self.persona_agent = Agent(name=agent_name or "Persona", instruction=instruction)

        # Minimal jobs object for base constructor
        jobs_object = Survey([]).by(self.persona_agent)

        super().__init__(
            jobs_object=jobs_object,
            output_formatters=output_formatters,
            description=description,
            application_name=application_name or "Person Simulator",
            initial_survey=None,
        )

    def _prepare_from_params(self, params: Any) -> 'HeadAttachments':
        from ..surveys import Survey
        from ..questions import QuestionFreeText

        # Normalize params into a Survey of free-text questions
        if isinstance(params, Survey):
            survey = params
        elif isinstance(params, list) and all(isinstance(q, str) for q in params):
            questions = [
                QuestionFreeText(question_name=f"q_{i}", question_text=text)
                for i, text in enumerate(params)
            ]
            survey = Survey(questions)
        else:
            raise TypeError(
                "params must be either a Survey or a list[str] of question texts"
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
            raise ValueError(f"Directory not found or not a directory: {directory_path}")

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
                    sections.append(f"<source path=\"{p}\">\n{text.strip()}\n</source>")
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
            search_scenarios = search_result[0] if isinstance(search_result, tuple) else search_result

            urls: list[str] = []
            for scenario in search_scenarios:
                try:
                    if "url" in scenario and isinstance(scenario["url"], str) and scenario["url"].strip():
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
                scraped = scrape_result[0] if isinstance(scrape_result, tuple) else scrape_result

                text_chunks: list[str] = []
                count = 0
                for scenario in scraped:
                    if count >= max_pages:
                        break
                    # Prefer full content/markdown fields
                    if "content" in scenario and isinstance(scenario["content"], str) and scenario["content"].strip():
                        text_chunks.append(scenario["content"].strip())
                    elif "markdown" in scenario and isinstance(scenario["markdown"], str) and scenario["markdown"].strip():
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



class DataLabelingParams(TypedDict):
    file_path: str
    labeling_question: Any


class DataLabelingApp(App):
    application_type: str = "data_labeling"

    def _prepare_from_params(self, params: DataLabelingParams) -> 'HeadAttachments':
        if 'labeling_question' not in params:
            raise ValueError("labeling_question is required for data labeling")
        if 'file_path' not in params:
            raise ValueError("file_path is required for data labeling")

        from ..scenarios import FileStore
        file_store = FileStore(path=params['file_path'])
        try:
            sl = file_store.to_scenario_list()
        except Exception as e:
            raise ValueError(f"Error converting file to scenario list: {e}. Allowed formats are csv and xlsx.")

        labeling_question = params['labeling_question']
        return HeadAttachments(scenario=sl, survey=labeling_question.to_survey())

    @classmethod
    def example(cls):
        from ..surveys import Survey
        from ..language_models import Model 
        from ..questions import QuestionFreeText, QuestionList
        initial_survey = Survey([QuestionFreeText(question_text = "What is your intended college major", question_name = "intended_college_major")])

        logic_survey = QuestionList(
            question_name = "courses_to_take", 
            question_text = "What courses do you need to take for major: {{scenario.intended_college_major}}"
        )
        m = Model()
        job = logic_survey.by(m) 
        return SingleScenarioApp(
            initial_survey = initial_survey,
            jobs_object = job,
            output_formatters = OutputFormatters([
                OutputFormatter(name = "Courses To Take").select('scenario.intended_college_major','answer.courses_to_take').table()
            ])
        )


if __name__ == "__main__":
    from edsl import QuestionFreeText, QuestionList
    initial_survey = Survey([QuestionFreeText(
       question_name = "raw_text", 
       question_text = "What is the text to split into a twitter thread?")]
    )
    jobs_survey = Survey([QuestionList(
       question_name = "twitter_thread", 
       question_text = "Please take this text: {{scenario.raw_text}} and split into a twitter thread, if necessary.")]
    )

    twitter_output_formatter = (
        OutputFormatter(name = "Twitter Thread Splitter")
        .select('answer.twitter_thread')
        .expand('answer.twitter_thread')
        .table()
    )

    app = SingleScenarioApp(
        application_name = "Twitter Thread Splitter",
        description = "This application splits text into a twitter thread.",
        initial_survey = initial_survey, 
        jobs_object = jobs_survey.to_jobs(), 
        output_formatters = OutputFormatters([twitter_output_formatter])
        )

    raw_text = """ 
    The Senate of the United States shall be composed of two Senators from each State, chosen by the Legislature thereof, for six Years; and each Senator shall have one Vote.
    Immediately after they shall be assembled in Consequence of the first Election, they shall be divided as equally as may be into three Classes. The Seats of the Senators of the first Class shall be vacated at the Expiration of the second Year, of the second Class at the Expiration of the fourth Year, and of the third Class at the Expiration of the sixth Year, so that one third may be chosen every second Year; and if Vacancies happen by Resignation, or otherwise, during the Recess of the Legislature of any State, the Executive thereof may make temporary Appointments until the next Meeting of the Legislature, which shall then fill such Vacancies.
    No Person shall be a Senator who shall not have attained to the Age of thirty Years, and been nine Years a Citizen of the United States, and who shall not, when elected, be an Inhabitant of that State for which he shall be chosen.
    The Vice President of the United States shall be President of the Senate, but shall have no Vote, unless they be equally divided.
    The Senate shall chuse their other Officers, and also a President pro tempore, in the Absence of the Vice President, or when he shall exercise the Office of President of the United States.
    The Senate shall have the sole Power to try all Impeachments. When sitting for that Purpose, they shall be on Oath or Affirmation. When the President of the United States is tried, the Chief Justice shall preside: And no Person shall be convicted without the Concurrence of two thirds of the Members present.
    Judgment in Cases of Impeachment shall not extend further than to removal from Office, and disqualification to hold and enjoy any Office of honor, Trust or Profit under the United States: but the Party convicted shall nevertheless be liable and subject to Indictment, Trial, Judgment and Punishment, according to Law.
    """

    lazarus_app = App.from_dict(app.to_dict())
    
    # non-interactive mode
    output = lazarus_app.output(params = {'raw_text': raw_text}, verbose = True)
    print(output)

