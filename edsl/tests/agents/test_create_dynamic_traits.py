from __future__ import annotations

from edsl.embeddings.create_dynamic_traits import CreateDynamicTraitsFunction
from edsl.embeddings.embedding_function import MockEmbeddingFunction
from edsl.agents import Agent, AgentList
from edsl import QuestionFreeText, Survey


def test_create_dynamic_traits_basic_mapping():
    # AgentList with codebook so trait docs are human text
    al = AgentList(
        [Agent(traits={"like_school": True, "fear_bees": False})],
        codebook={
            "like_school": "Do you like school?",
            "fear_bees": "Does this person fear bees?",
        },
    )

    # Minimal survey with two questions, names distinct from trait keys
    svy = Survey([
        QuestionFreeText(question_name="q0", question_text="Do you like school?"),
        QuestionFreeText(question_name="q1", question_text="Why not?"),
    ])

    # Deterministic normalized embeddings so identical text -> cosine 1.0
    ef = MockEmbeddingFunction(embedding_dim=8, normalize=True)
    builder = CreateDynamicTraitsFunction(agent_list=al, survey=svy, embedding_function=ef)

    q_to_traits = builder.compute_q_to_traits(max_traits_included=1)

    # We don't assert specific trait identity (embeddings are arbitrary).
    # Just check we pick exactly one existing trait per question.
    valid_traits = set(al.traits_keys if hasattr(al, "traits_keys") else [*al[0].traits.keys()])
    for _, traits in q_to_traits.items():
        assert len(traits) == 1
        assert traits[0] in valid_traits


def test_apply_to_agent_list_sets_dynamic_function():
    al = AgentList(
        [Agent(traits={"like_school": True, "fear_bees": False})],
        codebook={
            "like_school": "Do you like school?",
            "fear_bees": "Why not?",
        },
    )
    svy = Survey([
        QuestionFreeText(question_name="q0", question_text="Do you like school?"),
        QuestionFreeText(question_name="q1", question_text="Why not?"),
    ])
    ef = MockEmbeddingFunction(embedding_dim=6, normalize=True)
    builder = CreateDynamicTraitsFunction(agent_list=al, survey=svy, embedding_function=ef)

    # apply_to_agent_list returns a mapping; use list-valued for API that accepts multiple traits
    mapping = builder.apply_to_agent_list(max_traits_included=1, flatten=False)
    _ = al.set_dynamic_traits_from_question_map(mapping)

    # Extract prompts and ensure system prompts include exactly one trait reference per question
    prompts_ds = svy.by(al).prompts()
    scenarios = prompts_ds.to_scenario_list()

    # Look at system_prompt field for each prompt (Prompt objects -> .text)
    system_prompts = [sc['system_prompt'].text for sc in scenarios]

    # Each system prompt should include exactly one non-empty trait line following the header
    def count_trait_lines(text: str) -> int:
        if "Your traits:" not in text:
            return 0
        tail = text.split("Your traits:", 1)[1]
        lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
        return len(lines)

    counts = [count_trait_lines(p) for p in system_prompts]
    assert all(c == 1 for c in counts)


