"""Utilities to derive dynamic trait mappings from embeddings.

CreateDynamicTraitsFunction builds two EmbeddingsEngine instances:
- One over survey questions (one document per question)
- One over an AgentList (documents are codebook values when present, otherwise trait keys)

It computes cosine similarities between question texts and trait descriptions and
returns a question_name -> trait_key mapping, keeping at most max_traits_included
per question (default 1, i.e., the best match).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .embeddings_engine import EmbeddingsEngine


class CreateDynamicTraitsFunction:
    def __init__(
        self,
        agent_list: "Any",
        survey: "Any",
        embedding_function: Optional["Any"] = None,
    ) -> None:
        self.agent_list = agent_list
        self.survey = survey
        self.embedding_function = embedding_function
        self._engine_questions: Optional[EmbeddingsEngine] = None
        self._engine_traits: Optional[EmbeddingsEngine] = None

    def _ensure_engines(self) -> None:
        if self._engine_questions is None:
            self._engine_questions = EmbeddingsEngine.from_survey(
                self.survey, embedding_function=self.embedding_function
            )
        if self._engine_traits is None:
            self._engine_traits = EmbeddingsEngine.from_agent_list(
                self.agent_list, embedding_function=self.embedding_function
            )

    def compute_q_to_traits(self, max_traits_included: int = 1) -> Dict[str, List[str]]:
        """Compute mapping from question_name to top-N most similar trait keys.

        Args:
            max_traits_included: Number of top traits to include per question (default 1).

        Returns:
            Dict mapping question_name -> list of trait keys (highest cosine first).
        """
        self._ensure_engines()
        assert self._engine_questions is not None and self._engine_traits is not None

        # Precompute embeddings are already on the engines.
        q_docs = self._engine_questions.documents
        t_docs = self._engine_traits.documents

        # Build vectors
        q_vecs = [d.embedding for d in q_docs]
        t_vecs = [d.embedding for d in t_docs]
        q_ids = [d.id for d in q_docs]
        t_ids = [d.id for d in t_docs]

        # Compute cosine similarities
        mapping: Dict[str, List[Tuple[str, float]]] = {}
        for qi, qv in enumerate(q_vecs):
            if qv is None:
                continue
            sims: List[Tuple[str, float]] = []
            for tj, tv in enumerate(t_vecs):
                if tv is None:
                    continue
                sim = EmbeddingsEngine._cosine_similarity(qv, tv)
                sims.append((t_ids[tj], float(sim)))
            sims.sort(key=lambda x: x[1], reverse=True)
            mapping[q_ids[qi]] = sims[: max(1, int(max_traits_included))]

        # Convert to question_name -> trait_key list
        q_to_traits: Dict[str, List[str]] = {}
        for q_id, ranked in mapping.items():
            # q_id is like 'q:question_name' or 'q:index'
            q_name = q_id.split(":", 1)[1] if ":" in q_id else q_id
            q_to_traits[q_name] = [trait_id for trait_id, _ in ranked]
        return q_to_traits

    def apply_to_agent_list(
        self, max_traits_included: int = 1, *, flatten: bool = True
    ) -> Dict[str, Any]:
        """Compute mapping suitable for AgentList.set_dynamic_traits_from_question_map.

        By default returns a flattened mapping Dict[str, str] (one trait per question).
        If ``flatten=False``, returns Dict[str, List[str]] with up to ``max_traits_included`` traits.
        """
        mapping = self.compute_q_to_traits(max_traits_included=max_traits_included)
        if not flatten:
            return mapping
        # AgentList API expects a single trait per question
        return {q: traits[0] for q, traits in mapping.items() if traits}
