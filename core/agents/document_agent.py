"""
AMRIT RESEARCH OS v4.0
core/agents/document_agent.py

Document Analysis Agent.

Takes pasted / uploaded document text and produces a structured analysis:
  - summary
  - key points
  - extracted claims
  - validation notes (statistics-aware)
  - actionable suggestions
  - a refined report (via the self-critique loop)

Uses ModelRouter for LLM reasoning and SelfCritiqueLoop to polish the report.
Falls back to a lightweight heuristic when Ollama is offline.
"""

import re

from core.models.router import ModelRouter
from core.agents.critic import SelfCritiqueLoop


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").strip())


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


class DocumentAgent:

    def __init__(self, router: ModelRouter = None):
        self.router = router or ModelRouter()
        self.critic = SelfCritiqueLoop(self.router, cycles=2)

    # ─────────────────── helpers ───────────────────

    def _ask(self, task: str, prompt: str, system: str) -> str:
        client = self.router.client_for(task)
        if not client.is_available():
            return ""
        out = client.chat(prompt, system=system).strip()
        return "" if out.startswith("[Ollama") or out.startswith("[Error") else out

    @staticmethod
    def _heuristic_summary(text: str) -> str:
        sents = _sentences(text)
        return " ".join(sents[:3]) if sents else text[:300]

    @staticmethod
    def _heuristic_claims(text: str):
        markers = re.compile(
            r"\b(causes?|increases?|decreases?|improves?|reduces?|leads? to|"
            r"results? in|correlat|associat|prevents?|significant)\b", re.I)
        return [s for s in _sentences(text) if markers.search(s)][:8]

    # ─────────────────── pipeline ───────────────────

    def analyse(self, text: str, refine: bool = True) -> dict:
        text = _clean(text)
        if not text:
            return {"error": "empty document"}

        excerpt = text[:6000]      # keep prompt within context budget
        online = self.router.available()

        summary = self._ask(
            "research",
            f"Summarise this document in 3-4 sentences:\n\n{excerpt}",
            "You are an expert research analyst. Be precise and neutral.",
        ) or self._heuristic_summary(text)

        key_points_raw = self._ask(
            "research",
            f"List the 5 most important points as short bullet lines:\n\n{excerpt}",
            "You extract key points. Output one point per line, no preamble.",
        )
        key_points = [l.strip("-• \t") for l in key_points_raw.splitlines() if l.strip()][:8] \
            if key_points_raw else self._heuristic_claims(text)[:5]

        claims_raw = self._ask(
            "deep_reasoning",
            f"Extract the document's testable claims, one per line:\n\n{excerpt}",
            "You identify factual/testable claims only. One claim per line.",
        )
        claims = [l.strip("-• \t") for l in claims_raw.splitlines() if l.strip()][:8] \
            if claims_raw else self._heuristic_claims(text)

        validation = self._ask(
            "deep_reasoning",
            f"Critically evaluate the evidence quality, possible biases and "
            f"what is missing in this document:\n\n{excerpt}",
            "You are a rigorous peer reviewer. Be specific and critical.",
        ) or "Offline: unable to run LLM validation. Claims listed require external verification."

        suggestions = self._ask(
            "planning",
            f"Give 3-5 concrete, actionable next-step suggestions based on this "
            f"document:\n\n{excerpt}",
            "You are a strategic advisor. Output numbered, concrete actions.",
        ) or "1. Verify each claim against primary sources.\n2. Seek replication.\n3. Quantify effect sizes."

        report = (
            f"SUMMARY\n{summary}\n\n"
            f"KEY POINTS\n" + "\n".join(f"- {k}" for k in key_points) + "\n\n"
            f"CLAIMS\n" + "\n".join(f"- {c}" for c in claims) + "\n\n"
            f"VALIDATION\n{validation}\n\n"
            f"SUGGESTIONS\n{suggestions}"
        )

        critique = {}
        if refine and online:
            refined = self.critic.run(report, context="Document analysis report")
            report = refined["final_draft"]
            critique = {"score": refined["final_score"], "cycles": refined["cycles_run"]}

        return {
            "chars": len(text),
            "online": online,
            "summary": summary,
            "key_points": key_points,
            "claims": claims,
            "validation": validation,
            "suggestions": suggestions,
            "report": report,
            "critique": critique,
        }
