"""Shared sandboxed rendering for templates supplied in EDSL objects."""

from jinja2 import Environment
from jinja2.nativetypes import NativeCodeGenerator, NativeEnvironment, NativeTemplate
from jinja2.runtime import Macro
from jinja2.sandbox import SandboxedEnvironment, safe_range
from jinja2.utils import Namespace
from types import BuiltinMethodType, MethodType


_MISSING_TRAIT = object()


_READ_ONLY_METHODS = {
    dict: frozenset({"get", "items", "keys", "values", "copy"}),
    list: frozenset({"count", "index", "copy"}),
    tuple: frozenset({"count", "index"}),
    str: frozenset(
        {
            "capitalize",
            "casefold",
            "count",
            "endswith",
            "find",
            "index",
            "isalnum",
            "isalpha",
            "isascii",
            "isdecimal",
            "isdigit",
            "isidentifier",
            "islower",
            "isnumeric",
            "isprintable",
            "isspace",
            "istitle",
            "isupper",
            "join",
            "lower",
            "lstrip",
            "partition",
            "removeprefix",
            "removesuffix",
            "replace",
            "rfind",
            "rindex",
            "rpartition",
            "rsplit",
            "rstrip",
            "split",
            "splitlines",
            "startswith",
            "strip",
            "swapcase",
            "title",
            "upper",
        }
    ),
}


def _allowed_callable(obj, allowed_methods=()) -> bool:
    # Compare identities, not names or user-controlled attributes. In particular,
    # a live object's method named "get" is not equivalent to dict.get.
    if any(obj is helper for helper in (safe_range, dict, Namespace)):
        return True
    if type(obj) is Macro:
        return True
    if type(obj) is BuiltinMethodType:
        return obj.__name__ in _READ_ONLY_METHODS.get(type(obj.__self__), ())
    if type(obj) is MethodType:
        return any(
            type(obj.__self__) is owner
            and any(obj.__func__ is getattr(owner, name) for name in names)
            for owner, names in allowed_methods
        )
    return False


class EDSLSandboxedEnvironment(SandboxedEnvironment):
    """Deny calls except reviewed template helpers and read-only builtin methods.

    Filters, tests, and explicitly allowed methods are trusted application code.
    This policy does not make arbitrary Python objects safe to expose: properties
    and implicit operations can also execute code.
    """

    def __init__(self, *args, allowed_methods=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_methods = tuple(allowed_methods)

    def _get_agent_trait(self, obj, attribute):
        # Import lazily: Agent itself uses the shared template environment.
        from ..agents import Agent

        if isinstance(obj, Agent) and isinstance(attribute, str):
            traits = obj.traits
            if attribute in traits:
                value = traits[attribute]
                if self.is_safe_attribute(obj, attribute, value):
                    return value
                return self.unsafe_undefined(obj, attribute)
        return _MISSING_TRAIT

    def getattr(self, obj, attribute):
        """Prefer agent traits over colliding Python attributes in templates."""
        value = self._get_agent_trait(obj, attribute)
        if value is not _MISSING_TRAIT:
            return value
        return super().getattr(obj, attribute)

    def getitem(self, obj, argument):
        """Give bracket notation the same agent-trait precedence as dot notation."""
        value = self._get_agent_trait(obj, argument)
        if value is not _MISSING_TRAIT:
            return value
        return super().getitem(obj, argument)

    def is_safe_callable(self, obj):
        return _allowed_callable(
            obj, self.allowed_methods
        ) and super().is_safe_callable(obj)


class SandboxedNativeEnvironment(EDSLSandboxedEnvironment, NativeEnvironment):
    """Preserve native values while enforcing Jinja's sandbox checks."""


def make_environment(**kwargs) -> SandboxedEnvironment:
    return EDSLSandboxedEnvironment(**kwargs)


def require_sandbox(environment: Environment) -> SandboxedEnvironment:
    if not isinstance(environment, SandboxedEnvironment) or not environment.sandboxed:
        raise ValueError("EDSL template rendering requires a SandboxedEnvironment")
    # An ordinary or custom sandbox override must not restore Jinja's permissive
    # callable default. Intersect policies on an overlay, without mutating the
    # caller's environment or discarding its stricter attribute/call checks.
    restricted = environment.overlay()
    original_policy = environment.is_safe_callable
    allowed_methods = getattr(environment, "allowed_methods", ())
    restricted.is_safe_callable = lambda obj: (
        _allowed_callable(obj, allowed_methods) and original_policy(obj)
    )
    return restricted


def make_native_environment(environment=None) -> SandboxedEnvironment:
    if environment is None:
        return SandboxedNativeEnvironment()
    # Retain a caller's filters, undefined behavior, and custom security policy.
    # Constructing a fresh default native environment would discard that policy.
    native = require_sandbox(environment).overlay()
    native.code_generator_class = NativeCodeGenerator
    native.template_class = NativeTemplate
    native.concat = NativeEnvironment.concat
    return native


def safe_template(source: str, **kwargs):
    """Compile a string using a sandbox, including StrictUndefined overrides."""
    return make_environment(**kwargs).from_string(source)
