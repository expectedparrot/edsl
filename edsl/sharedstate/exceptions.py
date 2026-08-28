class SharedStateError(Exception):
    """Base class for shared-state authoring and runtime errors."""


class SharedStateAuthoringError(SharedStateError):
    pass


class SharedStateResolutionError(SharedStateError):
    pass


class SharedStateRuntimeError(SharedStateError):
    pass
