"""
AMRIT RESEARCH OS v3.0
core/memory/memory_manager.py

Memory System:
- SQLite based persistent storage
- Research History
- Previous Findings
- Hypothesis Evolution
- Self Evolution tracking
"""

import sqlite3
import datetime
import os


class MemoryManager:

    def __init__(self, db_path: str = "data/research.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                hypothesis   TEXT NOT NULL,
                domain       TEXT,
                dataset      TEXT,
                result       TEXT,
                verdict      TEXT,
                p_value      REAL,
                effect_size  REAL,
                date         TEXT DEFAULT (datetime('now')),
                citation_apa TEXT,
                citation_mla TEXT,
                citation_ieee TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS hypothesis_evolution (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                original        TEXT,
                revised         TEXT,
                reason          TEXT,
                evolved_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_reviews (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id   INTEGER REFERENCES findings(id),
                agent_name   TEXT,
                review       TEXT,
                reviewed_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS self_evolution (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT,   -- 'failed' | 'successful' | 'best_method'
                content      TEXT,
                recorded_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        self.conn.commit()

    # ─────────────────────────── Store ───────────────────────────

    def store_result(
        self,
        hypothesis: str,
        result: dict,
        domain: str = "",
        dataset: str = "",
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO findings
                (hypothesis, domain, dataset, result, verdict, p_value, effect_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hypothesis,
                domain,
                dataset,
                str(result),
                result.get("verdict", ""),
                result.get("p_value", None),
                result.get("effect_size", None),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def store_agent_review(
        self, finding_id: int, agent_name: str, review: str
    ):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO agent_reviews (finding_id, agent_name, review) VALUES (?,?,?)",
            (finding_id, agent_name, review),
        )
        self.conn.commit()

    def record_evolution(self, category: str, content: str):
        """Record a lesson learned (failed/successful hypothesis, best method)."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO self_evolution (category, content) VALUES (?,?)",
            (category, content),
        )
        self.conn.commit()

    def update_citations(self, finding_id: int, apa: str, mla: str, ieee: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE findings
            SET citation_apa=?, citation_mla=?, citation_ieee=?
            WHERE id=?
            """,
            (apa, mla, ieee, finding_id),
        )
        self.conn.commit()

    # ─────────────────────────── Retrieve ───────────────────────────

    def get_all_findings(self) -> list:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM findings ORDER BY date DESC")
        return cur.fetchall()

    def get_successful_hypotheses(self) -> list:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT hypothesis, verdict, p_value FROM findings WHERE verdict IN ('STRONG SUPPORT','WEAK SUPPORT')"
        )
        return cur.fetchall()

    def get_failed_hypotheses(self) -> list:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT hypothesis, verdict FROM findings WHERE verdict = 'NOT SUPPORTED'"
        )
        return cur.fetchall()

    def get_evolution_lessons(self) -> list:
        cur = self.conn.cursor()
        cur.execute("SELECT category, content, recorded_at FROM self_evolution ORDER BY recorded_at DESC")
        return cur.fetchall()

    def summary(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM findings")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM findings WHERE verdict IN ('STRONG SUPPORT','WEAK SUPPORT')")
        successes = cur.fetchone()[0]
        return {
            "total_experiments": total,
            "successful": successes,
            "failed": total - successes,
        }
