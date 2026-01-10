"""
Versioning-specific exception classes.

This module defines custom exceptions for the versioning module, extending
the BaseException class to provide consistent error handling for git-like
version control operations.
"""

from ..base import BaseException


class VersioningError(BaseException):
    """
    Base exception class for all versioning-related errors.

    This exception is the parent class for all exceptions related to
    git-like versioning operations including commits, branches, push/pull,
    and remote operations.
    """

    doc_page = "versioning"


class NonFastForwardPushError(VersioningError):
    """
    Exception raised when a push is rejected due to non-fast-forward.

    This occurs when the remote branch has commits that are not ancestors
    of the local branch. The local branch needs to be updated (pull) first,
    or force push must be used.

    To fix this error:
    1. Pull the latest changes from the remote first
    2. Resolve any conflicts if necessary
    3. Push again, or use force=True if you want to overwrite
    """

    def __init__(self, ref_name: str, remote_commit: str, local_commit: str, **kwargs):
        self.ref_name = ref_name
        self.remote_commit = remote_commit
        self.local_commit = local_commit
        message = (
            f"Non-fast-forward push rejected. Remote '{ref_name}' is at "
            f"{remote_commit[:10]}, local is at {local_commit[:10]}. Use force=True."
        )
        super().__init__(message, **kwargs)


class StagedChangesError(VersioningError):
    """
    Exception raised when an operation cannot proceed due to staged changes.

    This occurs when trying to perform operations like checkout, branch,
    push, or pull while there are uncommitted staged changes.

    To fix this error:
    1. Commit your staged changes with git_commit()
    2. Or discard them with git_discard()
    3. Or use force=True if the operation supports it
    """

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        message = f"Cannot {operation} with staged changes; commit or discard first"
        super().__init__(message, **kwargs)


class RefNotFoundError(VersioningError):
    """
    Exception raised when a branch or tag reference is not found.

    This occurs when trying to checkout, delete, or access a ref
    (branch or tag) that doesn't exist.

    To fix this error:
    1. Check available branches with git_status()
    2. Create the branch if needed with git_branch()
    3. Verify the ref name is spelled correctly
    """

    def __init__(self, ref_name: str, **kwargs):
        self.ref_name = ref_name
        message = f"Ref '{ref_name}' does not exist"
        super().__init__(message, **kwargs)


class CommitNotFoundError(VersioningError):
    """
    Exception raised when a commit is not found.

    This occurs when trying to access a commit by ID that doesn't
    exist in the repository.

    To fix this error:
    1. Verify the commit ID is correct
    2. Check if the commit exists in the repository
    3. If using a prefix, ensure it's unambiguous
    """

    def __init__(self, commit_id: str, **kwargs):
        self.commit_id = commit_id
        message = f"Commit {commit_id} not found"
        super().__init__(message, **kwargs)


class RemoteNotFoundError(VersioningError):
    """
    Exception raised when a remote repository is not found.

    This occurs when trying to push, pull, or fetch from a remote
    that hasn't been added yet.

    To fix this error:
    1. Add the remote first with git_add_remote()
    2. Verify the remote name is spelled correctly
    3. Check available remotes
    """

    def __init__(self, remote_name: str, **kwargs):
        self.remote_name = remote_name
        message = f"Remote '{remote_name}' not found"
        super().__init__(message, **kwargs)


class RemoteAlreadyExistsError(VersioningError):
    """
    Exception raised when trying to add a remote that already exists.

    To fix this error:
    1. Use a different remote name
    2. Remove the existing remote first with git_remove_remote()
    """

    def __init__(self, remote_name: str, **kwargs):
        self.remote_name = remote_name
        message = f"Remote '{remote_name}' already exists"
        super().__init__(message, **kwargs)


class DetachedHeadError(VersioningError):
    """
    Exception raised when an operation is not allowed in detached HEAD state.

    Detached HEAD means you're not on any branch. Some operations like
    push and pull require being on a branch, or explicitly specifying
    a ref name.

    To fix this error:
    1. Checkout a branch with git_checkout()
    2. Or specify ref_name explicitly in the operation
    """

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        message = (
            f"Cannot {operation} in detached HEAD state without specifying ref_name"
        )
        super().__init__(message, **kwargs)


class NothingToCommitError(VersioningError):
    """
    Exception raised when trying to commit with no staged changes.

    This occurs when git_commit() is called but there are no pending
    events/changes to commit.

    To fix this error:
    1. Make some changes first
    2. Verify changes were staged properly
    """

    def __init__(self, **kwargs):
        message = "Nothing to commit (clean)"
        super().__init__(message, **kwargs)


class BranchDeleteError(VersioningError):
    """
    Exception raised when a branch cannot be deleted.

    This occurs when trying to delete the current branch or a ref
    that is not a branch.

    To fix this error:
    1. Switch to a different branch before deleting
    2. Verify the ref is actually a branch, not a tag
    """

    def __init__(self, branch_name: str, reason: str, **kwargs):
        self.branch_name = branch_name
        self.reason = reason
        message = f"Cannot delete branch '{branch_name}': {reason}"
        super().__init__(message, **kwargs)


class AmbiguousRevisionError(VersioningError):
    """
    Exception raised when a revision prefix matches multiple commits.

    This occurs when using a short commit prefix that isn't unique.

    To fix this error:
    1. Use a longer prefix to uniquely identify the commit
    2. Use the full commit ID
    """

    def __init__(self, prefix: str, **kwargs):
        self.prefix = prefix
        message = f"Ambiguous commit prefix: {prefix}"
        super().__init__(message, **kwargs)


class UnknownRevisionError(VersioningError):
    """
    Exception raised when a revision cannot be resolved.

    This occurs when a branch name, tag, or commit prefix doesn't
    match anything in the repository.

    To fix this error:
    1. Check spelling of the revision
    2. Verify the branch/tag/commit exists
    """

    def __init__(self, rev: str, **kwargs):
        self.rev = rev
        message = f"Unknown revision: {rev}"
        super().__init__(message, **kwargs)


class RemoteRefNotFoundError(VersioningError):
    """
    Exception raised when a ref doesn't exist on the remote.

    This occurs when trying to pull a branch that doesn't exist
    on the remote repository.

    To fix this error:
    1. Push the branch to the remote first
    2. Verify the ref name is correct
    3. Check what refs exist on the remote
    """

    def __init__(self, remote_name: str, ref_name: str, **kwargs):
        self.remote_name = remote_name
        self.ref_name = ref_name
        message = f"Remote '{remote_name}' does not have ref '{ref_name}'"
        super().__init__(message, **kwargs)


class PullConflictError(VersioningError):
    """
    Exception raised when a pull results in a conflict.

    This occurs when the local and remote branches have diverged
    and cannot be fast-forwarded.

    To fix this error:
    1. Commit or discard local changes
    2. Consider using force to overwrite local changes
    3. Manual merge may be required
    """

    def __init__(self, ref_name: str, local_commit: str, remote_commit: str, **kwargs):
        self.ref_name = ref_name
        self.local_commit = local_commit
        self.remote_commit = remote_commit
        message = (
            f"Pull conflict on '{ref_name}': local is at {local_commit[:10]}, "
            f"remote is at {remote_commit[:10]}. Cannot fast-forward."
        )
        super().__init__(message, **kwargs)


class StateNotFoundError(VersioningError):
    """
    Exception raised when a state blob is not found.

    This occurs when trying to access state data that doesn't exist
    in the repository storage.

    To fix this error:
    1. Verify the state_id is correct
    2. Check if the repository is corrupted
    """

    def __init__(self, state_id: str, **kwargs):
        self.state_id = state_id
        message = f"State {state_id} not found"
        super().__init__(message, **kwargs)


class CommitBehindError(VersioningError):
    """
    Exception raised when trying to commit but the base is behind the branch.

    This occurs when the branch has advanced since you started making changes.
    Someone else may have pushed, or you may have committed from another instance.

    To fix this error:
    1. Pull the latest changes first
    2. Reapply your changes
    3. Or use force=True to overwrite (may lose data)
    """

    def __init__(self, branch: str, base_commit: str, current_commit: str, **kwargs):
        self.branch = branch
        self.base_commit = base_commit
        self.current_commit = current_commit
        message = (
            f"Cannot commit: your base commit ({base_commit[:10]}) is behind "
            f"'{branch}' ({current_commit[:10]}). Use force=True to overwrite."
        )
        super().__init__(message, **kwargs)


class InvalidHeadStateError(VersioningError):
    """
    Exception raised when the HEAD state is invalid.

    This occurs when there's no base_commit or head_ref, indicating
    a corrupted or uninitialized repository state.
    """

    def __init__(self, **kwargs):
        message = "Invalid HEAD state: no base_commit or head_ref"
        super().__init__(message, **kwargs)


class InvalidAliasError(VersioningError):
    """
    Exception raised when an alias format is invalid.

    Aliases must be URL-safe:
    - Lowercase alphanumeric characters and dashes only
    - No spaces (use dashes instead)
    - No underscores (use dashes instead)
    - No leading or trailing dashes
    - Format: "name" or "owner/name"

    To fix this error:
    1. Use lowercase letters, numbers, and dashes only
    2. Replace spaces and underscores with dashes
    3. Remove leading/trailing dashes
    """

    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class MissingAliasError(VersioningError):
    """
    Exception raised when alias is required but not provided.

    This occurs when trying to push to a new repository without
    specifying an alias, and no alias is stored in the object's
    _info metadata.

    To fix this error:
    1. Pass alias as a kwarg to git_push(): git_push(alias="my-name")
    2. Or set it first with git_set_info(alias="my-name")
    """

    def __init__(self, message: str = None, **kwargs):
        if message is None:
            message = "alias required: pass as kwarg or call git_set_info() first"
        super().__init__(message, **kwargs)
