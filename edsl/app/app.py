from typing import TYPE_CHECKING, Optional, Any, Callable, Union
from ..base import Base
from ..scenarios import Scenario
from ..surveys import Survey

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..scenarios import ScenarioList

#from .output import OutputFormatters  # runtime import for formatter list helper
from .output_formatter import OutputFormatter, OutputFormatters


# We want apps that take a survey
from abc import ABC, abstractmethod

class AppBase(ABC):
    # Registry for subclasses of AppBase
    registry = {}
    application_type = None

    """
    A class representing an EDSL application.

    An EDSL application requires the user to complete an initial survey. 
    This creates parameters that are used to run a jobs object.
    The jobs object has the logic for the application.
    """
    def __init__(self, 
        jobs_object: 'Jobs', 
        output_formatters: OutputFormatters, 
        description: Optional[str] = None,
        application_name: Optional[str] = None,
        initial_survey: Optional[Survey] = None):
        """Instantiate an AppBase object.
        
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
        if output_formatters is None or len(output_formatters) == 0:
            raise ValueError("At least one output formatter is required for all apps")
        self.output_formatters: OutputFormatters = output_formatters
        if application_name is not None and not isinstance(application_name, str):
            raise TypeError("application_name must be a string if provided")
        # Default to the class name if not provided
        self.application_name: str = application_name or self.__class__.__name__
        self._validate_parameters()

    @abstractmethod
    def answers_to_scenario(self, answers: dict) -> 'Scenario':
        """Converts the answers to a scenario.
        
        Args:
            answers: The answers to the application.
        """
        return Scenario(answers)

    @property 
    def parameters(self) -> dict:
        """Returns the parameters of the application.
        
        >>> AppBase.example().parameters
        [('raw_text', 'text', 'What is the text to split into a twitter thread?')]
        """
        return [(q.question_name, q.question_type, q.question_text) for q in self.initial_survey]


    def __repr__(self) -> str:
        return f"AppBase: application_name={self.application_name}, description={self.description}"


    def _validate_parameters(self) -> None:
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

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Do not register the base class itself
        if cls is AppBase:
            return
        # Enforce that subclasses define a non-None application_type
        application_type = getattr(cls, "application_type", None)
        if application_type is None:
            raise TypeError(f"{cls.__name__} must define a non-None class variable 'application_type'")
        # Register by class name and by application_type
        AppBase.registry[cls.__name__] = cls
        AppBase.registry[application_type] = cls


    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Convert the app to a dictionary.
        
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

    @classmethod
    def from_dict(cls, data: dict) -> 'AppBase':
        """Create an app from a dictionary.
        
        Args:
            data: A dictionary representing the app.
        
        Returns:
            An app object.
        """
        # Choose subclass via registry using application_type (if available)
        application_type = data.get("application_type")
        target_cls = AppBase.registry.get(application_type, cls) if application_type else cls

        # Reconstruct output formatters list if serialized
        from .output import OutputFormatters  # local import to avoid circular refs in type checking
        output_formatters = OutputFormatters.from_dict(data.get("output_formatters"))

        # Prepare constructor kwargs (shared __init__ across subclasses)
        kwargs = {
            "jobs_object": data.get("jobs_object"),
            "output_formatters": output_formatters,
            "description": data.get("description"),
            "application_name": data.get("application_name"),
            "initial_survey": data.get("initial_survey"),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        return target_cls(**kwargs)

    def generate_results(self, scenario_or_scenario_list: Union['Scenario','ScenarioList']) -> 'Results':
        return self.jobs_object.add_scenario_head(scenario_or_scenario_list).run()

    def output(self, answers: Optional[dict] = None, verbose: bool = False, formater_to_use: Optional[str] = None) -> Any:
        """Generate output by running and formatting results via the default output formatter."""

        if formater_to_use is not None:
            formatter = self.output_formatters.get_formatter(formater_to_use)
        else:
            formatter = self.output_formatters.get_default()

        if answers is None:
            answers = self._collect_answers_interactively()

        scenario = self.answers_to_scenario(answers)
        results = self.generate_results(scenario)
        return formatter.render(results)

    def run(
        self,
        formatter: Optional[str] = None,
        interactive: bool = True,
        verbose: bool = False,
        input_func: Callable[[str], str] = input,
        print_func: Callable[[Any], None] = print,
        **kwargs,
    ) -> Any:
        """Run the job, then render results using a chosen output formatter.

        - If `formatter` is provided, use it by id (or index if a string digit)
        - If `interactive` and no `formatter`, prompt the user to select
        - Otherwise, use the default formatter
        """
        import inspect
        import sys

        # Run and get results with a spinner if interactive
        sig = inspect.signature(self.generate_results)
        call_kwargs = dict(kwargs)
        if 'verbose' in sig.parameters:
            call_kwargs['verbose'] = verbose

        # If this is the interactive survey app and we're in interactive mode,
        # collect survey answers BEFORE starting the spinner so the spinner only
        # runs during the job execution (not while answering questions).
        try:
            is_interactive_survey_app = getattr(self, "application_type", None) == "interactive_survey"
        except Exception:
            is_interactive_survey_app = False
        if is_interactive_survey_app and interactive and sys.stdin and sys.stdin.isatty() and 'answers' not in call_kwargs:
            try:
                call_kwargs['answers'] = self._collect_answers_interactively()
            except Exception:
                # If pre-collection fails, fall back to normal generate_results behavior
                pass

        results = None
        if interactive and sys.stdout and sys.stdout.isatty():
            import threading
            import itertools
            import time

            stop_spinner = False

            def spinner_task():
                for ch in itertools.cycle("⠋⠙⠚⠞⠖⠦⠴⠲⠳⠓"):
                    if stop_spinner:
                        break
                    try:
                        sys.stdout.write(f"\rRunning job... {ch}")
                        sys.stdout.flush()
                    except Exception:
                        pass
                    time.sleep(0.1)
                try:
                    sys.stdout.write("\rRunning job... done   \n")
                    sys.stdout.flush()
                except Exception:
                    pass

            spinner_thread = threading.Thread(target=spinner_task, daemon=True)
            spinner_thread.start()
            try:
                results = self.generate_results(**call_kwargs)
            finally:
                stop_spinner = True
                spinner_thread.join()
        else:
            results = self.generate_results(**call_kwargs)

        # Resolve formatter
        chosen_formatter = None

        # Helper to coerce formatter selection
        def _resolve_formatter(selection: Optional[str]):
            if selection is None or selection == "default":
                return self.output_formatters.get_default()
            # Numeric index provided as string
            if isinstance(selection, str) and selection.isdigit():
                idx = int(selection) - 1
                return self.output_formatters[idx]
            # Treat as id
            try:
                return self.output_formatters[selection]  # type: ignore[index]
            except Exception:
                # Fallback to default if invalid
                return self.output_formatters.get_default()

        if formatter is not None:
            chosen_formatter = _resolve_formatter(formatter)
        elif interactive and sys.stdin and sys.stdin.isatty():
            # Interactive selection
            ids = self.output_formatters.ids()
            labels = self.output_formatters.labels()
            default_idx = self.output_formatters.default_index or 0

            print_func("Select an output option:")
            for i, (fid, label) in enumerate(zip(ids, labels), start=1):
                suffix = " (default)" if (i - 1) == default_idx else ""
                print_func(f"  [{i}] {label} ({fid}){suffix}")
            prompt = f"Enter number or id [default {default_idx + 1}]: "
            choice = input_func(prompt).strip()
            if choice == "":
                choice = str(default_idx + 1)
            chosen_formatter = _resolve_formatter(choice)
        else:
            chosen_formatter = self.output_formatters.get_default()

        rendered = chosen_formatter.render(results)
        # Print helpful confirmation/output for common return types
        try:
            from ..scenarios.file_store import FileStore  # local import to avoid cycle
        except Exception:
            FileStore = None  # type: ignore

        if isinstance(rendered, str):
            print_func(rendered)
        elif FileStore is not None and isinstance(rendered, FileStore):
            # Confirm saved path to user
            path = getattr(rendered, "path", None)
            if isinstance(path, str) and path:
                print_func(f"Saved file: {path}")
        return rendered

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
    def pull(cls, edsl_uuid: str) -> 'AppBase':
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
        from .output import OutputFormatters  # type: ignore
        output_formatters = OutputFormatters.from_dict(app_info.get('output_formatters_info'))

        # Resolve the concrete application class via the registry
        application_type = app_info.get('application_type')
        # Resolve by application_type first, then by class name, finally fallback to cls
        target_cls = (
            AppBase.registry.get(application_type)
            or AppBase.registry.get(app_info.get('class_name'))
            or cls
        )

        # Prepare kwargs (shared __init__ across subclasses)
        kwargs = {
            'jobs_object': jobs_object,
            'output_formatters': output_formatters,
            'description': app_info.get('description'),
            'application_name': app_info.get('application_name'),
            'initial_survey': initial_survey,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        return target_cls(**kwargs)

    @classmethod
    def example(cls):
        from ..surveys import Survey
        from ..language_models import Model 
        from ..questions import QuestionFreeText, QuestionList
        from .output import AnswersListOutput, OutputFormatters  # type: ignore
        initial_survey = Survey([QuestionFreeText(question_text = "What is your intended college major", question_name = "intended_college_major")])

        logic_survey = QuestionList(
            question_name = "courses_to_take", 
            question_text = "What courses do you need to take for major: {{scenario.intended_college_major}}"
        )
        m = Model()
        job = logic_survey.by(m) 
        return AppInteractiveSurvey(initial_survey = initial_survey, jobs_object = job, output_formatters = OutputFormatters([AnswersListOutput()]))


class App(AppBase):
    application_type = "basic_app"

    def answers_to_scenario(self, answers: dict) -> 'Scenario':
        from ..scenarios import Scenario
        return Scenario(answers)

class AppSurvey(AppBase):
    
    application_type = "survey"

    def generate_results(self, survey: 'Survey') -> 'Results':
        sl = survey.to_scenario_list()
        return self.jobs_object.add_scenario_head(sl).run()
    
class AppScenarioList(AppBase):

    application_type = "scenario_list"

    def generate_results(self, scenario_list: 'ScenarioList') -> 'Results':
        jobs = self.jobs_object.add_scenario_head(scenario_list)
        return jobs.run()

class AppText(AppBase):

    application_type = "text"

    def generate_results(self, text: str) -> 'Results':
        from ..scenarios import Scenario
        s = Scenario({'text': text})
        return self.jobs_object.add_scenario_head(s).run()

    @classmethod
    def example(cls):
        from ..questions import QuestionList 
        from .output import OutputFormatters  # type: ignore
        survey = QuestionList(question_name = "twitter_thread", 
        question_text = "Please take this text: {{scenario.text}} and split into a twitter thread.")
        jobs_object = survey.to_jobs().select('answer.twitter_thread').expand('answer.twitter_thread')
        return cls(
            jobs_object = jobs_object,
            description = "Applications that split text into a twitter thread",
            output_formatters = OutputFormatters([PassThroughOutput()])
            )
    
class AppImage(AppBase):

    application_type = "image"

    def generate_results(self, image_path: Any) -> 'Results':
        from ..scenarios import FileStore, Scenario
        s = Scenario({'image': FileStore(path = image_path)})
        return self.jobs_object.by(s).run()

class AppPDF(AppBase):
    
    application_type = "pdf"
    
    def generate_results(self, pdf_path: Any) -> 'Results':
        from ..scenarios import FileStore, Scenario
        s = Scenario({'paper': FileStore(path = pdf_path)})
        return self.jobs_object.by(s).run()

class AppInteractiveSurvey(AppBase):
    
    application_type = "interactive_survey"

    def generate_results(self, answers: Optional[dict] = None, verbose: bool = False) -> 'Results':
        """Generates the results of the application.
        
        Args:
            answers: A dictionary of answers to the initial survey. 
            If None, the user will be prompted to answer the questions.

        Returns:
            The results object generated by running the jobs object.
        """
        from ..scenarios import Scenario
        if answers is None:
            from ..surveys import InteractiveSurvey
            answers = InteractiveSurvey(self.initial_survey).run()

            # if a file was uploaded, we need to store it in the file store
            for question_name, answer in answers.items():
                q = self.initial_survey[question_name]
                if q.question_type == "file_upload":
                    from ..scenarios import FileStore
                    answers[question_name] = FileStore(path = answer)

        scenario = Scenario(answers)
        if verbose:
            print("Running the application...")

        if verbose:
            print("Adding scenario to the job...")
        # add scenario to the job (if it's recursive)
        self.jobs_object.add_scenario_head(scenario)
        if verbose:
            print("Scenario added to the job...")
            print("Running the job...")
        results = self.jobs_object.add_scenario_head(scenario).run(verbose = verbose)

        if verbose:
            print("Complete")
        self._results = results
        return results


    def code(self):
        pass


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

    app = App(
        application_name = "Twitter Thread Splitter",
        description = "This application splits text into a twitter thread.",
        initial_survey = initial_survey, 
        jobs_object = jobs_survey.to_jobs(), 
        output_formatters = OutputFormatters([twitter_output_formatter])
        )

    # app = AppText.example()
    raw_text = """ 
    The Senate of the United States shall be composed of two Senators from each State, chosen by the Legislature thereof, for six Years; and each Senator shall have one Vote.
    Immediately after they shall be assembled in Consequence of the first Election, they shall be divided as equally as may be into three Classes. The Seats of the Senators of the first Class shall be vacated at the Expiration of the second Year, of the second Class at the Expiration of the fourth Year, and of the third Class at the Expiration of the sixth Year, so that one third may be chosen every second Year; and if Vacancies happen by Resignation, or otherwise, during the Recess of the Legislature of any State, the Executive thereof may make temporary Appointments until the next Meeting of the Legislature, which shall then fill such Vacancies.
    No Person shall be a Senator who shall not have attained to the Age of thirty Years, and been nine Years a Citizen of the United States, and who shall not, when elected, be an Inhabitant of that State for which he shall be chosen.
    The Vice President of the United States shall be President of the Senate, but shall have no Vote, unless they be equally divided.
    The Senate shall chuse their other Officers, and also a President pro tempore, in the Absence of the Vice President, or when he shall exercise the Office of President of the United States.
    The Senate shall have the sole Power to try all Impeachments. When sitting for that Purpose, they shall be on Oath or Affirmation. When the President of the United States is tried, the Chief Justice shall preside: And no Person shall be convicted without the Concurrence of two thirds of the Members present.
    Judgment in Cases of Impeachment shall not extend further than to removal from Office, and disqualification to hold and enjoy any Office of honor, Trust or Profit under the United States: but the Party convicted shall nevertheless be liable and subject to Indictment, Trial, Judgment and Punishment, according to Law.
    """
    # non-interactive mode
    output = app.output(answers = {'raw_text': raw_text}, verbose = True)
    print(output)

    # interactive mode
    #output = app.output(verbose = True)
    #print(output)
    #app = App.example()
    # from ..surveys import Survey
    # from ..questions import QuestionFreeText, QuestionMultipleChoice
    # s = Survey([
    #     QuestionFreeText(
    #         question_name = "confusion", 
    #         question_text = "What might survey respondents be confused by: {{scenario.question_text }}?"),
    # ])
    # from ..scenarios import ScenarioList

    # sl = ScenarioList.from_list("tweet", ["I hate this movie", "I love this movie", "I think this movie is ok"])
    # jobs_object = Survey([
    #     QuestionMultipleChoice(
    #         question_name = "tweet_sentiment", 
    #         question_text = "What is the sentiment of the following tweet: {{scenario.tweet}}?",
    #         question_options = ["positive", "negative", "neutral"]
    #     )
    # ]).to_jobs()
    # from .output import RawResultsOutput  # type: ignore
    # from .output import TableOutput, OutputFormatters  # type: ignore
    # app = AppScenarioList(
    #     jobs_object = jobs_object,
    #     output_formatters = OutputFormatters([
    #         TableOutput([
    #         'scenario.tweet',
    #         'answer.tweet_sentiment',
    #         ]),
    #     ])
    # )

    # info = app.push()
    # new_app = AppBase.pull(info['uuid'])
    # output = new_app.output(scenario_list = sl, verbose = True)
    # print(output)
    
    #output = app.output(scenario_list = sl, verbose = True)
    #print(output)

    #results.select('scenario.question_text','answer.confusion').table()

    #output = app.output(verbose = True)
    #print(output)

