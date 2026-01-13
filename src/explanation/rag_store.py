# src/rag_store.py
from dataclasses import dataclass
from typing import List, Dict
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

@dataclass
class Doc:
    id: str
    text: str
    meta: Dict

class SimpleRAG:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(model_name)
        self.docs: List[Doc] = []
        self.index = None
        self.dim = None

    def add_docs(self, docs: List[Doc]):
        self.docs.extend(docs)

    def build(self):
        texts = [d.text for d in self.docs]
        embs = self.embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        self.dim = embs.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(embs.astype(np.float32))

    def query(self, q: str, k: int = 5) -> List[Doc]:
        if self.index is None:
            raise RuntimeError("RAG index not built. Call build() first.")
        qemb = self.embedder.encode([q], convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
        scores, idxs = self.index.search(qemb, k)
        results = []
        for i in idxs[0]:
            if i >= 0 and i < len(self.docs):
                results.append(self.docs[i])
        return results
