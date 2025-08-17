
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

@dataclass
class ChromaQA:
    persist_directory: str
    collection: str
    model_name: str = "intfloat/multilingual-e5-large"
    normalize: bool = True

    def __post_init__(self):
        safe_dir = Path(self.persist_directory).expanduser().as_posix()
        self.client = chromadb.PersistentClient(path=safe_dir)
        self.coll = self.client.get_collection(name=self.collection)
        self.model = SentenceTransformer(self.model_name)

    def _embed(self, text: str) -> List[float]:
        vec = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=self.normalize)[0]
        return vec.tolist()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        qvec = self._embed(query)
        res = self.coll.query(query_embeddings=[qvec], n_results=top_k)
        outs = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0] or res.get("distances", [])
        for i, doc in enumerate(docs):
            m = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else float("nan")
            outs.append({"content": doc, "distance": float(dist), "source": m.get("source"), "meta": m})
        return outs
