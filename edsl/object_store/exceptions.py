from edsl.base.base_exception import BaseException


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
            f"    al = AgentList.store.load(al._cas_uuid, root=root)\n"
            f"    # re-apply your changes to al\n"
            f"    al.store.save(message=\"...\")\n"
            f"\n"
            f"Or save to a new branch to preserve both versions:\n"
            f"\n"
            f"    al.store.save(message=\"...\", branch=\"my_branch\")"
        )
