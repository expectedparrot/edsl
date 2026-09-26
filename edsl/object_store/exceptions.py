from edsl.base.base_exception import BaseException


class AmbiguousUUIDError(BaseException):
    """Raised when a UUID prefix matches multiple objects."""

    doc_page = "agents"
    doc_anchor = "agent-list-versioning"

    def __init__(self, prefix: str, matches: list[str]):
        self.prefix = prefix
        self.matches = matches
        candidates = ", ".join(matches[:5])
        if len(matches) > 5:
            candidates += f", ... ({len(matches)} total)"
        super().__init__(
            f"UUID prefix '{prefix}' is ambiguous -- matches "
            f"{len(matches)} objects: {candidates}"
        )


class StaleBranchError(BaseException):
    """Raised when saving to a branch whose tip has moved since the object was loaded."""

    doc_page = "agents"
    doc_anchor = "agent-list-versioning"

    def __init__(self, branch, expected, actual):
        self.branch = branch
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Branch '{branch}' has moved: expected parent {expected[:10]}..., "
            f"actual tip {actual[:10]}....\n"
            f"\n"
            f"To fix, either pull the latest version and re-apply your changes:\n"
            f"\n"
            f"    obj, _meta = ObjectStore(root).load(uuid)\n"
            f"    # re-apply your changes to obj\n"
            f"    ObjectStore(root).save(obj, message=\"...\")\n"
            f"\n"
            f"Or save to a new branch to preserve both versions:\n"
            f"\n"
            f"    ObjectStore(root).save(obj, message=\"...\", branch=\"my_branch\")"
        )
