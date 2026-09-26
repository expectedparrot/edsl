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
