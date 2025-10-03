from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, TypedDict, Union, List, Mapping
import re
from html import escape
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
from .app_param_preparer import AppParamPreparer
from .answers_collector import AnswersCollector
from .app_html_renderer import AppHTMLRenderer
from .descriptors import InitialSurveyDescriptor, OutputFormattersDescriptor, AttachmentFormattersDescriptor, AppTypeRegistryDescriptor, ApplicationNameDescriptor
from .debug_info import DebugInfo

class App:
    """
    A class representing an EDSL application.

    An EDSL application requires the user to complete an initial survey.
    This creates parameters that are used to run a jobs object.
    The jobs object has the logic for the application.
    """

    # Subclass registry managed via descriptor
    _registry = AppTypeRegistryDescriptor()


    # Each subclass should set a unique application_type
    application_type: str = "base"

    def __init_subclass__(cls, **kwargs):
        if cls is App:
            return
        # Delegate validation and registration to descriptor (access the descriptor itself)
        App.__dict__["_registry"].register(cls)


    def __rshift__(self, next_app):
        "Chain this app to another app, creating a CompositeApp."
        from .composite_app import CompositeApp

        if isinstance(next_app, App):
            return CompositeApp(self, next_app)
        else:
            raise TypeError(f"Invalid operand for >>: {type(next_app).__name__}")

    # Descriptors
    initial_survey = InitialSurveyDescriptor()
    output_formatters = OutputFormattersDescriptor()
    attachment_formatters = AttachmentFormattersDescriptor()
    application_name: str = ApplicationNameDescriptor()  # type: ignore[assignment]

    def __init__(
        self,
        jobs_object: "Jobs",
        description: str,
        application_name: str,
        initial_survey: Survey,  # type: ignore[assignment]
        output_formatters: Optional[Mapping[str, OutputFormatter] | list[OutputFormatter] | OutputFormatters] = None,
        attachment_formatters: Optional[list[ObjectFormatter] | ObjectFormatter] = None,
        default_formatter_name: Optional[str] = None,
        default_params: Optional[dict[str, Any]] = None,
        fixed_params: Optional[dict[str, Any]] = None,
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
        # Validation is handled by descriptor
        self.initial_survey = initial_survey
        # Enforce default_output_formatter contract

        # Normalize and validate via descriptor
        self.output_formatters = output_formatters
        if default_formatter_name is not None:
            self.output_formatters.set_default(default_formatter_name)

        # Normalize via descriptor
        self.attachment_formatters = attachment_formatters

        # Validate and default via descriptor
        self.application_name = application_name
        # Defaults for initial_survey params keyed by question_name
        self._default_params: dict[str, Any] = dict(default_params or {})
        # Fixed params override any provided params at runtime
        self._fixed_params: dict[str, Any] = dict(fixed_params or {})
        # If any fixed params overlap with survey questions, prune those questions
        # so fixed param names are not present in the initial_survey.
        if self._fixed_params:
            try:
                survey_names = {q.question_name for q in self.initial_survey}
            except Exception:
                survey_names = set()
            overlapping = [k for k in self._fixed_params.keys() if k in survey_names]
            if overlapping:
                try:
                    # Drop these questions from the survey
                    self.initial_survey = self.initial_survey.drop(*overlapping)  # type: ignore[assignment]
                except Exception:
                    # If pruning fails, surface a clear error
                    raise ValueError(
                        f"Failed to prune fixed parameters from initial_survey: {sorted(overlapping)}"
                    )

        # Parameters are fully determined by the (possibly pruned) initial_survey
        from .app_validator import AppValidator

        AppValidator.validate_parameters(self)
        AppValidator.validate_initial_survey_edsl_uniqueness(self)

        # Debug info encapsulated in DebugInfo helper
        self.debug = DebugInfo(self)

        # Cache for generated results keyed by the hash of a jobs object
        self._generated_results: dict[int, "Results"] = {}

        # Register this app instance in the global registry
        try:
            from .app_registry import AppRegistry
            AppRegistry.register(self)
        except Exception:
            # Registration failures should not prevent app initialization
            pass

    @classmethod
    def list(cls) -> list[str]:
        """List all apps."""
        from ..coop.coop import Coop

        coop = Coop()
        return coop.list_apps()

    def __call__(self, **kwargs: Any) -> Any:
        """Call the app with the given parameters."""
        return self.output(params = kwargs)

    def _generate_results(self, modified_jobs_object: "Jobs") -> "Results":
        """Generate results from a modified jobs object with instance-level caching.

        Results are cached on the instance using the hash of the provided
        jobs object. If the same jobs configuration is requested again,
        the cached results are returned without re-running the jobs.
        """
        jobs_hash = hash(modified_jobs_object)
        cache = self._generated_results
        if jobs_hash in cache:
            results = cache[jobs_hash]
            self._debug_results_last = results
            return results

        results = modified_jobs_object.run(stop_on_exception=True)
        cache[jobs_hash] = results
        self._debug_results_last = results
        return results

    def output(
        self,
        params: dict[str, Any] | None,
        verbose: bool = False,
        formatter_name: Optional[str] = None,
    ) -> Any:
        if params is None:
            params = AnswersCollector.collect_interactively(self)
        # Apply App-level defaults for missing or None values
        params = self._apply_default_params(params)
        # Apply fixed params last so they win
        params = self._apply_fixed_params(params)
        head_attachments = self._prepare_and_apply_head_attachments(params)
        jobs = head_attachments.attach_to_head(self.jobs_object)
        self.debug.set_jobs(jobs)
        results = self._generate_results(jobs)
        formatted_output = self._format_output(results, formatter_name)
        self.debug.record_snapshot()
        return formatted_output

    # _render was used when renderer was external; no longer needed since
    # output() now orchestrates steps directly.

    def _prepare_and_apply_head_attachments(self, params: Any):
        self.debug.set_params(params)
        # Allow subclasses to customize how head attachments
        # are created from params via _prepare_from_params
        head_attachments = self._prepare_from_params(params)
        for formatter in self.attachment_formatters:
            head_attachments = head_attachments.apply_formatter(
                formatter, params=params
            )
        self.debug.set_head_attachments(head_attachments)
        return head_attachments

    def _select_formatter(self, formatter_name: Optional[str]):
        if formatter_name is not None:
            return self.output_formatters.get_formatter(formatter_name)
        return self.output_formatters.get_default()

    def _format_output(self, results: Any, formatter_name: Optional[str]) -> Any:
        formatter = self._select_formatter(formatter_name)
        # Provide a clear namespaced 'params' for template resolution while
        # preserving legacy top-level keys for backward compatibility.
        if isinstance(self.debug.params_last, dict):
            context_params = dict(self.debug.params_last)
            context = {"params": context_params, **context_params}
        else:
            context = {"params": {}}
        formatted = formatter.render(
            results,
            params=context,
        )
        self.debug.set_results(results)
        self.debug.set_output(formatted)
        return formatted

    def _apply_default_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Merge provided params with defaults declared on the App.

        Any key missing from params or explicitly None will be filled with the
        corresponding default when provided and when the key exists on the
        initial_survey.
        """
        merged: dict[str, Any] = dict(params or {})
        if not getattr(self, "_default_params", None):
            return merged
        try:
            survey_names = {q.question_name for q in self.initial_survey}
        except Exception:
            survey_names = set()
        for key, value in self._default_params.items():
            if survey_names and key not in survey_names:
                continue
            if key not in merged or merged.get(key) is None:
                merged[key] = value
        return merged

    def _apply_fixed_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply fixed params while rejecting user-provided values for fixed keys.

        If the caller supplies any parameter that is fixed on this App, raise an
        exception because fixed parameters must not be provided by the caller.
        Otherwise, merge the fixed values into the params.
        """
        if not getattr(self, "_fixed_params", None):
            return params
        provided_keys = set((params or {}).keys())
        fixed_keys = set(self._fixed_params.keys())
        forbidden = sorted(provided_keys.intersection(fixed_keys))
        if forbidden:
            raise ValueError(
                f"The following parameters are fixed and must not be provided by the caller: {forbidden}"
            )
        merged: dict[str, Any] = dict(params or {})
        for key, value in self._fixed_params.items():
            merged[key] = value
        return merged

    def _prepare_from_params(self, params: dict[str, Any]) -> HeadAttachments:
        """Translate initial_survey answers (params) into head attachments.

        This method is the canonical, single place where we:
        - Verify that the provided params align with the initial survey
        - Instantiate any declared EDSL objects (Scenario/ScenarioList, Survey, Agent/AgentList)
        
        - Collect non-EDSL answers as scenario variables and, if no Scenario is provided,
          build a single Scenario from those variables
        
        - Return a HeadAttachments instance containing up to one attachment for each
          destination (scenario, survey, agent_list)

        """
        # Derive head attachments exclusively from the initial_survey answers.
        if not isinstance(params, dict):
            raise TypeError(
                "App.output expects a params dict keyed by initial_survey question names. Got: "
                + type(params).__name__
            )


        # Make sure we didn't get any keys we don't know about, except allow fixed params
        survey_question_names = {q.question_name for q in self.initial_survey}
        fixed_names = set(getattr(self, "_fixed_params", {}).keys())
        unknown_keys = [k for k in params.keys() if k not in survey_question_names and k not in fixed_names]
        if unknown_keys:
            raise ValueError(
                f"Params contain keys not in initial_survey: {sorted(unknown_keys)}. "
                f"Survey question names: {sorted(survey_question_names)}"
            )

        from ..scenarios import Scenario, ScenarioList
        from ..surveys import Survey
        from ..agents import AgentList
        from ..base import RegisterSubclassesMeta
        from ..questions.register_questions_meta import RegisterQuestionsMeta

        scenario_attachment: ScenarioList | Scenario | None = None
        survey_attachment: Survey | None = None
        agent_list_attachment: AgentList | None = None

        dest_assigned = {"scenario": False, "survey": False, "agent_list": False}
        scenario_vars: dict[str, Any] = {}

        question_registry = RegisterQuestionsMeta.question_types_to_classes()
        edsl_registry = RegisterSubclassesMeta.get_registry()

        # Value transformers keyed by question_type
        # Each transformer takes the raw answer value and returns a normalized value
        # suitable for scenario variables. Unspecified types default to identity.
        def _identity(v: Any) -> Any:
            return v

        def _to_filestore(v: Any) -> Any:
            try:
                from ..scenarios import FileStore

                return FileStore(path=v)
            except Exception:
                return v

        value_transformers = {
            "file_upload": _to_filestore,
        }

        # Attachment handlers dispatched by instance type
        # Each handler performs destination uniqueness checks and sets the
        # corresponding attachment.
        from ..agents import Agent as _Agent

        def _attach_scenario(obj: Any) -> None:
            nonlocal scenario_attachment
            if dest_assigned["scenario"]:
                raise ValueError(
                    "Only one scenario attachment is allowed (Scenario or ScenarioList)."
                )
            scenario_attachment = obj
            dest_assigned["scenario"] = True

        def _attach_survey(obj: Any) -> None:
            nonlocal survey_attachment
            if dest_assigned["survey"]:
                raise ValueError("Only one Survey attachment is allowed.")
            survey_attachment = obj
            dest_assigned["survey"] = True

        def _attach_agent(obj: Any) -> None:
            nonlocal agent_list_attachment
            if dest_assigned["agent_list"]:
                raise ValueError("Only one AgentList/Agent attachment is allowed.")
            agent_list_attachment = obj if isinstance(obj, AgentList) else AgentList([obj])
            dest_assigned["agent_list"] = True

        attach_dispatch: list[tuple[tuple[type, ...], Any]] = [
            ((Scenario, ScenarioList), _attach_scenario),
            ((Survey,), _attach_survey),
            ((AgentList, _Agent), _attach_agent),
        ]

        def _instantiate_edsl_object(expected_type: str, answer_value: Any, question_name: str) -> tuple[bool, Any]:
            """Return (present, instance) where present indicates a meaningful value was provided.

            """
            if answer_value is None:
                return False, None
            if not isinstance(answer_value, dict):
                return True, answer_value
            if expected_type in question_registry:
                target_cls = question_registry[expected_type]
            else:
                target_cls = edsl_registry.get(expected_type)
            if target_cls is None:
                raise ValueError(
                    f"Unknown expected_object_type '{expected_type}' for question '{question_name}'."
                )
            if hasattr(target_cls, "from_dict"):
                return True, target_cls.from_dict(answer_value)
            return True, target_cls(**answer_value)

        for q in self.initial_survey:
            q_name = q.question_name
            if q_name not in params:
                continue
            answer_value = params[q_name]

            # 1) edsl_object: instantiate, then dispatch by instance type
            if q.question_type == "edsl_object":
                present, obj_instance = _instantiate_edsl_object(q.expected_object_type, answer_value, q_name)
                if not present:
                    continue
                # Dispatch by instance type
                for types, handler in attach_dispatch:
                    if isinstance(obj_instance, types):
                        handler(obj_instance)
                        break
                # Ignore other EDSL object types that are not head attachments
            else:
                # 2) Non-EDSL answers: treat as scenario variables (with per-type normalization)
                transform = value_transformers.get(q.question_type, _identity)
                scenario_vars[q_name] = transform(answer_value)

        # Also add fixed params (not present in the pruned survey) to scenario variables
        for k, v in getattr(self, "_fixed_params", {}).items():
            if k not in scenario_vars:
                scenario_vars[k] = v

        # If no explicit scenario object is attached but we have scenario variables,
        # synthesize a single Scenario from the collected variables.
        if not dest_assigned["scenario"] and scenario_vars:
            scenario_attachment = Scenario(scenario_vars)
            dest_assigned["scenario"] = True

        from .head_attachments import HeadAttachments

        # Assemble and return the final HeadAttachments bundle
        return HeadAttachments(
            scenario=(
                scenario_attachment
                if isinstance(scenario_attachment, (Scenario, ScenarioList))
                else None
            ),
            survey=survey_attachment,
            agent_list=agent_list_attachment,
        )

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
        # Delegate to OutputFormatters helper
        self.output_formatters.register(formatter, set_default=set_default)

        return self

    def with_output_formatter(self, name_or_formatter: str | OutputFormatter, formatter: OutputFormatter | None = None) -> "App":
        """Return a new app with an additional named output formatter.

        Args:
            name_or_formatter: Either the key to register under, or the formatter itself for backward-compatibility.
            formatter: The `OutputFormatter` instance to add (required if first arg is a name).
        """
        target_class = type(self)
        # Backward-compatible: called with only a formatter
        if isinstance(name_or_formatter, OutputFormatter) and formatter is None:
            name = getattr(name_or_formatter, "description", None) or getattr(name_or_formatter, "name", None)
            if not name:
                raise ValueError("formatter must have a non-empty description")
            formatter_obj = name_or_formatter
        else:
            name = name_or_formatter
            formatter_obj = formatter  # type: ignore[assignment]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("formatter name must be a non-empty string")
            if not isinstance(formatter_obj, OutputFormatter):
                raise TypeError("formatter must be an OutputFormatter")
        new_map = dict(self.output_formatters.mapping)
        if name in new_map:
            raise ValueError(f"Formatter with name '{name}' already exists")
        new_map[name] = formatter_obj
        return target_class(
            jobs_object=self.jobs_object,
            output_formatters=new_map,
            description=self.description,
            application_name=self.application_name,
            initial_survey=self.initial_survey,
            default_formatter_name=self.output_formatters.default,
        )

    def partial_application(self, fixed: dict[str, Any]) -> "App":
        """Return a new App instance with specified initial_survey params fixed.

        Args:
            fixed: Mapping of existing initial_survey question names to fixed values.

        Returns:
            A new App instance of the same concrete class with these values fixed.

        Raises:
            ValueError: If any key in `fixed` does not correspond to an initial_survey question.
        """
        if fixed is None:
            fixed = {}
        # Valid keys for partial application are current survey question names OR existing fixed params
        try:
            survey_names = {q.question_name for q in self.initial_survey}
        except Exception:
            survey_names = set()
        allowed_keys = set(survey_names).union(set(getattr(self, "_fixed_params", {}).keys()))
        unknown = [k for k in fixed.keys() if allowed_keys and k not in allowed_keys]
        if unknown:
            raise ValueError(
                f"partial_application received keys not in the current app's question names or fixed params: {sorted(unknown)}. "
                f"Allowed keys: {sorted(allowed_keys)}"
            )

        merged_fixed: dict[str, Any] = dict(getattr(self, "_fixed_params", {}) or {})
        merged_fixed.update(fixed)

        target_class = type(self)
        new_output_map = dict(self.output_formatters.mapping)
        # Build a pruned survey that drops any keys newly becoming fixed that are still present
        pruned_survey = self.initial_survey
        try:
            to_drop = [k for k in fixed.keys() if k in getattr(pruned_survey, "question_name_to_index", {})]
            if to_drop:
                pruned_survey = pruned_survey.drop(*to_drop)
        except Exception:
            # If we cannot drop, leave survey as-is; constructor will attempt pruning again
            pass

        return target_class(
            jobs_object=self.jobs_object,
            output_formatters=new_output_map,
            description=self.description,
            application_name=self.application_name,
            initial_survey=pruned_survey,
            default_formatter_name=self.output_formatters.default,
            attachment_formatters=self.attachment_formatters,
            default_params=self._default_params,
            fixed_params=merged_fixed,
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
        fmt_names = ", ".join(list(getattr(self.output_formatters, "mapping", {}).keys()))
        try:
            default_fmt = getattr(self.output_formatters, "default", None) or self.output_formatters.get_default()
            if not isinstance(default_fmt, str):
                default_fmt = getattr(default_fmt, "description", None) or getattr(default_fmt, "name", "<none>")
        except Exception:
            default_fmt = "<none>"
        attach_names = ", ".join([getattr(f, "name", f.__class__.__name__) for f in (self.attachment_formatters or [])])
        app_type = self.application_type
        return (
            f"{cls_name}(name='{self.application_name}', description='{self.description}', "
            f"application_type='{app_type}', "
            f"parameters={self.parameters}, "
            f"job='{job_cls}', survey_questions={num_questions}, head_params={head_param_count}, "
            f"formatters=[{fmt_names}], default_formatter='{default_fmt}', attachments=[{attach_names}])"
        )

    @staticmethod
    def _convert_markdown_to_html(md_text: str) -> str:
        """Convert markdown to HTML.

        Prefers the 'markdown' package if available. Falls back to a minimal
        regex-based converter that supports headings (#, ##, ###), bold, italics,
        and inline code, plus paragraph wrapping. Always escapes raw HTML first.
        """
        if md_text is None:
            return ""
        safe_text = escape(str(md_text))
        try:
            import markdown as md  # type: ignore
            return md.markdown(
                safe_text,
                extensions=["extra", "sane_lists", "tables"],
            )
        except Exception:
            pass

        text = safe_text
        # Headings
        text = re.sub(r"(?m)^######\s+(.+)$", r"<h6>\\1</h6>", text)
        text = re.sub(r"(?m)^#####\s+(.+)$", r"<h5>\\1</h5>", text)
        text = re.sub(r"(?m)^####\s+(.+)$", r"<h4>\\1</h4>", text)
        text = re.sub(r"(?m)^###\s+(.+)$", r"<h3>\\1</h3>", text)
        text = re.sub(r"(?m)^##\s+(.+)$", r"<h2>\\1</h2>", text)
        text = re.sub(r"(?m)^#\s+(.+)$", r"<h1>\\1</h1>", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\\1</code>", text)
        # Bold and italics (simple forms)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\\1</strong>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\\1</em>", text)
        # Paragraphs: split on blank lines
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        wrapped = [p if p.startswith("<h") else f"<p>{p}</p>" for p in parts]
        return "\n".join(wrapped)

    def _repr_html_(self) -> str:
        return AppHTMLRenderer(self).render()

    
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
        snap = self.debug.capture_snapshot()
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
        return self.debug.history

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
        OutputFormatter(description="Twitter Thread Splitter")
        .select("answer.twitter_thread")
        .expand("answer.twitter_thread")
        .table()
    )

    app = App(
        application_name="Twitter Thread Splitter",
        description="This application splits text into a twitter thread.",
        initial_survey=initial_survey,
        jobs_object=jobs_survey.to_jobs(),
        output_formatters={"splitter": twitter_output_formatter},
        default_formatter_name="splitter",
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
