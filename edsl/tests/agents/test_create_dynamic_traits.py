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
            "fear_bees": "Why not?",
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

    # Instead of asserting exact keys, assert that the matched trait's description
    # equals the question text (which is what the embedding is based on here).
    trait_to_desc = al.codebook
    qname_to_text = {q.question_name: q.question_text for q in svy.questions}

    for qname, traits in q_to_traits.items():
        top_trait = traits[0]
        assert trait_to_desc[top_trait] == qname_to_text[qname]


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

    # apply_to_agent_list returns a flat mapping Dict[str, str] by default
    mapping = builder.apply_to_agent_list(max_traits_included=1, flatten=False)
    # Ensure mapping is list-valued for API that accepts multiple traits
    _ = al.set_dynamic_traits_from_question_map(mapping)

    # Use real question objects for the dynamic function calls
    out0 = al[0].dynamic_traits_function(svy.questions[0])
    out1 = al[0].dynamic_traits_function(svy.questions[1])
    # Each mapping should produce exactly one trait for max_traits_included=1
    # Exactly one trait should be surfaced for each question per max_traits_included=1
    assert len(out0) == 1
    assert len(out1) == 1


