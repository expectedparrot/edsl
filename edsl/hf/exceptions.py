"""Errors in the EDSL Hugging Face interchange format."""


class HFSchemaError(ValueError):
    """Values cannot be represented by the requested column schema."""


class HFFormatVersionError(ValueError):
    """A dataset requires a newer EDSL format reader."""


class HFClassMismatchError(ValueError):
    """The stored list class differs from the requested class."""
