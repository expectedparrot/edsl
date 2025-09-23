from re import A
from typing import TYPE_CHECKING, Optional, Any, Callable, Union
from ..base import Base
from ..scenarios import Scenario
from ..surveys import Survey

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..scenarios import ScenarioList

from .output_formatter import OutputFormatter, OutputFormatters

class AppDeployment:
    license_type: str
    github_repo: str
    timestamp: str
    source_available: bool
    documentation: str
    thumbnail: str

from functools import partial

def single_scenario_prepare(app: 'App', params: dict) -> 'Jobs':
    from ..scenarios import FileStore
    for key, value in params.items():
        relevant_question = app.initial_survey[key]
        if relevant_question.question_type == "file_upload":
            params[key] = FileStore(path=value)
        else:
            params[key] = value
    scenario = Scenario(params)
    return app.jobs_object.add_scenario_head(scenario)

def edsl_survey_as_input(app: 'App', params: dict) -> 'Jobs':
    return app.jobs_object.add_scenario_head(params.to_scenario_list())

def give_survey_to_agents(app: 'App', params: dict) -> 'Jobs':
    return app.jobs_object.add_survey_to_head(params)

APPLICATION_INPUT_STRATEGIES = {
 'single_scenario_input': single_scenario_prepare,
 'edsl_survey_as_input': edsl_survey_as_input, 
 'give_to_agents': give_survey_to_agents,
}

class App:
    """
    A class representing an EDSL application.

    An EDSL application requires the user to complete an initial survey. 
    This creates parameters that are used to run a jobs object.
    The jobs object has the logic for the application.
    """
    def __init__(self, 
        jobs_object: 'Jobs', 
        output_formatters: Optional[list[OutputFormatter]] = None, 
        description: Optional[str] = None,
        application_name: Optional[str] = None,
        initial_survey: Optional[Survey] = None, 
        application_type: Optional[str] = 'single_scenario_input'):
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
        self.application_type = application_type
        if output_formatters is None or len(output_formatters) == 0:
            raise ValueError("At least one output formatter is required for all apps")
        self.output_formatters: OutputFormatters = OutputFormatters(output_formatters)
        if application_name is not None and not isinstance(application_name, str):
            raise TypeError("application_name must be a string if provided")
        # Default to the class name if not provided
        self.application_name: str = application_name or self.__class__.__name__
        self._validate_parameters()

        if application_type not in APPLICATION_INPUT_STRATEGIES:
            raise ValueError(f"Invalid application type: {application_type}")

        self._prepare_jobs_object = partial(APPLICATION_INPUT_STRATEGIES[application_type], app = self)

    @classmethod
    def list(cls) -> list[str]:
        """List all apps."""
        from ..coop.coop import Coop
        coop = Coop()
        return coop.list_apps()

    def _generate_results(self, modified_jobs_object: 'Jobs') -> 'Results':
        return modified_jobs_object.run()

    def output(self, answers: Optional[dict] = None, verbose: bool = False, formater_to_use: Optional[str] = None) -> Any:
        """Generate output by running and formatting results via the default output formatter."""

        if formater_to_use is not None:
            formatter = self.output_formatters.get_formatter(formater_to_use)
        else:
            formatter = self.output_formatters.get_default()

        if answers is None:
            answers = self._collect_answers_interactively()

        modified_jobs_object = self._prepare_jobs_object(params = answers)
        results = self._generate_results(modified_jobs_object)
        return formatter.render(results)


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

        return cls(**kwargs)


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
        from .output import OutputFormatters  # type: ignore
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

        return cls(**kwargs)

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
        return App(initial_survey = initial_survey, jobs_object = job, output_formatters = OutputFormatters([AnswersListOutput()]))


# class App(AppBase):
#     application_type = "basic_app"

    # def answers_to_scenario(self, answers: dict) -> 'Scenario':
    #     from ..scenarios import FileStore
    #     for key, value in answers.items():
    #         relevant_question = self.initial_survey[key]
    #         if relevant_question.question_type == "file_upload":
    #             answers[key] = FileStore(path=value)
    #         else:
    #             answers[key] = value
    #     return Scenario(answers)


# class AppSurvey(AppBase):
#     """An app that takes a survey as input."""
    
#     application_type = "survey"

#     def answers_to_scenario(self, answers: dict) -> 'Scenario':
#         return answers.to_scenario_list()

#     @classmethod
#     def example(cls):
#         from ..surveys import Survey
#         from ..questions import QuestionFreeText
#         initial_survey = None
#         jobs_object = Survey([QuestionFreeText(
#             question_name = "typos", 
#             question_text = "Are there any typos in {{ scenario.question_text }}?")]).to_jobs()
#         output_formatter = OutputFormatter(name = "Typo Checker").select('answer.typos').table()
#         a = AppSurvey(
#             initial_survey = initial_survey, 
#             jobs_object = jobs_object, 
#             output_formatters = OutputFormatters([output_formatter]))
#         return a


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
    output = lazarus_app.output(answers = {'raw_text': raw_text}, verbose = True)
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

