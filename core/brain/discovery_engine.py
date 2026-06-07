"""
AMRIT RESEARCH OS v4.0
core/brain/discovery_engine.py

Discovery Engine — the feature that sets AMRIT apart.

Flow:
  Read findings/papers -> find contradictions -> generate hypothesis -> rank

Example:
  Paper A: "A causes B"
  Paper B: "A does not cause B"
        -> New research question about the conditions under which A->B holds.

Uses the LLM (via ModelRouter) to detect semantic contradictions and to
propose new, testable hypotheses. Falls back to a keyword heuristic offline.
"""

import re

from core.models.router import ModelRouter

_NEGATIONS = re.compile(r"\b(no|not|does not|doesn't|without|fails to|absence|negative|unrelated)\b", re.I)


class DiscoveryEngine:

    def __init__(self, router: ModelRouter = None):
        self.router = router or ModelRouter()

    # ─────────────────── contradiction detection ───────────────────

    def find_contradictions(self, statements: list) -> list:
        """
        statements: list of {'text': str, 'source': str}
        Returns candidate contradicting pairs.
        """
        pairs = []
        for i in range(len(statements)):
            for j in range(i + 1, len(statements)):
                a, b = statements[i], statements[j]
                if self._looks_contradictory(a["text"], b["text"]):
                    pairs.append({
                        "a": a, "b": b,
                        "reason": "opposing polarity on shared concepts",
                    })
        return pairs

    @staticmethod
    def _shared_keywords(a: str, b: str) -> set:
        stop = {"the", "a", "an", "is", "are", "of", "and", "or", "to", "in", "on", "that", "does", "not"}
        wa = {w.lower().strip(".,?") for w in a.split() if len(w) > 3 and w.lower() not in stop}
        wb = {w.lower().strip(".,?") for w in b.split() if len(w) > 3 and w.lower() not in stop}
        return wa & wb

    def _looks_contradictory(self, a: str, b: str) -> bool:
        shared = self._shared_keywords(a, b)
        if len(shared) < 2:
            return False
        neg_a = bool(_NEGATIONS.search(a))
        neg_b = bool(_NEGATIONS.search(b))
        return neg_a != neg_b      # one negates, the other affirms

    # ─────────────────── hypothesis generation ───────────────────

    def generate_hypothesis(self, contradiction: dict) -> str:
        a, b = contradiction["a"]["text"], contradiction["b"]["text"]
        client = self.router.client_for("deep_reasoning")
        if not client.is_available():
            shared = self._shared_keywords(a, b)
            topic = ", ".join(list(shared)[:3]) or "the observed effect"
            return f"Under what conditions does the relationship involving {topic} hold versus fail?"
        prompt = (
            f"Two findings appear to contradict:\n"
            f"A: {a}\nB: {b}\n\n"
            f"Propose ONE novel, testable research hypothesis (one sentence) that "
            f"could reconcile or explain the contradiction."
        )
        out = client.chat(prompt, system="You are a creative but rigorous research scientist.")
        return out.strip().strip('"')

    def rank_hypotheses(self, hypotheses: list) -> list:
        """Rank by a simple novelty/specificity heuristic (longer + specific wins)."""
        scored = []
        for h in hypotheses:
            specificity = len(self._shared_keywords(h, h))   # unique content words
            score = min(1.0, 0.3 + specificity * 0.05)
            scored.append({"hypothesis": h, "score": round(score, 3)})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def discover(self, statements: list) -> dict:
        """Full discovery pass over a list of statements."""
        contradictions = self.find_contradictions(statements)
        new_hypotheses = [self.generate_hypothesis(c) for c in contradictions]
        return {
            "n_statements": len(statements),
            "contradictions": contradictions,
            "new_hypotheses": self.rank_hypotheses(new_hypotheses),
        }
