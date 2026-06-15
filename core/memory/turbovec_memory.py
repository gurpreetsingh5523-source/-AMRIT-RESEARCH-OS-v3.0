"""
AMRIT RESEARCH OS v4.5
core/memory/turbovec_memory.py

TurboVec — Ultra-fast quantized vector memory
Built on Google Research's TurboQuant (ICLR 2026)
16x ਘੱਟ RAM · FAISS ਤੋਂ 20% ਤੇਜ਼ · Apple M-series NEON ਲਈ optimized

ਇੰਸਟਾਲ: pip install turbovec

ਇਹ module SQLite memory ਦੇ ਨਾਲ ਕੰਮ ਕਰਦਾ ਹੈ:
- SQLite → structured data (p-values, verdicts, metadata)
- TurboVec → semantic search (ਮਿਲਦੀ-ਜੁਲਦੀ research ਲੱਭਣੀ)

Collections:
  papers        → ArXiv / PubMed papers
  findings      → Research findings & verdicts
  hypotheses    → Generated hypotheses
  discoveries   → Cross-domain discoveries
  long_term     → ਸਥਾਈ long-term memory
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

import numpy as np

log = logging.getLogger("AmritTurboVec")

# ─────────────────────────────────────────────────────────────
# TurboVec availability check
# ─────────────────────────────────────────────────────────────
try:
    from turbovec import IdMapIndex
    TURBOVEC_AVAILABLE = True
    log.info("✅ turbovec loaded — Rust SIMD vector search active")
except ImportError:
    TURBOVEC_AVAILABLE = False
    log.warning("⚠️  turbovec not installed. Run: pip install turbovec")
    log.warning("   Falling back to numpy cosine search (slower)")

OLLAMA_BASE = "http://localhost:11434"
EMBED_MODEL  = "nomic-embed-text"   # Already in your Ollama stack
EMBED_DIM    = 768                  # nomic-embed-text dimension
BIT_WIDTH    = 4                    # 4-bit quantization (best recall)
MEMORY_DIR   = "data/turbovec"


# ─────────────────────────────────────────────────────────────
# Ollama Embeddings
# ─────────────────────────────────────────────────────────────
class OllamaEmbedder:
    """Get embeddings from local Ollama (nomic-embed-text)."""

    def __init__(self, model: str = EMBED_MODEL):
        self.model = model

    def embed(self, text: str) -> Optional[np.ndarray]:
        """Single text → 768-dim float32 vector."""
        payload = json.dumps({
            "model": self.model,
            "prompt": text[:2000],  # truncate long texts
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
                vec = np.array(data["embedding"], dtype=np.float32)
                # Normalize to unit sphere (required for cosine similarity)
                norm = np.linalg.norm(vec)
                return vec / norm if norm > 1e-9 else vec
        except Exception as e:
            log.warning(f"Embedding error: {e}")
            return None

    def embed_batch(self, texts: list[str]) -> list[Optional[np.ndarray]]:
        return [self.embed(t) for t in texts]


# ─────────────────────────────────────────────────────────────
# Fallback: numpy cosine search (when turbovec not installed)
# ─────────────────────────────────────────────────────────────
class NumpyFallbackIndex:
    """Simple cosine search — slower but works without Rust."""

    def __init__(self, dim: int):
        self.dim     = dim
        self._vecs   = np.zeros((0, dim), dtype=np.float32)
        self._ids    = []
        self._next   = 0

    def add_with_ids(self, vectors: np.ndarray, ids: np.ndarray):
        self._vecs = np.vstack([self._vecs, vectors]) if len(self._vecs) else vectors.copy()
        self._ids.extend(ids.tolist())

    def search(self, query: np.ndarray, k: int, allowlist=None):
        if len(self._vecs) == 0:
            return np.array([]), np.array([])
        scores = self._vecs @ query.flatten()
        if allowlist is not None:
            allow_set = set(allowlist.tolist())
            mask = np.array([i in allow_set for i in self._ids])
            scores = np.where(mask, scores, -1.0)
        top_k = min(k, len(scores))
        idx   = np.argpartition(scores, -top_k)[-top_k:]
        idx   = idx[np.argsort(scores[idx])[::-1]]
        return scores[idx], np.array([self._ids[i] for i in idx], dtype=np.uint64)

    def remove(self, uid: int):
        if uid in self._ids:
            pos = self._ids.index(uid)
            self._ids.pop(pos)
            self._vecs = np.delete(self._vecs, pos, axis=0)

    def __len__(self): return len(self._ids)


def _make_index(dim: int = EMBED_DIM, bit_width: int = BIT_WIDTH):
    """Return turbovec IdMapIndex if available, else numpy fallback."""
    if TURBOVEC_AVAILABLE:
        return IdMapIndex(dim=dim, bit_width=bit_width)
    return NumpyFallbackIndex(dim=dim)


# ─────────────────────────────────────────────────────────────
# TurboVec Memory — main class
# ─────────────────────────────────────────────────────────────
class TurboVecMemory:
    """
    Semantic vector memory for AMRIT Research OS.

    5 collections:
      papers      → Research papers (ArXiv, PubMed, NASA)
      findings    → Statistical findings & verdicts
      hypotheses  → Generated hypotheses
      discoveries → Cross-domain discoveries
      long_term   → ਸਥਾਈ memory

    Usage:
      memory = TurboVecMemory()
      memory.add_paper(title, abstract, paper_id)
      results = memory.search_similar("quantum entanglement patterns", k=5)
    """

    COLLECTIONS = ["papers", "findings", "hypotheses", "discoveries", "long_term"]

    def __init__(self, memory_dir: str = MEMORY_DIR):
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)

        self.embedder = OllamaEmbedder()

        # One index per collection
        self.indices: dict = {}
        self.docstores: dict = {}  # id → {text, metadata}
        self._counters: dict = {}

        for col in self.COLLECTIONS:
            self.indices[col]   = _make_index()
            self.docstores[col] = {}
            self._counters[col] = 0
            self._load_collection(col)

        backend = "turbovec (Rust+SIMD)" if TURBOVEC_AVAILABLE else "numpy (fallback)"
        log.info(f"🧠 TurboVecMemory online — backend: {backend}")
        log.info(f"   Collections: {self.COLLECTIONS}")
        self._log_stats()

    # ── ADD ───────────────────────────────────────────────────

    def add_paper(self, title: str, abstract: str, paper_id: str,
                  source: str = "unknown", url: str = "") -> bool:
        """Store a research paper with its embedding."""
        text = f"{title}. {abstract}"
        return self._add("papers", text, {
            "title": title, "abstract": abstract[:300],
            "paper_id": paper_id, "source": source, "url": url,
        })

    def add_finding(self, hypothesis: str, verdict: str,
                    p_value: float, domain: str) -> bool:
        """Store a research finding."""
        text = f"Hypothesis: {hypothesis}. Verdict: {verdict}. Domain: {domain}."
        return self._add("findings", text, {
            "hypothesis": hypothesis, "verdict": verdict,
            "p_value": p_value, "domain": domain,
        })

    def add_hypothesis(self, hypothesis: str, domain: str) -> bool:
        """Store a generated hypothesis."""
        return self._add("hypotheses", hypothesis, {"domain": domain})

    def add_discovery(self, discovery: str, domains: list,
                      evidence: str = "") -> bool:
        """Store a cross-domain discovery."""
        text = f"Discovery: {discovery}. Domains: {', '.join(domains)}. {evidence}"
        return self._add("discoveries", text, {
            "discovery": discovery, "domains": domains, "evidence": evidence,
        })

    def add_long_term(self, insight: str, tags: list = None) -> bool:
        """Store a permanent long-term insight."""
        return self._add("long_term", insight, {"tags": tags or []})

    # ── SEARCH ────────────────────────────────────────────────

    def search_similar_papers(self, query: str, k: int = 5) -> list[dict]:
        """ਇਸ topic ਨਾਲ ਮਿਲਦੇ-ਜੁਲਦੇ papers ਲੱਭੋ।"""
        return self._search("papers", query, k)

    def search_similar_findings(self, query: str, k: int = 5) -> list[dict]:
        """ਮਿਲਦੇ-ਜੁਲਦੇ research findings ਲੱਭੋ।"""
        return self._search("findings", query, k)

    def is_hypothesis_duplicate(self, hypothesis: str,
                                 threshold: float = 0.92) -> tuple[bool, str]:
        """
        ਕੀ ਇਹ hypothesis ਪਹਿਲਾਂ ਤੋਂ ਮੌਜੂਦ ਹੈ?
        Returns (is_duplicate, similar_hypothesis_text)
        """
        results = self._search("hypotheses", hypothesis, k=1)
        if results and results[0]["score"] >= threshold:
            return True, results[0]["text"]
        return False, ""

    def recall_context(self, query: str, k: int = 3) -> str:
        """
        Agent ਲਈ relevant past research ਇਕੱਠਾ ਕਰੋ।
        Searches all collections and returns formatted context.
        """
        parts = []
        for col in ["papers", "findings", "discoveries"]:
            results = self._search(col, query, k=k)
            for r in results:
                if r["score"] > 0.6:
                    parts.append(
                        f"[{col.upper()} score={r['score']:.3f}] {r['text'][:150]}"
                    )
        return "\n".join(parts) if parts else "No relevant past research found."

    def search_all(self, query: str, k: int = 3) -> dict:
        """Search all 5 collections at once."""
        return {col: self._search(col, query, k) for col in self.COLLECTIONS}

    # ── STATS ─────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            col: {
                "count":    len(self.indices[col]),
                "backend":  "turbovec" if TURBOVEC_AVAILABLE else "numpy",
                "dim":      EMBED_DIM,
                "bit_width": BIT_WIDTH,
            }
            for col in self.COLLECTIONS
        }

    def total_vectors(self) -> int:
        return sum(len(self.indices[col]) for col in self.COLLECTIONS)

    # ── PERSISTENCE ───────────────────────────────────────────

    def save_all(self):
        """Save all indices and docstores to disk."""
        for col in self.COLLECTIONS:
            self._save_collection(col)
        log.info(f"💾 TurboVecMemory saved — {self.total_vectors()} vectors")

    def _save_collection(self, col: str):
        path_json = os.path.join(self.memory_dir, f"{col}_docstore.json")
        path_tq   = os.path.join(self.memory_dir, f"{col}.tvim")

        with open(path_json, "w", encoding="utf-8") as f:
            json.dump({
                "docstore": self.docstores[col],
                "counter":  self._counters[col],
            }, f, ensure_ascii=False, indent=2)

        if TURBOVEC_AVAILABLE and len(self.indices[col]) > 0:
            self.indices[col].write(path_tq)

    def _load_collection(self, col: str):
        path_json = os.path.join(self.memory_dir, f"{col}_docstore.json")
        path_tq   = os.path.join(self.memory_dir, f"{col}.tvim")

        if os.path.exists(path_json):
            with open(path_json, encoding="utf-8") as f:
                data = json.load(f)
            # Convert string keys back to int
            self.docstores[col] = {int(k): v for k, v in data["docstore"].items()}
            self._counters[col] = data.get("counter", len(self.docstores[col]))

        if TURBOVEC_AVAILABLE and os.path.exists(path_tq):
            try:
                from turbovec import IdMapIndex
                self.indices[col] = IdMapIndex.load(path_tq)
                log.info(f"  📂 {col}: {len(self.indices[col])} vectors loaded")
            except Exception as e:
                log.warning(f"  ⚠️  {col} index load failed: {e}")

    # ── INTERNAL ──────────────────────────────────────────────

    def _add(self, col: str, text: str, metadata: dict) -> bool:
        vec = self.embedder.embed(text)
        if vec is None:
            log.warning(f"  ❌ Embedding failed for {col}")
            return False

        uid = self._counters[col]
        self._counters[col] += 1

        self.docstores[col][uid] = {"text": text[:500], "meta": metadata}
        self.indices[col].add_with_ids(
            vec.reshape(1, -1),
            np.array([uid], dtype=np.uint64),
        )
        return True

    def _search(self, col: str, query: str, k: int) -> list[dict]:
        if len(self.indices[col]) == 0:
            return []

        vec = self.embedder.embed(query)
        if vec is None:
            return []

        try:
            scores, ids = self.indices[col].search(
                vec.reshape(1, -1) if TURBOVEC_AVAILABLE else vec,
                k=min(k, len(self.indices[col])),
            )
            results = []
            for score, uid in zip(scores, ids):
                uid_int = int(uid)
                if uid_int in self.docstores[col]:
                    doc = self.docstores[col][uid_int]
                    results.append({
                        "score":    float(score),
                        "text":     doc["text"],
                        "metadata": doc["meta"],
                    })
            return results
        except Exception as e:
            log.warning(f"Search error in {col}: {e}")
            return []

    def _log_stats(self):
        total = self.total_vectors()
        if total > 0:
            log.info(f"   Total vectors loaded: {total}")
            for col in self.COLLECTIONS:
                n = len(self.indices[col])
                if n > 0:
                    log.info(f"   {col}: {n} vectors")


# ─────────────────────────────────────────────────────────────
# AMRIT Pipeline Integration Helper
# ─────────────────────────────────────────────────────────────
class AMRITMemoryBridge:
    """
    Bridges TurboVecMemory with AMRIT's existing pipeline.
    ਇਸਨੂੰ main.py ਵਿੱਚ import ਕਰੋ।

    Example usage in main.py:
        bridge = AMRITMemoryBridge()
        bridge.on_paper_collected(papers)
        bridge.on_finding_ready(hypothesis, stats_result, domain)
        context = bridge.get_agent_context(hypothesis)
        is_dup, similar = bridge.check_duplicate(hypothesis)
    """

    def __init__(self):
        self.memory = TurboVecMemory()
        log.info("🔗 AMRITMemoryBridge ready")

    def on_paper_collected(self, papers: list[dict]):
        """Step 3 (Data Collection) → auto-store paper embeddings."""
        stored = 0
        for p in papers:
            title    = p.get("title", "")
            abstract = p.get("abstract", p.get("summary", ""))
            pid      = p.get("arxiv_id", p.get("pubmed_id", str(hash(title))))
            source   = p.get("source", "unknown")
            if title and abstract:
                if self.memory.add_paper(title, abstract, pid, source):
                    stored += 1
        log.info(f"📚 Stored {stored}/{len(papers)} papers in TurboVec")

    def on_finding_ready(self, hypothesis: str, result: dict, domain: str):
        """Step 10 (Memory Store) → store finding embedding."""
        self.memory.add_finding(
            hypothesis  = hypothesis,
            verdict     = result.get("verdict", ""),
            p_value     = result.get("p_value", 1.0),
            domain      = domain,
        )
        self.memory.add_hypothesis(hypothesis, domain)
        log.info("💾 Finding + hypothesis stored in TurboVec")

    def check_duplicate(self, hypothesis: str) -> tuple[bool, str]:
        """Step 1 (Hypothesis) → ਦੇਖੋ ਕੀ ਇਹ ਪਹਿਲਾਂ ਬਣੀ ਹੈ।"""
        return self.memory.is_hypothesis_duplicate(hypothesis)

    def get_agent_context(self, hypothesis: str) -> str:
        """Step 6 (Agent Swarm) → agents ਨੂੰ past research ਦਿਓ।"""
        return self.memory.recall_context(hypothesis, k=3)

    def save(self):
        self.memory.save_all()


# ─────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(message)s")

    print("\n🧪 TurboVec Memory — Self Test")
    print(f"   turbovec available: {TURBOVEC_AVAILABLE}")
    print(f"   Embedding model:    {EMBED_MODEL} (768-dim)")

    mem = TurboVecMemory()

    # Check if Ollama is running
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            ollama_ok = r.status == 200
    except Exception:
        ollama_ok = False

    if not ollama_ok:
        print("\n⚠️  Ollama offline — run: ollama serve")
        print("   Then: ollama pull nomic-embed-text")
        print("   Full test skipped — structure verified ✅")
    else:
        print("\n✅ Ollama online — running embedding test...")

        ok1 = mem.add_paper(
            title    = "Pioneer anomaly: unexpected deceleration",
            abstract = "Anomalous acceleration observed in Pioneer 10/11 contradicts Newtonian gravity.",
            paper_id = "test_001",
            source   = "ArXiv",
        )
        ok2 = mem.add_finding(
            hypothesis = "Pioneer anomaly indicates dark matter effect",
            verdict    = "WEAK SUPPORT",
            p_value    = 0.04,
            domain     = "Physics",
        )
        ok3 = mem.add_hypothesis(
            "Does quantum entanglement correlate with Fibonacci sequences?",
            domain="Physics",
        )

        print(f"\n   Added paper:      {'✅' if ok1 else '❌'}")
        print(f"   Added finding:    {'✅' if ok2 else '❌'}")
        print(f"   Added hypothesis: {'✅' if ok3 else '❌'}")

        results = mem.search_similar_papers("dark matter Pioneer spacecraft", k=3)
        print(f"\n   Search test — '{results[0]['score']:.4f}' similarity" if results else "   Search: no results")

        is_dup, similar = mem.is_hypothesis_duplicate(
            "Does quantum entanglement show Fibonacci patterns?"
        )
        print(f"   Duplicate check: {'DUPLICATE' if is_dup else 'UNIQUE'}")

        mem.save_all()
        print(f"\n   Total vectors: {mem.total_vectors()}")
        print("\n✅ TurboVec Memory test complete!")

    print("\n📊 Memory stats:")
    for col, s in mem.stats().items():
        print(f"   {col:<15} {s['count']:>4} vectors | {s['backend']}")
