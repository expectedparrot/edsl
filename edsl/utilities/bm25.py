"""Simple BM25Okapi implementation to avoid the rank_bm25 dependency."""

import math
from typing import List


class BM25Okapi:
    """BM25Okapi ranking function for token-based document search.

    Parameters
    ----------
    corpus : list of list of str
        Pre-tokenized documents (each document is a list of tokens).
    k1 : float
        Term-frequency saturation parameter (default 1.5).
    b : float
        Length-normalization parameter (default 0.75).
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lengths) / self.corpus_size if self.corpus_size else 1.0
        self.corpus = corpus

        # Build document-frequency table
        self.df: dict[str, int] = {}
        for doc in corpus:
            seen = set(doc)
            for token in seen:
                self.df[token] = self.df.get(token, 0) + 1

        # Pre-compute IDF values
        self.idf: dict[str, float] = {}
        for token, freq in self.df.items():
            self.idf[token] = math.log(
                (self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0
            )

    def get_scores(self, query: List[str]) -> List[float]:
        """Return BM25 scores for each document given a tokenized query."""
        scores = [0.0] * self.corpus_size
        for token in query:
            idf = self.idf.get(token, 0.0)
            if idf == 0.0:
                continue
            for i, doc in enumerate(self.corpus):
                tf = doc.count(token)
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_lengths[i] / self.avgdl)
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        return scores
