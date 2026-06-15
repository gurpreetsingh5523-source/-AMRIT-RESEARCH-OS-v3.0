"""
AMRIT RESEARCH OS v4.5
core/realtime/patient_timeline.py

Patient ਦੀ ਪੂਰੀ journey track ਕਰਦਾ ਹੈ — data ਤੋਂ ਦਵਾਈ ਤੱਕ।
SQLite ਵਿੱਚ persistent storage।

Timeline Steps:
  1. INGESTED       → Data received
  2. ANALYSING      → Medical pipeline running
  3. PATTERNS       → PatternAnalyzer running
  4. REPORT_READY   → PDF generated
  5. DOCTOR_QUEUE   → Waiting for doctor review
  6. APPROVED       → Doctor verified
  7. DISPATCHED     → Sent to medical center
  8. COMPLETED      → Patient collected medicine
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("AmritTimeline")

DB_PATH = "data/amrit_medical.db"

STEPS = [
    "INGESTED", "ANALYSING", "PATTERNS",
    "REPORT_READY", "DOCTOR_QUEUE", "APPROVED",
    "DISPATCHED", "COMPLETED",
]


class PatientTimeline:
    """
    Persistent patient journey tracker using SQLite.
    Each patient has a timeline of steps with timestamps.
    """

    def __init__(self, db_path: str = DB_PATH):
        import os
        os.makedirs("data", exist_ok=True)
        self.db = db_path
        self._init_db()
        log.info(f"📋 PatientTimeline ready → {db_path}")

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id   TEXT PRIMARY KEY,
                    name         TEXT,
                    age          INTEGER,
                    gender       TEXT,
                    created_at   TEXT,
                    current_step TEXT DEFAULT 'INGESTED',
                    severity     TEXT DEFAULT 'UNKNOWN',
                    metadata     TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS timeline_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id   TEXT,
                    step         TEXT,
                    timestamp    TEXT,
                    details      TEXT DEFAULT '',
                    actor        TEXT DEFAULT 'system',
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
                );
                CREATE TABLE IF NOT EXISTS lab_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id   TEXT,
                    marker       TEXT,
                    value        REAL,
                    unit         TEXT,
                    status       TEXT,
                    timestamp    TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
                );
            """)

    # ── Patient Management ────────────────────────────────────
    def add_patient(self, patient_id: str, name: str,
                    age: int = 0, gender: str = "unknown",
                    metadata: dict = None) -> bool:
        try:
            with sqlite3.connect(self.db) as c:
                c.execute(
                    "INSERT OR IGNORE INTO patients VALUES (?,?,?,?,?,?,?,?)",
                    (patient_id, name, age, gender,
                     datetime.now().isoformat(),
                     "INGESTED", "UNKNOWN",
                     json.dumps(metadata or {}))
                )
                self._log_step(c, patient_id, "INGESTED", "Patient data received")
            log.info(f"  ➕ Patient added: {name} ({patient_id})")
            return True
        except Exception as e:
            log.error(f"  ❌ add_patient error: {e}")
            return False

    def advance_step(self, patient_id: str, step: str,
                     details: str = "", actor: str = "system") -> bool:
        """Move patient to next pipeline step."""
        if step not in STEPS:
            log.warning(f"Unknown step: {step}")
            return False
        try:
            with sqlite3.connect(self.db) as c:
                c.execute(
                    "UPDATE patients SET current_step=? WHERE patient_id=?",
                    (step, patient_id)
                )
                self._log_step(c, patient_id, step, details, actor)
            log.info(f"  ⏩ {patient_id} → {step}")
            return True
        except Exception as e:
            log.error(f"  ❌ advance_step error: {e}")
            return False

    def set_severity(self, patient_id: str, severity: str) -> None:
        """CRITICAL | MODERATE | NORMAL"""
        with sqlite3.connect(self.db) as c:
            c.execute(
                "UPDATE patients SET severity=? WHERE patient_id=?",
                (severity.upper(), patient_id)
            )

    # ── Lab History ───────────────────────────────────────────
    def add_lab_values(self, patient_id: str,
                       flags: list[dict]) -> int:
        """Store blood report abnormal flags to lab_history."""
        stored = 0
        ts = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db) as c:
                for f in flags:
                    c.execute(
                        "INSERT INTO lab_history(patient_id,marker,value,unit,status,timestamp) VALUES(?,?,?,?,?,?)",
                        (patient_id,
                         f.get("marker",""),
                         f.get("value", 0),
                         f.get("unit", ""),
                         f.get("status",""),
                         ts)
                    )
                    stored += 1
        except Exception as e:
            log.error(f"  ❌ lab history error: {e}")
        return stored

    def get_lab_history(self, patient_id: str,
                        marker: str = None,
                        limit: int = 20) -> list[dict]:
        """Get lab value history for a patient (for trend charts)."""
        query = "SELECT marker,value,unit,status,timestamp FROM lab_history WHERE patient_id=?"
        params: list = [patient_id]
        if marker:
            query += " AND marker LIKE ?"
            params.append(f"%{marker}%")
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        try:
            with sqlite3.connect(self.db) as c:
                rows = c.execute(query, params).fetchall()
            return [
                {"marker": r[0], "value": r[1], "unit": r[2],
                 "status": r[3], "timestamp": r[4]}
                for r in rows
            ]
        except Exception as e:
            log.error(f"lab_history query error: {e}")
            return []

    # ── Queries ───────────────────────────────────────────────
    def get_patient(self, patient_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT * FROM patients WHERE patient_id=?",
                (patient_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "patient_id": row[0], "name": row[1], "age": row[2],
            "gender": row[3], "created_at": row[4],
            "current_step": row[5], "severity": row[6],
            "metadata": json.loads(row[7] or "{}"),
        }

    def get_journey(self, patient_id: str) -> list[dict]:
        """Full timeline for a patient."""
        with sqlite3.connect(self.db) as c:
            rows = c.execute(
                "SELECT step,timestamp,details,actor FROM timeline_events "
                "WHERE patient_id=? ORDER BY timestamp",
                (patient_id,)
            ).fetchall()
        return [{"step": r[0], "timestamp": r[1],
                 "details": r[2], "actor": r[3]} for r in rows]

    def get_pending_doctor_queue(self) -> list[dict]:
        """All patients waiting for doctor approval."""
        with sqlite3.connect(self.db) as c:
            rows = c.execute(
                "SELECT patient_id,name,age,gender,severity,created_at "
                "FROM patients WHERE current_step='DOCTOR_QUEUE' "
                "ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'MODERATE' THEN 1 ELSE 2 END"
            ).fetchall()
        return [{"patient_id": r[0], "name": r[1], "age": r[2],
                 "gender": r[3], "severity": r[4], "created_at": r[5]}
                for r in rows]

    def get_dashboard_stats(self) -> dict:
        """Summary stats for the dashboard metric cards."""
        with sqlite3.connect(self.db) as c:
            total     = c.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            pending   = c.execute("SELECT COUNT(*) FROM patients WHERE current_step NOT IN ('COMPLETED','DISPATCHED')").fetchone()[0]
            reports   = c.execute("SELECT COUNT(*) FROM patients WHERE current_step IN ('REPORT_READY','DOCTOR_QUEUE','APPROVED','DISPATCHED','COMPLETED')").fetchone()[0]
            approved  = c.execute("SELECT COUNT(*) FROM patients WHERE current_step IN ('APPROVED','DISPATCHED','COMPLETED')").fetchone()[0]
            dispatched= c.execute("SELECT COUNT(*) FROM patients WHERE current_step IN ('DISPATCHED','COMPLETED')").fetchone()[0]
            critical  = c.execute("SELECT COUNT(*) FROM patients WHERE severity='CRITICAL' AND current_step NOT IN ('COMPLETED')").fetchone()[0]
        return {
            "total_patients": total,
            "pending":        pending,
            "reports":        reports,
            "approved":       approved,
            "dispatched":     dispatched,
            "critical_alerts":critical,
        }

    def _log_step(self, conn, patient_id: str, step: str,
                  details: str = "", actor: str = "system"):
        conn.execute(
            "INSERT INTO timeline_events(patient_id,step,timestamp,details,actor) VALUES(?,?,?,?,?)",
            (patient_id, step, datetime.now().isoformat(), details, actor)
        )
