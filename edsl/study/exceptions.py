from edsl.base.base_exception import BaseException


class StudyError(BaseException):
    """Base exception for all Study-related errors."""

    pass


class StudyGitError(StudyError):
    """Git operation failed (untracked files, uncommitted changes, push/pull failures)."""

    pass


class StudyServerError(StudyError):
    """Meta-server communication error."""

    pass


class StudyAuthError(StudyError):
    """Signature or key issue."""

    pass


class StudyNotRegisteredError(StudyError):
    """Operation attempted before registering the study with the server."""

    pass
