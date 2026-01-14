from __future__ import annotations
from typing import (
    TYPE_CHECKING,
    Optional,
    Any,
    TypedDict,
    Mapping,
    Callable,
    Union,
    Set,
)
from functools import wraps

from ..scenarios import Scenario
from ..surveys import Survey
from .base_macro import BaseMacro

# Event-sourcing infrastructure
from ..versioning import GitMixin
from ..store import Store
from .macro_events import apply_macro_event
from .macro_codec import MacroCodec

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..jobs import Jobs
    from ..results import Results
    from .head_attachments import HeadAttachments

    try:
        from typing import Self
    except ImportError:
        from typing import TypeVar

        Self = TypeVar("Self", bound="Macro")

else:
    # At runtime, we can use a simple string annotation
    Self = "Macro"  # Adjust to your class name

from .output_formatter import OutputFormatter, OutputFormatters
from .api_payload import build_api_payload, reconstitute_from_api_payload
from .answers_collector import AnswersCollector
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


class Macro(GitMixin, BaseMacro):
    # Subclass registry managed via descriptor
    _registry = MacroTypeRegistryDescriptor()

    # Each subclass should set a unique application_type
    application_type: str = "base"

    # Event-sourcing configuration
    _versioned = "store"
    _store_class = Store
    _event_handler = apply_macro_event
    _codec = MacroCodec()

    def __init_subclass__(cls, **kwargs):
        if cls is Macro:
            return
        # Delegate validation and registration to descriptor (access the descriptor itself)
        Macro.__dict__["_registry"].register(cls)

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
            OutputFormatter(description="Echo", output_type="ScenarioList")
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
        __macro_identifier: Optional[str] = None,
        *,
        application_name: Optional[str] = None,
        display_name: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        initial_survey: Optional[Survey] = None,  # type: ignore[assignment]
        jobs_object: Optional["Jobs"] = None,
        output_formatters: Optional[
            Mapping[str, OutputFormatter] | list[OutputFormatter] | OutputFormatters
        ] = None,
        attachment_formatters: Optional[list[ObjectFormatter] | ObjectFormatter] = None,
        default_formatter_name: Optional[str] = None,
        default_params: Optional[dict[str, Any]] = None,
        fixed_params: Optional[dict[str, Any]] = None,
        client_mode: bool = False,
        pseudo_run: bool = False,
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
            __macro_identifier: Internal parameter used by __new__ to signal server loading.
        """
        # If instance was already initialized by __new__ (from server), skip initialization
        if hasattr(self, "_initialized") and self._initialized:
            return

        # Check required arguments when creating new instance
        if __macro_identifier is None:
            if application_name is None:
                raise TypeError(
                    "Macro.__init__() missing required argument: 'application_name'. "
                    "To load from server, use: Macro('owner/alias')"
                )
            if display_name is None:
                raise TypeError(
                    "Macro.__init__() missing required argument: 'display_name'"
                )
            if short_description is None:
                raise TypeError(
                    "Macro.__init__() missing required argument: 'short_description'"
                )
            if long_description is None:
                raise TypeError(
                    "Macro.__init__() missing required argument: 'long_description'"
                )
            if initial_survey is None:
                raise TypeError(
                    "Macro.__init__() missing required argument: 'initial_survey'"
                )

        # Initialize GitMixin
        super().__init__()

        # Initialize the store with all state in meta (Macro is config, not row data)
        self.store = Store(
            entries=[],  # Not used - Macro stores everything in meta
            meta={
                # Component refs (commit_hashes)
                "initial_survey_ref": None,
                "jobs_object_ref": None,
                # Component aliases (for pulling from Coop)
                "initial_survey_alias": None,
                "jobs_object_alias": None,
                # Embedded formatters
                "output_formatters": {},  # {name: serialized_formatter}
                "attachment_formatters": [],
                # Scalar metadata
                "application_name": None,
                "display_name": None,
                "short_description": None,
                "long_description": None,
                "default_params": {},
                "fixed_params": {},
                "default_formatter_name": None,
                "client_mode": client_mode,
                "pseudo_run": pseudo_run,
            },
        )

        # Store live component references
        self._jobs_object = jobs_object
        self._update_jobs_object_ref()

        # Set via descriptors (handles validation)
        self.application_name = application_name
        self.display_name = display_name
        self.short_description = short_description
        self.long_description = long_description
        # Validation is handled by descriptor - also updates store.meta
        self.initial_survey = initial_survey
        self._update_initial_survey_ref()

        # Normalize and validate via descriptor
        self.output_formatters = output_formatters
        if default_formatter_name is not None:
            self.output_formatters.set_default(default_formatter_name)
        self._store_output_formatters()

        # Normalize via descriptor
        self.attachment_formatters = attachment_formatters
        self._store_attachment_formatters()

        # Defaults for initial_survey params keyed by question_name
        self._default_params: dict[str, Any] = dict(default_params or {})
        self.store.meta["default_params"] = dict(self._default_params)

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
        from .macro_registry import MacroRegistry

        MacroRegistry.register(self)

        self.client_mode = client_mode
        self.pseudo_run = pseudo_run

        # Mark as initialized to prevent re-initialization
        self._initialized = True

    # =========================================================================
    # Event-sourcing support methods
    # =========================================================================

    @property
    def jobs_object(self) -> Optional["Jobs"]:
        """Get the jobs object associated with this macro."""
        return getattr(self, "_jobs_object", None)

    @jobs_object.setter
    def jobs_object(self, value: Optional["Jobs"]) -> None:
        """Set the jobs object and update the ref in store."""
        self._jobs_object = value
        if hasattr(self, "store"):
            self._update_jobs_object_ref()

    def _update_initial_survey_ref(self) -> None:
        """Update the initial_survey ref in store.meta."""
        survey = getattr(self, "_initial_survey", None)
        if survey is not None and hasattr(survey, "commit_hash"):
            self.store.meta["initial_survey_ref"] = survey.commit_hash
        else:
            self.store.meta["initial_survey_ref"] = None

    def _update_jobs_object_ref(self) -> None:
        """Update the jobs_object ref in store.meta."""
        jobs = getattr(self, "_jobs_object", None)
        if jobs is not None and hasattr(jobs, "commit_hash"):
            self.store.meta["jobs_object_ref"] = jobs.commit_hash
        else:
            self.store.meta["jobs_object_ref"] = None

    def _store_output_formatters(self) -> None:
        """Store output formatters in store.meta."""
        if not hasattr(self, "store"):
            return
        ofs = getattr(self, "_output_formatters", None)
        if ofs is None:
            return

        # Store serialized formatters in meta
        formatters_dict = {}
        for name, formatter in ofs.mapping.items():
            formatter_data = formatter.to_dict() if hasattr(formatter, "to_dict") else {}
            formatters_dict[name] = formatter_data
        self.store.meta["output_formatters"] = formatters_dict

        # Store default formatter name in meta
        self.store.meta["default_formatter_name"] = ofs.default

    def _store_attachment_formatters(self) -> None:
        """Store attachment formatters in store.meta."""
        if not hasattr(self, "store"):
            return
        afs = getattr(self, "_attachment_formatters", None) or []
        serialized = []
        for formatter in afs:
            if hasattr(formatter, "to_dict"):
                serialized.append(formatter.to_dict())
            else:
                serialized.append({})
        self.store.meta["attachment_formatters"] = serialized

    @classmethod
    def _from_store(cls, store: Store) -> "Macro":
        """Create a Macro instance from a Store (used by GitMixin for event replay).

        This method reconstructs a Macro from its store representation.
        Since the store only contains refs for Survey and Jobs, we need to
        resolve them to live components for full reconstruction.

        Note: This creates a Macro without live component references. For full
        reconstruction, use from_dict with embedded component data.
        """
        instance = object.__new__(cls)

        # Set the store
        instance.store = store

        # Initialize GitMixin attributes
        instance._git = None
        instance._needs_git_init = False

        # Initialize component references as None (they need to be resolved)
        instance._initial_survey = None
        instance._jobs_object = None

        # Rebuild output formatters from store.meta
        instance._output_formatters = cls._rebuild_output_formatters(store.meta)

        # Rebuild attachment formatters from store.meta
        instance._attachment_formatters = cls._rebuild_attachment_formatters(
            store.meta.get("attachment_formatters", [])
        )

        # Restore scalar metadata
        instance._application_name = store.meta.get("application_name")
        instance._display_name = store.meta.get("display_name")
        instance._short_description = store.meta.get("short_description")
        instance._long_description = store.meta.get("long_description")
        instance._default_params = dict(store.meta.get("default_params", {}))
        instance._fixed_params = dict(store.meta.get("fixed_params", {}))
        instance.client_mode = store.meta.get("client_mode", False)
        instance.pseudo_run = store.meta.get("pseudo_run", False)

        # Other cached state
        instance._generated_results = {}
        instance._set_params = None
        instance._initialized = True

        return instance

    @classmethod
    def _rebuild_output_formatters(cls, meta: dict) -> "OutputFormatters":
        """Rebuild OutputFormatters from store.meta."""
        from .output_formatter import OutputFormatters, OutputFormatter

        formatter_map = {}
        formatters_dict = meta.get("output_formatters", {})
        for name, data in formatters_dict.items():
            if name and data:
                try:
                    formatter = OutputFormatter.from_dict(data)
                    formatter_map[name] = formatter
                except Exception:
                    # Skip formatters that can't be deserialized
                    pass

        ofs = OutputFormatters(formatter_map)
        default_name = meta.get("default_formatter_name")
        if default_name and default_name in formatter_map:
            ofs.set_default(default_name)

        return ofs

    @classmethod
    def _rebuild_attachment_formatters(cls, serialized: list) -> list:
        """Rebuild attachment formatters from serialized data."""
        from .output_formatter import ObjectFormatter

        formatters = []
        for data in serialized:
            if data:
                try:
                    formatter = ObjectFormatter.from_dict(data)
                    formatters.append(formatter)
                except Exception:
                    # Skip formatters that can't be deserialized
                    pass
        return formatters

    # =========================================================================
    # Related objects support (for git push/pull)
    # =========================================================================

    def _get_related_objects(self) -> list:
        """Return related objects that should be pushed/pulled with this Macro.

        Macro references its components (Survey, Jobs) by commit_hash.
        When pushing Macro, all components are pushed first so their refs can
        be resolved when the Macro is pulled.

        Returns:
            List of (name, object) tuples for Survey and Jobs.
        """
        return [
            ("initial-survey", self._initial_survey),
            ("jobs", self._jobs_object),
        ]

    def _store_related_aliases(self, aliases: dict) -> None:
        """Store component aliases in store.meta for later resolution during pull.

        Args:
            aliases: Dictionary mapping component names to their Coop aliases.
        """
        # Map component names to store.meta keys
        name_to_key = {
            "initial-survey": "initial_survey_alias",
            "jobs": "jobs_object_alias",
        }
        for name, alias in aliases.items():
            if name in name_to_key:
                self.store.meta[name_to_key[name]] = alias

    def _resolve_related_objects_after_pull(self) -> None:
        """Pull and resolve component objects after Macro has been pulled.

        Uses the component aliases stored in store.meta to clone each component
        from Coop and set the live component references.
        """
        from ..surveys import Survey
        from ..jobs import Jobs

        # Map alias keys to (component class, attribute name)
        alias_to_info = {
            "initial_survey_alias": (Survey, "_initial_survey"),
            "jobs_object_alias": (Jobs, "_jobs_object"),
        }

        for alias_key, (component_cls, attr_name) in alias_to_info.items():
            alias = self.store.meta.get(alias_key)
            if alias:
                print(f"Pulling {component_cls.__name__} from '{alias}'...")
                try:
                    obj = component_cls.git_clone(alias)
                    setattr(self, attr_name, obj)
                except Exception as e:
                    print(f"Warning: Could not pull {component_cls.__name__}: {e}")

    @disabled_in_client_mode
    def push(self, *args, force: bool = False, **kwargs) -> dict:
        """Push the macro to the server.

        Args:
            force: If True, patch the existing object instead of creating a new one.
                   Prints a message indicating the patching operation.
            *args: Positional arguments passed to the base push method.
            **kwargs: Keyword arguments passed to the base push method.

        Uses the Base class 'push' method or 'patch' method when force=True.
        """
        if "alias" not in kwargs:
            kwargs["alias"] = self.alias()
        if "description" not in kwargs:
            kwargs["description"] = self.short_description

        if force:
            # When force=True, patch the existing object instead of pushing a new one
            print(
                f"Force mode enabled: patching existing macro '{kwargs['alias']}' instead of creating new version"
            )

            try:
                from edsl.coop import Coop
                from edsl.config import CONFIG

                coop = Coop()

                # Get current username from profile
                profile = coop.get_profile()
                username = profile["username"]

                # Construct full URL format for patching (like pull method does)
                alias_url = (
                    f"{CONFIG.EXPECTED_PARROT_URL}/content/{username}/{kwargs['alias']}"
                )

                # Patch the existing object
                return self.patch(
                    url_or_uuid=alias_url,
                    description=kwargs.get("description"),
                    value=self,
                    visibility=kwargs.get("visibility"),
                )

            except Exception as e:
                print(f"Error during force patch: {e}")
                print("Falling back to regular push...")
                return super().push(*args, **kwargs)
        else:
            return super().push(*args, **kwargs)

    @disabled_in_client_mode
    def to_dict_for_client(self) -> dict:
        """Convert the macro to a dictionary suitable for client-side use."""
        d = self.to_dict()
        _ = d.pop("jobs_object")
        return d

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

        if self.pseudo_run:
            results = modified_jobs_object.pseudo_run()
        else:
            results = modified_jobs_object.run(
                stop_on_exception=stop_on_exception,
                disable_remote_inference=disable_remote_inference,
            )
        cache[jobs_hash] = results
        return results

    def by(self, params: Scenario | dict) -> Any:
        """
        Use this method to set the parameters for the macro.

        This is used to set the parameters for the macro when it is run.
        """
        self._set_params = dict(params)
        return self

    def __call__(self, **kwargs: Any) -> Any:
        """Call the macro with the given parameters.

        >>> macro = Macro.example()
        >>> macro(text="hello", disable_remote_inference=True)
        MacroRunOutput(...)
        """
        if "disable_remote_inference" in kwargs:
            disable_remote_inference = kwargs.pop("disable_remote_inference")
        else:
            disable_remote_inference = False
        return self.output(
            params=kwargs, disable_remote_inference=disable_remote_inference
        )

    def run(self, **kwargs: Any) -> "MacroRunOutput":
        """
        Run the macro and return formatted output or a JSON API payload.
        """
        if kwargs == {}:
            if self._set_params is not None:  # the macro might have parameters set
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
    ) -> Union[Results, dict]:
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

        ofs = self.output_formatters
        return MacroRunOutput(
            results=reconstructed_results,
            formatters=ofs,
            params=params or {},
            # default_formatter_name=ofs.default,
        )

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
    ) -> Union[MacroRunOutput, dict]:
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

        if params is None:  # collect params from the terminal
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
            self.jobs_object.duplicate()  # duplicate, as it modifies the jobs object
        )

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
        self,
        params: ParamsDict,
        *,
        survey_names: Optional[Set[str]] = None,
        default_params: Optional[ParamsDict] = None,
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

    def _add_summary_details(self, output, max_formatters: int):
        """Add Macro-specific details to summary repr."""
        # Jobs info
        job_cls = (
            getattr(self.jobs_object, "__class__").__name__
            if self.jobs_object
            else "None"
        )
        output.append("    job_type=", style="white")
        output.append(f"'{job_cls}'", style="blue")
        output.append(",\n", style="white")

        # Call parent to add formatters
        super()._add_summary_details(output, max_formatters)

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
            OutputFormatter(
                description="Ranked Scenario List", output_type="ScenarioList"
            )
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
                ScenarioAttachmentFormatter(
                    description="Pairwise choose_k", output_type="ScenarioList"
                ).choose_k(2)
            ],
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
