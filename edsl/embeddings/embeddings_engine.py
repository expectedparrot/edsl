"""Main embeddings engine for document storage and similarity search."""

from typing import List, Dict, Optional, Any, TYPE_CHECKING
import math
from dataclasses import dataclass
import html

from ..base.base_class import Base
from .embedding_function import EmbeddingFunction
 
if TYPE_CHECKING:
    from ..surveys import Survey
    from ..agents import AgentList

@dataclass
class Document:
    """Represents a document with its content and metadata."""
    
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass 
class SearchResult:
    """Represents a search result with document and similarity score."""
    
    document: Document
    similarity_score: float


class EmbeddingsEngine(Base):
    """Main engine for document embedding, storage, and similarity search.
    
    This class provides functionality to:
    - Load documents and generate their embeddings using an injected embedding function
    - Store documents with their embeddings and metadata
    - Perform similarity search against stored documents

    Examples:
        Create an engine with the mock embedding function, add documents, and search.

        >>> from .embedding_function import MockEmbeddingFunction
        >>> engine = EmbeddingsEngine(embedding_function=MockEmbeddingFunction(embedding_dim=8))
        >>> engine.add_document(id="a", content="alpha")
        >>> engine.add_document(id="b", content="beta")
        >>> engine.search("alpha", top_k=1)[0].document.id
        'a'
        >>> engine.count()
        2

        Round-trip serialize and deserialize using ScenarioList-style dict and registry:

        >>> from .embedding_function import MockEmbeddingFunction
        >>> e1 = EmbeddingsEngine(MockEmbeddingFunction(embedding_dim=4))
        >>> _ = [e1.add_document(id=str(i), content=c) for i, c in enumerate(["x", "y"])]
        >>> d = e1.to_dict()
        >>> 'scenarios' in d and 'embedding_function' in d
        True
        >>> all('embedding' in s for s in d['scenarios'])
        True
        >>> e2 = EmbeddingsEngine.from_dict(d)
        >>> e2.count()
        2
        >>> [r.document.id for r in e2.search("x", top_k=1)][0]
        '0'
    """
    
    def __init__(self, embedding_function: EmbeddingFunction):
        """Initialize the embeddings engine.
        
        Args:
            embedding_function: The embedding function to use for generating embeddings
        """
        self.embedding_function = embedding_function
        self.documents: List[Document] = []

    @classmethod
    def from_survey(
        cls,
        survey: "Survey",
        embedding_function: Optional[EmbeddingFunction] = None,
        include_question_text: bool = True,
        include_options: bool = True,
    ) -> "EmbeddingsEngine":
        """Create an EmbeddingsEngine from an EDSL Survey.

        - Creates one document per question
        - When include_question_text is True, the question's text is included
        - When include_options is True, any options are appended to the same content string
        - Uses OpenAI embeddings by default; pass a different embedding_function to override

        Examples:
            >>> from edsl.surveys import Survey
            >>> from edsl.embeddings.embedding_function import MockEmbeddingFunction
            >>> eng = EmbeddingsEngine.from_survey(Survey.example(), embedding_function=MockEmbeddingFunction(embedding_dim=4))
            >>> eng.count() > 0
            True
        """
        if embedding_function is None:
            from .embedding_function import OpenAIEmbeddingFunction
            from ..key_management import KeyLookupBuilder

            # Use EDSL's key management system to get API credentials
            key_lookup = KeyLookupBuilder().build()
            embedding_function = OpenAIEmbeddingFunction(key_lookup=key_lookup)

        engine = cls(embedding_function=embedding_function)

        # Build documents from survey questions: one document per question.
        doc_dicts: List[Dict[str, Any]] = []
        questions = getattr(survey, "questions", []) or []
        for q_index, q in enumerate(questions):
            parts: List[str] = []
            # Include question text
            if include_question_text and hasattr(q, "question_text") and q.question_text:
                parts.append(str(q.question_text))
            # Append options (as plain text) to the same content string
            if include_options and hasattr(q, "question_options") and getattr(q, "question_options"):
                option_texts = [str(opt) for opt in getattr(q, "question_options")]
                if option_texts:
                    parts.append(" ".join(option_texts))

            content = " ".join(parts).strip()
            if not content:
                continue

            q_name = getattr(q, "question_name", None)
            doc_id = f"q:{q_name or q_index}"
            doc_dicts.append(
                {
                    "id": doc_id,
                    "content": content,
                    "metadata": {"type": "question", "question_name": q_name},
                }
            )

        if doc_dicts:
            engine.add_documents(doc_dicts)
        return engine

    @classmethod
    def from_agent_list(
        cls,
        agent_list: "AgentList",
        embedding_function: Optional[EmbeddingFunction] = None,
    ) -> "EmbeddingsEngine":
        """Create an EmbeddingsEngine from an AgentList.

        - If agents have a codebook, use the codebook values as documents and the codebook keys as ids
        - Otherwise, use the trait keys as document ids and the literal key strings as documents

        The rationale: when a codebook is present it contains human-friendly descriptions
        of the trait keys; those are more suitable as document content.

        Examples:
            >>> from edsl.agents import Agent, AgentList
            >>> from .embedding_function import MockEmbeddingFunction
            >>> al = AgentList([Agent(traits={'age': 30}, codebook={'age': 'Age in years'})])
            >>> eng = EmbeddingsEngine.from_agent_list(al, embedding_function=MockEmbeddingFunction(embedding_dim=4))
            >>> eng.count() > 0
            True
        """
        if embedding_function is None:
            from .embedding_function import OpenAIEmbeddingFunction
            from ..key_management import KeyLookupBuilder

            # Use EDSL's key management system to get API credentials
            key_lookup = KeyLookupBuilder().build()
            embedding_function = OpenAIEmbeddingFunction(key_lookup=key_lookup)

        engine = cls(embedding_function=embedding_function)

        # Determine if codebook is present on agents (use first agent that has one)
        codebook: Optional[Dict[str, str]] = None
        for agent in getattr(agent_list, "data", []) or []:
            if hasattr(agent, "codebook") and isinstance(agent.codebook, dict) and agent.codebook:
                codebook = agent.codebook
                break

        doc_dicts: List[Dict[str, Any]] = []
        if codebook:
            # Use codebook values as documents; keys as ids
            for key, value in codebook.items():
                doc_dicts.append(
                    {
                        "id": key,
                        "content": str(value),
                        "metadata": {"source": "agent_codebook"},
                    }
                )
        else:
            # Fallback: use trait keys aggregated across agents; use the literal key as the document
            trait_keys: List[str] = getattr(agent_list, "trait_keys", [])
            for key in trait_keys:
                doc_dicts.append(
                    {
                        "id": key,
                        "content": key,
                        "metadata": {"source": "agent_trait_key"},
                    }
                )

        if doc_dicts:
            engine.add_documents(doc_dicts)
        return engine

    # --- Base abstract methods implementation ---
    @classmethod
    def example(cls) -> "EmbeddingsEngine":
        """Return a small example engine with one document.

        Uses the mock embedding function for deterministic behavior in docs/tests.
        """
        from .embedding_function import MockEmbeddingFunction

        engine = cls(embedding_function=MockEmbeddingFunction(embedding_dim=8))
        engine.add_document(id="example", content="hello world")
        return engine

    def to_dict(self, add_edsl_version: bool = False) -> Dict[str, Any]:
        """Serialize engine to a plain dict with a list of scenarios and function metadata.

        - Documents are serialized as a list of dictionaries under key 'scenarios'.
        - Each scenario dict contains: 'id', 'content', optional 'metadata', and 'embedding'.
        - The embedding function is serialized by its registered short name and params.
        """
        scenarios_payload = [
            {
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata,
                "embedding": doc.embedding,
                **({"edsl_version": __import__("edsl").__version__, "edsl_class_name": "Scenario"} if add_edsl_version else {}),
            }
            for doc in self.documents
        ]
        d: Dict[str, Any] = {
            "scenarios": scenarios_payload,
            "embedding_function": getattr(self.embedding_function, "short_name", self.embedding_function.__class__.__name__),
            "embedding_function_params": {
                **({"embedding_dim": getattr(self.embedding_function, "embedding_dim", 1536)} if hasattr(self.embedding_function, "embedding_dim") else {}),
                **({"normalize": getattr(self.embedding_function, "_normalize", False)} if hasattr(self.embedding_function, "_normalize") else {}),
            },
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EmbeddingsEngine":
        """Deserialize engine from dictionary with ScenarioList-like structure."""
        ef_name = d.get("embedding_function", "mock")
        ef_params = d.get("embedding_function_params", {})
        ef = EmbeddingFunction.create_by_name(ef_name, **ef_params)
        engine = cls(embedding_function=ef)
        scenarios = d.get("scenarios", [])
        for scen_dict in scenarios:
            # scen_dict may include edsl metadata; only pick our fields
            doc_id = scen_dict.get("id")
            content = scen_dict.get("content")
            metadata = scen_dict.get("metadata", {})
            embedding = scen_dict.get("embedding", None)
            if doc_id is None or content is None:
                continue
            # Do not compute embeddings during deserialization; set to None for lazy fill
            engine.documents.append(
                Document(
                    id=str(doc_id),
                    content=str(content),
                    metadata=metadata,
                    embedding=embedding,
                )
            )
        return engine

    def code(self) -> str:
        """Generate Python code that recreates this engine and its documents."""
        try:
            embedding_dim = getattr(self.embedding_function, "embedding_dim", 1536)
            normalize = getattr(self.embedding_function, "_normalize", False)
        except Exception:
            embedding_dim = 1536
            normalize = False

        lines = [
            "from edsl.embeddings.embeddings_engine import EmbeddingsEngine",
            "from edsl.embeddings.embedding_function import MockEmbeddingFunction",
            f"engine = EmbeddingsEngine(MockEmbeddingFunction(embedding_dim={embedding_dim}, normalize={normalize}))",
        ]
        for doc in self.documents:
            lines.append(
                f"engine.add_document(id={doc.id!r}, content={doc.content!r}, metadata={doc.metadata!r})"
            )
        return "\n".join(lines)

    # --- Representations ---
    def __repr__(self) -> str:  # noqa: D401
        """Developer-friendly summary showing documents and embedding status."""
        header = (
            f"EmbeddingsEngine(embedding_function={self.embedding_function.__class__.__name__}, "
            f"documents={len(self.documents)})"
        )
        if not self.documents:
            return header
        lines = [header, "  documents:"]
        max_items = 10
        for index, doc in enumerate(self.documents[:max_items]):
            has_emb = doc.embedding is not None
            dim = len(doc.embedding) if has_emb else 0
            indicator = "✓" if has_emb else "·"
            content_preview = str(doc.content)
            if len(content_preview) > 60:
                content_preview = content_preview[:57] + "..."
            lines.append(
                f"    [{indicator}] id={doc.id!r} dim={dim} content={content_preview!r}"
            )
        if len(self.documents) > max_items:
            lines.append(f"    ... and {len(self.documents) - max_items} more")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """HTML table showing id, content preview, and embedding status/dimension."""
        rows = []
        for doc in self.documents:
            has_emb = doc.embedding is not None
            dim = len(doc.embedding) if has_emb else 0
            indicator = "✓" if has_emb else "&middot;"
            content_preview = str(doc.content)
            if len(content_preview) > 80:
                content_preview = content_preview[:77] + "..."
            rows.append(
                (
                    html.escape(str(doc.id)),
                    html.escape(content_preview),
                    f"{indicator} {dim if has_emb else ''}".strip(),
                )
            )

        table_rows = [
            "<tr><th style=\"text-align:left\">ID</th><th style=\"text-align:left\">Content</th><th style=\"text-align:left\">Embedding</th></tr>"
        ]
        for id_cell, content_cell, emb_cell in rows[:200]:
            table_rows.append(
                f"<tr><td>{id_cell}</td><td>{content_cell}</td><td>{emb_cell}</td></tr>"
            )
        if len(rows) > 200:
            table_rows.append(
                f"<tr><td colspan=3>... and {len(rows) - 200} more</td></tr>"
            )

        title = (
            f"EmbeddingsEngine &mdash; {len(self.documents)} documents, "
            f"function: {html.escape(self.embedding_function.__class__.__name__)}"
        )
        return (
            "<div>" + title + "</div>" +
            "<table border=1 cellspacing=0 cellpadding=4>" +
            "".join(table_rows) +
            "</table>"
        )
        
    def add_document(self, id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a single document to the engine.
        
        Args:
            id: Unique identifier for the document
            content: Text content of the document
            metadata: Optional metadata dictionary for the document
        """
        if metadata is None:
            metadata = {}
            
        embedding = self.embedding_function.embed_query(content)
        document = Document(id=id, content=content, metadata=metadata, embedding=embedding)
        self.documents.append(document)
        
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add multiple documents to the engine.
        
        Args:
            documents: List of document dictionaries with 'id', 'content', and optional 'metadata' keys

        Examples:
            >>> from edsl.embeddings.embedding_function import MockEmbeddingFunction
            >>> engine = EmbeddingsEngine(MockEmbeddingFunction(embedding_dim=4))
            >>> engine.add_documents([
            ...     {"id": "1", "content": "x"},
            ...     {"id": "2", "content": "y"},
            ... ])
            >>> engine.count()
            2
        """
        texts = [doc["content"] for doc in documents]
        embeddings = self.embedding_function.embed_documents(texts)
        
        for doc_dict, embedding in zip(documents, embeddings):
            document = Document(
                id=doc_dict["id"],
                content=doc_dict["content"], 
                metadata=doc_dict.get("metadata", {}),
                embedding=embedding
            )
            self.documents.append(document)
            
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search for similar documents using cosine similarity.
        
        Args:
            query: Query text to search for
            top_k: Number of top results to return
            
        Returns:
            List of SearchResult objects ranked by similarity score (highest first)

        Examples:
            >>> from edsl.embeddings.embedding_function import MockEmbeddingFunction
            >>> engine = EmbeddingsEngine(MockEmbeddingFunction(embedding_dim=6))
            >>> engine.add_document(id="a", content="alpha")
            >>> engine.add_document(id="b", content="beta")
            >>> [r.document.id for r in engine.search("alpha", top_k=2)][0]
            'a'
        """
        if not self.documents:
            return []
            
        query_embedding = self.embedding_function.embed_query(query)

        # Lazily compute any missing document embeddings in batch for efficiency
        missing_indices = [i for i, d in enumerate(self.documents) if d.embedding is None]
        if missing_indices:
            texts = [self.documents[i].content for i in missing_indices]
            new_embeddings = self.embedding_function.embed_documents(texts)
            for idx, emb in zip(missing_indices, new_embeddings):
                self.documents[idx].embedding = emb
        
        results = []
        for document in self.documents:
            if document.embedding is None:
                continue
                
            similarity = self._cosine_similarity(query_embedding, document.embedding)
            results.append(SearchResult(document=document, similarity_score=similarity))
            
        # Sort by similarity score (highest first) and return top_k
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]
        
    def get_document(self, id: str) -> Optional[Document]:
        """Retrieve a document by its ID.
        
        Args:
            id: Document ID to retrieve
            
        Returns:
            Document if found, None otherwise
        """
        for document in self.documents:
            if document.id == id:
                return document
        return None
        
    def remove_document(self, id: str) -> bool:
        """Remove a document by its ID.
        
        Args:
            id: Document ID to remove
            
        Returns:
            True if document was found and removed, False otherwise
        """
        for i, document in enumerate(self.documents):
            if document.id == id:
                del self.documents[i]
                return True
        return False
        
    def clear(self) -> None:
        """Remove all documents from the engine."""
        self.documents.clear()
        
    def count(self) -> int:
        """Get the number of documents stored in the engine."""
        return len(self.documents)
        
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have the same length")
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
            
        return dot_product / (magnitude1 * magnitude2)

    # --- Visualization helpers ---
    def distance_matrix(
        self,
        *,
        show_values: bool = False,
        cell_size: int = 18,
        label_size: int = 12,
        padding: int = 6,
        auto_open: bool = True,
    ) -> "Any":
        """Return a view object for the cosine-similarity distance matrix.

        The returned object supports `.to_svg()`, `.save(path)`, `.open()`, `.show()`,
        and renders in notebooks via `_repr_html_`.
        """
        from .embeddings_visualization import DistanceMatrixView

        view = DistanceMatrixView(
            engine=self,
            show_values=show_values,
            cell_size=cell_size,
            label_size=label_size,
            padding=padding,
        )
        try:
            import sys as _sys
            if auto_open and hasattr(_sys.stdout, "isatty") and _sys.stdout.isatty():
                view.open()
        except Exception:
            pass
        return view

    def tsne(
        self,
        *,
        width: int = 600,
        height: int = 400,
        perplexity: float = 30.0,
        random_state: int = 42,
        label_size: int = 12,
        auto_open: bool = True,
    ) -> "Any":
        """Return a view object for a 2D t-SNE (or PCA fallback) scatter plot.

        The returned object supports `.to_svg()`, `.save(path)`, `.open()`, `.show()`,
        and renders in notebooks via `_repr_html_`.
        """
        from .embeddings_visualization import TSNEView

        view = TSNEView(
            engine=self,
            width=width,
            height=height,
            perplexity=perplexity,
            random_state=random_state,
            label_size=label_size,
        )
        try:
            import sys as _sys
            if auto_open and hasattr(_sys.stdout, "isatty") and _sys.stdout.isatty():
                view.open()
        except Exception:
            pass
        return view

    # --- Clustering ---
    def cluster_dbscan(
        self,
        *,
        eps: Optional[float] = None,
        min_samples: int = 3,
        metric: str = "cosine",
        target_num_clusters: Optional[int] = None,
        eps_grid: Optional[List[float]] = None,
    ) -> "Any":
        """Run DBSCAN clustering on document embeddings.

        If `target_num_clusters` is provided and `eps` is None, eps will be swept
        over a small grid and the result with closest cluster count is returned.
        Returns a DBSCANClusteringResult with labels, clusters, noise indices, and params.
        """
        from .embeddings_clustering import EmbeddingsClustering

        return EmbeddingsClustering.dbscan(
            engine=self,
            eps=eps,
            min_samples=min_samples,
            metric=metric,
            target_num_clusters=target_num_clusters,
            eps_grid=eps_grid,
        )

    def view_clusters(
        self,
        *,
        # Clustering params
        eps: Optional[float] = None,
        min_samples: int = 3,
        metric: str = "cosine",
        target_num_clusters: Optional[int] = None,
        eps_grid: Optional[List[float]] = None,
        # t-SNE view params
        width: int = 600,
        height: int = 400,
        perplexity: float = 30.0,
        random_state: int = 42,
        label_size: int = 12,
        instant_tooltips: bool = True,
        auto_open: bool = False,
    ) -> "Any":
        """Cluster then visualize documents with t-SNE, colored by cluster.

        Returns a TSNEView that renders in notebooks and supports show/save/open.
        """
        # Run clustering
        from .embeddings_clustering import EmbeddingsClustering
        from .embeddings_visualization import TSNEView

        result = EmbeddingsClustering.dbscan(
            engine=self,
            eps=eps,
            min_samples=min_samples,
            metric=metric,
            target_num_clusters=target_num_clusters,
            eps_grid=eps_grid,
        )

        # Build doc_id -> cluster_id mapping
        doc_to_cluster: Dict[str, int] = {}
        for cid, doc_ids in result.clusters_doc_ids.items():
            for doc_id in doc_ids:
                doc_to_cluster[doc_id] = int(cid)

        view = TSNEView(
            engine=self,
            width=width,
            height=height,
            perplexity=perplexity,
            random_state=random_state,
            label_size=label_size,
            cluster_assignments=doc_to_cluster,
            instant_tooltips=instant_tooltips,
        )
        if auto_open:
            try:
                import sys as _sys
                if hasattr(_sys.stdout, "isatty") and _sys.stdout.isatty():
                    view.open()
            except Exception:
                pass
        return view