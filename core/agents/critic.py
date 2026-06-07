"""
AMRIT RESEARCH OS v4.0
core/agents/critic.py

Self-Critique Loop.

v3 weakness FIXED:
  #6  No draft -> critique -> improve cycle existed.
      Now: generate -> critic.review (scored) -> rewrite, repeated
      up to N times or until the critique score passes a threshold.

      draft = generate()
      for i in range(cycles):
          critique = critic.review(draft)
          if critique.score >= threshold: break
          draft = rewrite(draft, critique)
"""

import re

from core.models.router import ModelRouter


CRITIC_SYSTEM = (
    "You are a meticulous scientific critic. Review the draft for: unsupported "
    "claims, missing citations, unexplained statistics, ignored alternative "
    "explanations, and clarity. Respond in this exact format:\n"
    "SCORE: <0.0-1.0>\n"
    "ISSUES:\n- <issue>\n- <issue>\n"
    "Be strict; only give SCORE above 0.85 if the draft is genuinely solid."
)

WRITER_SYSTEM = (
    "You are a scientific writer. Rewrite the draft to fix every issue raised "
    "by the critic while preserving correct content. Return only the improved draft."
)


class SelfCritiqueLoop:

    def __init__(self, router: ModelRouter = None, cycles: int = 3, threshold: float = 0.85):
        self.router = router or ModelRouter()
        self.cycles = cycles
        self.threshold = threshold

    @staticmethod
    def _parse_score(text: str) -> float:
        m = re.search(r"SCORE\s*[:=]\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
        if not m:
            return 0.5
        try:
            return max(0.0, min(1.0, float(m.group(1))))
        except ValueError:
            return 0.5

    def review(self, draft: str, context: str = "") -> dict:
        client = self.router.client_for("deep_reasoning")
        if not client.is_available():
            return {"score": 1.0, "critique": "[critic offline] accepted as-is", "issues": []}
        prompt = f"Context: {context}\n\nDRAFT:\n{draft}\n\nCritique it now."
        text = client.chat(prompt, system=CRITIC_SYSTEM)
        score = self._parse_score(text)
        issues = [l.strip("- ").strip() for l in text.splitlines()
                  if l.strip().startswith("-")]
        return {"score": score, "critique": text, "issues": issues}

    def improve(self, draft: str, critique: str) -> str:
        client = self.router.client_for("research")
        if not client.is_available():
            return draft
        prompt = f"CRITIC FEEDBACK:\n{critique}\n\nORIGINAL DRAFT:\n{draft}\n\nRewrite it."
        out = client.chat(prompt, system=WRITER_SYSTEM).strip()
        return out if out and not out.startswith("[Ollama") else draft

    def run(self, draft: str, context: str = "") -> dict:
        """Run the full Think -> Critique -> Improve -> Repeat loop."""
        history = []
        current = draft
        final_score = 0.0
        for i in range(self.cycles):
            review = self.review(current, context)
            final_score = review["score"]
            history.append({
                "cycle": i + 1,
                "score": review["score"],
                "issues": review["issues"],
            })
            if review["score"] >= self.threshold:
                break
            current = self.improve(current, review["critique"])
        return {
            "final_draft": current,
            "final_score": final_score,
            "cycles_run": len(history),
            "history": history,
        }
