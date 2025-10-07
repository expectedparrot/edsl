from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, TypedDict, Union, List, Mapping
import re
from html import escape
from pathlib import Path
from abc import ABC

from functools import wraps

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
from .api_payload import build_api_payload, reconstitute_from_api_payload
from .app_param_preparer import AppParamPreparer
from .answers_collector import AnswersCollector
from .app_html_renderer import AppHTMLRenderer
from .app_run_output import AppRunOutput
from .descriptors import (
    InitialSurveyDescriptor,
    OutputFormattersDescriptor,
    AttachmentFormattersDescriptor,
    AppTypeRegistryDescriptor,
    ApplicationNameDescriptor,
    DisplayNameDescriptor,
    ShortDescriptionDescriptor,
    LongDescriptionDescriptor,
    FixedParamsDescriptor,
)


class ParamsDict(TypedDict, total=False):
    """Loose schema for params supplied to App.output; keys are initial_survey question names."""

    pass


def disabled_in_client_mode(method):
    """Decorator to disable instance methods when `self.client_mode` is True.

    When applied to an instance method, calling the method will raise a RuntimeError
    if the instance has `client_mode` set to True. Otherwise, the method executes normally.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if getattr(self, "client_mode", False):
            raise RuntimeError(
                f"{self.__class__.__name__}.{method.__name__} is disabled in client mode"
            )
        return method(self, *args, **kwargs)

    return wrapper


class AppMixin:

    @staticmethod
    def _resolve_app_identifier(
        app_id_or_qualified_name: str, server_url: str = "http://localhost:8000"
    ) -> str:
        """Resolve a qualified name 'owner/alias' to an app_id, or return the app_id unchanged.
        
        Args:
            app_id_or_qualified_name: Either an app_id UUID or a qualified name 'owner/alias'.
            server_url: URL of the FastAPI server.
            
        Returns:
            The resolved app_id.
        """
        if isinstance(app_id_or_qualified_name, str) and "/" in app_id_or_qualified_name:
            parts = app_id_or_qualified_name.split("/", 1)
            if len(parts) == 2:
                try:
                    from .app_server_client import AppServerClient
                    return AppServerClient.resolve_app_id(app_id_or_qualified_name, server_url=server_url)
                except Exception:
                    # Fall back to treating input as an app_id if resolution fails
                    pass
        return app_id_or_qualified_name

    @classmethod
    def list(
        cls, server_url: str = "http://localhost:8000", search: Optional[str] = None, owner: Optional[str] = None
    ) -> list[dict]:
        """List all apps from a FastAPI server.

        Args:
            server_url: URL of the FastAPI server (default: http://localhost:8000)
            search: Optional search string to filter apps.
            owner: Optional owner string to filter apps by owner.

        Returns:
            List of app metadata dictionaries.

        Example:
            >>> apps = App.list()  # doctest: +SKIP
        """
        from .app_server_client import AppServerClient
        from ..scenarios import ScenarioList

        class AvailableApps(ScenarioList):

            def fetch(self, id: int):
                app_id = self[id].get("app_id")
                return App.from_id(app_id)

        apps_data = AppServerClient.list_apps(server_url=server_url, search=search, owner=owner)
        
        # Handle both old and new field structures
        normalized_apps = []
        for app_data in apps_data:
            # Convert old structure to new structure if needed
            if 'name' in app_data and 'description' in app_data:
                # Old structure - convert to new
                name_data = app_data['name']
                desc_data = app_data['description']
                
                if isinstance(name_data, dict):
                    app_data['application_name'] = name_data.get('alias', 'unknown_app')
                    app_data['display_name'] = name_data.get('name', 'Unknown App')
                else:
                    app_data['application_name'] = str(name_data).lower().replace(' ', '_')
                    app_data['display_name'] = str(name_data)
                
                if isinstance(desc_data, dict):
                    app_data['short_description'] = desc_data.get('short', 'No description available.')
                    app_data['long_description'] = desc_data.get('long', desc_data.get('short', 'No description available.'))
                else:
                    desc_str = str(desc_data)
                    app_data['short_description'] = desc_str
                    app_data['long_description'] = desc_str
                
                # Remove old fields
                app_data.pop('name', None)
                app_data.pop('description', None)
            
            normalized_apps.append(app_data)
        
        sl = AvailableApps(
            Scenario.from_dict(s) for s in normalized_apps
        )
        return sl.select('qualified_name', 'display_name', 'short_description', 'long_description')

    @classmethod
    def full_info(cls, app_id_or_qualified_name: str, server_url: str = "http://localhost:8000") -> dict:
        """Get full information about an app."""
        resolved_app_id = cls._resolve_app_identifier(app_id_or_qualified_name, server_url)
        d = App.from_id(resolved_app_id, server_url).to_dict()
        d.pop('jobs_object')
        d.pop('output_formatters')
        d.pop('attachment_formatters')
        survey = Survey.from_dict(d.pop('initial_survey'))
        d['params'] = {q.question_name: q.question_text for q in survey.questions}
        from ..scenarios import Scenario
        return Scenario(d)

    @classmethod
    def pull(cls, edsl_uuid: str) -> "App":
        """Pull an app by UUID from the remote registry/service.
        
        This gets the full app definition from the remote registry/service.
        """
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
            application_name="example_app",
            display_name="Example App",
            short_description="A minimal example app that echoes user input.",
            long_description="A minimal example app that echoes user input using the test model.",
            initial_survey=initial_survey,
            jobs_object=echo_job,
            output_formatters={"echo": echo_formatter},
            default_formatter_name="echo",
        )
    
    @classmethod
    def delete(
        cls,
        app_id_or_qualified_name: str,
        *,
        server_url: str = "http://localhost:8000",
        owner: str | None = None,
    ) -> dict:
        """Delete an app from the server.

        Args:
            app_id_or_qualified_name: The app ID or qualified name 'owner/alias' to delete.
                If a qualified name is provided and no explicit owner is given, the owner
                will be extracted from the qualified name.
            server_url: URL of the FastAPI server.
            owner: Optional owner string; required if the server stored an owner.
                If not provided and app_id_or_qualified_name is a qualified name, 
                the owner will be extracted automatically.

        Returns:
            Server response dictionary.
        """
        from .app_server_client import AppServerClient

        # Extract owner from qualified name if not explicitly provided
        if owner is None and isinstance(app_id_or_qualified_name, str) and "/" in app_id_or_qualified_name:
            parts = app_id_or_qualified_name.split("/", 1)
            if len(parts) == 2:
                owner = parts[0]
        
        resolved_app_id = cls._resolve_app_identifier(app_id_or_qualified_name, server_url)
        try:
            return AppServerClient.delete_app(resolved_app_id, server_url=server_url, owner=owner)
        except Exception as e:
            from .exceptions import FailedToDeleteAppError
            raise FailedToDeleteAppError(f"Failed to delete app {app_id_or_qualified_name}: {e}") from e


class ClientFacingApp(AppMixin):    

    def __new__(cls, app_id_or_qualified_name: Optional[str] = None, **config):
        if app_id_or_qualified_name:
            resolved_app_id = cls._resolve_app_identifier(app_id_or_qualified_name)
            return App.from_id(resolved_app_id)
        else:
            return App(**config)


class App(AppMixin, Base):

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
    display_name: str = DisplayNameDescriptor()  # type: ignore[assignment]
    short_description: str = ShortDescriptionDescriptor()  # type: ignore[assignment]
    long_description: str = LongDescriptionDescriptor()  # type: ignore[assignment]
    fixed_params = FixedParamsDescriptor()

    def __init__(
        self,
        application_name: str,
        display_name: str,
        short_description: str,
        long_description: str,
        initial_survey: Survey,  # type: ignore[assignment]
        jobs_object: Optional["Jobs"] = None,
        output_formatters: Optional[
            Mapping[str, OutputFormatter] | list[OutputFormatter] | OutputFormatters
        ] = None,
        attachment_formatters: Optional[list[ObjectFormatter] | ObjectFormatter] = None,
        default_formatter_name: Optional[str] = None,
        default_params: Optional[dict[str, Any]] = None,
        fixed_params: Optional[dict[str, Any]] = None,
        client_mode: bool = False,
    ):
        """Instantiate an App object.

        Args:
            application_name: Valid Python identifier used as alias for deployment.
            display_name: Human-readable name for this application.
            short_description: One sentence description.
            long_description: Longer description of the application.
            initial_survey: The initial survey to use for the application.
            jobs_object: The jobs object that is the logic of the application.
            output_formatters: The output formatters to use for the application.
            attachment_formatters: The attachment formatters to use for the application.
            default_formatter_name: The name of the default output formatter.
            default_params: Default parameter values for the initial survey.
            fixed_params: Fixed parameter values that cannot be overridden by the caller.
            client_mode: Whether the app is in client mode (remote execution).
        """
        self.jobs_object = jobs_object
        # Set via descriptors (handles validation)
        self.application_name = application_name
        self.display_name = display_name
        self.short_description = short_description
        self.long_description = long_description
        # Validation is handled by descriptor
        self.initial_survey = initial_survey
        # Enforce default_output_formatter contract

        # Normalize and validate via descriptor
        self.output_formatters = output_formatters
        if default_formatter_name is not None:
            self.output_formatters.set_default(default_formatter_name)

        # Normalize via descriptor
        self.attachment_formatters = attachment_formatters
        # Defaults for initial_survey params keyed by question_name
        self._default_params: dict[str, Any] = dict(default_params or {})
        # Fixed params override any provided params at runtime
        # Normalize and assign via descriptor (handles pruning on assignment)
        self.fixed_params = dict(fixed_params or {})
        self._set_params = None

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

        self.client_mode = client_mode

    @classmethod
    def from_id(cls, app_id: str, server_url: str = "http://localhost:8000") -> "BaseApp":
        """Create an app from a given app_id or qualified name 'owner/alias'."""
        # Lazy imports to avoid cycles
        from .app_server_client import AppServerClient
        from .output_formatter import OutputFormatters, ObjectFormatter
        from .stub_job import StubJob

        resolved_app_id = cls._resolve_app_identifier(app_id, server_url)

        # Fetch client-safe app dict from server
        data = AppServerClient.instantiate_remote_app_client(resolved_app_id)

        # Inject a minimal StubJob dict so from_dict can deserialize it
        if not data.get("jobs_object"):
            data["jobs_object"] = {"return_type": "survey"}
        data['client_mode'] = True
        app = cls.from_dict(data)
        app.app_id = resolved_app_id
        return app

    @disabled_in_client_mode
    def to_dict_for_client(self) -> dict:
        """Convert the app to a dictionary suitable for client-side use."""
        d = self.to_dict()
        _ = d.pop("jobs_object")
        return d

    @disabled_in_client_mode
    def deploy(self, server_url: str = "http://localhost:8000", owner: str = "johnjhorton", source_available: bool = False, force: bool = False) -> str:
        """Deploy this app to a FastAPI server.

        Args:
            server_url: URL of the FastAPI server (default: http://localhost:8000)
            owner: Required owner string used for global uniqueness (default: 'johnjhorton').
            source_available: If True, the source code is available to future users.
            force: If True, overwrite any existing app with the same owner/alias.

        Returns:
            The app_id assigned by the server.

        Example:
            >>> app = App.example()
            >>> app_id = app.deploy()  # doctest: +SKIP
        """
        from .app_server_client import AppServerClient
 
        return AppServerClient.deploy(self, server_url=server_url, owner=owner, source_available=source_available, force=force)

    def __call__(self, **kwargs: Any) -> Any:
        """Call the app with the given parameters."""
        return self.output(params=kwargs)

    @disabled_in_client_mode
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

    def by(self, params: Scenario | dict) -> Any:
        """
        Use 
        """
        self._set_params = dict(params)
        return self


    def run(self, **kwargs: Any) -> Any:
        """
        Run the app and return formatted output or a JSON API payload.
        """
        if kwargs == {}:
            if self._set_params is not None:
                kwargs = self._set_params
            else:
                raise ValueError("params must be provided, got empty dict")
        return self.output(params=kwargs)

    def output(
        self,
        params: ParamsDict | None,
        formatter_name: Optional[str] = None,
        stop_on_exception: bool = True,
        disable_remote_inference: bool = False,
        verbose: bool = False,
        api_payload: bool = False,
        server_url: str = "http://localhost:8000",
        app_id: Optional[str] = None,
    ) -> Any:
        """Run the app and return formatted output or a JSON API payload."""
        if self.client_mode:
            return self._remote_output(
                params=params,
                formatter_name=formatter_name,
                server_url=server_url,
                app_id=app_id,
            )
        else:
            return self._local_output(
                params=params,
                formatter_name=formatter_name,
                stop_on_exception=stop_on_exception,
                disable_remote_inference=disable_remote_inference,
                verbose=verbose,
                api_payload=api_payload,
            )

    def _remote_output(
        self,
        *,
        params: ParamsDict | None,
        formatter_name: Optional[str] = None,
        server_url: str = "http://localhost:8000",
        app_id: Optional[str] = None,
    ) -> Any:
        """Run output remotely and return the locally rendered result using server-returned Results + formatters."""
        # Lazy import to avoid cycles
        from .app_server_client import AppServerClient

        if app_id is None:
            app_id = self.app_id

        target_app_id = app_id or AppServerClient.deploy(self, server_url=server_url, owner="johnjhorton")
        exec_resp = AppServerClient.execute_app(
            target_app_id,
            dict(params or {}),
            formatter_name=formatter_name,
            server_url=server_url,
            api_payload=True,
            return_results=True,
        )
        # Expect standardized payload strictly: result -> results/formatters/selected_formatter
        packet = exec_resp["result"]
        from .output_formatter import OutputFormatters
        from ..results import Results

        reconstructed_results = Results.from_dict(packet["results"])
        ofs = OutputFormatters.from_dict(packet["formatters"])
        selected = packet.get("selected_formatter")
        
        # Return AppRunOutput for consistent interface
        return AppRunOutput(
            results=reconstructed_results,
            formatters=ofs,
            params=params or {},
            default_formatter_name=selected or ofs.default,
        )

    @disabled_in_client_mode
    def _local_output(
        self,
        params: ParamsDict | None,
        formatter_name: Optional[str] = None,
        stop_on_exception: bool = True,
        disable_remote_inference: bool = False,
        verbose: bool = False,
        api_payload: bool = False,
    ) -> Any:
        """Run the app and return formatted output or a JSON API payload.

        Args:
            params: Mapping of answers keyed by `initial_survey` question names. If None, collects interactively.
            verbose: Currently unused; reserved for future logging controls.
            formatter_name: Optional explicit formatter selection; defaults to the App's default formatter.
            stop_on_exception: If True, abort job execution on first exception.
            disable_remote_inference: If True, force local execution where supported.
            api_payload: When True, return a JSON-serializable payload suitable for API responses.

        Returns:
            The formatted output as produced by the selected formatter, or a JSON-serializable object when
            `api_payload=True` containing `meta` and `data` (plus optional `preview`).

        Doctest (API payload keys):
            >>> app = App.example()
            >>> out = app.output(params={"text": "hello"}, api_payload=True, disable_remote_inference=True)
            >>> set(["meta","data"]).issubset(set(out.keys()))
            True
        """

        if params is None:
            params = AnswersCollector.collect_interactively(self)

        params = self._apply_default_params(
            params
        )  # Apply default params first so they can be overridden by fixed params
        params = self._apply_fixed_params(
            params
        )  # Apply fixed params last so they 'win'

        # Prepare head attachments - these are what will get attached to the jobs object
        head_attachments = self._prepare_head_attachments(params)
        modified_jobs_object = head_attachments.attach_to_head(
            self.jobs_object
        )  # attach them

        results = self._generate_results(
            modified_jobs_object,
            stop_on_exception=stop_on_exception,
            disable_remote_inference=disable_remote_inference,
        )

        if not api_payload:
            # Return AppRunOutput for interactive use
            return AppRunOutput(
                results=results,
                formatters=self.output_formatters,
                params=params or {},
                default_formatter_name=formatter_name or self.output_formatters.default,
            )

        # For API payload, format immediately and build envelope
        formatted_output = self._format_output(results, formatter_name, params)
        return build_api_payload(formatted_output, formatter_name, self, params)

    # Inline helpers moved to api_payload module
    @disabled_in_client_mode
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

    def _format_output(
        self, results: "Results", formatter_name: Optional[str], params: ParamsDict
    ) -> Any:
        """Apply the selected output formatter to results with a params context.

        Builds a context with both namespaced `params` and top-level keys for compatibility
        with existing templates and passes it to the formatter's render method.

        The 'params' key allows the formatter to be parameterized with the values from the initial_survey.


        """
        formatter = self._select_formatter(formatter_name)
        return formatter.render(
            results, params={"params": dict(params or {})}
        )  # {"params": dict(params or {})} is a bit of a hack to allow the formatter to be parameterized with the values from the initial_survey.

    @staticmethod
    def reconstitute_api_output(payload: Any) -> Any:
        """Reverse `api_payload` envelope back to the formatted output.

        Accepts either a full API envelope or a raw value; raw values are returned unchanged.

        Doctest:
            >>> app = App.example()
            >>> env = app.output(params={"text": "hello"}, api_payload=True, disable_remote_inference=True)
            >>> restored = App.reconstitute_api_output(env)
            >>> isinstance(restored, str) or isinstance(restored, list) or hasattr(restored, 'to_dict')
            True
        """
        return reconstitute_from_api_payload(payload)

    def _apply_default_params(
        self, params: ParamsDict, *, survey_names=None, default_params=None
    ) -> ParamsDict:
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
        survey_names = (
            {q.question_name for q in self.initial_survey}
            if survey_names is None
            else survey_names
        )
        default_params = (
            self._default_params if default_params is None else default_params
        )

        # survey_names = {q.question_name for q in initial_survey}
        merged: dict[str, Any] = dict(params or {})
        for key, value in default_params.items():
            if survey_names and key not in survey_names:
                continue
            if key not in merged or merged.get(key) is None:
                merged[key] = value
        return merged

    def _apply_fixed_params(
        self, params: ParamsDict, *, fixed_params=None
    ) -> ParamsDict:
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

    @disabled_in_client_mode
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

    @disabled_in_client_mode
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
            application_name=self.application_name,
            display_name=self.display_name,
            short_description=self.short_description,
            long_description=self.long_description,
            initial_survey=self.initial_survey,
            jobs_object=self.jobs_object,
            output_formatters=new_map,
            default_formatter_name=self.output_formatters.default,
        )

    @disabled_in_client_mode
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
            application_name=self.application_name,
            display_name=self.display_name,
            short_description=self.short_description,
            long_description=self.long_description,
            initial_survey=pruned_survey,
            jobs_object=self.jobs_object,
            output_formatters=new_output_map,
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
        fmt_names = ", ".join(fmt_names_list[:8]) + (
            "..." if len(fmt_names_list) > 8 else ""
        )
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
            getattr(f, "name", f.__class__.__name__)
            for f in (self.attachment_formatters or [])
        ]
        attach_names = ", ".join(attach_names_list[:8]) + (
            "..." if len(attach_names_list) > 8 else ""
        )
        app_type = self.application_type

        return (
            f"{cls_name}(application_name='{self.application_name}', display_name='{self.display_name}', "
            f"short_description='{self.short_description}', "
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
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
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
            application_name: Optional Python identifier for the app (defaults to 'ranking_app').
            display_name: Optional human-readable name (defaults to 'Ranking App').
            short_description: Optional one-sentence description.
            long_description: Optional longer description.
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
            raise TypeError(
                "option_fields must be a sequence of exactly two field names"
            )

        try:
            q_opts = getattr(ranking_question, "question_options", None)
            q_text = getattr(ranking_question, "question_text", "") or ""
            haystack = (
                " ".join([str(x) for x in (q_opts or []) if isinstance(x, str)])
                + " "
                + str(q_text)
            )
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
            application_name=application_name or "ranking_app",
            display_name=display_name or "Ranking App",
            short_description=short_description or "An app that ranks items via pairwise comparisons.",
            long_description=long_description or "An app that ranks items via pairwise comparisons using a survey-based approach.",
            initial_survey=Survey(
                [
                    QuestionEDSLObject(
                        question_name="input_items",
                        question_text="Provide the items to rank as a ScenarioList",
                        expected_object_type="ScenarioList",
                    )
                ]
            ),
            jobs_object=jobs_object,
            output_formatters={"ranked_list": output_formatter},
            default_formatter_name="ranked_list",
            attachment_formatters=[
                # Transform the provided ScenarioList into pairwise comparisons
                ScenarioAttachmentFormatter(description="Pairwise choose_k").choose_k(2)
            ],
        )

    @disabled_in_client_mode
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



if __name__ == "__main__":
    # import doctest
    # doctest.testmod(optionflags=doctest.ELLIPSIS)
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
        .to_markdown()
    )

    app = ClientFacingApp(
        application_name="twitter_thread_splitter",
        display_name="Twitter Thread Splitter",
        short_description="This application splits text into a twitter thread.",
        long_description="This application takes long-form text and splits it into tweet-sized chunks suitable for posting as a Twitter thread.",
        initial_survey=initial_survey,
        jobs_object=jobs_survey.to_jobs(),
        output_formatters={"splitter": twitter_output_formatter},
        default_formatter_name="splitter",
    )

    raw_text = """
    The Senate of the United States shall be composed of two Senators from each State, chosen by the Legislature thereof, for six Years; and each Senator shall have one Vote.
    Immediately after they shall be assembled in Consequence of the first Election, they shall be divided as equally as may be into three Classes. The Seats of the Senators of the first Class shall be vacated at the Expiration of the second Year, of the second Class at the Expiration of the fourth Year, and of the third Class at the Expiration of the sixth Year, so that one third may be chosen every second Year; and if Vacancies happen by Resignation, or otherwise, during the Recess of the Legislature, the Executive thereof may make temporary Appointments until the next Meeting of the Legislature, which shall then fill such Vacancies.
    No Person shall be a Senator who shall not have attained to the Age of thirty Years, and been nine Years a Citizen of the United States, and who shall not, when elected, be an Inhabitant of that State for which he shall be chosen.
    The Vice President of the United States shall be President of the Senate, but shall have no Vote, unless they be equally divided.
    The Senate shall chuse their other Officers, and also a President pro tempore, in the Absence of the Vice President, or when he shall exercise the Office of President of the United States.
    The Senate shall have the sole Power to try all Impeachments. When sitting for that Purpose, they shall be on Oath or Affirmation. When the President of the United States is tried, the Chief Justice shall preside: And no Person shall be convicted without the Concurrence of two thirds of the Members present.
    Judgment in Cases of Impeachment shall not extend further than to removal from Office, and disqualification to hold and enjoy any Office of honor, Trust or Profit under the United States: but the Party convicted shall nevertheless be liable and subject to Indictment, Trial, Judgment and Punishment, according to Law.
    """

    # Deploy and run remotely (standardized path)
    app_id = app.deploy()

    # Local output
    local_out = app.output(
        params={"raw_text": raw_text},
        formatter_name="splitter",
        disable_remote_inference=False,
    )

    # Remote output
    remote_app = ClientFacingApp(app_id=app_id)

    remote_out = remote_app._remote_output(
        params={"raw_text": raw_text},
        formatter_name="splitter",
        server_url="http://localhost:8000",
        #      app_id=app_id,
    )

    print("Local equals Remote:", str(local_out) == str(remote_out))
    print(remote_out)
