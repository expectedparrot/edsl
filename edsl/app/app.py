from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, TypedDict, Union, List
from pathlib import Path
from abc import ABC

from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..agents import AgentList
 

if TYPE_CHECKING:
    from ..scenarios import ScenarioList
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from ..agents import AgentList
    from .head_attachments import HeadAttachments

from .output_formatter import OutputFormatter, OutputFormatters
from .output_formatter import ObjectFormatter
from .app_param_preparer import AppParamPreparer
from .answers_collector import AnswersCollector
from .app_renderer import AppRenderer

## We need the notion of modifying elements before they are attached.
## The Outformat would be the natural way to do this.
## Maybe rename to ObjectTransformer?

from abc import ABC, abstractmethod

 


class App(ABC):
    """
    A class representing an EDSL application.

    An EDSL application requires the user to complete an initial survey.
    This creates parameters that are used to run a jobs object.
    The jobs object has the logic for the application.
    """

    # Subclass registry: maps application_type -> subclass
    _registry: dict[str, type["App"]] = {}


    # Each subclass should set a unique application_type
    application_type: str = "base"

        # Subclasses must define a default_output_formatter used when none is supplied
    default_output_formatter: Optional[OutputFormatter] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Skip base class itself
        if cls is App:
            return
        app_type = getattr(cls, "application_type", None)
        if not isinstance(app_type, str) or not app_type.strip():
            raise TypeError(
                f"{cls.__name__} must define a non-empty 'application_type' class attribute."
            )
        # Enforce uniqueness
        if app_type in App._registry and App._registry[app_type] is not cls:
            existing = App._registry[app_type].__name__
            raise ValueError(
                f"Duplicate application_type '{app_type}' for {cls.__name__}; already registered by {existing}."
            )
        # Enforce that subclasses declare a class-level default_output_formatter
        default_fmt = getattr(cls, "default_output_formatter", None)
        if not isinstance(default_fmt, OutputFormatter):
            raise TypeError(
                f"{cls.__name__} must define a class-level default_output_formatter (OutputFormatter)."
            )
        if not getattr(default_fmt, "name", None):
            raise ValueError(
                f"{cls.__name__}.default_output_formatter must have a unique, non-empty name"
            )
        App._registry[app_type] = cls


    def __rshift__(self, pipe_or_app):
        "Creates a composite app: either add a pipe or chain to another app."
        from .composite_app import CompositeApp
        from .output_formatter import ObjectFormatter

        if isinstance(pipe_or_app, ObjectFormatter):
            return CompositeApp(self, pipe_or_app, None)
        elif isinstance(pipe_or_app, App):
            pipe = self.default_output_formatter
            return CompositeApp(self, pipe, pipe_or_app)
        else:
            raise TypeError(f"Invalid operand for >>: {type(pipe_or_app).__name__}")

    def __init__(
        self,
        jobs_object: "Jobs",
        description: str,
        application_name: str,
        initial_survey: Survey,  # type: ignore[assignment]
        output_formatters: Optional[list[OutputFormatter] | OutputFormatter] = None,
        attachment_formatters: Optional[list[ObjectFormatter] | ObjectFormatter] = None,
    ):
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

        if self.initial_survey is None:
            raise ValueError("An initial_survey is required for all apps. The initial survey fully determines parameter names and EDSL object inputs.")
        # Enforce default_output_formatter contract

        # Normalize provided formatters or fall back to class default
        formatters = output_formatters or type(self).default_output_formatter

        if isinstance(formatters, OutputFormatters):
            self.output_formatters = formatters
        else:
            if not isinstance(formatters, list):
                formatters = [formatters]
            if not formatters:
                raise ValueError("output_formatters must be a non-empty list")
            self.output_formatters = OutputFormatters(formatters)

        attachment_formatters = [] if attachment_formatters is None else attachment_formatters
        if attachment_formatters and not isinstance(attachment_formatters, list):
            attachment_formatters = [attachment_formatters]

        self.attachment_formatters = attachment_formatters

        if application_name is not None and not isinstance(application_name, str):
            raise TypeError("application_name must be a string if provided")
        # Default to the class name if not provided
        self.application_name: str = application_name or self.__class__.__name__
        # Parameters are fully determined by the initial_survey
        from .app_validator import AppValidator

        AppValidator.validate_parameters(self)
        AppValidator.validate_initial_survey_edsl_uniqueness(self)

        # Debug storage for post-hoc inspection
        self._debug_params_last: Any | None = None
        self._debug_head_attachments_last: Any | None = None
        self._debug_jobs_last: Any | None = None
        self._debug_results_last: Any | None = None
        self._debug_output_last: Any | None = None
        self._debug_history: list[dict] = []

    @classmethod
    def list(cls) -> list[str]:
        """List all apps."""
        from ..coop.coop import Coop

        coop = Coop()
        return coop.list_apps()

    def _generate_results(self, modified_jobs_object: "Jobs") -> "Results":
        """Generate results from a modified jobs object."""
        return modified_jobs_object.run(stop_on_exception=True)

    def output(
        self,
        params: "Any",
        verbose: bool = False,
        formatter_name: Optional[str] = None,
    ) -> Any:
        if params is None:
            params = AnswersCollector.collect_interactively(self)
        # Capture params and head attachments/jobs for debugging
        self._debug_params_last = params
        head_attachments = AppParamPreparer.prepare(self, params)
        # Apply attachment formatters
        for formatter in self.attachment_formatters:
            head_attachments = head_attachments.apply_formatter(
                formatter, params=params
            )

        self._debug_head_attachments_last = head_attachments
        jobs = head_attachments.attach_to_head(self.jobs_object)
        self._debug_jobs_last = jobs
        formatted_output = AppRenderer.render(self, jobs, formatter_name)

        # Record consolidated snapshot after _render populates results/output
        from .debug_snapshot import DebugSnapshot

        self._debug_history.append(DebugSnapshot.capture(self))

        return formatted_output

    def _render(self, jobs: "Jobs", formatter_name: Optional[str]) -> Any:
        return AppRenderer.render(self, jobs, formatter_name)

    def _prepare_from_params(self, params: Any) -> HeadAttachments:
        from .app_param_preparer import AppParamPreparer

        return AppParamPreparer.prepare(self, params)

    def add_output_formatter(
        self, formatter: OutputFormatter, set_default: bool = False
    ) -> "App":
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

    def with_output_formatter(self, formatter: OutputFormatter) -> "App":
        """Make a new app with the same parameters but with the additional output formatter."""
        target_class = type(self)
        return target_class(
            jobs_object=self.jobs_object,
            output_formatters=[formatter],
            description=self.description,
            application_name=self.application_name,
            initial_survey=self.initial_survey,
        )

    @property
    def parameters(self) -> dict:
        """Returns the parameters of the application.

        >>> App.example().parameters
        [('raw_text', 'text', 'What is the text to split into a twitter thread?')]
        """
        return [
            (q.question_name, q.question_type, q.question_text)
            for q in self.initial_survey
        ]

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        job_cls = getattr(self.jobs_object, "__class__").__name__
        num_questions = len(list(self.initial_survey))
        head_param_count = len(getattr(self.jobs_object, "head_parameters", []) or [])
        fmt_names = ", ".join([f.name for f in getattr(self.output_formatters, "data", [])])
        try:
            default_fmt = self.output_formatters.get_default().name
        except Exception:
            default_fmt = "<none>"
        attach_names = ", ".join([getattr(f, "name", f.__class__.__name__) for f in (self.attachment_formatters or [])])
        return (
            f"{cls_name}(name='{self.application_name}', type='{self.application_type}', "
            f"job='{job_cls}', survey_questions={num_questions}, head_params={head_param_count}, "
            f"formatters=[{fmt_names}], default_formatter='{default_fmt}', attachments=[{attach_names}])"
        )

    

    

    

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        from .app_serialization import AppSerialization

        return AppSerialization.to_dict(self, add_edsl_version=add_edsl_version)

    @property
    def application_type(self) -> str:  # type: ignore[override]
        return getattr(self.__class__, "application_type", self.__class__.__name__)

    @classmethod
    def from_dict(cls, data: dict) -> "App":
        from .app_serialization import AppSerialization

        return AppSerialization.from_dict(cls, data)

    @property
    def debug_last(self) -> dict:
        """Return the most recent debug snapshot of the app run."""
        from .debug_snapshot import DebugSnapshot

        snap = DebugSnapshot.capture(self)
        return {
            "params": snap.params,
            "head_attachments": snap.head_attachments,
            "jobs": snap.jobs,
            "results": snap.results,
            "formatted_output": snap.formatted_output,
        }

    @property
    def debug_history(self) -> List[dict]:
        """Return the list of all debug snapshots captured so far."""
        return self._debug_history

    def push(
        self,
        visibility: Optional[str] = "unlisted",
        description: Optional[str] = None,
        alias: Optional[str] = None,
    ):
        from .app_remote import AppRemote

        return AppRemote.push(self, visibility=visibility, description=description, alias=alias)

    @classmethod
    def pull(cls, edsl_uuid: str) -> "App":
        from .app_remote import AppRemote

        return AppRemote.pull(cls, edsl_uuid)


if __name__ == "__main__":
    from edsl import QuestionFreeText, QuestionList

    initial_survey = Survey(
        [
            QuestionFreeText(
                question_name="raw_text",
                question_text="What is the text to split into a twitter thread?",
            )
        ]
    )
    jobs_survey = Survey(
        [
            QuestionList(
                question_name="twitter_thread",
                question_text="Please take this text: {{scenario.raw_text}} and split into a twitter thread, if necessary.",
            )
        ]
    )

    twitter_output_formatter = (
        OutputFormatter(name="Twitter Thread Splitter")
        .select("answer.twitter_thread")
        .expand("answer.twitter_thread")
        .table()
    )

    app = App(
        application_name="Twitter Thread Splitter",
        description="This application splits text into a twitter thread.",
        initial_survey=initial_survey,
        jobs_object=jobs_survey.to_jobs(),
        output_formatters=OutputFormatters([twitter_output_formatter]),
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
    output = lazarus_app.output(params={"raw_text": raw_text}, verbose=True)
    print(output)
