"""
AMRIT RESEARCH OS v4.5
core/agents/planner_agent.py

Research Planner Agent.

Pipeline:
    Question -> Planner -> Research Tasks -> Agents -> Validator -> Report

  1. Planner   : break the question into 3-5 concrete research sub-tasks.
  2. Tasks     : for each sub-task, gather evidence (ArXiv) + reason with the
                 best model to produce a finding.
  3. Validator : the SelfCritiqueLoop scores the synthesised draft and the
                 draft is improved until it passes the threshold.
  4. Report    : a final structured report (optionally exported to PDF).

Everything is offline-safe: if Ollama is unavailable the agent falls back
to heuristic task splitting and skips LLM reasoning.
"""

import re

from core.models.router import ModelRouter
from core.agents.critic import SelfCritiqueLoop


PLANNER_SYSTEM = (
    "You are a research planner. Given a question, break it into 3 to 5 "
    "concrete, independent research sub-tasks. Reply with ONLY a numbered "
    "list, one sub-task per line, no preamble."
)

TASK_SYSTEM = (
    "You are a domain researcher. Using the provided evidence snippets and "
    "your knowledge, answer the sub-task in 3-5 sentences. Be specific and "
    "note uncertainty where evidence is weak."
)

SYNTH_SYSTEM = (
    "You are a senior researcher. Synthesise the sub-task findings into a "
    "single coherent report with: Overview, Key Findings, Open Questions, "
    "and a one-line Conclusion. Be rigorous and concise."
)


class ResearchPlannerAgent:

    def __init__(self, router: ModelRouter = None, data=None, tools=None):
        self.router = router or ModelRouter()
        self.data = data
        self.tools = tools
        self.critic = SelfCritiqueLoop(self.router, cycles=2, threshold=0.85)

    # ─────────────────── helpers ───────────────────

    def _ask(self, task: str, prompt: str, system: str) -> str:
        client = self.router.client_for(task)
        if not client.is_available():
            return ""
        out = client.chat(prompt, system=system).strip()
        return "" if out.startswith("[Ollama") or out.startswith("[Error") else out

    def _plan(self, question: str) -> list:
        raw = self._ask("planning", f"Question: {question}", PLANNER_SYSTEM)
        tasks = []
        for line in raw.splitlines():
            line = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip("-• \t")
            if line:
                tasks.append(line)
        if not tasks:  # offline / empty -> heuristic split
            tasks = [
                f"Background and definitions for: {question}",
                f"Current evidence and key studies on: {question}",
                f"Limitations, risks and open questions for: {question}",
            ]
        return tasks[:5]

    def _evidence(self, query: str, k: int = 3) -> list:
        if not self.data:
            return []
        try:
            papers = self.data.search_arxiv(query, max_results=k)
        except Exception:
            return []
        return [p for p in papers if p.get("title")]

    # ─────────────────── pipeline ───────────────────

    def run(self, question: str, gather_evidence: bool = True) -> dict:
        plan = self._plan(question)

        tasks = []
        for sub in plan:
            evidence = self._evidence(sub) if gather_evidence else []
            ev_text = "\n".join(
                f"- {e.get('title','')}: {e.get('summary','')}" for e in evidence
            ) or "(no external evidence retrieved)"
            finding = self._ask(
                "research",
                f"Sub-task: {sub}\n\nEvidence:\n{ev_text}\n\nAnswer the sub-task.",
                TASK_SYSTEM,
            ) or f"(offline) Could not reason about: {sub}"
            tasks.append({
                "task": sub,
                "evidence": [{"title": e.get("title", ""), "link": e.get("link", "")}
                             for e in evidence],
                "finding": finding,
            })

        # Synthesise a draft from all findings
        joined = "\n\n".join(f"### {t['task']}\n{t['finding']}" for t in tasks)
        draft = self._ask(
            "deep_reasoning",
            f"Question: {question}\n\nSub-task findings:\n{joined}\n\nWrite the report.",
            SYNTH_SYSTEM,
        ) or joined

        # Validate + improve via the self-critique loop
        validated = self.critic.run(draft, context=f"Research question: {question}")

        return {
            "question": question,
            "plan": plan,
            "tasks": tasks,
            "draft": draft,
            "report": validated["final_draft"],
            "validation_score": validated["final_score"],
            "validation_cycles": validated["cycles_run"],
            "validation_history": validated["history"],
            "online": bool(self.router.available()),
        }
