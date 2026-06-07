"""
AMRIT RESEARCH OS v4.0
core/medical/blood_report_parser.py

Blood report parser — extracts lab markers from a text or PDF report,
compares each against reference ranges, and flags HIGH / LOW values.

PDF support is optional: if `pdfplumber` or `PyPDF2` is installed it is
used; otherwise paste the report text directly.

DISCLAIMER: Educational tool. Not a medical diagnosis.
"""

import re
import os


# marker -> (regex aliases, unit, low, high)
MARKERS = {
    "hba1c":        (r"hba1c|glycated h[ae]moglobin|a1c", "%", 4.0, 5.6),
    "glucose":      (r"glucose|blood sugar|fbs", "mg/dL", 70, 99),
    "total_cholesterol": (r"total cholesterol|cholesterol total|\bcholesterol\b", "mg/dL", 0, 200),
    "ldl":          (r"ldl", "mg/dL", 0, 100),
    "hdl":          (r"hdl", "mg/dL", 40, 60),
    "triglycerides":(r"triglycerides?|\btg\b", "mg/dL", 0, 150),
    "hemoglobin":   (r"h[ae]moglobin|\bhb\b|hgb", "g/dL", 13.0, 17.0),
    "wbc":          (r"wbc|white blood cell|leu[ck]ocyte", "10^3/uL", 4.0, 11.0),
    "rbc":          (r"rbc|red blood cell|erythrocyte", "10^6/uL", 4.5, 5.9),
    "platelets":    (r"platelet|plt", "10^3/uL", 150, 450),
    "creatinine":   (r"creatinine", "mg/dL", 0.6, 1.3),
    "tsh":          (r"\btsh\b|thyroid stimulating", "mIU/L", 0.4, 4.0),
    "vitamin_d":    (r"vitamin\s*d|25[- ]?oh", "ng/mL", 30, 100),
    "crp":          (r"\bcrp\b|c[- ]?reactive", "mg/L", 0, 3.0),
}


class BloodReportParser:

    # ─────────────────── input ───────────────────

    @staticmethod
    def read_pdf(path: str) -> str:
        """Extract text from a PDF if a PDF library is available."""
        if not os.path.exists(path):
            return ""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            pass
        try:
            import PyPDF2
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                return "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception:
            return ""

    def load(self, source: str) -> str:
        """Accept a file path (txt/pdf) or raw report text."""
        if os.path.exists(source):
            if source.lower().endswith(".pdf"):
                return self.read_pdf(source)
            with open(source, "r", errors="ignore") as f:
                return f.read()
        return source

    # ─────────────────── parsing ───────────────────

    def parse(self, source: str) -> dict:
        text = self.load(source)
        low_text = text.lower()
        markers = {}

        for name, (alias, unit, lo, hi) in MARKERS.items():
            # find "<alias> ... <number>"
            pattern = rf"(?:{alias})[^0-9\-]{{0,40}}([0-9]+(?:\.[0-9]+)?)"
            m = re.search(pattern, low_text)
            if not m:
                continue
            value = float(m.group(1))
            if value < lo:
                flag = "LOW"
            elif value > hi:
                flag = "HIGH"
            else:
                flag = "NORMAL"
            markers[name] = {
                "value": value,
                "unit": unit,
                "reference": f"{lo}-{hi}",
                "flag": flag,
            }

        abnormal = {k: v for k, v in markers.items() if v["flag"] != "NORMAL"}
        return {
            "markers_found": len(markers),
            "markers": markers,
            "abnormal": abnormal,
            "summary": self._summary(abnormal),
            "disclaimer": "Educational only. Not a medical diagnosis. Consult a physician.",
        }

    @staticmethod
    def _summary(abnormal: dict) -> str:
        if not abnormal:
            return "All detected markers are within reference ranges."
        parts = [f"{k.replace('_', ' ').title()} {v['flag']} ({v['value']} {v['unit']})"
                 for k, v in abnormal.items()]
        return "Out-of-range: " + "; ".join(parts)
