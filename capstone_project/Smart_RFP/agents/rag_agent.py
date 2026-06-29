"""
agents/rag_agent.py  (Agent 1 - RAG Retrieval)
----------------------------------------------
Searches the internal knowledge base for the chunks most relevant to each
requirement and returns them as grounded "evidence" with their source titles.

Implementation note:
  The architecture diagram shows OpenAI embeddings + FAISS/pgvector. Since we are
  using Groq (which has no embeddings endpoint) and want a zero-setup, always-works
  capstone, retrieval here uses TF-IDF + cosine similarity (scikit-learn). It needs
  no model download and demonstrates the exact same retrieve-by-relevance behaviour.

  To upgrade to true semantic embeddings later, swap TfidfVectorizer for
  sentence-transformers ('all-MiniLM-L6-v2') and store the vectors -- the public
  function signature below does not need to change.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import get_kb_docs
from config import RAG_TOP_K

from langsmith import traceable

from metrics import (
    RAG_QUERIES,
    RAG_RESULTS,
    RAG_EMPTY,
)

class RAGAgent:
    @traceable(
    name="RAG Agent Initialization",
    run_type="chain",
    )
    def __init__(self):
        self.docs = get_kb_docs()
        self.corpus = [d["content"] for d in self.docs]
        self.vectorizer = None
        self.matrix = None
        if self.corpus:
            self.vectorizer = TfidfVectorizer(stop_words="english")
            self.matrix = self.vectorizer.fit_transform(self.corpus)
    
    @traceable(
        name="RAG Retrieval",
        run_type="retriever",
    )
    def retrieve(self, query: str, top_k: int = RAG_TOP_K):
        RAG_QUERIES.inc()
        """Return up to top_k relevant KB docs above a similarity threshold."""
        if not self.corpus or self.vectorizer is None:
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sims.argsort()[::-1][:top_k]
        results = []
        for idx in ranked:
            score = float(sims[idx])
            if score < 0.04:          # weak / no real match -> skip
                continue
            d = self.docs[idx]
            results.append({
                "title": d["title"],
                "doc_type": d["doc_type"],
                "content": d["content"],
                "score": round(score, 3),
            })
        RAG_RESULTS.observe(len(results))

        if len(results) == 0:
            RAG_EMPTY.inc()
        return results
