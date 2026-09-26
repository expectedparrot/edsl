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
