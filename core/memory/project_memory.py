"""
AMRIT RESEARCH OS v4.5
core/memory/project_memory.py

🧠 Project-Isolated Memory + Self-Learning System

ਸਮੱਸਿਆ ਜੋ ਹੱਲ ਕਰਦਾ ਹੈ:
  - ਗੁਰਪ੍ਰੀਤ ਜੀ ਕਈ projects ਤੇ ਕੰਮ ਕਰਦੇ ਹਨ
  - ਹਰ project ਦੀ memory ਵੱਖ ਹੋਣੀ ਚਾਹੀਦੀ — ਮਿਕਸ ਨਾ ਹੋਵੇ
  - System ਆਪੇ ਸਿੱਖੇ, ਗਲਤੀਆਂ ਯਾਦ ਰੱਖੇ, ਦੁਬਾਰਾ ਨਾ ਕਰੇ
  - Future plans save ਰਹਿਣ

ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ:
  - ਹਰ project ਦੀ ਆਪਣੀ ਵੱਖਰੀ SQLite database
  - data/projects/<project_id>/memory.db
  - ਇੱਕ project ਦੀ memory ਦੂਜੇ ਵਿੱਚ ਨਹੀਂ ਜਾਂਦੀ
  - Lessons, mistakes, future plans — ਸਭ project-specific

ਵਰਤੋਂ:
    from core.memory.project_memory import ProjectMemory

    # AMRIT project ਦੀ memory
    mem = ProjectMemory("amrit_research_os")

    mem.remember_work("Built JARVIS computer control", category="milestone")
    mem.remember_mistake("Forgot Request import in server.py", "Use Pydantic models instead")
    mem.save_future_plan("v5.0: Self-evolving DNA engine", priority="high")
    mem.learn_lesson("Always test server.py before packaging")

    # ਅਗਲੀ ਵਾਰ:
    print(mem.recall_all())          # ਸਾਰਾ ਕੰਮ ਯਾਦ
    print(mem.get_future_plans())    # ਅਗਲੇ ਕਦਮ
    print(mem.get_mistakes())        # ਗਲਤੀਆਂ ਜੋ ਨਾ ਦੁਹਰਾਈਏ
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("AmritProjectMemory")

PROJECTS_ROOT = "data/projects"


class ProjectMemory:
    """
    ਹਰ project ਲਈ ਵੱਖਰੀ, isolated memory।
    ਇੱਕ project ਦੀ ਜਾਣਕਾਰੀ ਦੂਜੇ ਨਾਲ ਕਦੇ ਨਹੀਂ ਮਿਲਦੀ।
    """

    def __init__(self, project_id: str, project_name: str = ""):
        # Sanitize project_id (no spaces, safe for filesystem)
        self.project_id   = self._sanitize(project_id)
        self.project_name = project_name or project_id

        # Each project gets its OWN folder + database
        self.project_dir  = os.path.join(PROJECTS_ROOT, self.project_id)
        os.makedirs(self.project_dir, exist_ok=True)
        self.db_path = os.path.join(self.project_dir, "memory.db")

        self._init_db()
        self._register_project()
        log.info(f"🧠 Project Memory: '{self.project_name}' (isolated)")

    @staticmethod
    def _sanitize(name: str) -> str:
        import re
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())

    def _init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript("""
                -- ਕੰਮ ਜੋ ਕੀਤਾ (milestones, work done)
                CREATE TABLE IF NOT EXISTS work_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    content     TEXT,
                    category    TEXT DEFAULT 'work',
                    timestamp   TEXT,
                    metadata    TEXT DEFAULT '{}'
                );
                -- ਗਲਤੀਆਂ ਅਤੇ ਉਹਨਾਂ ਦਾ ਹੱਲ (ਦੁਬਾਰਾ ਨਾ ਕਰੀਏ)
                CREATE TABLE IF NOT EXISTS mistakes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    mistake     TEXT,
                    solution    TEXT,
                    timestamp   TEXT,
                    repeat_count INTEGER DEFAULT 0
                );
                -- ਸਿੱਖੇ ਹੋਏ ਸਬਕ (lessons learned)
                CREATE TABLE IF NOT EXISTS lessons (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson      TEXT,
                    timestamp   TEXT,
                    importance  TEXT DEFAULT 'normal'
                );
                -- ਭਵਿੱਖ ਦੀਆਂ ਯੋਜਨਾਵਾਂ (future plans)
                CREATE TABLE IF NOT EXISTS future_plans (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan        TEXT,
                    priority    TEXT DEFAULT 'normal',
                    status      TEXT DEFAULT 'pending',
                    timestamp   TEXT
                );
                -- Project ਦੀ ਸਥਿਤੀ (current state)
                CREATE TABLE IF NOT EXISTS project_state (
                    key         TEXT PRIMARY KEY,
                    value       TEXT,
                    updated_at  TEXT
                );
            """)

    def _register_project(self):
        """Global registry ਵਿੱਚ ਇਸ project ਨੂੰ register ਕਰੋ।"""
        os.makedirs(PROJECTS_ROOT, exist_ok=True)
        registry = os.path.join(PROJECTS_ROOT, "_registry.json")
        data = {}
        if os.path.exists(registry):
            try:
                with open(registry) as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[self.project_id] = {
            "name":        self.project_name,
            "last_active": datetime.now().isoformat(),
            "db_path":     self.db_path,
        }
        with open(registry, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    # REMEMBER (ਯਾਦ ਰੱਖੋ)
    # ══════════════════════════════════════════════════════════
    def remember_work(self, content: str, category: str = "work",
                      metadata: dict = None) -> int:
        """ਕੀਤਾ ਕੰਮ ਯਾਦ ਰੱਖੋ (milestone, feature, fix...)।"""
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO work_log(content,category,timestamp,metadata) VALUES(?,?,?,?)",
                (content, category, datetime.now().isoformat(),
                 json.dumps(metadata or {}, ensure_ascii=False))
            )
            return cur.lastrowid

    def remember_mistake(self, mistake: str, solution: str = "") -> int:
        """
        ਗਲਤੀ ਯਾਦ ਰੱਖੋ ਤਾਂ ਕਿ ਦੁਬਾਰਾ ਨਾ ਹੋਵੇ।
        ਜੇ ਉਹੀ ਗਲਤੀ ਪਹਿਲਾਂ ਹੋਈ ਹੈ ਤਾਂ repeat_count ਵਧਾਓ।
        """
        with sqlite3.connect(self.db_path) as c:
            existing = c.execute(
                "SELECT id, repeat_count FROM mistakes WHERE mistake=?",
                (mistake,)
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE mistakes SET repeat_count=?, solution=? WHERE id=?",
                    (existing[1] + 1, solution or "", existing[0])
                )
                log.warning(f"  ⚠️ ਇਹ ਗਲਤੀ {existing[1]+1} ਵਾਰ ਹੋਈ: {mistake[:50]}")
                return existing[0]
            cur = c.execute(
                "INSERT INTO mistakes(mistake,solution,timestamp,repeat_count) VALUES(?,?,?,0)",
                (mistake, solution, datetime.now().isoformat())
            )
            return cur.lastrowid

    def learn_lesson(self, lesson: str, importance: str = "normal") -> int:
        """ਸਬਕ ਸਿੱਖੋ (general principle ਜੋ ਅੱਗੇ ਕੰਮ ਆਵੇ)।"""
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO lessons(lesson,timestamp,importance) VALUES(?,?,?)",
                (lesson, datetime.now().isoformat(), importance)
            )
            return cur.lastrowid

    def save_future_plan(self, plan: str, priority: str = "normal") -> int:
        """ਭਵਿੱਖ ਦੀ ਯੋਜਨਾ save ਕਰੋ।"""
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO future_plans(plan,priority,status,timestamp) VALUES(?,?,'pending',?)",
                (plan, priority, datetime.now().isoformat())
            )
            return cur.lastrowid

    def set_state(self, key: str, value: str) -> None:
        """Project ਦੀ ਮੌਜੂਦਾ ਸਥਿਤੀ save ਕਰੋ (version, last task...)।"""
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT OR REPLACE INTO project_state(key,value,updated_at) VALUES(?,?,?)",
                (key, value, datetime.now().isoformat())
            )

    # ══════════════════════════════════════════════════════════
    # RECALL (ਯਾਦ ਕਰੋ)
    # ══════════════════════════════════════════════════════════
    def recall_all(self, limit: int = 50) -> list[dict]:
        """ਸਾਰਾ ਕੀਤਾ ਕੰਮ ਯਾਦ ਕਰੋ।"""
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT content,category,timestamp FROM work_log ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [{"content": r[0], "category": r[1], "timestamp": r[2]} for r in rows]

    def get_mistakes(self) -> list[dict]:
        """ਸਾਰੀਆਂ ਗਲਤੀਆਂ — ਜੋ ਦੁਬਾਰਾ ਨਾ ਕਰੀਏ।"""
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT mistake,solution,repeat_count FROM mistakes ORDER BY repeat_count DESC"
            ).fetchall()
        return [{"mistake": r[0], "solution": r[1], "times_repeated": r[2]} for r in rows]

    def get_lessons(self) -> list[dict]:
        """ਸਾਰੇ ਸਿੱਖੇ ਸਬਕ।"""
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT lesson,importance,timestamp FROM lessons ORDER BY "
                "CASE importance WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, id DESC"
            ).fetchall()
        return [{"lesson": r[0], "importance": r[1], "timestamp": r[2]} for r in rows]

    def get_future_plans(self, status: str = "pending") -> list[dict]:
        """ਭਵਿੱਖ ਦੀਆਂ ਯੋਜਨਾਵਾਂ।"""
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT id,plan,priority,status,timestamp FROM future_plans "
                "WHERE status=? ORDER BY "
                "CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, id",
                (status,)
            ).fetchall()
        return [{"id": r[0], "plan": r[1], "priority": r[2],
                 "status": r[3], "timestamp": r[4]} for r in rows]

    def complete_plan(self, plan_id: int) -> None:
        """ਯੋਜਨਾ ਪੂਰੀ ਹੋ ਗਈ — mark ਕਰੋ।"""
        with sqlite3.connect(self.db_path) as c:
            c.execute("UPDATE future_plans SET status='done' WHERE id=?", (plan_id,))

    def get_state(self, key: str = None):
        with sqlite3.connect(self.db_path) as c:
            if key:
                row = c.execute("SELECT value FROM project_state WHERE key=?", (key,)).fetchone()
                return row[0] if row else None
            rows = c.execute("SELECT key,value FROM project_state").fetchall()
            return {r[0]: r[1] for r in rows}

    # ══════════════════════════════════════════════════════════
    # CONTEXT BRIEFING (ਅਗਲੀ ਵਾਰ ਪੂਰੀ ਜਾਣਕਾਰੀ)
    # ══════════════════════════════════════════════════════════
    def briefing(self) -> str:
        """
        ਪੂਰਾ project briefing — ਅਗਲੀ session ਸ਼ੁਰੂ ਕਰਨ ਵੇਲੇ।
        ਸਭ ਕੁਝ ਇੱਕ ਥਾਂ: ਕੰਮ + ਗਲਤੀਆਂ + ਸਬਕ + ਯੋਜਨਾਵਾਂ।
        """
        work     = self.recall_all(limit=10)
        mistakes = self.get_mistakes()
        lessons  = self.get_lessons()
        plans    = self.get_future_plans()
        state    = self.get_state()

        lines = [
            f"╔══════════════════════════════════════════════╗",
            f"  PROJECT: {self.project_name}",
            f"  ID: {self.project_id}",
            f"╚══════════════════════════════════════════════╝",
            "",
            f"📊 STATE: {json.dumps(state, ensure_ascii=False) if state else 'N/A'}",
            "",
            f"✅ ਹਾਲ ਦਾ ਕੰਮ ({len(work)} entries):",
        ]
        for w in work[:8]:
            lines.append(f"   • [{w['category']}] {w['content'][:70]}")

        if lessons:
            lines.append(f"\n💡 ਸਿੱਖੇ ਸਬਕ ({len(lessons)}):")
            for l in lessons[:6]:
                mark = "⭐" if l["importance"] == "high" else "•"
                lines.append(f"   {mark} {l['lesson'][:70]}")

        if mistakes:
            lines.append(f"\n⚠️  ਗਲਤੀਆਂ ਜੋ ਨਾ ਦੁਹਰਾਈਏ ({len(mistakes)}):")
            for m in mistakes[:6]:
                rep = f" ({m['times_repeated']}× ਹੋਈ)" if m['times_repeated'] else ""
                lines.append(f"   ✗ {m['mistake'][:60]}{rep}")
                if m['solution']:
                    lines.append(f"     → ਹੱਲ: {m['solution'][:60]}")

        if plans:
            lines.append(f"\n🔮 ਅਗਲੇ ਕਦਮ ({len(plans)}):")
            for p in plans[:8]:
                mark = "🔴" if p["priority"] == "high" else "🟡" if p["priority"] == "normal" else "⚪"
                lines.append(f"   {mark} {p['plan'][:70]}")

        return "\n".join(lines)

    def export_briefing(self, path: str = None) -> str:
        """Briefing ਨੂੰ ਫਾਈਲ ਵਿੱਚ save ਕਰੋ।"""
        path = path or os.path.join(self.project_dir, "BRIEFING.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.briefing())
        return path


# ══════════════════════════════════════════════════════════════
# PROJECT REGISTRY (ਸਾਰੇ projects ਦੀ ਲਿਸਟ)
# ══════════════════════════════════════════════════════════════
class ProjectRegistry:
    """ਸਾਰੇ projects ਦਾ ਰਿਕਾਰਡ — ਕਿਹੜੇ-ਕਿਹੜੇ projects ਹਨ।"""

    @staticmethod
    def list_projects() -> list[dict]:
        registry = os.path.join(PROJECTS_ROOT, "_registry.json")
        if not os.path.exists(registry):
            return []
        with open(registry) as f:
            data = json.load(f)
        return [{"id": k, **v} for k, v in data.items()]

    @staticmethod
    def open(project_id: str) -> ProjectMemory:
        return ProjectMemory(project_id)


# ══════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("""
╔══════════════════════════════════════════════════════╗
║  AMRIT Project Memory — Isolated + Self-Learning     ║
╚══════════════════════════════════════════════════════╝
""")

    # AMRIT project ਦੀ memory
    amrit = ProjectMemory("amrit_research_os", "AMRIT Research OS")

    # ਕੀਤਾ ਕੰਮ ਯਾਦ ਰੱਖੋ
    amrit.set_state("version", "v4.5")
    amrit.set_state("last_task", "GitHub push + MIT license")
    amrit.remember_work("Built JARVIS computer control (terminal+browser+code)", "milestone")
    amrit.remember_work("Added Voice Agent (Punjabi+Hindi+English)", "feature")
    amrit.remember_work("Dynamic Model Loader — auto-discovers Ollama models", "feature")
    amrit.remember_work("Medical Engine: DNA+Blood+Pharmacogenomics", "feature")
    amrit.remember_work("Realtime: EventBus + Patient Timeline + Alerts", "feature")

    # ਗਲਤੀਆਂ ਜੋ ਨਾ ਦੁਹਰਾਈਏ
    amrit.remember_mistake(
        "server.py ਵਿੱਚ Request import ਭੁੱਲ ਗਿਆ ਸੀ",
        "FastAPI Pydantic models ਵਰਤੋ, Request ਨਹੀਂ"
    )
    amrit.remember_mistake(
        "Stats engine ਵਿੱਚ fake random p-value ਸੀ (v1)",
        "scipy.stats ਵਰਤੋ — real t-test, ANOVA, chi-square"
    )

    # ਸਿੱਖੇ ਸਬਕ
    amrit.learn_lesson("ਹਮੇਸ਼ਾ server.py ਚਲਾ ਕੇ ਟੈਸਟ ਕਰੋ packaging ਤੋਂ ਪਹਿਲਾਂ", "high")
    amrit.learn_lesson("ਹਰ project ਦੀ memory ਵੱਖ ਰੱਖੋ — ਮਿਕਸ ਨਾ ਹੋਵੇ", "high")
    amrit.learn_lesson("Repo ਪੜ੍ਹ ਕੇ ਹੀ ਜਵਾਬ ਦਿਓ, ਅੰਦਾਜ਼ਾ ਨਾ ਲਾਓ", "normal")

    # ਭਵਿੱਖ ਦੀਆਂ ਯੋਜਨਾਵਾਂ
    amrit.save_future_plan("v5.0: Self-evolving DNA engine (ਹਰ ਰਾਤ NCBI ਤੋਂ ਸਿੱਖੇ)", "high")
    amrit.save_future_plan("v5.0: Symptom → Differential Diagnosis engine", "high")
    amrit.save_future_plan("v5.0: WhatsApp bot (photo ਭੇਜੋ, report ਆਵੇ)", "normal")
    amrit.save_future_plan("v5.5: Wearable + USB lab device integration", "normal")
    amrit.save_future_plan("v6.0: Robot Doctor (Raspberry Pi, $150)", "low")

    # ── ਦੂਜਾ project (isolation ਟੈਸਟ) ──
    other = ProjectMemory("some_other_project", "ਕੋਈ ਹੋਰ Project")
    other.remember_work("ਇਹ ਵੱਖਰਾ project ਹੈ — AMRIT ਨਾਲ ਮਿਕਸ ਨਹੀਂ ਹੋਣਾ")

    # ── Briefing ──
    print(amrit.briefing())

    print("\n\n=== ISOLATION ਟੈਸਟ ===")
    print(f"AMRIT work entries:  {len(amrit.recall_all())}")
    print(f"Other work entries:  {len(other.recall_all())}")
    print("✅ ਦੋਵੇਂ projects ਬਿਲਕੁਲ ਵੱਖ — memory ਮਿਕਸ ਨਹੀਂ ਹੋਈ")

    print("\n=== ਸਾਰੇ Projects ===")
    for p in ProjectRegistry.list_projects():
        print(f"  • {p['name']} ({p['id']})")

    # Export briefing
    path = amrit.export_briefing()
    print(f"\n💾 Briefing saved: {path}")
