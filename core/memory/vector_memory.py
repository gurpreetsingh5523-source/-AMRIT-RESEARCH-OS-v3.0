"""
AMRIT RESEARCH OS v4.0
core/memory/vector_memory.py

Vector Memory System (ChromaDB) — semantic recall.

v3 weakness FIXED:
  #4  Memory only did `SELECT * FROM findings` (exact match).
      Now research is embedded and stored in ChromaDB so the system
      can ask "has anything LIKE this been researched before?".

Collections:
  conversations      - user/agent dialogue turns
  papers             - collected paper abstracts/metadata
  research_notes     - hypotheses, findings, agent reviews
  discoveries        - contradictions & generated hypotheses
  long_term_memory   - distilled lessons that persist

Embeddings come from local Ollama (nomic-embed-text) so nothing is
downloaded at import time and everything stays offline. If Ollama is
unavailable, ChromaDB's built-in default embedder is used as a fallback.
"""

import os
import uuid
import datetime

from core.ai.ollama_client import OllamaClient

COLLECTIONS = [
    "conversations",
    "papers",
    "research_notes",
    "discoveries",
    "long_term_memory",
]


class _OllamaEmbedding:
    """ChromaDB-compatible embedding function backed by local Ollama."""

    def __init__(self, model: str = "nomic-embed-text:latest"):
        self.model = model
        self.client = OllamaClient(model=model)

    def _embed_many(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return [self.client.embeddings(t, model=self.model) for t in texts]

    # Supports both the legacy callable interface and the newer
    # embed_documents / embed_query interface used by ChromaDB >= 1.x.
    def __call__(self, input):
        return self._embed_many(input)

    def embed_documents(self, input):
        return self._embed_many(input)

    def embed_query(self, input):
        return self._embed_many(input)

    def name(self) -> str:                      # required by newer ChromaDB
        return f"ollama-{self.model}"


class VectorMemory:

    def __init__(self, path: str = "data/vector_store"):
        os.makedirs(path, exist_ok=True)
        self.path = path
        self.enabled = False
        self._collections = {}
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=path)
            self._embed = self._build_embedder()
            for name in COLLECTIONS:
                self._collections[name] = self.client.get_or_create_collection(
                    name=name, embedding_function=self._embed
                )
            self.enabled = True
        except Exception as e:                  # ChromaDB missing or failed
            self.error = str(e)

    def _build_embedder(self):
        """Prefer local Ollama embeddings; fall back to Chroma default."""
        ollama = OllamaClient(model="nomic-embed-text:latest")
        if ollama.is_available() and ollama.embeddings("test"):
            return _OllamaEmbedding()
        # Fallback: let ChromaDB use its built-in default embedder.
        return None

    # ─────────────────── write ───────────────────

    def add(self, collection: str, text: str, metadata: dict = None) -> str:
        """Embed and store a document. Returns the generated id."""
        if not self.enabled or collection not in self._collections:
            return ""
        doc_id = str(uuid.uuid4())
        meta = {"ts": datetime.datetime.now().isoformat()}
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})
        try:
            self._collections[collection].add(
                ids=[doc_id], documents=[text], metadatas=[meta]
            )
            return doc_id
        except Exception:
            return ""

    def remember_finding(self, hypothesis: str, result: dict, domain: str = "") -> str:
        text = (
            f"Hypothesis: {hypothesis}\n"
            f"Verdict: {result.get('verdict')}  "
            f"p={result.get('p_value')}  effect={result.get('effect_size')}"
        )
        return self.add("research_notes", text, {
            "domain": domain,
            "verdict": result.get("verdict", ""),
            "p_value": result.get("p_value", ""),
        })

    def remember_paper(self, paper: dict) -> str:
        text = f"{paper.get('title', '')}\n{paper.get('summary', paper.get('abstract', ''))}"
        return self.add("papers", text, {
            "source": paper.get("source", ""),
            "link": paper.get("link", paper.get("doi", "")),
        })

    def remember_discovery(self, text: str, metadata: dict = None) -> str:
        return self.add("discoveries", text, metadata)

    # ─────────────────── read ───────────────────

    def search(self, collection: str, query: str, k: int = 3) -> list:
        """Semantic search within a collection. Returns list of dicts."""
        if not self.enabled or collection not in self._collections:
            return []
        try:
            res = self._collections[collection].query(query_texts=[query], n_results=k)
        except Exception:
            return []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out = []
        for i, doc in enumerate(docs):
            out.append({
                "text": doc,
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            })
        return out

    def recall_similar_research(self, hypothesis: str, k: int = 3) -> list:
        """'Has anything like this been researched before?'"""
        return self.search("research_notes", hypothesis, k)

    def stats(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": getattr(self, "error", "unavailable")}
        return {
            "enabled": True,
            "path": self.path,
            "embedder": self._embed.name() if self._embed else "chroma-default",
            "collections": {
                name: self._collections[name].count()
                for name in self._collections
            },
        }
