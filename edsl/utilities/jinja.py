"""Shared sandboxed rendering for templates supplied in EDSL objects."""

from jinja2 import Environment
from jinja2.nativetypes import NativeCodeGenerator, NativeEnvironment, NativeTemplate
from jinja2.sandbox import SandboxedEnvironment


class SandboxedNativeEnvironment(SandboxedEnvironment, NativeEnvironment):
    """Preserve native values while enforcing Jinja's sandbox checks."""


def make_environment(**kwargs) -> SandboxedEnvironment:
    return SandboxedEnvironment(**kwargs)


def require_sandbox(environment: Environment) -> SandboxedEnvironment:
    if not isinstance(environment, SandboxedEnvironment) or not environment.sandboxed:
        raise ValueError("EDSL template rendering requires a SandboxedEnvironment")
    return environment


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
