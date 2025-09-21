from typing import TYPE_CHECKING, Optional, Any
from ..base import Base
from ..scenarios import Scenario
from ..surveys import Survey

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..scenarios import ScenarioList
    OutputFormatter = Any  # type alias for type hints only

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
        output_formatter: 'OutputFormatter', 
        description: Optional[str] = None,
        application_type: Optional[str] = None,
        initial_survey: Optional[Survey] = None):
        self.jobs_object = jobs_object
        self.description = description
        self.initial_survey = initial_survey
        if output_formatter is None:
            raise ValueError("output_formatter is required for all apps")
        self.output_formatter: Any = output_formatter


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
            "output_formatter": self.output_formatter.to_dict(add_edsl_version = add_edsl_version),
        }

    @classmethod
    def from_dict(cls, data: dict):
        # Choose subclass via registry using application_type (if available)
        application_type = data.get("application_type")
        target_cls = AppBase.registry.get(application_type, cls) if application_type else cls

        # Reconstruct output formatter if serialized
        try:
            from .output import load_output_from_dict  # type: ignore
            output_formatter = load_output_from_dict(data.get("output_formatter"))
        except Exception:
            output_formatter = data.get("output_formatter")

        # Prepare constructor kwargs filtered to the target class's __init__
        import inspect

        init_params = inspect.signature(target_cls.__init__).parameters
        candidate_kwargs = {
            "jobs_object": data.get("jobs_object"),
            "output_formatter": output_formatter,
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
        """Generate output by running and formatting results via the configured output formatter."""
        import inspect
        sig = inspect.signature(self.generate_results)
        call_kwargs = dict(kwargs)
        if 'verbose' in sig.parameters:
            call_kwargs['verbose'] = verbose
        results = self.generate_results(**call_kwargs)
        return self.output_formatter.render(results)

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
            'output_formatter_info': self.output_formatter.to_dict(),
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
        from .output import load_output_from_dict  # type: ignore
        output_formatter = load_output_from_dict(app_info.get('output_formatter_info'))

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
            'output_formatter': output_formatter,
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
        from .output import AnswersListOutput  # type: ignore
        initial_survey = Survey([QuestionFreeText(question_text = "What is your intended college major", question_name = "intended_college_major")])

        logic_survey = QuestionList(
            question_name = "courses_to_take", 
            question_text = "What courses do you need to take for major: {{scenario.intended_college_major}}"
        )
        m = Model()
        job = logic_survey.by(m) 
        return AppInteractiveSurvey(initial_survey = initial_survey, jobs_object = job, output_formatter = AnswersListOutput())



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
            answers: A dictionary of answers to the initial survey. If None, the user will be prompted to answer the questions.

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

# class App(Base):
#     """
#     A class representing an EDSL application.

#     An EDSL application requires the user to complete an initial survey. 
#     This creates parameters that are used to run a jobs object.
#     The jobs object has the logic for the application.


#     Possible outputs: 
#     - A list
#     - text 
#     - Report (docx, txt)
#     - An EDSL object (Results, Survey, Scenario, ScenarioList)
#     - A file (csv, json, etc.)
#     """

#     def __init__(self, 
#         initial_survey: 'Survey', 
#         jobs_object: 'Jobs', 
#         report_template: Optional[str] = None, 
#         description: Optional[str] = None,
#         output_formatter: Optional[Any] = None):
#         """Initializes the application."""
#         self.initial_survey = initial_survey
#         self.jobs_object = jobs_object
#         self.report_template = report_template
#         self.description = description
#         if output_formatter is None:
#             # Use relative imports to avoid absolute package paths
#             from .output import RawResultsOutput, ReportFromTemplateOutput  # type: ignore
#             if self.report_template:
#                 output_formatter = ReportFromTemplateOutput(template=self.report_template)
#             else:
#                 output_formatter = RawResultsOutput()
#         self.output_formatter: Any = output_formatter


#         self._results = None

#     @property
#     def parameters(self) -> 'ScenarioList':
#         """Returns the parameters of the application."""
#         from ..scenarios import ScenarioList, Scenario
#         sl = ScenarioList()
#         for question in self.initial_survey:
#             question_type = question.question_type
#             question_name = question.question_name
#             question_text = question.question_text
#             sl.append(Scenario({'question_name': question_name, 'question_type': question_type, 'question_text': question_text}))
#         return sl
 
#     def generate_results(self, answers: Optional[dict] = None, verbose: bool = False) -> 'Results':
#         """Generates the results of the application.
        
#         Args:
#             answers: A dictionary of answers to the initial survey. If None, the user will be prompted to answer the questions.

#         Returns:
#             The results object generated by running the jobs object.
#         """
#         from ..scenarios import Scenario
#         if answers is None:
#             from ..surveys import InteractiveSurvey
#             answers = InteractiveSurvey(self.initial_survey).run()

#             # if a file was uploaded, we need to store it in the file store
#             for question_name, answer in answers.items():
#                 q = self.initial_survey[question_name]
#                 if q.question_type == "file_upload":
#                     from ..scenarios import FileStore
#                     answers[question_name] = FileStore(path = answer)

#         scenario = Scenario(answers)
#         if verbose:
#             print("Running the application...")

#         if verbose:
#             print("Adding scenario to the job...")
#         # add scenario to the job (if it's recursive)
#         self.jobs_object.add_scenario_head(scenario)
#         if verbose:
#             print("Scenario added to the job...")
#             print("Running the job...")
#         results = self.jobs_object.add_scenario_head(scenario).run(verbose = verbose)

#         if verbose:
#             print("Complete")
#         self._results = results
#         return results

#     def _to_scenario_list(self, columns: Optional[list] = None) -> 'ScenarioList':
#         """Converts the results to a ScenarioList."""
#         from ..scenarios import ScenarioList
#         if self._results is None:
#             self.generate_results()
#         return self._results.to_scenario_list(*(columns or []))

#     def output(self, answers: Optional[dict] = None, verbose: bool = False):
#         """Generate the application's output using the configured formatter."""
#         results = self.generate_results(answers = answers, verbose = verbose)
#         return self.output_formatter.render(results)

        

#     def to_dict(self, add_edsl_version: bool = True):
#         return {
#             "initial_survey": self.initial_survey.to_dict(add_edsl_version = add_edsl_version),
#             "jobs_object": self.jobs_object.to_dict(add_edsl_version = add_edsl_version),
#             "report_template": self.report_template,
#             "description": self.description,
#             "output_formatter": self.output_formatter.to_dict(add_edsl_version = add_edsl_version),
#         }

#     @classmethod
#     def from_dict(cls, data: dict):
#         from .output import load_output_from_dict  # type: ignore
#         output_formatter = load_output_from_dict(data.get("output_formatter"))
#         return cls(
#             initial_survey = data["initial_survey"], 
#             jobs_object = data["jobs_object"], 
#             report_template = data.get("report_template"), 
#             description = data.get("description"),
#             output_formatter = output_formatter)

    def code(self):
        pass


    # @classmethod
    # def example(cls):
    #     from ..surveys import Survey
    #     from ..language_models import Model 
    #     from ..questions import QuestionFreeText, QuestionList
    #     from .output import AnswersListOutput  # type: ignore
    #     initial_survey = Survey([QuestionFreeText(question_text = "What is your intended college major", question_name = "intended_college_major")])

    #     logic_survey = QuestionList(
    #         question_name = "courses_to_take", 
    #         question_text = "What courses do you need to take for major: {{scenario.intended_college_major}}"
    #     )
    #     m = Model()
    #     job = logic_survey.by(m) 
    #     return cls(initial_survey = initial_survey, jobs_object = job, output_formatter = AnswersListOutput())




if __name__ == "__main__":
    #app = App.example()
    from ..surveys import Survey
    from ..questions import QuestionFreeText, QuestionMultipleChoice
    s = Survey([
        QuestionFreeText(
            question_name = "confusion", 
            question_text = "What might survey respondents be confused by: {{scenario.question_text }}?"),
    ])
    #jobs_object = s.to_jobs()
    #app = AppSurvey(jobs_object = jobs_object)
    #output = app.output(survey = Survey.example(), verbose = True)
    #print(output.select('answer.confusion').table())
    #results = jobs_object.by(Survey.example().to_scenario_list()).run(verbose = True)
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
    from .output import TableOutput  # type: ignore
    app = AppScenarioList(
        jobs_object = jobs_object,
        output_formatter = TableOutput([
            'scenario.tweet',
            'answer.tweet_sentiment',
        ]),
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

