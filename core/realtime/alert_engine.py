"""
AMRIT RESEARCH OS v4.5
core/realtime/alert_engine.py  +  core/realtime/live_monitor.py

AlertEngine:
  - ਹਰ lab value ਨੂੰ check ਕਰਦਾ ਹੈ
  - Critical/moderate alerts fire ਕਰਦਾ ਹੈ
  - EventBus ਤੇ publish ਕਰਦਾ ਹੈ
  - SQLite ਵਿੱਚ store ਕਰਦਾ ਹੈ
  - WebSocket ਰਾਹੀਂ dashboard ਨੂੰ push ਕਰਦਾ ਹੈ

LiveMonitor:
  - Background thread — ਹਰ 30 ਸਕਿੰਟ ਵਿੱਚ check
  - ਨਵੇਂ patients detect ਕਰਦਾ ਹੈ
  - Pending analyses run ਕਰਦਾ ਹੈ
  - PatternAnalyzer update ਕਰਦਾ ਹੈ
  - Dashboard ਨੂੰ live data push ਕਰਦਾ ਹੈ
"""

import threading
import time
import logging
import json
import sqlite3
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger("AmritRealtime")

DB_PATH = "data/amrit_medical.db"

# ══════════════════════════════════════════════════════════════
# ALERT ENGINE
# ══════════════════════════════════════════════════════════════
class AlertEngine:
    """
    Real-time clinical alert system.
    Fires alerts when lab values cross critical thresholds.
    """

    # Clinical thresholds — immediate alert values
    CRITICAL_THRESHOLDS = {
        "Hemoglobin":      {"low": 7.0,  "high": 20.0, "unit": "g/dL"},
        "Glucose":         {"low": 50.0, "high": 400.0,"unit": "mg/dL"},
        "Platelets":       {"low": 50.0, "high": 1000.0,"unit":"×10³/μL"},
        "Creatinine":      {"low": 0.0,  "high": 5.0,  "unit": "mg/dL"},
        "ALT":             {"low": 0.0,  "high": 200.0, "unit": "U/L"},
        "AST":             {"low": 0.0,  "high": 200.0, "unit": "U/L"},
        "Potassium":       {"low": 2.5,  "high": 6.5,  "unit": "mEq/L"},
        "Sodium":          {"low": 120.0,"high": 155.0, "unit": "mEq/L"},
        "Total Bilirubin": {"low": 0.0,  "high": 10.0, "unit": "mg/dL"},
        "HbA1c":           {"low": 0.0,  "high": 12.0, "unit": "%"},
    }

    MODERATE_THRESHOLDS = {
        "Hemoglobin":      {"low": 9.0,   "high": 18.0},
        "Glucose":         {"low": 60.0,  "high": 250.0},
        "Creatinine":      {"low": 0.0,   "high": 2.5},
        "LDL":             {"low": 0.0,   "high": 160.0},
        "Cholesterol":     {"low": 0.0,   "high": 240.0},
        "TSH":             {"low": 0.1,   "high": 6.0},
        "Vitamin D":       {"low": 20.0,  "high": 150.0},
    }

    PHARMACOGENOMIC_ALERTS = {
        "CYP2D6": "⚠️ Codeine/Tramadol may be dangerous — poor metabolizer variant",
        "DPYD":   "🚨 5-FU chemotherapy CONTRAINDICATED — DPYD deficiency",
        "VKORC1": "⚠️ Warfarin dose adjustment required — VKORC1 variant",
        "TPMT":   "🚨 Azathioprine/Mercaptopurine — severe toxicity risk",
        "BRCA1":  "ℹ️ Cancer surveillance recommended — BRCA1 variant detected",
    }

    def __init__(self, db_path: str = DB_PATH, event_bus=None):
        import os; os.makedirs("data", exist_ok=True)
        self.db = db_path
        self.bus = event_bus
        self._init_db()
        log.info("🚨 AlertEngine ready")

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id  TEXT,
                    patient_name TEXT,
                    severity    TEXT,
                    marker      TEXT,
                    value       REAL,
                    unit        TEXT,
                    message     TEXT,
                    timestamp   TEXT,
                    acknowledged INTEGER DEFAULT 0
                )
            """)

    def check_blood_flags(self, patient_id: str,
                          patient_name: str,
                          flags: list[dict]) -> list[dict]:
        """
        Check all blood flags against thresholds.
        Returns list of generated alerts.
        """
        generated = []
        for f in flags:
            marker = f.get("marker", "")
            value  = f.get("value", 0)
            unit   = f.get("unit", "")

            # Check critical
            crit = self.CRITICAL_THRESHOLDS.get(marker)
            if crit and (value <= crit["low"] or value >= crit["high"]):
                alert = self._create_alert(
                    patient_id, patient_name, "CRITICAL",
                    marker, value, unit,
                    f"CRITICAL: {marker} = {value} {unit} — immediate intervention required"
                )
                generated.append(alert)
                continue

            # Check moderate
            mod = self.MODERATE_THRESHOLDS.get(marker)
            if mod and (value <= mod["low"] or value >= mod["high"]):
                alert = self._create_alert(
                    patient_id, patient_name, "MODERATE",
                    marker, value, unit,
                    f"MODERATE: {marker} = {value} {unit} — physician review needed"
                )
                generated.append(alert)

        return generated

    def check_gene_variants(self, patient_id: str,
                             patient_name: str,
                             variants: list[str]) -> list[dict]:
        """Check gene variants for pharmacogenomic alerts."""
        generated = []
        for gene in variants:
            msg = self.PHARMACOGENOMIC_ALERTS.get(gene.upper())
            if msg:
                alert = self._create_alert(
                    patient_id, patient_name,
                    "CRITICAL" if "🚨" in msg else "MODERATE",
                    gene, 0, "gene", msg
                )
                generated.append(alert)
        return generated

    def _create_alert(self, patient_id: str, patient_name: str,
                      severity: str, marker: str, value: float,
                      unit: str, message: str) -> dict:
        ts = datetime.now().isoformat()
        alert = {
            "patient_id":   patient_id,
            "patient_name": patient_name,
            "severity":     severity,
            "marker":       marker,
            "value":        value,
            "unit":         unit,
            "message":      message,
            "timestamp":    ts,
        }
        # Store in DB
        try:
            with sqlite3.connect(self.db) as c:
                c.execute(
                    "INSERT INTO alerts(patient_id,patient_name,severity,marker,value,unit,message,timestamp) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (patient_id, patient_name, severity, marker,
                     value, unit, message, ts)
                )
        except Exception as e:
            log.error(f"Alert store error: {e}")

        # Publish to event bus
        if self.bus:
            topic = f"alert.{severity.lower()}"
            self.bus.publish(topic, alert, source="AlertEngine")

        log.info(f"  🚨 [{severity}] {patient_name}: {message[:60]}")
        return alert

    def get_active_alerts(self, severity: str = None,
                          limit: int = 50) -> list[dict]:
        """Get unacknowledged alerts, newest first."""
        query = "SELECT * FROM alerts WHERE acknowledged=0"
        params = []
        if severity:
            query += " AND severity=?"
            params.append(severity.upper())
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        try:
            with sqlite3.connect(self.db) as c:
                rows = c.execute(query, params).fetchall()
            cols = ["id","patient_id","patient_name","severity","marker",
                    "value","unit","message","timestamp","acknowledged"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            log.error(f"get_alerts error: {e}")
