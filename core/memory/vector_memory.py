"""
AMRIT RESEARCH OS v4.5
core/memory/vector_memory.py

Vector Memory System — semantic recall, now backed by **turbovec**
(Google Research's TurboQuant, ICLR 2026) instead of ChromaDB.

Why turbovec instead of ChromaDB:
  - 16x smaller RAM (10M docs: ~31 GB → ~4 GB at 4-bit)
  - 12-20% faster search than FAISS on Apple M-series (NEON SIMD)
  - No train phase, no heavy dependency tree, fully local / air-gapped
  - Embeddings stay local via Ollama (nomic-embed-text, 768-dim)

The public API is unchanged from the previous ChromaDB implementation, so
every call site (server.py, main.py, tool_manager, scheduler, agents) keeps
working without modification:

  add(collection, text, metadata)        -> doc_id
  remember_finding(hypothesis, result, domain)
  remember_paper(paper)
  remember_discovery(text, metadata)
  search(collection, query, k)           -> [{text, metadata, distance}]
  recall_similar_research(hypothesis, k) -> [{text, metadata, distance}]
  stats()                                -> {enabled, path, embedder, collections}
  .enabled                               -> bool

`distance` is `1 - cosine_similarity` (lower = closer), matching the old
ChromaDB semantics so existing sorting/threshold logic is preserved.

Collections:
  conversations      - user/agent dialogue turns
  papers             - collected paper abstracts/metadata
  research_notes     - hypotheses, findings, agent reviews
  discoveries        - contradictions & generated hypotheses
  long_term_memory   - distilled lessons that persist
  hypotheses         - generated hypotheses (duplicate detection)
"""

import os
import json
import uuid
import datetime
import logging

import numpy as np

from core.memory.turbovec_memory import (
    OllamaEmbedder,
    _make_index,
    TURBOVEC_AVAILABLE,
    EMBED_DIM,
    BIT_WIDTH,
)

log = logging.getLogger("AmritVectorMemory")

COLLECTIONS = [
    "conversations",
    "papers",
    "research_notes",
    "discoveries",
    "long_term_memory",
    "hypotheses",
]


class VectorMemory:
    """turbovec-backed semantic memory with a ChromaDB-compatible surface."""

    def __init__(self, path: str = "data/vector_store"):
        os.makedirs(path, exist_ok=True)
        self.path = path
        self.enabled = False
        self.error = None

        self.embedder = OllamaEmbedder()
        self._indices = {}     # collection -> turbovec/numpy index
        self._docs = {}        # collection -> {uid:int -> {doc_id, text, meta}}
        self._counters = {}    # collection -> next uid

        try:
            for name in COLLECTIONS:
                self._ensure(name)
            # Memory is "enabled" only if local embeddings are reachable.
            probe = self.embedder.embed("amrit memory probe")
            self.enabled = probe is not None
            if not self.enabled:
                self.error = "Ollama embeddings unavailable (run: ollama serve)"
        except Exception as e:
            self.error = str(e)
            self.enabled = False

        backend = "turbovec (Rust+SIMD)" if TURBOVEC_AVAILABLE else "numpy (fallback)"
        log.info(f"VectorMemory online — backend: {backend}, enabled: {self.enabled}")

    # ─────────────────── internal helpers ───────────────────

    def _ensure(self, collection: str):
        """Create a collection (and load any persisted data) on first use."""
        if collection in self._indices:
            return
        self._indices[collection] = _make_index(EMBED_DIM, BIT_WIDTH)
        self._docs[collection] = {}
        self._counters[collection] = 0
        self._load_collection(collection)

    def _paths(self, collection: str):
        return (
            os.path.join(self.path, f"{collection}_docstore.json"),
            os.path.join(self.path, f"{collection}.tvim"),
        )

    def _load_collection(self, collection: str):
        path_json, path_idx = self._paths(collection)
        if os.path.exists(path_json):
            try:
                with open(path_json, encoding="utf-8") as f:
                    data = json.load(f)
                self._docs[collection] = {int(k): v for k, v in data.get("docstore", {}).items()}
                self._counters[collection] = data.get("counter", len(self._docs[collection]))
            except Exception as e:
                log.warning(f"  {collection} docstore load failed: {e}")
        if TURBOVEC_AVAILABLE and os.path.exists(path_idx):
            try:
                from turbovec import IdMapIndex
                self._indices[collection] = IdMapIndex.load(path_idx)
            except Exception as e:
                log.warning(f"  {collection} index load failed: {e}")

    def _save_collection(self, collection: str):
        path_json, path_idx = self._paths(collection)
        try:
            with open(path_json, "w", encoding="utf-8") as f:
                json.dump({
                    "docstore": self._docs[collection],
                    "counter": self._counters[collection],
                }, f, ensure_ascii=False)
            if TURBOVEC_AVAILABLE and len(self._indices[collection]) > 0:
                self._indices[collection].write(path_idx)
        except Exception as e:
            log.warning(f"  {collection} save failed: {e}")

    def save_all(self):
        for collection in self._indices:
            self._save_collection(collection)

    # alias used by the pipeline bridge
    save = save_all

    # ─────────────────── write ───────────────────

    def add(self, collection: str, text: str, metadata: dict = None) -> str:
        """Embed and store a document. Returns the generated doc id (or '')."""
        if not self.enabled or not text:
            return ""
        self._ensure(collection)
        vec = self.embedder.embed(text)
        if vec is None:
            return ""

        doc_id = str(uuid.uuid4())
        meta = {"ts": datetime.datetime.now().isoformat()}
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})

        uid = self._counters[collection]
        self._counters[collection] += 1
        self._docs[collection][uid] = {"doc_id": doc_id, "text": text[:1000], "meta": meta}
        try:
            self._indices[collection].add_with_ids(
                vec.reshape(1, -1),
                np.array([uid], dtype=np.uint64),
            )
            self._save_collection(collection)
            return doc_id
        except Exception as e:
            log.warning(f"add failed in {collection}: {e}")
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
        if not self.enabled or not query:
            return []
        self._ensure(collection)
        index = self._indices[collection]
        if len(index) == 0:
            return []
        vec = self.embedder.embed(query)
        if vec is None:
            return []
        try:
            scores, ids = index.search(
                vec.reshape(1, -1) if TURBOVEC_AVAILABLE else vec,
                k=min(k, len(index)),
            )
            # turbovec returns 2D (1, k); numpy fallback returns 1D — flatten both.
            scores = np.asarray(scores).reshape(-1)
            ids = np.asarray(ids).reshape(-1)

            out = []
            for score, uid in zip(scores, ids):
                uid_int = int(uid)
                doc = self._docs[collection].get(uid_int)
                if doc:
                    out.append({
                        "text": doc["text"],
                        "metadata": doc["meta"],
                        # cosine distance: lower = closer (matches old Chroma semantics)
                        "distance": round(1.0 - float(score), 4),
                    })
            return out
        except Exception as e:
            log.warning(f"search failed in {collection}: {e}")
            return []

    def recall_similar_research(self, hypothesis: str, k: int = 3) -> list:
        """'Has anything like this been researched before?'"""
        return self.search("research_notes", hypothesis, k)

    def stats(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": self.error or "unavailable"}
        return {
            "enabled": True,
            "path": self.path,
            "embedder": f"ollama-{self.embedder.model}",
            "backend": "turbovec" if TURBOVEC_AVAILABLE else "numpy",
            "collections": {name: len(self._indices[name]) for name in self._indices},
        }


# ─────────────────────────────────────────────────────────────
# AMRIT Pipeline Integration Helper
# ─────────────────────────────────────────────────────────────
class AMRITMemoryBridge:
    """
    Thin pipeline helper that delegates to a shared VectorMemory so there is a
    single semantic store (no duplicate indexes).

    Usage in main.py:
        bridge = AMRITMemoryBridge(self.vmem)
        bridge.on_paper_collected(papers)
        bridge.on_finding_ready(hypothesis, stats_result, domain)
        is_dup, similar = bridge.check_duplicate(hypothesis)
        context = bridge.get_agent_context(hypothesis)
    """

    def __init__(self, vector_memory: VectorMemory = None):
        self.memory = vector_memory or VectorMemory()
        log.info("AMRITMemoryBridge ready (shared VectorMemory)")

    def on_paper_collected(self, papers: list) -> int:
        """Step 3 (Data Collection) → auto-store paper embeddings."""
        stored = 0
        for p in papers:
            if not isinstance(p, dict):
                continue
            title = p.get("title", "")
            if title and "error" not in p:
                if self.memory.remember_paper(p):
                    stored += 1
        if papers:
            log.info(f"TurboVec: stored {stored}/{len(papers)} papers")
        return stored

    def on_finding_ready(self, hypothesis: str, result: dict, domain: str):
        """Step 10 (Memory Store) → store finding + hypothesis embedding."""
        self.memory.remember_finding(hypothesis, result, domain)
        self.memory.add("hypotheses", hypothesis, {"domain": domain})

    def check_duplicate(self, hypothesis: str, threshold: float = 0.92) -> tuple:
        """Step 1 → has this hypothesis been seen before? (similarity ≥ threshold)."""
        results = self.memory.search("hypotheses", hypothesis, k=1)
        if results:
            similarity = 1.0 - (results[0]["distance"] or 1.0)
            if similarity >= threshold:
                return True, results[0]["text"]
        return False, ""

    def get_agent_context(self, hypothesis: str, k: int = 3) -> str:
        """Step 6 → gather relevant past research for the agents."""
        parts = []
        for col in ["papers", "research_notes", "discoveries"]:
            for r in self.memory.search(col, hypothesis, k):
                similarity = 1.0 - (r["distance"] or 1.0)
                if similarity > 0.6:
                    parts.append(f"[{col.upper()} sim={similarity:.3f}] {r['text'][:150]}")
        return "\n".join(parts) if parts else "No relevant past research found."

    def save(self):
        self.memory.save_all()
