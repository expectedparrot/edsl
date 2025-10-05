from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, TypedDict, Union, List, Mapping
import re
from html import escape
from pathlib import Path
from abc import ABC

 

from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..agents import AgentList
from ..base import Base

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
from .descriptors import (
    InitialSurveyDescriptor,
    OutputFormattersDescriptor,
    AttachmentFormattersDescriptor,
    AppTypeRegistryDescriptor,
    ApplicationNameDescriptor,
    FixedParamsDescriptor,
)
 


class ParamsDict(TypedDict, total=False):
    """Loose schema for params supplied to App.output; keys are initial_survey question names."""
    pass


class App(Base):
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

    # Descriptors
    initial_survey = InitialSurveyDescriptor()
    output_formatters = OutputFormattersDescriptor()
    attachment_formatters = AttachmentFormattersDescriptor()
    application_name: str = ApplicationNameDescriptor()  # type: ignore[assignment]
    fixed_params = FixedParamsDescriptor()

    def __init__(
        self,
        jobs_object: "Jobs",
        description: str,
        application_name: str,
        initial_survey: Survey,  # type: ignore[assignment]
        output_formatters: Optional[
            Mapping[str, OutputFormatter] | list[OutputFormatter] | OutputFormatters
        ] = None,
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
        # Normalize and assign via descriptor (handles pruning on assignment)
        self.fixed_params = dict(fixed_params or {})

        # Parameters are fully determined by the (possibly pruned) initial_survey
        from .app_validator import AppValidator

        AppValidator.validate_parameters(self)
        AppValidator.validate_initial_survey_edsl_uniqueness(self)

        

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
        return self.output(params=kwargs)

    def _generate_results(
        self,
        modified_jobs_object: "Jobs",
        stop_on_exception: bool = True,
        disable_remote_inference: bool = False,
    ) -> "Results":
        """Generate results for the given jobs object with instance-level caching.


        >>> app = App.example()
        >>> app._generated_results 
        {}
        >>> app._generate_results(app.jobs_object)  # doctest: +ELLIPSIS
        Results(...)
        >>> len(app._generated_results)
        1

        Args:
            modified_jobs_object: Fully prepared jobs object (after head attachments).
            stop_on_exception: If True, abort execution on the first exception.
            disable_remote_inference: If True, request local execution where supported.

        Returns:
            The computed `Results`, possibly served from the per-instance cache when the
            provided jobs object hashes to a previously computed value.
        """
        jobs_hash = hash(modified_jobs_object)
        cache = self._generated_results
        if jobs_hash in cache:
            results = cache[jobs_hash]
            return results

        results = modified_jobs_object.run(
            stop_on_exception=stop_on_exception,
            disable_remote_inference=disable_remote_inference,
        )
        cache[jobs_hash] = results
        return results

    def output(
        self,
        params: ParamsDict | None,
        formatter_name: Optional[str] = None,
        stop_on_exception: bool = True,
        disable_remote_inference: bool = False,
        verbose: bool = False,
    ) -> Any:
        """Run the app and return formatted output.

        Args:
            params: Mapping of answers keyed by `initial_survey` question names. If None, collects interactively.
            verbose: Currently unused; reserved for future logging controls.
            formatter_name: Optional explicit formatter selection; defaults to the App's default formatter.
            stop_on_exception: If True, abort job execution on first exception.
            disable_remote_inference: If True, force local execution where supported.

        Returns:
            The formatted output as produced by the selected output formatter.
        """
        
        if params is None:
            params = AnswersCollector.collect_interactively(self)

        params = self._apply_default_params(params) # Apply default params first so they can be overridden by fixed params
        params = self._apply_fixed_params(params)  # Apply fixed params last so they 'win'

        
        # Prepare head attachments - these are what will get attached to the jobs object
        head_attachments = self._prepare_head_attachments(params)
        modified_jobs_object = head_attachments.attach_to_head(self.jobs_object) # attach them

        results = self._generate_results(
            modified_jobs_object,
            stop_on_exception=stop_on_exception,
            disable_remote_inference=disable_remote_inference,
        )

        formatted_output = self._format_output(results, formatter_name, params)

        return formatted_output

    def _prepare_head_attachments(self, params: ParamsDict) -> HeadAttachments:
        """Prepare and apply head attachments derived from provided params.

        Derives a `HeadAttachments` instance based on the `initial_survey` answers
        and applies any configured attachment formatters to those attachments.

        The attachment formatters are applied to the attachments after they are prepared.
        They do things like take an inputed Survey and turn it into a ScenarioList, for example.

        Args:
            params: Parameters keyed by `initial_survey` question names.

        Returns:
            A finalized `HeadAttachments` instance ready to attach to the jobs object.
        """
        head_attachments = self._prepare_from_params(params)
        for formatter in self.attachment_formatters:
            head_attachments = head_attachments.apply_formatter(
                formatter, params=params
            )
        return head_attachments

    def _select_formatter(self, formatter_name: Optional[str]) -> OutputFormatter:
        """Return the output formatter by explicit name or the default when not provided.
        
        Args:
            formatter_name: The name of the output formatter to select.

        Returns:
            The output formatter.

        >>> app = App.example()
        >>> app._select_formatter(None)
        OutputFormatter(...)
        >>> app._select_formatter("echo")
        OutputFormatter(...)
        >>> app._select_formatter("fake")
        Traceback (most recent call last):
        ...
        ValueError: Formatter 'fake' not found. Available formatters: ['echo', 'raw_results']

        """
        if formatter_name is not None:
            return self.output_formatters.get_formatter(formatter_name)
        return self.output_formatters.get_default()

    def _format_output(self, results: 'Results', formatter_name: Optional[str], params: ParamsDict) -> Any:
        """Apply the selected output formatter to results with a params context.

        Builds a context with both namespaced `params` and top-level keys for compatibility
        with existing templates and passes it to the formatter's render method.

        The 'params' key allows the formatter to be parameterized with the values from the initial_survey.


        """
        formatter = self._select_formatter(formatter_name)
        return formatter.render(results, params={"params": dict(params or {})}) # {"params": dict(params or {})} is a bit of a hack to allow the formatter to be parameterized with the values from the initial_survey.


    def _apply_default_params(self, params: ParamsDict, *, survey_names = None, default_params = None) -> ParamsDict:
        """Merge provided params with defaults declared on the App.

        Any key missing from params or explicitly None will be filled with the
        corresponding default when provided and when the key exists on the
        initial_survey.

        Args:
            params: The parameters to merge with the defaults.
            survey_names: Optional set of allowed question names; defaults to the App's `initial_survey` names.
            default_params: Optional mapping of default parameter values; defaults to the App's `_default_params`.

        Doctest:
        >>> app = App.example()
        >>> # Provide defaults and limit to a specific survey key via overrides
        >>> app._apply_default_params({}, survey_names={'text'}, default_params={'text': 'hi', 'extra': 'x'})
        {'text': 'hi'}
        >>> # Existing non-None value is preserved
        >>> app._apply_default_params({'text': 'yo'}, survey_names={'text'}, default_params={'text': 'hi'})
        {'text': 'yo'}
        >>> # None is treated as missing and gets filled from defaults
        >>> app._apply_default_params({'text': None}, survey_names={'text'}, default_params={'text': 'hi'})
        {'text': 'hi'}

        Returns:
            The merged parameters.
        """
        survey_names = {q.question_name for q in self.initial_survey} if survey_names is None else survey_names
        default_params = self._default_params if default_params is None else default_params

        #survey_names = {q.question_name for q in initial_survey}
        merged: dict[str, Any] = dict(params or {})
        for key, value in default_params.items():
            if survey_names and key not in survey_names:
                continue
            if key not in merged or merged.get(key) is None:
                merged[key] = value
        return merged

    def _apply_fixed_params(self, params: ParamsDict, *, fixed_params = None) -> ParamsDict:
        """Apply fixed params while rejecting user-provided values for fixed keys.

        If the caller supplies any parameter that is fixed on this App, raise an
        exception because fixed parameters must not be provided by the caller.
        Otherwise, merge the fixed values into the params.

        Doctest (dependency-injected fixed_params):
        >>> app = App.example()
        >>> # Merge injected fixed params when caller doesn't provide those keys
        >>> app._apply_fixed_params({'text': 'hi'}, fixed_params={'lang': 'en'})
        {'text': 'hi', 'lang': 'en'}
        >>> # Reject when caller supplies a fixed key
        >>> app._apply_fixed_params({'lang': 'fr'}, fixed_params={'lang': 'en'})
        Traceback (most recent call last):
        ...
        ValueError: The following parameters are fixed and must not be provided by the caller: ['lang']
        """
        fixed_params = self.fixed_params if fixed_params is None else fixed_params
        provided_keys = set((params or {}).keys())
        fixed_keys = set(fixed_params.keys())
        forbidden = sorted(provided_keys.intersection(fixed_keys))
        if forbidden:
            raise ValueError(
                f"The following parameters are fixed and must not be provided by the caller: {forbidden}"
            )
        merged: dict[str, Any] = dict(params or {})
        for key, value in fixed_params.items():
            merged[key] = value
        return merged

    def _prepare_from_params(self, params: ParamsDict) -> HeadAttachments:
        """Translate initial_survey answers (params) into head attachments.

        This method is the canonical, single place where we:
        - Verify that the provided params align with the initial survey
        - Instantiate any declared EDSL objects (Scenario/ScenarioList, Survey, Agent/AgentList)

        - Collect non-EDSL answers as scenario variables and, if no Scenario is provided,
          build a single Scenario from those variables

        - Return a HeadAttachments instance containing up to one attachment for each
          destination (scenario, survey, agent_list)

        """
        
        from .head_attachments_builder import HeadAttachmentsBuilder
        return HeadAttachmentsBuilder.build(self, params)

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

    def add_attachment_formatter(self, formatter: "ObjectFormatter") -> "App":
        """Add an attachment formatter (fluent).
        
        Args:
            formatter: The `ObjectFormatter` instance to add.

        Returns:
            The `App` instance to allow fluent chaining.
        """
        current = list(self.attachment_formatters or [])
        current.append(formatter)
        self.attachment_formatters = current
        return self

    def code(self) -> str:
        """Return the code for the app.
        
        Returns:
            The code for the app.
        """
        raise NotImplementedError("App.code() is not implemented")

    def with_output_formatter(
        self,
        name_or_formatter: str | OutputFormatter,
        formatter: OutputFormatter | None = None,
    ) -> "App":
        """Return a new app with an additional named output formatter.

        Args:
            name_or_formatter: Either the key to register under, or the formatter itself for backward-compatibility.
            formatter: The `OutputFormatter` instance to add (required if first arg is a name).
        """
        target_class = type(self)
        # Backward-compatible: called with only a formatter
        if isinstance(name_or_formatter, OutputFormatter) and formatter is None:
            name = getattr(name_or_formatter, "description", None) or getattr(
                name_or_formatter, "name", None
            )
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
        except (TypeError, AttributeError):
            survey_names = set()
        allowed_keys = set(survey_names).union(
            set(getattr(self, "fixed_params", {}).keys())
        )
        unknown = [k for k in fixed.keys() if allowed_keys and k not in allowed_keys]
        if unknown:
            raise ValueError(
                f"partial_application received keys not in the current app's question names or fixed params: {sorted(unknown)}. "
                f"Allowed keys: {sorted(allowed_keys)}"
            )

        merged_fixed: dict[str, Any] = dict(getattr(self, "fixed_params", {}) or {})
        merged_fixed.update(fixed)

        target_class = type(self)
        new_output_map = dict(self.output_formatters.mapping)
        # Build a pruned survey that drops any keys newly becoming fixed that are still present
        pruned_survey = self.initial_survey
        try:
            to_drop = [
                k
                for k in fixed.keys()
                if k in getattr(pruned_survey, "question_name_to_index", {})
            ]
            if to_drop:
                pruned_survey = pruned_survey.drop(*to_drop)
        except (AttributeError, TypeError):
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
    def parameters(self) -> list[tuple[str, str, str]]:
        """Return list of (name, type, text) derived from the initial survey."""
        return [
            (q.question_name, q.question_type, q.question_text)
            for q in self.initial_survey
        ]

    def __repr__(self) -> str:
        return self._repr_summary()

    def _repr_summary(self) -> str:
        cls_name = self.__class__.__name__
        job_cls = getattr(self.jobs_object, "__class__").__name__
        num_questions = len(list(self.initial_survey))
        head_param_count = len(getattr(self.jobs_object, "head_parameters", []) or [])
        fmt_names_list = list(getattr(self.output_formatters, "mapping", {}).keys())
        fmt_names = ", ".join(fmt_names_list[:8]) + ("..." if len(fmt_names_list) > 8 else "")
        try:
            default_fmt_obj = (
                getattr(self.output_formatters, "default", None)
                or self.output_formatters.get_default()
            )
            default_fmt = (
                default_fmt_obj
                if isinstance(default_fmt_obj, str)
                else getattr(default_fmt_obj, "description", None)
                or getattr(default_fmt_obj, "name", "<none>")
            )
        except Exception:
            default_fmt = "<none>"
        attach_names_list = [
            getattr(f, "name", f.__class__.__name__) for f in (self.attachment_formatters or [])
        ]
        attach_names = ", ".join(attach_names_list[:8]) + ("..." if len(attach_names_list) > 8 else "")
        app_type = self.application_type
        return (
            f"{cls_name}(name='{self.application_name}', description='{self.description}', "
            f"application_type='{app_type}', parameters={self.parameters}, job='{job_cls}', "
            f"survey_questions={num_questions}, head_params={head_param_count}, "
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
        """Rich HTML representation used in notebooks and rich console renderers."""
        return AppHTMLRenderer(self).render()

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Serialize this app to a JSON-serializable dict."""
        from .app_serialization import AppSerialization

        return AppSerialization.to_dict(self, add_edsl_version=add_edsl_version)

    @property
    def application_type(self) -> str:  # type: ignore[override]
        """Return the application type identifier.

        Identity is class-based: by default returns the class attribute
        `application_type` if present, otherwise the class name. Builders that
        return `App` instances typically rely on the default class identity.
        """
        return getattr(self.__class__, "application_type", self.__class__.__name__)

    @classmethod
    def from_dict(cls, data: dict) -> "App":
        """Deserialize an app (possibly subclass) from a dict payload."""
        from .app_serialization import AppSerialization

        return AppSerialization.from_dict(cls, data)

    @classmethod
    def create_ranking_app(
        cls,
        ranking_question: "QuestionMultipleChoice",
        option_fields: "Sequence[str]",
        application_name: Optional[str] = None,
        description: Optional[str] = None,
        option_base: Optional[str] = None,
        rank_field: str = "rank",
        max_pairwise_count: int = 500,
    ) -> "App":
        """Create an App configured to rank items via pairwise comparisons.

        Args:
            ranking_question: A QuestionMultipleChoice configured to compare two options
                using Jinja placeholders like '{{ scenario.<field>_1 }}' and '{{ scenario.<field>_2 }}'.
            option_fields: Sequence of field names corresponding to the two options in the comparison
                (e.g., ['food_1', 'food_2']).
            application_name: Optional human-readable name.
            description: Optional description.
            option_base: Optional base field name (e.g., 'food'). Currently not used by the builder; kept for API parity.
            rank_field: Name of the rank field to include in the output ScenarioList. Currently controlled by the formatter.
            max_pairwise_count: Maximum number of pairwise comparisons to generate. Reserved for future use.

        Returns:
            An App instance ready to accept a ScenarioList under the 'input_items' parameter
            and output a ranked ScenarioList using the 'ranked_list' formatter.
        """
        # Validate option_fields shape and basic usage
        try:
            if len(option_fields) != 2:
                raise ValueError(
                    "option_fields must contain exactly two field names, e.g., ['item_1','item_2']"
                )
        except TypeError:
            raise TypeError("option_fields must be a sequence of exactly two field names")

        try:
            q_opts = getattr(ranking_question, "question_options", None)
            q_text = getattr(ranking_question, "question_text", "") or ""
            haystack = " ".join([str(x) for x in (q_opts or []) if isinstance(x, str)]) + " " + str(q_text)
            missing = [f for f in option_fields if f not in haystack]
            if missing:
                raise ValueError(
                    f"ranking_question does not appear to reference fields: {missing}. "
                    f"Ensure templates include these (e.g., '{{{{ scenario.{option_fields[0]} }}}}', '{{{{ scenario.{option_fields[1]} }}}}')."
                )
        except Exception:
            pass

        # Local imports to avoid any potential import cycles
        from typing import (
            Sequence as _Sequence,
        )  # noqa: F401  (type hints only via annotations)
        from ..surveys import Survey
        from ..questions import QuestionEDSLObject  # for initial input
        from .output_formatter import OutputFormatter, ScenarioAttachmentFormatter

        survey = Survey([ranking_question])
        jobs_object = survey.to_jobs()

        output_formatter = (
            OutputFormatter(description="Ranked Scenario List")
            .to_scenario_list()
            .to_ranked_scenario_list(
                option_fields=option_fields,
                answer_field=ranking_question.question_name,
            )
        )

        return cls(
            jobs_object=jobs_object,
            output_formatters={"ranked_list": output_formatter},
            default_formatter_name="ranked_list",
            attachment_formatters=[
                # Transform the provided ScenarioList into pairwise comparisons
                ScenarioAttachmentFormatter(description="Pairwise choose_k").choose_k(2)
            ],
            description=description,
            application_name=application_name,
            initial_survey=Survey(
                [
                    QuestionEDSLObject(
                        question_name="input_items",
                        question_text="Provide the items to rank as a ScenarioList",
                        expected_object_type="ScenarioList",
                    )
                ]
            ),
        )

    

    def push(
        self,
        visibility: Optional[str] = "unlisted",
        description: Optional[str] = None,
        alias: Optional[str] = None,
    ):
        """Push this app to a remote registry/service and return the remote handle."""
        from .app_remote import AppRemote

        return AppRemote.push(
            self, visibility=visibility, description=description, alias=alias
        )

    @classmethod
    def pull(cls, edsl_uuid: str) -> "App":
        """Pull an app by UUID from the remote registry/service."""
        from .app_remote import AppRemote

        return AppRemote.pull(cls, edsl_uuid)

    @classmethod
    def example(cls) -> "App":
        """Return a minimal App configured with Model('test') for local testing.

        Example:
            >>> app = App.example()
            >>> out = app.output(params={"text": "hello"}, disable_remote_inference=True)
            >>> bool(out)
            True
        """
        # Import locally to avoid cycles
        from ..surveys import Survey
        from ..questions import QuestionFreeText, QuestionList
        from ..language_models.model import Model
        from .output_formatter import OutputFormatter

        initial_survey = Survey(
            [
                QuestionFreeText(
                    question_name="text",
                    question_text="Provide a short text",
                )
            ]
        )

        # Simple echo job that repeats the input text; bound to test model
        echo_job = Survey(
            [
                QuestionFreeText(
                    question_name="echo",
                    question_text="Echo this back: {{ scenario.text }}",
                )
            ]
        ).by(Model("test"))

        echo_formatter = (
            OutputFormatter(description="Echo")
            .select("answer.echo")
            .to_scenario_list()
            .table()
        )

        return cls(
            application_name="Example App",
            description="A minimal example app that echoes user input.",
            initial_survey=initial_survey,
            jobs_object=echo_job,
            output_formatters={"echo": echo_formatter},
            default_formatter_name="echo",
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    # from edsl import QuestionFreeText, QuestionList

    # initial_survey = Survey(
    #     [
    #         QuestionFreeText(
    #             question_name="raw_text",
    #             question_text="What is the text to split into a twitter thread?",
    #         )
    #     ]
    # )
    # jobs_survey = Survey(
    #     [
    #         QuestionList(
    #             question_name="twitter_thread",
    #             question_text="Please take this text: {{scenario.raw_text}} and split into a twitter thread, if necessary.",
    #         )
    #     ]
    # )

    # twitter_output_formatter = (
    #     OutputFormatter(description="Twitter Thread Splitter")
    #     .select("answer.twitter_thread")
    #     .expand("answer.twitter_thread")
    #     .table()
    # )

    # app = App(
    #     application_name="Twitter Thread Splitter",
    #     description="This application splits text into a twitter thread.",
    #     initial_survey=initial_survey,
    #     jobs_object=jobs_survey.to_jobs(),
    #     output_formatters={"splitter": twitter_output_formatter},
    #     default_formatter_name="splitter",
    # )

    # raw_text = """ 
    # The Senate of the United States shall be composed of two Senators from each State, chosen by the Legislature thereof, for six Years; and each Senator shall have one Vote.
    # Immediately after they shall be assembled in Consequence of the first Election, they shall be divided as equally as may be into three Classes. The Seats of the Senators of the first Class shall be vacated at the Expiration of the second Year, of the second Class at the Expiration of the fourth Year, and of the third Class at the Expiration of the sixth Year, so that one third may be chosen every second Year; and if Vacancies happen by Resignation, or otherwise, during the Recess of the Legislature of any State, the Executive thereof may make temporary Appointments until the next Meeting of the Legislature, which shall then fill such Vacancies.
    # No Person shall be a Senator who shall not have attained to the Age of thirty Years, and been nine Years a Citizen of the United States, and who shall not, when elected, be an Inhabitant of that State for which he shall be chosen.
    # The Vice President of the United States shall be President of the Senate, but shall have no Vote, unless they be equally divided.
    # The Senate shall chuse their other Officers, and also a President pro tempore, in the Absence of the Vice President, or when he shall exercise the Office of President of the United States.
    # The Senate shall have the sole Power to try all Impeachments. When sitting for that Purpose, they shall be on Oath or Affirmation. When the President of the United States is tried, the Chief Justice shall preside: And no Person shall be convicted without the Concurrence of two thirds of the Members present.
    # Judgment in Cases of Impeachment shall not extend further than to removal from Office, and disqualification to hold and enjoy any Office of honor, Trust or Profit under the United States: but the Party convicted shall nevertheless be liable and subject to Indictment, Trial, Judgment and Punishment, according to Law.
    # """

    # lazarus_app = App.from_dict(app.to_dict())

    # # non-interactive mode
    # output = lazarus_app.output(params={"raw_text": raw_text}, verbose=True)
    # print(output)
