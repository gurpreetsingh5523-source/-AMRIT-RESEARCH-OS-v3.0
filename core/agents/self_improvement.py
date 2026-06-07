"""
AMRIT RESEARCH OS v4.0
core/agents/self_improvement.py

Self-Learning · Skill Creation · Automatic Tool Building.

Three capabilities:

  1. learn()        - self-learning: distil lessons from recent memory into
                      the long_term_memory vector collection so the system
                      gets better over time.

  2. create_skill() - skill creation: generate a structured, reusable skill
                      (goal + ordered steps) and persist it to disk.

  3. build_tool()   - automatic tool building: generate a Python `run(**kwargs)`
                      function from a description, VALIDATE it in the sandbox,
                      persist it, and register it live in the ToolManager.

Safety: generated tool code is always validated in the existing sandbox
(static blocklist + isolated subprocess) before it is registered. Tools
that fail validation are never registered.
"""

import os
import re
import json
import datetime

from core.models.router import ModelRouter


SKILL_SYSTEM = (
    "You design reusable skills for an autonomous research system. Given a "
    "skill name and description, output ONLY:\n"
    "GOAL: <one line>\n"
    "STEPS:\n- <step>\n- <step>\n- <step>\n"
    "WHEN_TO_USE: <one line>\n"
)

TOOL_SYSTEM = (
    "You write small, dependency-free Python tools. Output ONLY a Python "
    "function named `run` that takes keyword arguments and RETURNS a "
    "JSON-serialisable dict (no printing, no file/network access, stdlib "
    "only). No explanation, no markdown fences."
)

LEARN_SYSTEM = (
    "You are a reflective learner. From the notes below, distil 3-5 concise, "
    "general lessons that would improve future research. One lesson per line, "
    "start each with '- '. No preamble."
)


class SkillFactory:

    def __init__(self, router: ModelRouter = None, sandbox=None,
                 vector_memory=None, tools=None,
                 skills_dir: str = "data/skills",
                 tools_dir: str = "data/built_tools"):
        self.router = router or ModelRouter()
        self.sandbox = sandbox
        self.vmem = vector_memory
        self.tools = tools                     # ToolManager (for live registration)
        self.skills_dir = skills_dir
        self.tools_dir = tools_dir
        os.makedirs(skills_dir, exist_ok=True)
        os.makedirs(tools_dir, exist_ok=True)
        self._reload_built_tools()

    # ─────────────────── helpers ───────────────────

    def _ask(self, task: str, prompt: str, system: str) -> str:
        client = self.router.client_for(task)
        if not client.is_available():
            return ""
        out = client.chat(prompt, system=system).strip()
        return "" if out.startswith("[Ollama") or out.startswith("[Error") else out

    @staticmethod
    def _strip_fences(code: str) -> str:
        code = re.sub(r"^```[a-zA-Z]*\n?", "", code.strip())
        code = re.sub(r"\n?```$", "", code.strip())
        return code.strip()

    # ─────────────────── 1. self-learning ───────────────────

    def learn(self, extra_note: str = "") -> dict:
        """Distil lessons from recent memory into long_term_memory."""
        notes = []
        if self.vmem and self.vmem.enabled:
            for coll in ("research_notes", "conversations", "discoveries"):
                for hit in self.vmem.search(coll, extra_note or "research findings", k=3):
                    if hit.get("text"):
                        notes.append(hit["text"])
        if extra_note:
            notes.append(extra_note)
        if not notes:
            return {"learned": [], "stored": 0, "reason": "no source notes available"}

        raw = self._ask("deep_reasoning", "NOTES:\n" + "\n".join(notes[:12]), LEARN_SYSTEM)
        lessons = [l.strip("-• \t") for l in raw.splitlines() if l.strip()] if raw else []
        if not lessons:
            # offline heuristic: keep the most informative note
            lessons = [notes[0][:200]]

        stored = 0
        if self.vmem and self.vmem.enabled:
            for lesson in lessons:
                if self.vmem.add("long_term_memory", lesson, {"type": "lesson"}):
                    stored += 1
        return {"learned": lessons, "stored": stored}

    # ─────────────────── 2. skill creation ───────────────────

    def create_skill(self, name: str, description: str) -> dict:
        raw = self._ask("planning", f"Skill: {name}\nDescription: {description}", SKILL_SYSTEM)
        goal, steps, when = "", [], ""
        for line in (raw or "").splitlines():
            s = line.strip()
            if s.upper().startswith("GOAL:"):
                goal = s.split(":", 1)[1].strip()
            elif s.upper().startswith("WHEN_TO_USE:"):
                when = s.split(":", 1)[1].strip()
            elif s.startswith("-"):
                steps.append(s.strip("-• \t"))
        if not steps:  # offline fallback
            goal = goal or description
            steps = [f"Understand the goal: {description}",
                     "Gather the relevant inputs",
                     "Apply the method and validate the result"]

        skill = {
            "name": name,
            "slug": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "goal": goal or description,
            "steps": steps,
            "when_to_use": when,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        path = os.path.join(self.skills_dir, skill["slug"] + ".json")
        with open(path, "w") as f:
            json.dump(skill, f, indent=2)
        if self.vmem and self.vmem.enabled:
            self.vmem.add("long_term_memory",
                          f"Skill '{name}': {skill['goal']}",
                          {"type": "skill"})
        return skill

    def list_skills(self) -> list:
        out = []
        for fn in sorted(os.listdir(self.skills_dir)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(self.skills_dir, fn)) as f:
                        out.append(json.load(f))
                except Exception:
                    pass
        return out

    # ─────────────────── 3. automatic tool building ───────────────────

    def _validate_code(self, code: str, test_args: dict) -> dict:
        """Run the generated tool in the sandbox with test args."""
        if not self.sandbox:
            return {"ok": False, "reason": "no sandbox attached"}
        harness = (
            "import json\n"
            f"ARGS = json.loads('''{json.dumps(test_args)}''')\n"
            + code + "\n"
            "print('<<RESULT>>' + json.dumps(run(**ARGS)))\n"
        )
        res = self.sandbox.run(harness)
        if not res.get("ok"):
            return {"ok": False, "reason": res.get("reason") or res.get("stderr") or "execution failed"}
        out = res.get("stdout", "")
        marker = out.rfind("<<RESULT>>")
        sample = None
        if marker != -1:
            try:
                sample = json.loads(out[marker + len("<<RESULT>>"):].strip())
            except Exception:
                sample = None
        return {"ok": True, "sample_output": sample}

    def build_tool(self, name: str, description: str,
                   test_args: dict = None, code: str = "") -> dict:
        """Generate (or accept) a `run(**kwargs)` tool, validate, persist, register."""
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        test_args = test_args or {}

        if not code:
            code = self._ask(
                "coding",
                f"Tool name: {name}\nWhat it should do: {description}\n"
                f"It will be called as run(**{json.dumps(test_args)}).",
                TOOL_SYSTEM,
            )
            code = self._strip_fences(code)
        if not code or "def run" not in code:
            return {"ok": False, "name": name,
                    "reason": "no valid tool code generated (model offline or bad output)",
                    "code": code}

        check = self._validate_code(code, test_args)
        if not check["ok"]:
            return {"ok": False, "name": name, "reason": check["reason"], "code": code}

        # Persist code + metadata
        py_path = os.path.join(self.tools_dir, slug + ".py")
        with open(py_path, "w") as f:
            f.write(code)
        meta = {
            "name": name, "slug": slug, "description": description,
            "test_args": test_args, "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        with open(os.path.join(self.tools_dir, slug + ".json"), "w") as f:
            json.dump(meta, f, indent=2)

        self._register_tool(slug, code)
        return {"ok": True, "name": name, "slug": slug,
                "sample_output": check.get("sample_output"), "code": code}

    def _register_tool(self, slug: str, code: str):
        """Register a live tool in the ToolManager that runs via the sandbox."""
        if not self.tools:
            return

        def _runner(**kwargs):
            return self._validate_code(code, kwargs).get("sample_output")

        self.tools.registry["built_" + slug] = _runner

    def _reload_built_tools(self):
        """Re-register previously built tools on startup."""
        if not os.path.isdir(self.tools_dir):
            return
        for fn in os.listdir(self.tools_dir):
            if fn.endswith(".py"):
                slug = fn[:-3]
                try:
                    with open(os.path.join(self.tools_dir, fn)) as f:
                        self._register_tool(slug, f.read())
                except Exception:
                    pass

    def list_built_tools(self) -> list:
        out = []
        if not os.path.isdir(self.tools_dir):
            return out
        for fn in sorted(os.listdir(self.tools_dir)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(self.tools_dir, fn)) as f:
                        out.append(json.load(f))
                except Exception:
                    pass
        return out
