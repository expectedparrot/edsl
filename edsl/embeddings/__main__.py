"""CLI for indexing and searching with the embeddings engine using a mock provider.

Usage examples:
    # Index from a file and then search
    python -m edsl.embeddings --index-file documents.txt --search "hello" --top-k 3

    # Index from stdin
    cat documents.txt | python -m edsl.embeddings --index-file - --search "hello"

    # Generate embeddings ad-hoc without indexing
    python -m edsl.embeddings --embed-query "hello world"
    python -m edsl.embeddings --embed-file documents.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .embedding_function import MockEmbeddingFunction
from .embeddings_engine import EmbeddingsEngine


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index and search using a mock embeddings engine."
    )

    # Indexing inputs
    parser.add_argument(
        "--index-file",
        type=str,
        help="Path to a file with one document per line to index, or '-' for stdin.",
    )

    # Standalone embedding (no indexing) helpers
    parser.add_argument(
        "--embed-query", type=str, help="Emit embedding vector for a single query."
    )
    parser.add_argument(
        "--embed-file",
        type=str,
        help="Emit embedding vectors for each line in file or '-' for stdin.",
    )

    # Search options
    parser.add_argument(
        "--search", type=str, help="Query string to search against indexed documents."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top results to return (default: 5).",
    )

    parser.add_argument(
        "--dim",
        type=int,
        default=1536,
        help="Embedding dimension (default: 1536).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for deterministic randomness (default: 42).",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Disable seeding for non-deterministic results.",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="L2-normalize each embedding vector.",
    )
    return parser.parse_args(argv)


def read_documents_from_file(file_path: str) -> List[str]:
    if file_path == "-":
        return [line.rstrip("\n") for line in sys.stdin if line.strip()]
    with open(file_path, "r", encoding="utf-8") as input_file:
        return [line.rstrip("\n") for line in input_file if line.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_arguments(argv)

    seed_value: Optional[int] = None if args.no_seed else args.seed
    embedding_function = MockEmbeddingFunction(
        embedding_dim=args.dim,
        seed=seed_value,
        normalize=bool(args.normalize),
    )

    # Ad-hoc embeddings mode
    if args.embed_query:
        vector = embedding_function.embed_query(args.embed_query)
        print(json.dumps(vector))
        return 0

    if args.embed_file:
        docs = read_documents_from_file(args.embed_file)
        vectors = embedding_function.embed_documents(docs)
        print(json.dumps(vectors))
        return 0

    engine = EmbeddingsEngine(embedding_function=embedding_function)

    # Optional indexing
    if args.index_file:
        docs = read_documents_from_file(args.index_file)
        documents_payload = [
            {"id": str(i), "content": content, "metadata": {}}
            for i, content in enumerate(docs)
        ]
        engine.add_documents(documents_payload)

    # Optional search
    if args.search:
        results = engine.search(args.search, top_k=args.top_k)
        output = [
            {
                "id": result.document.id,
                "content": result.document.content,
                "similarity": result.similarity_score,
            }
            for result in results
        ]
        print(json.dumps(output))
        return 0

    # If nothing else requested, print count of indexed docs when indexing was provided
    if args.index_file:
        print(json.dumps({"indexed_documents": engine.count()}))
        return 0

    # If no operation was specified
    print(json.dumps({"message": "No operation specified. Use --help for usage."}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
