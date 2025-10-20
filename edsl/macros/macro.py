from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, TypedDict, Mapping, Callable
import re
from html import escape

from functools import wraps

from ..scenarios import Scenario
from ..surveys import Survey
from ..base import Base

if TYPE_CHECKING:
    from ..scenarios import ScenarioList
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from .head_attachments import HeadAttachments

from .output_formatter import OutputFormatter, OutputFormatters
from .api_payload import build_api_payload, reconstitute_from_api_payload
from .answers_collector import AnswersCollector
from .macro_html_renderer import MacroHTMLRenderer
from .macro_run_output import MacroRunOutput
from .descriptors import (
    InitialSurveyDescriptor,
    OutputFormattersDescriptor,
    AttachmentFormattersDescriptor,
    MacroTypeRegistryDescriptor,
    ApplicationNameDescriptor,
    DisplayNameDescriptor,
    ShortDescriptionDescriptor,
    LongDescriptionDescriptor,
    FixedParamsDescriptor,
)


class ParamsDict(TypedDict, total=False):
    """Loose schema for params supplied to Macro.output; keys are initial_survey question names."""

    pass


def disabled_in_client_mode(method) -> Callable:
    """Decorator to disable instance methods when `self.client_mode` is True.

    When applied to an instance method, calling the method will raise a RuntimeError
    if the instance has `client_mode` set to True. Otherwise, the method executes normally.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if getattr(self, "client_mode", False):
            from .exceptions import ClientModeError

            raise ClientModeError(
                message=f"{self.__class__.__name__}.{method.__name__} is disabled in client mode. If it's a macro you created, you can 'pull' it to get the full macro object."
            )
        return method(self, *args, **kwargs)

    return wrapper


class MacroMixin:
    """Mixin for Macro class.

    This provides methods that are available to both the Macro and ClientFacingMacro classes.
    """

    @classmethod
    def public_macros(cls) -> "ScenarioList":
        """List all deployed macros.

        Returns:
            List of deployed macro information.
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        # Fetch list of deployed macros
        response = requests.get(
            f"{BASE_URL}/api/v0/macros/deployed",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        macros_list = response.json()
        from ..scenarios import ScenarioList

        return ScenarioList.from_list_of_dicts(macros_list["deployed_macros"])

    @classmethod
    def instantiate_public_macro(cls, qualified_name: str) -> "Macro":
        """Instantiate a public macro by fully qualified name.

        This is used to instantiate a macro from a fully qualified name.
        The macro lacks the jobs_object, which means to execute, the params are sent to the server.
        This is controlled by the client_mode flag.

        Args:
            qualified_name: The fully qualified name of the macro.

        Returns:
            The instantiated macro.
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        alias = qualified_name.split("/")[-1]
        owner = qualified_name.split("/")[-2]

        # Fetch macro dictionary
        response = requests.get(
            f"{BASE_URL}/api/v0/macros/deployed/{owner}/{alias}/instantiate_macro_client",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        macro_dict = response.json()

        m = Macro.from_dict(macro_dict)
        m.macro_id = cls.get_public_macro_uuid(owner, alias)
        m.client_mode = True
        return m

    @classmethod
    def get_public_macro_uuid(cls, owner: str, alias: str) -> str:
        """Get macro UUID from fully qualified name.

        GET /api/v0/macros/deployed/{owner}/{alias}/uuid

        Args:
            owner: The owner of the macro.
            alias: The alias of the macro.

        Returns:
            The macro UUID.
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        response = requests.get(
            f"{BASE_URL}/api/v0/macros/deployed/{owner}/{alias}/uuid",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        return response.json()["macro_uuid"]

    @classmethod
    def create_client_macro(
        cls, macro_id_or_qualified_name: Optional[str] = None
    ) -> Macro:
        """Create a client-facing macro from a macro_id or qualified name."""
        import requests
        from uuid import UUID

        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        MACRO_UUID = macro_id_or_qualified_name
        # Fetch macro dictionary
        response = requests.get(
            f"{BASE_URL}/api/v0/macros/{MACRO_UUID}/instantiate_macro_client",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        macro_dict = response.json()

        m = Macro.from_dict(macro_dict)
        m.client_mode = True
        m.macro_id = MACRO_UUID
        return m

    @classmethod
    def example(cls) -> "Macro":
        """Return a minimal Macro configured with Model('test') for local testing.

        Example:
            >>> macro = Macro.example()
            >>> out = macro.output(params={"text": "hello"}, disable_remote_inference=True)
            >>> bool(out)
            True
        """
        # Import locally to avoid cycles
        from ..surveys import Survey
        from ..questions import QuestionFreeText
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
            application_name="example_macro",
            display_name="Example Macro",
            short_description="A minimal example macro that echoes user input.",
            long_description="A minimal example macro that echoes user input using the test model.",
            initial_survey=initial_survey,
            jobs_object=echo_job,
            output_formatters={"echo": echo_formatter},
            default_formatter_name="echo",
        )


class ClientFacingMacro(MacroMixin):
    """Facade for creating Macro instances with simplified interface.

    The key reason for doing this is so that the macro can be instantiated from a fully qualified name if
    it's deployed. If it's not deployed, the macro is not depoyed but it's one belonging to the user, it gets pulled.
    If none of the above, a new macro is created using the provided config.

    Usage:
        macro = ClientFacingMacro("owner/alias")  # Pull from server
        macro = ClientFacingMacro(application_name="...", ...)  # Create new
    """

    def __new__(cls, macro_id_or_qualified_name: Optional[str] = None, **config):
        if macro_id_or_qualified_name:
            try:
                deployed_macro = Macro.instantiate_public_macro(
                    macro_id_or_qualified_name
                )
                return deployed_macro
            except Exception as e:
                print(f"Error instantiating public macro: {e}")
                return Macro.pull(macro_id_or_qualified_name)
            # Use inherited pull method from Base
            # Need to handle client macro case.
            return Macro.pull(macro_id_or_qualified_name)
        else:
            return Macro(**config)

    @classmethod
    def pull(cls, macro_id_or_qualified_name: str) -> "Macro":
        """Pull a macro from the server.

        Automatically detects and returns the correct type (Macro or CompositeMacro).

        Args:
            macro_id_or_qualified_name: Either a macro_id UUID or qualified name 'owner/alias'.

        Returns:
            Macro or CompositeMacro instance depending on the stored object type.
        """
        return Macro.pull(macro_id_or_qualified_name)

    @classmethod
    def from_dict(cls, data: dict) -> "Macro":
        """Deserialize a macro from a dictionary.

        Automatically detects and returns the correct type (Macro or CompositeMacro).

        Args:
            data: Dictionary representation of a macro.

        Returns:
            Macro or CompositeMacro instance depending on the application_type.
        """
        return Macro.from_dict(data)

    @classmethod
    def list(self, *args, **kwargs) -> "ScenarioList":
        """Delegate to the actual Macro class."""
        return Macro.list(*args, **kwargs)


class Macro(MacroMixin, Base):
    # Subclass registry managed via descriptor
    _registry = MacroTypeRegistryDescriptor()

    # Each subclass should set a unique application_type
    application_type: str = "base"

    def __init_subclass__(cls, **kwargs):
        if cls is Macro:
            return
        # Delegate validation and registration to descriptor (access the descriptor itself)
        Macro.__dict__["_registry"].register(cls)

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
        """Instantiate a Macro object.

        Args:
            application_name: Valid Python identifier used as alias for deployment.
            display_name: Human-readable name for this macro.
            short_description: One sentence description.
            long_description: Longer description of the macro.
            initial_survey: The initial survey to use for the macro.
            jobs_object: The jobs object that is the logic of the macro.
            output_formatters: The output formatters to use for the macro.
            attachment_formatters: The attachment formatters to use for the macro.
            default_formatter_name: The name of the default output formatter.
            default_params: Default parameter values for the initial survey.
            fixed_params: Fixed parameter values that cannot be overridden by the caller.
            client_mode: Whether the macro is in client mode (remote execution).
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
        from .macro_validator import MacroValidator

        MacroValidator.validate_parameters(self)
        MacroValidator.validate_initial_survey_edsl_uniqueness(self)

        # Cache for generated results keyed by the hash of a jobs object
        self._generated_results: dict[int, "Results"] = {}

        # Register this macro instance in the global registry
        try:
            from .macro_registry import MacroRegistry

            MacroRegistry.register(self)
        except Exception:
            # Registration failures should not prevent macro initialization
            pass

        self.client_mode = client_mode

    def alias(self) -> str:
        """Return the alias of the macro.

        >>> macro = Macro.example()
        >>> macro.alias()
        'example-macro'
        """
        return self.application_name.replace("_", "-")

    def push(self, *args, **kwargs) -> dict:
        """Push the macro to the server."""
        if "alias" not in kwargs:
            kwargs["alias"] = self.alias()
        if "description" not in kwargs:
            kwargs["description"] = self.short_description
        return super().push(*args, **kwargs)

    @disabled_in_client_mode
    def to_dict_for_client(self) -> dict:
        """Convert the macro to a dictionary suitable for client-side use."""
        d = self.to_dict()
        _ = d.pop("jobs_object")
        return d

    def __call__(self, **kwargs: Any) -> Any:
        """Call the macro with the given parameters."""
        return self.output(params=kwargs)

    @disabled_in_client_mode
    def _generate_results(
        self,
        modified_jobs_object: "Jobs",
        stop_on_exception: bool = True,
        disable_remote_inference: bool = False,
    ) -> "Results":
        """Generate results for the given jobs object with instance-level caching.


        >>> macro = Macro.example()
        >>> macro._generated_results
        {}
        >>> results = macro._generate_results(macro.jobs_object, disable_remote_inference=True)
        >>> type(results).__name__
        'Results'
        >>> len(macro._generated_results)
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
        Run the macro and return formatted output or a JSON API payload.
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
        # server_url: str = "http://localhost:8000",
        # macro_id: Optional[str] = None,
    ) -> Any:
        """Run the macro and return formatted output or a JSON API payload."""
        if self.client_mode:
            return self._remote_output(
                params=params,
                # formatter_name=formatter_name,
                # server_url=server_url,
                # macro_id=macro_id,
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

    def _serialize_params(self, params: ParamsDict | None) -> dict:
        """Serialize params by calling to_dict on objects that have that attribute.

        This method handles the serialization of EDSL objects (Scenario, ScenarioList,
        Survey, Agent, etc.) for transmission to remote servers. Objects with a 'to_dict'
        method are wrapped with metadata to enable reconstruction on the server side.

        Server-side usage:
            On the server, use _deserialize_params to reconstruct the original objects
            before calling the macro's output method:

            ```python
            # On server
            deserialized_params = macro._deserialize_params(serialized_params)
            result = macro.output(params=deserialized_params, ...)
            ```

        Args:
            params: The parameters to serialize

        Returns:
            Dictionary with serialized parameters. EDSL objects are wrapped with:
            - '__edsl_object__': True (marker)
            - '__edsl_type__': Class name
            - '__edsl_module__': Module path
            - 'data': Serialized object data
        """
        if params is None:
            return {}

        serialized = {}
        for key, value in params.items():
            if hasattr(value, "to_dict"):
                # Serialize EDSL objects (Scenario, ScenarioList, Survey, Agent, etc.)
                serialized[key] = {
                    "__edsl_object__": True,
                    "__edsl_type__": value.__class__.__name__,
                    "__edsl_module__": value.__class__.__module__,
                    "data": value.to_dict(),
                }
            else:
                # Keep primitive types as-is
                serialized[key] = value

        return serialized

    def _deserialize_params(self, serialized_params: dict) -> ParamsDict:
        """Deserialize params by reconstructing EDSL objects from their serialized form.

        Args:
            serialized_params: The serialized parameters

        Returns:
            Dictionary with deserialized parameters
        """
        if not serialized_params:
            return {}

        deserialized = {}
        for key, value in serialized_params.items():
            if isinstance(value, dict) and value.get("__edsl_object__"):
                # Reconstruct EDSL object
                obj_type = value["__edsl_type__"]
                obj_module = value["__edsl_module__"]
                obj_data = value["data"]

                try:
                    # Import the module and get the class
                    import importlib

                    module = importlib.import_module(obj_module)
                    obj_class = getattr(module, obj_type)

                    # Reconstruct the object
                    deserialized[key] = obj_class.from_dict(obj_data)
                except (ImportError, AttributeError, TypeError):
                    # If reconstruction fails, keep the serialized data
                    # This provides graceful degradation
                    deserialized[key] = value
            else:
                # Keep primitive types as-is
                deserialized[key] = value

        return deserialized

    def _test_serialization_roundtrip(self, params: ParamsDict | None) -> bool:
        """Test that serialization and deserialization preserves the original params.

        This method is useful for debugging and ensuring the round trip works correctly.

        Args:
            params: The parameters to test

        Returns:
            True if the round trip preserves the original params, False otherwise

        Example:
            >>> macro = Macro.example()
            >>> test_params = {"text": "hello", "number": 42}
            >>> macro._test_serialization_roundtrip(test_params)
            True
        """
        if params is None:
            return True

        try:
            # Serialize and then deserialize
            serialized = self._serialize_params(params)
            deserialized = self._deserialize_params(serialized)

            # Compare the results
            # For EDSL objects, we need to compare their dict representations
            # since object identity won't be preserved
            for key in params:
                original = params[key]
                restored = deserialized[key]

                if hasattr(original, "to_dict") and hasattr(restored, "to_dict"):
                    # Compare EDSL objects by their dict representation
                    if original.to_dict() != restored.to_dict():
                        return False
                else:
                    # Compare primitive types directly
                    if original != restored:
                        return False

            return True
        except Exception:
            return False

    def _remote_output(
        self,
        *,
        params: ParamsDict | None,
    ) -> Any:
        """Run output remotely and return the locally rendered result using server-returned Results + formatters."""
        import requests
        from uuid import UUID

        # Configuration
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key
        MACRO_UUID = self.macro_id
        # Execute macro with parameters
        response = requests.post(
            f"{BASE_URL}/api/v0/macros/execute",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={"macro_uuid": MACRO_UUID, "params": self._serialize_params(params)},
        )
        response.raise_for_status()
        result = response.json()

        # Get the results UUID
        results_uuid = result["results_uuid"]
        print(f"Macro executed successfully! Results UUID: {results_uuid}")

        # Now you can pull the results object
        from ..results import Results

        reconstructed_results = Results.pull(results_uuid)

        from .output_formatter import OutputFormatters

        ofs = self.output_formatters
        return MacroRunOutput(
            results=reconstructed_results,
            formatters=ofs,
            params=params or {},
            # default_formatter_name=ofs.default,
        )

    @disabled_in_client_mode
    def deploy(self, macro_uuid: Optional[str] = None, overwrite: bool = False) -> None:
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        if macro_uuid is None:
            print("Deploying macro with no UUID, pushing to server...")
            info = self.push(overwrite=overwrite)
            macro_uuid = info["uuid"]
            print(f"Deployed macro with UUID: {macro_uuid}")

        MACRO_UUID = macro_uuid

        print(f"Deploying macro with UUID: {MACRO_UUID}")
        response = requests.post(
            f"{BASE_URL}/api/v0/macros/{MACRO_UUID}/deploy",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        result = response.json()

        print(f"Status: {result['status']}")
        print(f"Fully qualified name: {result['fully_qualified_name']}")
        print(f"Deployed: {result['deployed']}")

    def inject_results(self, results: Results, params: ParamsDict | None = None) -> Any:
        """Inject results into the macro.

        Args:
            results: The results to inject.

        Returns:
            The macro.
        """
        return MacroRunOutput(
            results=results,
            formatters=self.output_formatters,
            params=params or {},
            default_formatter_name=self.output_formatters.default,
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
        """Run the macro and return formatted output or a JSON API payload.

        Args:
            params: Mapping of answers keyed by `initial_survey` question names. If None, collects interactively.
            verbose: Currently unused; reserved for future logging controls.
            formatter_name: Optional explicit formatter selection; defaults to the Macro's default formatter.
            stop_on_exception: If True, abort job execution on first exception.
            disable_remote_inference: If True, force local execution where supported.
            api_payload: When True, return a JSON-serializable payload suitable for API responses.

        Returns:
            The formatted output as produced by the selected formatter, or a JSON-serializable object when
            `api_payload=True` containing `meta` and `data` (plus optional `preview`).

        Doctest (API payload keys):
            >>> macro = Macro.example()
            >>> out = macro.output(params={"text": "hello"}, api_payload=True, disable_remote_inference=True)
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
            self.jobs_object.duplicate()
        )  # attach them

        results = self._generate_results(
            modified_jobs_object,
            stop_on_exception=stop_on_exception,
            disable_remote_inference=disable_remote_inference,
        )

        if not api_payload:
            # Return MacroRunOutput for interactive use
            return MacroRunOutput(
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

        >>> macro = Macro.example()
        >>> macro._select_formatter(None)  # doctest: +ELLIPSIS
        OutputFormatter(description='Echo', ...)
        >>> macro._select_formatter("echo")  # doctest: +ELLIPSIS
        OutputFormatter(description='Echo', ...)
        >>> macro._select_formatter("fake")
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
            >>> macro = Macro.example()
            >>> env = macro.output(params={"text": "hello"}, api_payload=True, disable_remote_inference=True)
            >>> restored = Macro.reconstitute_api_output(env)
            >>> isinstance(restored, str) or isinstance(restored, list) or hasattr(restored, 'to_dict')
            True
        """
        return reconstitute_from_api_payload(payload)

    def _apply_default_params(
        self, params: ParamsDict, *, survey_names=None, default_params=None
    ) -> ParamsDict:
        """Merge provided params with defaults declared on the Macro.

        Any key missing from params or explicitly None will be filled with the
        corresponding default when provided and when the key exists on the
        initial_survey.

        Args:
            params: The parameters to merge with the defaults.
            survey_names: Optional set of allowed question names; defaults to the Macro's `initial_survey` names.
            default_params: Optional mapping of default parameter values; defaults to the Macro's `_default_params`.

        Doctest:
        >>> macro = Macro.example()
        >>> # Provide defaults and limit to a specific survey key via overrides
        >>> macro._apply_default_params({}, survey_names={'text'}, default_params={'text': 'hi', 'extra': 'x'})
        {'text': 'hi'}
        >>> # Existing non-None value is preserved
        >>> macro._apply_default_params({'text': 'yo'}, survey_names={'text'}, default_params={'text': 'hi'})
        {'text': 'yo'}
        >>> # None is treated as missing and gets filled from defaults
        >>> macro._apply_default_params({'text': None}, survey_names={'text'}, default_params={'text': 'hi'})
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

        If the caller supplies any parameter that is fixed on this Macro, raise an
        exception because fixed parameters must not be provided by the caller.
        Otherwise, merge the fixed values into the params.

        Doctest (dependency-injected fixed_params):
        >>> macro = Macro.example()
        >>> # Merge injected fixed params when caller doesn't provide those keys
        >>> macro._apply_fixed_params({'text': 'hi'}, fixed_params={'lang': 'en'})
        {'text': 'hi', 'lang': 'en'}
        >>> # Reject when caller supplies a fixed key
        >>> macro._apply_fixed_params({'lang': 'fr'}, fixed_params={'lang': 'en'})
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
    ) -> "Macro":
        """Add an additional output formatter to this macro (fluent).

        Args:
            formatter: An `OutputFormatter` instance to add.
            set_default: If True, set this formatter as the default for subsequent outputs.

        Returns:
            The `Macro` instance to allow fluent chaining.

        Raises:
            TypeError: If `formatter` is not an `OutputFormatter`.
            ValueError: If the formatter has no name or the name already exists.
        """
        # Delegate to OutputFormatters helper
        self.output_formatters.register(formatter, set_default=set_default)

        return self

    @disabled_in_client_mode
    def add_attachment_formatter(self, formatter: "ObjectFormatter") -> "Macro":
        """Add an attachment formatter (fluent).

        Args:
            formatter: The `ObjectFormatter` instance to add.

        Returns:
            The `Macro` instance to allow fluent chaining.
        """
        current = list(self.attachment_formatters or [])
        current.append(formatter)
        self.attachment_formatters = current
        return self

    @disabled_in_client_mode
    def code(self) -> str:
        """Return the code for the macro.

        Returns:
            The code for the macro.
        """
        raise NotImplementedError("Macro.code() is not implemented")

    def with_output_formatter(
        self,
        name_or_formatter: str | OutputFormatter,
        formatter: OutputFormatter | None = None,
    ) -> "Macro":
        """Return a new macro with an additional named output formatter.

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
    def partial_application(self, fixed: dict[str, Any]) -> "Macro":
        """Return a new Macro instance with specified initial_survey params fixed.

        Args:
            fixed: Mapping of existing initial_survey question names to fixed values.

        Returns:
            A new Macro instance of the same concrete class with these values fixed.

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
    def parameters(self) -> "ScenarioList":
        """Return ScenarioList of parameter info derived from the initial survey."""
        from ..scenarios.scenario_list import ScenarioList

        return ScenarioList(
            [
                Scenario(
                    {
                        "question_name": q.question_name,
                        "question_type": q.question_type,
                        "question_text": q.question_text,
                    }
                )
                for q in self.initial_survey
            ]
        )

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Macro.

        This representation provides a simplified view suitable for doctests.
        Used primarily for doctests and debugging.
        """
        cls_name = self.__class__.__name__
        return (
            f"{cls_name}(application_name='{self.application_name}', "
            f"display_name='{self.display_name}', "
            f"short_description='{self.short_description[:50]}...', "
            f"...)"
        )

    def _summary_repr(self, max_formatters: int = 5, max_params: int = 5) -> str:
        """Generate a summary representation of the Macro with Rich formatting.

        Args:
            max_formatters: Maximum number of formatters to show before truncating
            max_params: Maximum number of parameters to show before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io

        # Build the Rich text
        output = Text()
        cls_name = self.__class__.__name__

        output.append(f"{cls_name}(\n", style="bold cyan")

        # Application info
        output.append("    application_name=", style="white")
        output.append(f"'{self.application_name}'", style="yellow")
        output.append(",\n", style="white")

        output.append("    display_name=", style="white")
        output.append(f"'{self.display_name}'", style="green")
        output.append(",\n", style="white")

        # Short description (truncate if too long)
        desc = self.short_description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        output.append("    short_description=", style="white")
        output.append(f"'{desc}'", style="cyan")
        output.append(",\n", style="white")

        # Application type - use getattr to get the actual class attribute value
        app_type = getattr(self.__class__, "application_type", "base")
        if not isinstance(app_type, str):
            app_type = self.__class__.__name__
        output.append("    application_type=", style="white")
        output.append(f"'{app_type}'", style="magenta")
        output.append(",\n", style="white")

        # Parameters
        param_names = [p["question_name"] for p in self.parameters]
        num_params = len(param_names)
        output.append(f"    num_parameters={num_params}", style="white")

        if num_params > 0:
            output.append(",\n    parameters=[", style="white")
            for i, name in enumerate(param_names[:max_params]):
                output.append(f"'{name}'", style="bold yellow")
                if i < min(num_params, max_params) - 1:
                    output.append(", ", style="white")
            if num_params > max_params:
                output.append(f", ... ({num_params - max_params} more)", style="dim")
            output.append("]", style="white")

        output.append(",\n", style="white")

        # Jobs info
        job_cls = (
            getattr(self.jobs_object, "__class__").__name__
            if self.jobs_object
            else "None"
        )
        output.append("    job_type=", style="white")
        output.append(f"'{job_cls}'", style="blue")
        output.append(",\n", style="white")

        # Formatters
        fmt_names_list = list(getattr(self.output_formatters, "mapping", {}).keys())
        num_formatters = len(fmt_names_list)
        output.append(f"    num_formatters={num_formatters}", style="white")

        if num_formatters > 0:
            output.append(",\n    formatters=[", style="white")
            for i, name in enumerate(fmt_names_list[:max_formatters]):
                output.append(f"'{name}'", style="yellow")
                if i < min(num_formatters, max_formatters) - 1:
                    output.append(", ", style="white")
            if num_formatters > max_formatters:
                output.append(
                    f", ... ({num_formatters - max_formatters} more)", style="dim"
                )
            output.append("]", style="white")

        # Default formatter
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

        if default_fmt != "<none>":
            output.append(",\n    default_formatter=", style="white")
            output.append(f"'{default_fmt}'", style="bold green")

        output.append("\n)", style="bold cyan")

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

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
        return MacroHTMLRenderer(self).render()

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Serialize this macro to a JSON-serializable dict."""
        from .macro_serialization import MacroSerialization

        return MacroSerialization.to_dict(self, add_edsl_version=add_edsl_version)

    @property
    def application_type(self) -> str:  # type: ignore[override]
        """Return the application type identifier.

        Identity is class-based: by default returns the class attribute
        `application_type` if present, otherwise the class name. Builders that
        return `App` instances typically rely on the default class identity.
        """
        return getattr(self.__class__, "application_type", self.__class__.__name__)

    @classmethod
    def from_dict(cls, data: dict) -> "Macro":
        """Deserialize a macro (possibly subclass) from a dict payload."""
        from .macro_serialization import MacroSerialization

        return MacroSerialization.from_dict(cls, data)

    @classmethod
    def create_ranking_macro(
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
    ) -> "Macro":
        """Create a Macro configured to rank items via pairwise comparisons.

        Args:
            ranking_question: A QuestionMultipleChoice configured to compare two options
                using Jinja placeholders like '{{ scenario.<field>_1 }}' and '{{ scenario.<field>_2 }}'.
            option_fields: Sequence of field names corresponding to the two options in the comparison
                (e.g., ['food_1', 'food_2']).
            application_name: Optional Python identifier for the macro (defaults to 'ranking_macro').
            display_name: Optional human-readable name (defaults to 'Ranking Macro').
            short_description: Optional one-sentence description.
            long_description: Optional longer description.
            option_base: Optional base field name (e.g., 'food'). Currently not used by the builder; kept for API parity.
            rank_field: Name of the rank field to include in the output ScenarioList. Currently controlled by the formatter.
            max_pairwise_count: Maximum number of pairwise comparisons to generate. Reserved for future use.

        Returns:
            A Macro instance ready to accept a ScenarioList under the 'input_items' parameter
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
            application_name=application_name or "ranking_macro",
            display_name=display_name or "Ranking Macro",
            short_description=short_description
            or "A macro that ranks items via pairwise comparisons.",
            long_description=long_description
            or "A macro that ranks items via pairwise comparisons using a survey-based approach.",
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


if __name__ == "__main__":
    import doctest

    doctest.testmod()
