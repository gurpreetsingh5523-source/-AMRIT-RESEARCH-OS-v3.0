"""
AMRIT RESEARCH OS v4.5
core/medical/medical_integration.py

ਇਹ ਫਾਈਲ ਤਿੰਨ ਕੰਮ ਕਰਦੀ ਹੈ:

1. PatternAnalyzer     — time-series trends + IsolationForest anomaly detection
2. MedicalReportBuilder — medical analysis → existing PDFExporter ਨਾਲ connect
3. MedicalDispatch     — PDF → email to medical center (existing EmailAgent ਵਰਤਦਾ ਹੈ)

ਇੰਸਟਾਲ: pip install scikit-learn numpy scipy
ਬਾਕੀ ਸਭ (PDFExporter, EmailAgent) ਪਹਿਲਾਂ ਤੋਂ repo ਵਿੱਚ ਹੈ।

WORKFLOW:
   Patient Data Input
         ↓
   MedicalSciencePipeline (medical_science_engine.py)
         ↓
   PatternAnalyzer (anomaly + trend detection)
         ↓
   MedicalReportBuilder → PDFExporter (pdf_exporter.py)
         ↓
   PDF ਡਾਕਟਰ ਨੂੰ ਮਿਲਦੀ ਹੈ (print / email)
         ↓
   ਡਾਕਟਰ manually review ਕਰਦਾ ਹੈ
         ↓
   MedicalDispatch → EmailAgent → Medical Center
         ↓
   ਮਰੀਜ਼ ਦਵਾਈ ਲੈਂਦਾ ਹੈ

⚠️  RESEARCH / CLINICAL DECISION SUPPORT ONLY
    Final prescription requires licensed physician verification.
"""

import os
import json
import logging
import datetime
from typing import Optional

import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

log = logging.getLogger("AmritMedical")

# ──────────────────────────────────────────────────────────────
# Lazy imports — only load repo modules when available
# ──────────────────────────────────────────────────────────────
def _get_pdf_exporter():
    try:
        from core.reporting.pdf_exporter import PDFExporter
        return PDFExporter(output_dir="reports/medical")
    except ImportError:
        log.warning("PDFExporter not found — using standalone fallback")
        return None

def _get_email_agent():
    try:
        from core.agents.email_agent import EmailAgent
        return EmailAgent()
    except ImportError:
        log.warning("EmailAgent not found — email dispatch unavailable")
        return None


# ══════════════════════════════════════════════════════════════
# 1. PATTERN ANALYZER
# ══════════════════════════════════════════════════════════════
class PatternAnalyzer:
    """
    Real-time pattern detection for medical time-series data.

    ਕੀ ਕਰਦਾ ਹੈ:
    - Linear trend (ਵੱਧ ਰਿਹਾ / ਘੱਟ ਰਿਹਾ / stable)
    - IsolationForest anomaly detection (sudden spike/drop)
    - Fractal analysis of DNA (Hurst exponent)
    - Chaos theory for glucose/heart rate variability
    - Multi-marker correlation detection

    Usage:
        pa = PatternAnalyzer(window=10)
        pa.add("hemoglobin", 9.2, "2026-06-01")
        pa.add("hemoglobin", 8.8, "2026-06-08")
        trend = pa.trend("hemoglobin")
        alerts = pa.check_alert("hemoglobin", 7.5)
    """

    # Alert thresholds — severity levels
    CRITICAL_CHANGE_PCT = 20.0   # >20% change = critical alert
    MODERATE_CHANGE_PCT = 10.0   # >10% change = moderate alert

    def __init__(self, window: int = 10):
        self.window = window
        # {marker: [(timestamp, value), ...]}
        self._history: dict[str, list] = {}

    # ── Add observation ───────────────────────────────────────
    def add(self, marker: str, value: float, timestamp: str = "") -> None:
        """Add a new lab value observation."""
        ts = timestamp or datetime.datetime.now().isoformat()
        if marker not in self._history:
            self._history[marker] = []
        self._history[marker].append((ts, float(value)))
        # Keep only last N
        if len(self._history[marker]) > self.window:
            self._history[marker].pop(0)

    def add_from_blood_report(self, flags: list[dict]) -> None:
        """Bulk-add from BloodReportParser/AI output."""
        ts = datetime.datetime.now().isoformat()
        for f in flags:
            marker = f.get("marker", "").replace(" ", "_").lower()
            value  = f.get("value")
            if marker and value is not None:
                self.add(marker, float(value), ts)

    # ── Trend ─────────────────────────────────────────────────
    def trend(self, marker: str) -> str:
        """Linear regression slope → trend label."""
        pts = self._history.get(marker, [])
        if len(pts) < 3:
            return "insufficient data"
        vals = np.array([v for _, v in pts], dtype=float)
        X = np.arange(len(vals)).reshape(-1, 1)
        slope = LinearRegression().fit(X, vals).coef_[0]
        pct_change = (slope / (vals.mean() or 1)) * 100
        if pct_change > 5:
            return f"📈 RISING (+{pct_change:.1f}%/period)"
        if pct_change < -5:
            return f"📉 FALLING ({pct_change:.1f}%/period)"
        return "➡️  STABLE"

    def trend_all(self) -> dict[str, str]:
        """Trend for all tracked markers."""
        return {m: self.trend(m) for m in self._history}

    # ── Anomaly ───────────────────────────────────────────────
    def is_anomaly(self, marker: str, new_value: float) -> tuple[bool, str]:
        """
        IsolationForest anomaly detection.
        Returns (is_anomaly, reason).
        """
        pts = self._history.get(marker, [])
        if len(pts) < 5:
            return False, "insufficient history"

        vals = np.array([v for _, v in pts], dtype=float).reshape(-1, 1)
        clf  = IsolationForest(contamination=0.1, random_state=42).fit(vals)
        pred = clf.predict([[new_value]])[0]

        if pred == -1:
            mean_val = vals.mean()
            pct_dev  = abs(new_value - mean_val) / (mean_val or 1) * 100
            severity = "🚨 CRITICAL" if pct_dev > self.CRITICAL_CHANGE_PCT \
                       else "⚠️  MODERATE"
            return True, f"{severity} anomaly — {pct_dev:.1f}% deviation from baseline {mean_val:.2f}"
        return False, "normal"

    def check_alert(self, marker: str, new_value: float) -> dict:
        """Full alert check: anomaly + trend + percentage change."""
        is_anom, reason = self.is_anomaly(marker, new_value)
        trend_str = self.trend(marker)

        # Percentage change from last known value
        pts = self._history.get(marker, [])
        pct_change = None
        if pts:
            last_val = pts[-1][1]
            if last_val != 0:
                pct_change = (new_value - last_val) / last_val * 100

        return {
            "marker":     marker,
            "new_value":  new_value,
            "is_anomaly": is_anom,
            "reason":     reason,
            "trend":      trend_str,
            "pct_change": round(pct_change, 2) if pct_change is not None else None,
            "alert_level": "CRITICAL" if is_anom and abs(pct_change or 0) > self.CRITICAL_CHANGE_PCT
                           else "MODERATE" if is_anom
                           else "NORMAL",
        }

    # ── Fractal DNA Analysis ──────────────────────────────────
    @staticmethod
    def hurst_exponent(dna_sequence: str) -> dict:
        """
        Hurst exponent for DNA sequence.
        H > 0.5 → persistent (long-range correlations → repeat expansions possible)
        H < 0.5 → anti-persistent (random sequence)
        H ≈ 0.5 → random walk (healthy variation)
        """
        binary = [1 if c in "AG" else 0
                  for c in dna_sequence.upper() if c in "ACGT"]
        if len(binary) < 50:
            return {"hurst": 0.5, "interpretation": "insufficient sequence length"}

        N      = len(binary)
        lags   = list(range(10, min(100, N // 4), 5))
        rs_vals = []

        for lag in lags:
            chunks = [binary[i:i+lag] for i in range(0, N - lag, lag)]
            rs_chunk = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                arr    = np.array(chunk, dtype=float)
                mean   = arr.mean()
                cumsum = np.cumsum(arr - mean)
                R      = cumsum.max() - cumsum.min()
                S      = arr.std()
                if S > 0:
                    rs_chunk.append(R / S)
            if rs_chunk:
                rs_vals.append(np.mean(rs_chunk))

        if len(rs_vals) < 2:
            return {"hurst": 0.5, "interpretation": "insufficient data"}

        lags_used = lags[:len(rs_vals)]
        with np.errstate(divide="ignore", invalid="ignore"):
            coeffs = np.polyfit(np.log(lags_used), np.log(rs_vals), 1)
        H = float(coeffs[0])

        if H > 0.65:
            interp = "⚠️ High persistence — possible repeat expansion (Huntington's, Fragile X risk)"
        elif H < 0.35:
            interp = "ℹ️ Anti-persistent — highly variable sequence, possible mutation hotspot"
        else:
            interp = "✅ Near-random walk — normal sequence variation"

        return {
            "hurst":          round(H, 4),
            "interpretation": interp,
            "clinical_note":  "Hurst exponent measures long-range correlations in DNA",
        }

    # ── Sample Entropy (Chaos) ────────────────────────────────
    @staticmethod
    def sample_entropy(time_series: list[float], m: int = 2) -> dict:
        """
        Sample entropy for glucose/heart rate variability.
        Higher entropy → more complex/chaotic signal → may indicate pathology.
        """
        ts = np.array(time_series, dtype=float)
        if len(ts) < 10:
            return {"sample_entropy": None, "interpretation": "Need ≥10 data points"}

        r  = 0.2 * ts.std()
        N  = len(ts)

        def _count_matches(m_val):
            patterns = np.array([ts[i:i+m_val] for i in range(N - m_val)])
            count = 0
            for i, p in enumerate(patterns):
                dists = np.max(np.abs(patterns - p), axis=1)
                count += np.sum(dists <= r) - 1  # exclude self
            return count

        cm   = _count_matches(m)
        cm1  = _count_matches(m + 1)

        if cm == 0:
            return {"sample_entropy": 0.0, "interpretation": "Perfectly regular signal"}

        se = float(-np.log(cm1 / cm)) if cm1 > 0 else 0.0

        if se > 1.5:
            interp = "⚠️ High complexity — irregular pattern (diabetes/arrhythmia risk)"
        elif se < 0.3:
            interp = "⚠️ Low complexity — overly regular (possible pathological rigidity)"
        else:
            interp = "✅ Normal physiological complexity"

        return {
            "sample_entropy":  round(se, 4),
            "interpretation":  interp,
            "n_points":        N,
        }

    # ── Multi-marker correlation ──────────────────────────────
    def correlation_matrix(self) -> dict:
        """
        Pearson correlations between all tracked markers.
        Flags clinically interesting correlations.
        """
        markers = [m for m, pts in self._history.items() if len(pts) >= 3]
        if len(markers) < 2:
            return {}

        # Align by index (not timestamp for simplicity)
        min_len = min(len(self._history[m]) for m in markers)
        matrix  = {}

        INTERESTING_PAIRS = {
            frozenset({"glucose", "hba1c"}):        "Consistent diabetes indicator",
            frozenset({"ldl", "cholesterol"}):      "Lipid panel correlation",
            frozenset({"alt", "ast"}):              "Liver enzyme correlation",
            frozenset({"hemoglobin", "ferritin"}):  "Iron-deficiency anemia pattern",
            frozenset({"tsh", "free_t4"}):          "Thyroid axis",
        }

        for i, m1 in enumerate(markers):
            for m2 in markers[i+1:]:
                v1 = [v for _, v in self._history[m1]][-min_len:]
                v2 = [v for _, v in self._history[m2]][-min_len:]
                if len(v1) < 3:
                    continue
                r, p = stats.pearsonr(v1, v2)
                pair  = frozenset({m1.split("_")[0], m2.split("_")[0]})
                note  = INTERESTING_PAIRS.get(pair, "")
                matrix[f"{m1}↔{m2}"] = {
                    "pearson_r": round(float(r), 4),
                    "p_value":   round(float(p), 6),
                    "significant": p < 0.05,
                    "clinical_note": note,
                }
        return matrix

    # ── History export ────────────────────────────────────────
    def export_history(self, path: str = "data/pattern_history.json") -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._history, f, indent=2)

    def load_history(self, path: str = "data/pattern_history.json") -> None:
        if os.path.exists(path):
            with open(path) as f:
                self._history = json.load(f)


# ══════════════════════════════════════════════════════════════
# 2. MEDICAL REPORT BUILDER
# ══════════════════════════════════════════════════════════════
class MedicalReportBuilder:
    """
    Connects medical analysis results to the existing PDFExporter.
    Generates a complete, print-ready clinical report.

    Doctor workflow:
      1. Report PDF ਪ੍ਰਿੰਟ ਹੁੰਦੀ ਹੈ
      2. ਡਾਕਟਰ manually review ਕਰਦਾ ਹੈ
      3. Sign ਕਰਕੇ Medical Center ਨੂੰ ਭੇਜਦਾ ਹੈ
    """

    def __init__(self):
        self._pdf = _get_pdf_exporter()
        self._analyzer = PatternAnalyzer()

    def build_patient_report(self,
                              patient_info: dict,
                              analysis: dict,
                              pattern_alerts: list = None) -> str:
        """
        Generate complete clinical PDF report.
        Returns path to saved PDF file.
        """
        now  = datetime.datetime.now()
        name = patient_info.get("name", "Patient")
        pid  = patient_info.get("id", "N/A")
        age  = patient_info.get("age", "N/A")
        gender = patient_info.get("gender", "N/A")

        sections = []

        # ── 1. Patient Header ──────────────────────────────────
        sections.append({
            "heading": "Patient Information",
            "body": (
                f"Name:     {name}\n"
                f"ID:       {pid}\n"
                f"Age:      {age}   |   Gender: {gender}\n"
                f"Report:   {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"System:   AMRIT Research OS v4.0\n"
                f"Status:   PENDING DOCTOR VERIFICATION\n"
                f"WARNING:  AI-generated analysis — physician review mandatory"
            ),
        })

        # ── 2. Executive Summary ───────────────────────────────
        severity = (
            analysis.get("blood_analysis", {})
            .get("severity_summary", "Analysis complete")
        )
        patterns = (
            analysis.get("blood_analysis", {})
            .get("suspected_patterns", [])
        )
        sections.append({
            "heading": "Executive Summary",
            "body": (
                f"{severity}\n\n"
                f"Detected Patterns: {', '.join(patterns) if patterns else 'None'}\n\n"
                f"{analysis.get('ai_synthesis', '')[:600]}"
            ),
        })

        # ── 3. Blood Report Abnormalities ─────────────────────
        flags = analysis.get("blood_analysis", {}).get("abnormal_flags", [])
        if flags:
            flag_lines = []
            for f in flags:
                flag_lines.append(
                    f"  {f['severity']:<10} {f['marker']:<30} "
                    f"= {f['value']:>8} {f['unit']:<10} "
                    f"[Normal: {f['range']}] ({f['status']})"
                )
            sections.append({
                "heading": "Blood Report — Abnormal Values",
                "body": "\n".join(flag_lines) if flag_lines else "All values within range",
            })

        # ── 4. Priority Actions ────────────────────────────────
        actions = analysis.get("blood_analysis", {}).get("priority_action", [])
        if actions:
            sections.append({
                "heading": "Priority Clinical Actions",
                "body": "\n".join(f"  • {a}" for a in actions),
            })

        # ── 5. DNA Analysis ────────────────────────────────────
        dna = analysis.get("dna_analysis", {})
        if dna:
            clinical_notes = dna.get("clinical_notes", [])
            repeats = dna.get("repeat_regions", [])
            orfs    = dna.get("open_reading_frames", [])
            hurst   = analysis.get("hurst_analysis", {})

            dna_body = (
                f"Sequence length: {dna.get('length_bp', 0)} bp\n"
                f"GC content:      {dna.get('gc_content_pct', 0)}%\n"
                f"Coding potential: {dna.get('codon_analysis', {}).get('coding_potential', 'N/A')}\n"
                f"Open reading frames: {len(orfs)}\n"
                f"Repeat regions:  {len(repeats)}\n"
            )
            if hurst:
                dna_body += (
                    f"Hurst exponent:  {hurst.get('hurst', 'N/A')}\n"
                    f"DNA pattern:     {hurst.get('interpretation', '')}\n"
                )
            if clinical_notes:
                dna_body += "\nClinical Notes:\n"
                dna_body += "\n".join(f"  {n}" for n in clinical_notes)
            if repeats:
                dna_body += "\n\nRepeat Regions Detected:\n"
                for r in repeats[:5]:
                    dna_body += (
                        f"  Unit={r['unit']} x{r['count']} at pos {r['start']} "
                        f"— {r['note']}\n"
                    )

            sections.append({"heading": "DNA Sequence Analysis", "body": dna_body})

        # ── 6. Pharmacogenomics ────────────────────────────────
        pg = analysis.get("drug_gene_profile", {})
        if pg:
            caution_drugs = pg.get("caution_drugs", [])
            recs = pg.get("recommendations", [])
            pg_body = f"{pg.get('summary', '')}\n\n"
            if caution_drugs:
                pg_body += f"Drugs requiring dose adjustment:\n"
                pg_body += "\n".join(f"  • {d}" for d in caution_drugs)
            if recs:
                pg_body += "\n\nGene-Specific Notes:\n"
                for r in recs:
                    pg_body += f"  {r.get('gene', '')}: {r.get('action', '')}\n"
            sections.append({"heading": "Pharmacogenomics — Drug-Gene Interactions", "body": pg_body})

        # ── 7. Pattern Alerts ──────────────────────────────────
        if pattern_alerts:
            alert_body = ""
            for a in pattern_alerts:
                alert_body += (
                    f"  [{a.get('alert_level', 'INFO')}] "
                    f"{a.get('marker', '')} = {a.get('new_value', '')} "
                    f"| {a.get('reason', '')} | Trend: {a.get('trend', '')}\n"
                )
            sections.append({
                "heading": "Real-Time Pattern Alerts",
                "body": alert_body or "No pattern alerts",
            })

        # ── 8. PubMed Research Links ───────────────────────────
        pubmed = analysis.get("blood_analysis", {}).get("pubmed_research", [])
        if pubmed:
            sections.append({
                "heading": "Relevant Research (PubMed)",
                "body": "\n".join(f"  • {url}" for url in pubmed),
            })

        # ── 9. Doctor Verification Block ───────────────────────
        sections.append({
            "heading": "Doctor Verification (Mandatory)",
            "body": (
                "This report has been generated by AMRIT AI Research System.\n"
                "It is NOT a final medical diagnosis or prescription.\n\n"
                "Physician Review:\n"
                "  [ ] Findings reviewed and verified\n"
                "  [ ] Prescription approved / modified\n"
                "  [ ] Forward to Medical Center\n\n"
                "Doctor Signature: _______________________\n"
                "Date: ________________   Reg. No.: ________________\n\n"
                "After physician approval, forward this report to the Medical\n"
                "Center so the patient can collect prescribed medication."
            ),
        })

        # ── 10. AI Disclaimer ─────────────────────────────────
        sections.append({
            "heading": "Disclaimer",
            "body": (
                "RESEARCH / CLINICAL DECISION SUPPORT TOOL ONLY.\n"
                "All AI-generated findings must be verified by a licensed physician.\n"
                "Medication may only be dispensed after written physician approval.\n"
                "AMRIT Research OS v4.5 | " + now.strftime("%Y-%m-%d")
            ),
        })

        # ── Generate PDF ───────────────────────────────────────
        fname = f"patient_{pid}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"

        if self._pdf:
            path = self._pdf.build(
                title    = "AMRIT Medical Analysis Report",
                subtitle = f"Patient: {name} | ID: {pid} | {now.strftime('%Y-%m-%d %H:%M')}",
                sections = sections,
                filename = fname,
            )
            log.info(f"✅ Medical PDF generated: {path}")
            return path
        else:
            # Fallback: plain text file
            path = f"reports/medical/{fname.replace('.pdf', '.txt')}"
            os.makedirs("reports/medical", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"AMRIT Medical Analysis Report\n{'='*50}\n")
                for s in sections:
                    f.write(f"\n{s['heading']}\n{'-'*40}\n{s['body']}\n")
            log.info(f"✅ Medical report (text) saved: {path}")
            return path


# ══════════════════════════════════════════════════════════════
# 3. MEDICAL DISPATCH
# ══════════════════════════════════════════════════════════════
class MedicalDispatch:
    """
    Sends the verified medical report PDF to the Medical Center via email.

    Workflow:
      PDF → Doctor verifies (manually) → MedicalDispatch.send() →
      Medical Center receives → Patient gets medicine

    ਵਰਤੋ:
      dispatch = MedicalDispatch(
          medical_center_email="pharmacy@hospital.com",
          clinic_name="AMRIT Health Clinic"
      )
      result = dispatch.send(
          pdf_path="reports/medical/patient_P001.pdf",
          patient_info={...},
          doctor_name="Dr. Singh"
      )

    SMTP ਸੈੱਟਅੱਪ:
      export SMTP_HOST=smtp.gmail.com
      export SMTP_PORT=587
      export SMTP_USER=clinic@gmail.com
      export SMTP_PASS=your-app-password
    """

    EMAIL_TEMPLATE = """Dear Medical Center Team,

Please find attached the AI-generated medical analysis report for the following patient.
This report has been reviewed and approved by the attending physician.

Patient Details:
  Name:   {name}
  ID:     {pid}
  Age:    {age}
  Gender: {gender}

Approving Physician: {doctor}
Clinic: {clinic}
Report Date: {date}

ACTION REQUIRED:
Please prepare and dispense the prescribed medication as per the attached report.
The patient has been informed to collect their medication from your center.

The attached PDF contains:
  • Complete blood/DNA analysis
  • AI pattern detection results
  • Drug-gene interaction alerts
  • Physician-verified prescription notes

⚠️ This report has been verified by a licensed physician before dispatch.

Regards,
AMRIT Research OS v4.0
{clinic}
"""

    def __init__(self,
                 medical_center_email: str = "",
                 clinic_name: str = "AMRIT Health Clinic"):
        self._email_agent = _get_email_agent()
        self.center_email = medical_center_email
        self.clinic_name  = clinic_name

    def send(self,
             pdf_path: str,
             patient_info: dict,
             doctor_name: str = "Attending Physician",
             override_email: str = "") -> dict:
        """
        Send the approved medical report to the Medical Center.
        Returns send result dict.
        """
        recipient = override_email or self.center_email
        if not recipient:
            return {
                "sent": False,
                "reason": "No medical center email configured. "
                          "Set medical_center_email in MedicalDispatch().",
            }

        name   = patient_info.get("name", "Patient")
        pid    = patient_info.get("id", "N/A")
        age    = patient_info.get("age", "N/A")
        gender = patient_info.get("gender", "N/A")
        now    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        subject = (
            f"[AMRIT] Medical Report — Patient {name} (ID: {pid}) — "
            f"Physician Approved"
        )
        body = self.EMAIL_TEMPLATE.format(
            name=name, pid=pid, age=age, gender=gender,
            doctor=doctor_name, clinic=self.clinic_name, date=now,
        )

        if self._email_agent:
            result = self._email_agent.send_email(
                to_addr         = recipient,
                subject         = subject,
                body            = body,
                attachment_path = pdf_path,
            )
        else:
            # Fallback: show what would be sent
            result = {
                "sent":   False,
                "reason": "EmailAgent unavailable — install with: pip install (no extra deps needed)",
                "would_send_to": recipient,
                "subject": subject,
                "pdf_path": pdf_path,
            }

        log.info(f"📧 Medical dispatch: {'✅ SENT' if result.get('sent') else '❌ FAILED'}"
                 f" → {recipient}")
        return result

    def preview(self, patient_info: dict, doctor_name: str = "Dr.") -> str:
        """Preview the email that would be sent (for testing)."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        return self.EMAIL_TEMPLATE.format(
            name   = patient_info.get("name", "Patient"),
            pid    = patient_info.get("id", "N/A"),
            age    = patient_info.get("age", "N/A"),
            gender = patient_info.get("gender", "N/A"),
            doctor = doctor_name,
            clinic = self.clinic_name,
            date   = now,
        )


# ══════════════════════════════════════════════════════════════
# 4. COMPLETE MEDICAL PIPELINE ORCHESTRATOR
# ══════════════════════════════════════════════════════════════
class FullMedicalOrchestrator:
    """
    Single entry point for the complete medical workflow.
    Connects to existing AMRIT components.

    Usage in main.py or server.py:
        from core.medical.medical_integration import FullMedicalOrchestrator

        orch = FullMedicalOrchestrator(
            medical_center_email="pharmacy@hospital.com"
        )

        # Step 1: Analyse patient
        report_path = orch.analyse_and_report(
            patient_info={"name": "Gurpreet Singh", "id": "P001",
                         "age": 35, "gender": "male"},
            blood_report_text="Hemoglobin: 9.2 ...",
            gene_variants=["CYP2D6", "BRCA1"],
        )

        # Step 2: After doctor physically verifies PDF, send to medical center
        result = orch.dispatch_to_medical_center(
            pdf_path=report_path,
            patient_info={"name": "Gurpreet Singh", "id": "P001"},
            doctor_name="Dr. Sharma",
        )
    """

    def __init__(self,
                 medical_center_email: str = "",
                 clinic_name: str = "AMRIT Health Clinic",
                 ollama_model: str = "qwen3:8b"):

        self.report_builder = MedicalReportBuilder()
        self.dispatch       = MedicalDispatch(medical_center_email, clinic_name)
        self.pattern        = PatternAnalyzer(window=10)
        self._ollama_model  = ollama_model

        # Try to load existing pipeline
        try:
            from core.medical.medical_science_engine import MedicalSciencePipeline
            self._pipeline = MedicalSciencePipeline(ollama_model=ollama_model)
            log.info("✅ MedicalSciencePipeline connected")
        except ImportError:
            self._pipeline = None
            log.warning("⚠️  MedicalSciencePipeline not found — analysis may be limited")

        log.info(f"🏥 FullMedicalOrchestrator ready | clinic: {clinic_name}")

    def analyse_and_report(self,
                            patient_info: dict,
                            blood_report_text: str = "",
                            dna_sequence: str = "",
                            gene_variants: list = None,
                            lab_image_path: str = "") -> str:
        """
        Full pipeline: data → analysis → pattern detection → PDF report.
        Returns path to generated PDF.
        """
        log.info(f"🔬 Starting analysis: {patient_info.get('name', 'Patient')}")

        # ── Run medical analysis ──────────────────────────────
        if self._pipeline:
            analysis = self._pipeline.full_patient_analysis(
                blood_report_text = blood_report_text,
                dna_sequence      = dna_sequence,
                gene_variants     = gene_variants or [],
                lab_image_path    = lab_image_path,
                patient_info      = patient_info,
            )
        else:
            analysis = {"note": "Pipeline unavailable — using basic analysis"}

        # ── Pattern analysis ──────────────────────────────────
        flags = analysis.get("blood_analysis", {}).get("abnormal_flags", [])
        self.pattern.add_from_blood_report(flags)

        pattern_alerts = []
        for f in flags:
            marker = f.get("marker", "").replace(" ", "_").lower()
            value  = f.get("value")
            if marker and value:
                alert = self.pattern.check_alert(marker, float(value))
                if alert.get("alert_level") != "NORMAL":
                    pattern_alerts.append(alert)

        # ── DNA Hurst exponent ────────────────────────────────
        if dna_sequence:
            hurst = self.pattern.hurst_exponent(dna_sequence)
            analysis["hurst_analysis"] = hurst

        # ── Generate PDF ──────────────────────────────────────
        pdf_path = self.report_builder.build_patient_report(
            patient_info   = patient_info,
            analysis       = analysis,
            pattern_alerts = pattern_alerts,
        )

        log.info(f"📄 Report ready: {pdf_path}")
        log.info("⏳ Waiting for doctor physical verification…")
        return pdf_path

    def dispatch_to_medical_center(self,
                                    pdf_path: str,
                                    patient_info: dict,
                                    doctor_name: str = "Attending Physician",
                                    override_email: str = "") -> dict:
        """
        Send doctor-approved report to Medical Center.
        Call this ONLY after doctor has physically verified the PDF.
        """
        log.info(f"📧 Dispatching to Medical Center…")
        result = self.dispatch.send(
            pdf_path       = pdf_path,
            patient_info   = patient_info,
            doctor_name    = doctor_name,
            override_email = override_email,
        )
        if result.get("sent"):
            log.info(f"✅ Medical Center notified — patient can collect medicine")
        else:
            log.warning(f"❌ Dispatch failed: {result.get('reason')}")
        return result


# ══════════════════════════════════════════════════════════════
# DEMO & TEST
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

    print("""
╔════════════════════════════════════════════════════╗
║  AMRIT Medical Integration — Pattern + PDF + Email ║
╚════════════════════════════════════════════════════╝
""")

    # ── PatternAnalyzer test ──────────────────────────────────
    print("📈 TEST 1: Pattern Analyzer")
    pa = PatternAnalyzer(window=8)
    # Simulate 6 months of Hemoglobin readings (declining trend)
    hb_readings = [13.5, 12.8, 11.9, 10.5, 9.8, 9.2]
    for i, val in enumerate(hb_readings):
        pa.add("hemoglobin", val, f"2026-0{i+1}-01")

    print(f"  Hemoglobin trend: {pa.trend('hemoglobin')}")
    alert = pa.check_alert("hemoglobin", 7.5)
    print(f"  Alert level: {alert['alert_level']}")
    print(f"  Reason: {alert['reason']}")

    # ── Hurst Exponent test ───────────────────────────────────
    print("\n🧬 TEST 2: Hurst Exponent (CAG repeat sequence)")
    cag_repeat = "ATG" + "CAG" * 35 + "TAA"  # 35 CAG repeats (Huntington's threshold)
    hurst = PatternAnalyzer.hurst_exponent(cag_repeat)
    print(f"  Hurst: {hurst['hurst']} | {hurst['interpretation']}")

    # ── Sample Entropy test ───────────────────────────────────
    print("\n💉 TEST 3: Sample Entropy (glucose variability)")
    glucose_series = [95, 180, 72, 210, 88, 195, 65, 220, 91, 175, 68, 200]
    se = PatternAnalyzer.sample_entropy(glucose_series)
    print(f"  Sample Entropy: {se['sample_entropy']} | {se['interpretation']}")

    # ── Correlation ───────────────────────────────────────────
    print("\n🔗 TEST 4: Multi-marker Correlation")
    glucose_vals = [95, 120, 140, 160, 180]
    hba1c_vals   = [5.5, 6.2, 6.8, 7.1, 7.8]
    for i in range(5):
        pa.add("glucose", glucose_vals[i])
        pa.add("hba1c",   hba1c_vals[i])
    corr = pa.correlation_matrix()
    for pair, c in corr.items():
        if c.get("significant"):
            print(f"  {pair}: r={c['pearson_r']} p={c['p_value']} → {c.get('clinical_note','')}")

    # ── Report Builder test ───────────────────────────────────
    print("\n📄 TEST 5: Medical Report Builder (PDF)")
    builder = MedicalReportBuilder()
    sample_analysis = {
        "blood_analysis": {
            "severity_summary": "🚨 URGENT: 3 critical values",
            "suspected_patterns": ["Anemia", "Diabetes"],
            "abnormal_flags": [
                {"marker": "Hemoglobin", "value": 7.5, "unit": "g/dL",
                 "status": "LOW", "severity": "HIGH", "range": "13.5-17.5 g/dL"},
            ],
            "priority_action": [
                "🚨 Hemoglobin 7.5 g/dL — transfusion threshold — urgent review",
            ],
            "pubmed_research": ["https://pubmed.ncbi.nlm.nih.gov/?term=severe+anemia"],
        },
        "ai_synthesis": "Patient shows critical anemia with diabetic pattern. Immediate intervention required.",
        "hurst_analysis": hurst,
    }
    pdf_path = builder.build_patient_report(
        patient_info   = {"name": "Test Patient", "id": "P001", "age": 45, "gender": "male"},
        analysis       = sample_analysis,
        pattern_alerts = [alert],
    )
    print(f"  PDF saved: {pdf_path}")

    # ── Dispatch preview ──────────────────────────────────────
    print("\n📧 TEST 6: Medical Dispatch Email Preview")
    dispatch = MedicalDispatch(
        medical_center_email="pharmacy@hospital.com",
        clinic_name="AMRIT Health Clinic"
    )
    preview = dispatch.preview(
        {"name": "Test Patient", "id": "P001", "age": 45, "gender": "male"},
        doctor_name="Dr. Gurpreet Singh"
    )
    print(preview[:400] + "...")
    print("\n✅ All tests complete!")
    print("\n📋 To send to Medical Center after doctor approval:")
    print('   result = dispatch.send(pdf_path, patient_info, "Dr. Name")')
    print("   Requires: SMTP_HOST, SMTP_USER, SMTP_PASS environment variables")
