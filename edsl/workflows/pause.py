"""Serializable observation pauses evaluated at completed step boundaries."""

from dataclasses import dataclass, replace

from edsl._data_contracts import validate_data
from edsl.sharedstate import StateRead
from edsl.sharedstate.dsl import Expr, decode, encode, walk
from edsl.sharedstate.model import step_from_dict, step_to_dict


@dataclass(frozen=True)
class PauseRule:
    """Pause once after ``after`` if a predicate on a state snapshot is true.

    A pause preserves remaining work and live economic state. Explicit resume
    acknowledges the boundary; the same rule is never applied twice. Scope
    must be literal because this condition belongs to the coordinator, not a
    particular participant. ``condition`` uses the shared-state expression DSL.
    """

    name: str
    after: str
    read: StateRead
    condition: Expr | bool = True
    resume_when: Expr | bool = True

    def __post_init__(self):
        if not self.name or not self.after:
            raise ValueError("pause requires a name and a completed boundary step")
        if not isinstance(self.read, StateRead):
            raise TypeError("pause requires a state read")
        validate_data(self.read.scope, path="pause scope")
        if not isinstance(self.condition, (Expr, bool)) or not isinstance(
            self.resume_when, (Expr, bool)
        ):
            raise TypeError("pause condition must be a state expression or boolean")
        machine = self.read.definition.machines[self.read.target]
        replace(machine, complete_when=self.condition).validate()
        replace(machine, complete_when=self.resume_when).validate()
        for predicate in (self.condition, self.resume_when):
            for node in walk(predicate):
                if not isinstance(node, Expr) or node.op != "ref":
                    continue
                namespace, name = node.kwargs["namespace"], node.kwargs["name"]
                allowed = {"state": machine.fields, "constant": machine.constants}
                if namespace == "local":
                    continue
                if (
                    namespace not in allowed
                    or name.split(".")[0] not in allowed[namespace]
                ):
                    raise ValueError(f"invalid pause reference: {namespace}.{name}")

    def to_dict(self):
        return {
            "name": self.name,
            "after": self.after,
            "read": step_to_dict(self.read),
            "condition": encode(self.condition),
            "resume_when": encode(self.resume_when),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["after"],
            step_from_dict(data["read"]),
            decode(data["condition"]),
            decode(data.get("resume_when", True)),
        )
