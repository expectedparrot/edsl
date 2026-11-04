class SharedStateError(Exception):
    """Base class for shared-state authoring and runtime errors."""


class SharedStateAuthoringError(SharedStateError):
    pass


class SharedStateResolutionError(SharedStateError):
    pass


class SharedStateRuntimeError(SharedStateError):
    pass


class MachineValidationError(SharedStateAuthoringError, ValueError):
    """An authoring error with a stable location in a Machine definition."""

    def __init__(self, machine: str, path: str, reason: str):
        self.machine = machine
        self.path = path
        self.reason = reason
        super().__init__(f"{machine} at {path}: {reason}")


class UnsupportedCapabilityError(SharedStateRuntimeError, ValueError):
    """A destination cannot execute one or more versioned requirements."""

    def __init__(self, machine, missing):
        self.machine = machine
        self.missing = tuple(sorted(missing))
        self.paths = {name: tuple(missing[name]) for name in self.missing}
        details = "; ".join(f"{name} at {self.paths[name][0]}" for name in self.missing)
        super().__init__(
            f"{machine}: unsupported or unregistered capabilities: {details}"
        )

    def to_dict(self):
        return {
            "machine": self.machine,
            "missing": list(self.missing),
            "paths": {name: list(paths) for name, paths in self.paths.items()},
        }


def validate_reason_code(code):
    """Rejection metadata is a bounded public identifier, never an expression."""
    import re

    if (
        not isinstance(code, str)
        or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", code) is None
    ):
        raise ValueError(
            "rejection code must be a literal identifier of 1 to 64 ASCII characters"
        )


class CommandRejected(SharedStateRuntimeError, ValueError):
    """An intentional domain rejection, distinct from an execution failure.

    Command execution returns a rejected result. The legacy dict-returning
    Runtime.close convenience API raises this exception instead.
    """

    def __init__(self, reason_code):
        validate_reason_code(reason_code)
        self.reason_code = reason_code
        super().__init__(f"command rejected: {reason_code}")
