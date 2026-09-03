"""First causal-layer slice of the automated mug-negotiation study."""

from edsl import QuestionYesNo, Survey
from edsl.causal import (
    CausalAnalysisPlan,
    EndogenousVariable,
    Equation,
    EstimatorSpec,
    ExperimentDesign,
    ExogenousVariable,
    Measurement,
    ParticipantScope,
    PathEffect,
    StructuralCausalModel,
    AgentRole,
    ExperimentCompiler,
)
from edsl.conversations import AnyStop, Conversation, MaxUtterances, OrderedTurns, SemanticStop


def build_mug_study():
    """Return the authored SCM, frozen analysis plan, and factorial design."""
    deal = EndogenousVariable(
        "deal_occurred",
        "binary",
        "indicator",
        "1 if buyer and seller agree to a sale; 0 otherwise",
        Measurement(
            "buyer",
            Survey([QuestionYesNo(question_name="deal_occurred", question_text="Did you and the seller agree to a sale?")]),
            "deal_occurred",
        ),
        levels=[0, 1],
    )
    budget = ExogenousVariable(
        "buyer_budget",
        "continuous",
        "USD",
        "maximum amount the buyer may pay",
        ParticipantScope("buyer"),
        [5, 10, 20, 40],
        "Your maximum budget is {{ value }} USD.",
    )
    attachment = ExogenousVariable(
        "seller_attachment",
        "ordinal",
        "attachment_level",
        "seller's sentimental attachment to the mug",
        ParticipantScope("seller"),
        ["none", "low", "high", "extreme"],
        "Your sentimental attachment is {{ value }}.",
        levels=["none", "low", "high", "extreme"],
    )
    scm = StructuralCausalModel(
        [budget, attachment, deal],
        [Equation(deal, [budget, attachment], family="linear_probability")],
        name="mug-negotiation-v1",
        metadata={"scenario": "A buyer and seller negotiate over a mug."},
    )
    plan = CausalAnalysisPlan(
        scm,
        [PathEffect(budget, deal), PathEffect(attachment, deal)],
        EstimatorSpec(covariance="HC3"),
    )
    design = ExperimentDesign.factorial(
        scm.exogenous_variables,
        replications=20,
        seed="mug-negotiation-v1",
    )
    return scm, plan, design


def build_mug_conversation() -> Conversation:
    return Conversation(
        "mug-negotiation",
        ["buyer", "seller"],
        "A buyer and seller negotiate the sale of a mug.",
        OrderedTurns(["buyer", "seller"]),
        AnyStop(
            SemanticStop(judge="conversation-coordinator", question="Has the negotiation reached a deal, a clear impasse, or another natural endpoint?"),
            MaxUtterances(20),
        ),
        include_remaining_turns=True,
    )


def build_compiled_mug_experiment():
    scm, plan, design = build_mug_study()
    roles = [
        AgentRole("buyer", "buy the mug at the lowest acceptable price", "never pay more than your private maximum budget"),
        AgentRole("seller", "sell the mug at the highest acceptable price", "only accept a deal you prefer to keeping the mug"),
    ]
    return ExperimentCompiler().compile(plan=plan, design=design, roles=roles), build_mug_conversation()


def build_original_mug_study():
    """Reconstruct the 405-cell mug design reported in Manning et al. (2024)."""
    deal = EndogenousVariable(
        "deal_occurred",
        "binary",
        "indicator",
        "1 if buyer and seller explicitly agree on a price; 0 otherwise",
        Measurement(
            "coordinator",
            Survey(
                [
                    QuestionYesNo(
                        question_name="deal_occurred",
                        question_text=(
                            "Did the buyer and seller explicitly agree on the price "
                            "of the mug during their interaction?"
                        ),
                    )
                ]
            ),
            "deal_occurred",
        ),
        levels=[0, 1],
    )
    budget = ExogenousVariable(
        "buyer_budget",
        "continuous",
        "USD",
        "the buyer's maximum budget for the mug",
        ParticipantScope("buyer"),
        [3, 6, 7, 8, 10, 13, 18, 20, 25],
        "Your budget for the mug is {{ value }} USD.",
    )
    minimum_price = ExogenousVariable(
        "seller_minimum_price",
        "continuous",
        "USD",
        "the seller's minimum acceptable price for the mug",
        ParticipantScope("seller"),
        [3, 5, 7, 8, 10, 13, 18, 20, 25],
        "Your minimum acceptable price for the mug is {{ value }} USD.",
    )
    attachment_levels = [
        "no emotional attachment",
        "slight emotional attachment",
        "moderate emotional attachment",
        "high emotional attachment",
        "extreme emotional attachment",
    ]
    attachment = ExogenousVariable(
        "seller_attachment",
        "ordinal",
        "attachment_level",
        "the seller's feelings of love toward the mug",
        ParticipantScope("seller"),
        attachment_levels,
        "Your feelings of love for the mug are: {{ value }}.",
        levels=attachment_levels,
    )
    scm = StructuralCausalModel(
        [budget, minimum_price, attachment, deal],
        [Equation(deal, [budget, minimum_price, attachment], family="linear_probability")],
        name="mug-negotiation-original-design",
        metadata={
            "scenario": "Two people bargaining over a mug.",
            "source": "Manning, Zhu, and Horton (2024), Figure 2",
            "replication_kind": "design replication with a contemporary model",
        },
    )
    plan = CausalAnalysisPlan(
        scm,
        [
            PathEffect(budget, deal),
            PathEffect(minimum_price, deal),
            PathEffect(attachment, deal),
        ],
        EstimatorSpec(covariance="HC3"),
    )
    design = ExperimentDesign.factorial(
        scm.exogenous_variables,
        replications=1,
        seed="manning-zhu-horton-2024-mug",
    )
    return scm, plan, design


def build_compiled_original_mug_experiment():
    """Compile the paper's published mug factorial into executable roles."""
    _, plan, design = build_original_mug_study()
    roles = [
        AgentRole(
            "buyer",
            "buy the mug at the lowest acceptable price",
            "never agree to pay more than your private budget",
        ),
        AgentRole(
            "seller",
            "sell the mug at the highest acceptable price",
            "never agree to accept less than your private minimum acceptable price",
        ),
        AgentRole(
            "coordinator",
            "measure the completed interaction accurately",
            "report only outcomes explicitly supported by the transcript",
        ),
    ]
    return (
        ExperimentCompiler().compile(plan=plan, design=design, roles=roles),
        build_mug_conversation(),
        plan,
    )


if __name__ == "__main__":
    compiled, conversation = build_compiled_mug_experiment()
    print({"experiment": compiled.to_dict(), "conversation": conversation.to_dict()})
