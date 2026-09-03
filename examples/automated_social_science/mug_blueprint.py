"""A complete serializable blueprint for the mug negotiation study."""

from edsl.causal import (
    BlueprintCompiler,
    CausalStudyBlueprint,
    DesignPolicy,
    ExecutionChannel,
    InformationPolicy,
    ResearchQuestion,
    StudyRole,
)

from .mug_causal_spec import build_mug_conversation, build_mug_study


def build_mug_blueprint() -> CausalStudyBlueprint:
    """Author the scientific and operational study definition in one object."""
    _, plan, _ = build_mug_study()
    return CausalStudyBlueprint(
        "mug-negotiation-blueprint-v1",
        ResearchQuestion(
            "How do a buyer's budget and a seller's attachment affect agreement?",
            "Simulated buyer-seller dyads",
            "A bilateral negotiation over a mug",
            [
                "Higher buyer budgets increase agreement.",
                "Greater seller attachment decreases agreement.",
            ],
        ),
        plan,
        [
            StudyRole(
                "buyer",
                "buy the mug at the lowest acceptable price",
                ["never pay more than the private maximum budget"],
                ExecutionChannel("llm", {"model_policy": "study-default"}),
            ),
            StudyRole(
                "seller",
                "sell the mug at the highest acceptable price",
                ["only accept a deal preferred to keeping the mug"],
                ExecutionChannel("llm", {"model_policy": "study-default"}),
            ),
        ],
        [
            InformationPolicy("buyer_budget", "private", ["buyer"]),
            InformationPolicy("seller_attachment", "private", ["seller"]),
        ],
        DesignPolicy(replications=20, seed="mug-negotiation-v1"),
        build_mug_conversation(),
        metadata={"example": True},
    )


if __name__ == "__main__":
    compiled = BlueprintCompiler().compile(build_mug_blueprint())
    print(compiled.to_dict())
