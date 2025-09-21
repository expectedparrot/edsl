from typing import TYPE_CHECKING, Optional, Any, Callable
from ..base import Base
from ..scenarios import Scenario
from ..surveys import Survey

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..scenarios import ScenarioList
from .output import OutputFormatters  # runtime import for formatter list helper

# We want apps that take a survey
from abc import ABC, abstractmethod

class AppBase(ABC):
    # Simple registry for subclasses of AppBase
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
        application_type: Optional[str] = None,
        initial_survey: Optional[Survey] = None):
        self.jobs_object = jobs_object
        self.description = description
        self.initial_survey = initial_survey
        if output_formatters is None or len(output_formatters) == 0:
            raise ValueError("At least one output formatter is required for all apps")
        self.output_formatters: OutputFormatters = output_formatters


    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Do not register the base class itself
        if cls is AppBase:
            return
        # Register by class name
        AppBase.registry[cls.__name__] = cls
        # Also register by application_type if provided
        application_type = getattr(cls, "application_type", None)
        if application_type:
            AppBase.registry[application_type] = cls

    def to_dict(self, add_edsl_version: bool = True):
        return {
            "initial_survey": self.initial_survey.to_dict(add_edsl_version = add_edsl_version) if self.initial_survey else None,
            "jobs_object": self.jobs_object.to_dict(add_edsl_version = add_edsl_version),
            "application_type": self.application_type,
            "description": self.description,
            "output_formatters": self.output_formatters.to_dict(add_edsl_version = add_edsl_version),
        }

    @classmethod
    def from_dict(cls, data: dict):
        # Choose subclass via registry using application_type (if available)
        application_type = data.get("application_type")
        target_cls = AppBase.registry.get(application_type, cls) if application_type else cls

        # Reconstruct output formatters list if serialized
        from .output import OutputFormatters  # local import to avoid circular refs in type checking
        output_formatters = OutputFormatters.from_dict(data.get("output_formatters"))

        # Prepare constructor kwargs filtered to the target class's __init__
        import inspect

        init_params = inspect.signature(target_cls.__init__).parameters
        candidate_kwargs = {
            "jobs_object": data.get("jobs_object"),
            "output_formatters": output_formatters,
            "description": data.get("description"),
            "application_type": data.get("application_type"),
            "initial_survey": data.get("initial_survey"),
        }
        filtered_kwargs = {k: v for k, v in candidate_kwargs.items() if v is not None and k in init_params}

        return target_cls(**filtered_kwargs)

    @abstractmethod
    def generate_results(self, *args, **kwargs) -> 'Results':
        pass

    def output(self, verbose: bool = False, **kwargs) -> Any:
        """Generate output by running and formatting results via the default output formatter."""
        import inspect
        sig = inspect.signature(self.generate_results)
        call_kwargs = dict(kwargs)
        if 'verbose' in sig.parameters:
            call_kwargs['verbose'] = verbose
        results = self.generate_results(**call_kwargs)
        formatter = self.output_formatters.get_default()
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

        # Run and get results
        sig = inspect.signature(self.generate_results)
        call_kwargs = dict(kwargs)
        if 'verbose' in sig.parameters:
            call_kwargs['verbose'] = verbose
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

            print_func("Select an output formatter:")
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
        # Print strings to stdout for convenience, regardless of return
        if isinstance(rendered, str):
            print_func(rendered)
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

        # Filter kwargs to the target class constructor signature
        import inspect
        init_params = inspect.signature(target_cls.__init__).parameters
        candidate_kwargs = {
            'jobs_object': jobs_object,
            'output_formatters': output_formatters,
            'description': app_info.get('description'),
            'application_type': application_type,
            'initial_survey': initial_survey,
        }
        filtered_kwargs = {k: v for k, v in candidate_kwargs.items() if v is not None and k in init_params}

        return target_cls(**filtered_kwargs)

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



class AppSurvey(AppBase):
    
    application_type = "survey"

    def generate_results(self, survey: 'Survey') -> 'Results':
        sl = survey.to_scenario_list()
        return self.jobs_object.add_scenario_head(sl).run()
    
class AppScenarioList(AppBase):

    application_type = "scenario_list"

    def generate_results(self, scenario_list: 'ScenarioList') -> 'Results':
        jobs = self.jobs_object.by(scenario_list)
        return jobs.run()
    
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
    #app = App.example()
    from ..surveys import Survey
    from ..questions import QuestionFreeText, QuestionMultipleChoice
    s = Survey([
        QuestionFreeText(
            question_name = "confusion", 
            question_text = "What might survey respondents be confused by: {{scenario.question_text }}?"),
    ])
    from ..scenarios import ScenarioList

    sl = ScenarioList.from_list("tweet", ["I hate this movie", "I love this movie", "I think this movie is ok"])
    jobs_object = Survey([
        QuestionMultipleChoice(
            question_name = "tweet_sentiment", 
            question_text = "What is the sentiment of the following tweet: {{scenario.tweet}}?",
            question_options = ["positive", "negative", "neutral"]
        )
    ]).to_jobs()
    from .output import RawResultsOutput  # type: ignore
    from .output import TableOutput, OutputFormatters  # type: ignore
    app = AppScenarioList(
        jobs_object = jobs_object,
        output_formatters = OutputFormatters([
            TableOutput([
            'scenario.tweet',
            'answer.tweet_sentiment',
            ]),
        ])
    )

    info = app.push()
    new_app = AppBase.pull(info['uuid'])
    output = new_app.output(scenario_list = sl, verbose = True)
    print(output)
    
    #output = app.output(scenario_list = sl, verbose = True)
    #print(output)

    #results.select('scenario.question_text','answer.confusion').table()

    #output = app.output(verbose = True)
    #print(output)

