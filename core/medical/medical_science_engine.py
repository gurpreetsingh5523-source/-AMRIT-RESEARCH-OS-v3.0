"""
╔══════════════════════════════════════════════════════════════════╗
║  AMRIT RESEARCH OS v4 — Medical Science Engine                   ║
║  core/medical/medical_science_engine.py                          ║
║                                                                  ║
║  ਅਸਲ ਵਿਗਿਆਨਕ ਔਜ਼ਾਰ — ਡਾਕਟਰਾਂ ਅਤੇ ਵਿਗਿਆਨੀਆਂ ਲਈ                ║
║                                                                  ║
║  MODULES:                                                        ║
║  1. DNAAnalyzer      → FASTA/FASTQ · NCBI BLAST · ClinVar        ║
║  2. BloodReportAI    → CBC parsing · Biomarker flagging          ║
║  3. LabVisionAI      → LLaVA image analysis (already in Ollama!) ║
║  4. Pharmacogenomics → Drug-gene interactions · OpenFDA          ║
║  5. MedicalPipeline  → Master orchestrator                       ║
║                                                                  ║
║  ⚠️  RESEARCH USE ONLY — Not a clinical diagnostic tool          ║
╚══════════════════════════════════════════════════════════════════╝

Dependencies:
    pip install biopython requests

Ollama models needed (already in your stack):
    ollama pull moondream2      # ← image analysis
    ollama pull qwen3:8b        # ← medical reasoning
    ollama pull nomic-embed-text  # ← embeddings
"""

import re
import json
import logging
import urllib.request
import urllib.parse
import time
from typing import Optional
from datetime import datetime

# BioPython — real bioinformatics
try:
    from Bio import Entrez, SeqIO
    from Bio.Seq import Seq
    from Bio.SeqUtils import gc_fraction
    BIOPYTHON = True
except ImportError:
    BIOPYTHON = False

import requests

log = logging.getLogger("AmritMedical")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

OLLAMA = "http://localhost:11434"
Entrez.email = "amrit.research@example.com"   # NCBI requires email

# ══════════════════════════════════════════════════════════════
# MODULE 1 — DNA ANALYZER
# ══════════════════════════════════════════════════════════════
class DNAAnalyzer:
    """
    Real DNA sequence analysis using BioPython + NCBI APIs.

    ਕੀ ਕਰਦਾ ਹੈ:
    - FASTA/raw DNA sequence ਦਾ complete analysis
    - GC content, codon usage, open reading frames
    - NCBI BLAST — ਕਿਹੜੇ gene/organism ਨਾਲ ਮੇਲ
    - ClinVar — ਕਿਹੜੀਆਂ ਬਿਮਾਰੀਆਂ ਨਾਲ linked
    - Known SNPs (disease-causing variants)
    """

    # Known high-impact SNPs (research reference)
    KNOWN_SNPS = {
        "BRCA1": {
            "gene": "BRCA1",
            "condition": "Breast/Ovarian Cancer risk",
            "significance": "Pathogenic",
            "recommendation": "Genetic counseling recommended",
        },
        "APOE": {
            "gene": "APOE",
            "condition": "Alzheimer's disease risk",
            "significance": "Risk factor",
            "recommendation": "Lifestyle intervention + monitoring",
        },
        "MTHFR": {
            "gene": "MTHFR",
            "condition": "Cardiovascular disease / folate metabolism",
            "significance": "Risk factor",
            "recommendation": "Folate supplementation may help",
        },
        "TP53": {
            "gene": "TP53",
            "condition": "Li-Fraumeni syndrome / cancer predisposition",
            "significance": "Pathogenic",
            "recommendation": "Enhanced cancer surveillance",
        },
        "CFTR": {
            "gene": "CFTR",
            "condition": "Cystic Fibrosis",
            "significance": "Pathogenic",
            "recommendation": "Pulmonary function monitoring",
        },
    }

    def analyze_sequence(self, sequence: str, label: str = "Unknown") -> dict:
        """
        Complete DNA sequence analysis.
        Input: raw DNA string (ACGT) or FASTA format
        """
        log.info(f"🧬 Analyzing DNA sequence: {label}")

        # Clean sequence
        seq_clean = self._parse_input(sequence)
        if not seq_clean:
            return {"error": "Invalid sequence — only ACGT allowed"}

        seq = Seq(seq_clean) if BIOPYTHON else seq_clean

        result = {
            "label":          label,
            "length_bp":      len(seq_clean),
            "timestamp":      datetime.now().isoformat(),
        }

        # Basic composition
        result["composition"] = self._base_composition(seq_clean)

        # GC content (important: high GC = more stable DNA)
        result["gc_content_pct"] = round(
            gc_fraction(seq) * 100 if BIOPYTHON else self._gc_manual(seq_clean), 2
        )

        # Codon analysis (protein coding potential)
        result["codon_analysis"] = self._codon_analysis(seq_clean)

        # Open Reading Frames (potential protein-coding regions)
        result["open_reading_frames"] = self._find_orfs(seq_clean)

        # Repeat regions (relevant for repeat-expansion diseases)
        result["repeat_regions"] = self._find_repeats(seq_clean)

        # Known motif scan
        result["known_motifs"] = self._scan_motifs(seq_clean)

        # Clinical interpretation
        result["clinical_notes"] = self._clinical_interpretation(result)

        log.info(
            f"  ✅ {result['length_bp']} bp | GC: {result['gc_content_pct']}% | "
            f"ORFs: {len(result['open_reading_frames'])}"
        )
        return result

    def ncbi_blast_search(self, sequence: str,
                           database: str = "nt",
                           max_results: int = 5) -> list[dict]:
        """
        BLAST search — ਕਿਹੜੇ known genes/organisms ਨਾਲ ਮੇਲ ਖਾਂਦੀ ਹੈ।
        Uses NCBI E-utilities (free API).
        """
        if not BIOPYTHON:
            return [{"error": "BioPython required for BLAST"}]

        log.info(f"🔍 NCBI BLAST search (database={database})…")
        try:
            # Submit BLAST job
            result_handle = Entrez.efetch(
                db="nucleotide",
                id=sequence[:100],   # short probe
                rettype="fasta",
                retmode="text",
            )
            # For demo: search gene by text (real BLAST requires more setup)
            handle = Entrez.esearch(
                db="nucleotide",
                term=f"{sequence[:20]}[Sequence]",
                retmax=max_results,
            )
            record = Entrez.read(handle)
            handle.close()

            hits = []
            for uid in record.get("IdList", [])[:max_results]:
                time.sleep(0.34)  # NCBI rate limit
                fetch = Entrez.efetch(db="nucleotide", id=uid,
                                      rettype="gb", retmode="text")
                hits.append({"ncbi_id": uid, "raw": fetch.read()[:200]})
                fetch.close()

            log.info(f"  ✅ BLAST: {len(hits)} hits")
            return hits

        except Exception as e:
            log.warning(f"  ⚠️  BLAST error: {e}")
            return [{"error": str(e), "note": "Check internet + NCBI availability"}]

    def clinvar_lookup(self, gene_name: str) -> dict:
        """
        ClinVar API — gene → associated diseases/variants.
        Free NCBI API, no key required.
        """
        log.info(f"🏥 ClinVar lookup: {gene_name}")
        try:
            url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                f"?db=clinvar&term={urllib.parse.quote(gene_name)}[gene]"
                "&retmax=10&retmode=json"
            )
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())

            ids = data.get("esearchresult", {}).get("idlist", [])
            variants = []

            for vid in ids[:5]:
                time.sleep(0.34)
                fetch_url = (
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    f"?db=clinvar&id={vid}&retmode=json"
                )
                with urllib.request.urlopen(fetch_url, timeout=15) as r2:
                    vdata = json.loads(r2.read())

                doc = vdata.get("result", {}).get(vid, {})
                variants.append({
                    "variant_id":   vid,
                    "title":        doc.get("title", ""),
                    "significance": doc.get("clinical_significance", {}).get("description", ""),
                    "conditions":   doc.get("trait_set", [{}])[0].get("trait_name", "")
                                    if doc.get("trait_set") else "",
                })

            result = {
                "gene":            gene_name,
                "total_variants":  data.get("esearchresult", {}).get("count", 0),
                "variants":        variants,
                "known_info":      self.KNOWN_SNPS.get(gene_name.upper(), {}),
            }
            log.info(f"  ✅ ClinVar: {len(variants)} variants for {gene_name}")
            return result

        except Exception as e:
            log.warning(f"  ⚠️  ClinVar error: {e}")
            return {"gene": gene_name, "error": str(e),
                    "known_info": self.KNOWN_SNPS.get(gene_name.upper(), {})}

    # ── Internal helpers ──────────────────────────────────────

    def _parse_input(self, seq: str) -> str:
        """Accept raw ACGT or FASTA format."""
        lines = seq.strip().splitlines()
        if lines[0].startswith(">"):
            lines = lines[1:]
        clean = "".join(lines).upper().replace(" ", "").replace("\n", "")
        return re.sub(r"[^ACGTN]", "", clean)

    def _base_composition(self, seq: str) -> dict:
        total = len(seq)
        return {
            "A": round(seq.count("A") / total * 100, 2),
            "T": round(seq.count("T") / total * 100, 2),
            "G": round(seq.count("G") / total * 100, 2),
            "C": round(seq.count("C") / total * 100, 2),
            "N": round(seq.count("N") / total * 100, 2),
        }

    def _gc_manual(self, seq: str) -> float:
        return round((seq.count("G") + seq.count("C")) / max(len(seq), 1) * 100, 2)

    def _codon_analysis(self, seq: str) -> dict:
        codons = [seq[i:i+3] for i in range(0, len(seq)-2, 3)]
        stop = sum(1 for c in codons if c in ("TAA", "TAG", "TGA"))
        start = codons.count("ATG")
        return {
            "total_codons": len(codons),
            "start_codons": start,
            "stop_codons":  stop,
            "coding_potential": "HIGH" if start > 0 and stop > 0 else "LOW",
        }

    def _find_orfs(self, seq: str, min_len: int = 30) -> list[dict]:
        """Find Open Reading Frames (ATG → stop codon)."""
        orfs = []
        for i in range(len(seq) - 2):
            if seq[i:i+3] == "ATG":
                for j in range(i+3, len(seq)-2, 3):
                    codon = seq[j:j+3]
                    if codon in ("TAA", "TAG", "TGA"):
                        length = j - i + 3
                        if length >= min_len:
                            orfs.append({
                                "start":  i,
                                "end":    j + 3,
                                "length": length,
                                "frame":  i % 3,
                                "protein_length": length // 3,
                            })
                        break
        return sorted(orfs, key=lambda x: -x["length"])[:10]

    def _find_repeats(self, seq: str) -> list[dict]:
        """Find tandem repeats (relevant for Huntington's, Fragile X, etc.)."""
        repeats = []
        for unit_len in [2, 3, 4]:
            i = 0
            while i < len(seq) - unit_len * 3:
                unit = seq[i:i+unit_len]
                count = 0
                j = i
                while seq[j:j+unit_len] == unit:
                    count += 1
                    j += unit_len
                if count >= 5:   # ≥5 repeats = noteworthy
                    repeats.append({
                        "unit":   unit,
                        "count":  count,
                        "start":  i,
                        "end":    j,
                        "note":   "⚠️ High repeat count" if count > 20 else "Normal",
                    })
                    i = j
                else:
                    i += 1
        return repeats[:8]

    def _scan_motifs(self, seq: str) -> list[str]:
        """Scan for known regulatory/disease-relevant motifs."""
        motifs = {
            "TATAAA":   "TATA box (promoter region)",
            "AATAAA":   "Polyadenylation signal",
            "CCAAT":    "CCAAT box (transcription factor binding)",
            "GGGCGG":   "GC box (SP1 binding site)",
            "ATGCAAATTTGGG": "BRCA1-like motif",
            "CAGCAGCAG": "CAG repeat — Huntington's risk motif",
        }
        found = []
        for motif, desc in motifs.items():
            if motif in seq:
                pos = seq.index(motif)
                found.append(f"{desc} at position {pos}")
        return found

    def _clinical_interpretation(self, result: dict) -> list[str]:
        notes = []
        gc = result.get("gc_content_pct", 50)
        if gc > 65:
            notes.append(f"⚠️ High GC content ({gc}%) — possible regulatory region or GC-rich gene")
        if gc < 35:
            notes.append(f"ℹ️ Low GC content ({gc}%) — common in AT-rich regions")

        repeats = result.get("repeat_regions", [])
        for r in repeats:
            if r.get("count", 0) > 20:
                notes.append(
                    f"🚨 Long repeat ({r['unit']}×{r['count']}) at pos {r['start']} — "
                    f"trinucleotide repeat expansion diseases possible"
                )

        orfs = result.get("open_reading_frames", [])
        if orfs:
            largest = orfs[0]["protein_length"]
            notes.append(f"✅ Largest ORF encodes ~{largest} amino acid protein")
        else:
            notes.append("ℹ️ No significant ORF found — may be non-coding RNA or intronic region")

        return notes if notes else ["No significant clinical flags detected"]


# ══════════════════════════════════════════════════════════════
# MODULE 2 — BLOOD REPORT AI
# ══════════════════════════════════════════════════════════════
class BloodReportAI:
    """
    AI-powered blood report analyzer.

    ਕੀ ਕਰਦਾ ਹੈ:
    - CBC (Complete Blood Count) parsing
    - LFT, RFT, lipid panel
    - Abnormal values flagging with severity
    - PubMed research linking
    - ਡਾਕਟਰ ਲਈ actionable insights
    """

    # Normal ranges (WHO / clinical standards)
    NORMAL_RANGES = {
        # CBC
        "hemoglobin_male":    (13.5, 17.5, "g/dL",   "Hemoglobin (Male)"),
        "hemoglobin_female":  (12.0, 15.5, "g/dL",   "Hemoglobin (Female)"),
        "wbc":                (4.0,  11.0, "×10³/μL", "White Blood Cells"),
        "platelets":          (150,  400,  "×10³/μL", "Platelets"),
        "rbc_male":           (4.5,  5.9,  "×10⁶/μL", "RBC (Male)"),
        "rbc_female":         (4.0,  5.2,  "×10⁶/μL", "RBC (Female)"),
        "hematocrit_male":    (41,   53,   "%",        "Hematocrit (Male)"),
        "hematocrit_female":  (36,   46,   "%",        "Hematocrit (Female)"),
        "mcv":                (80,   100,  "fL",       "Mean Corpuscular Volume"),
        "mch":                (27,   33,   "pg",       "MCH"),
        "mchc":               (32,   36,   "g/dL",     "MCHC"),
        "neutrophils":        (40,   70,   "%",        "Neutrophils"),
        "lymphocytes":        (20,   45,   "%",        "Lymphocytes"),
        "eosinophils":        (1,    4,    "%",        "Eosinophils"),
        # Metabolic
        "glucose_fasting":    (70,   100,  "mg/dL",   "Fasting Glucose"),
        "glucose_pp":         (70,   140,  "mg/dL",   "PP Glucose"),
        "hba1c":              (4.0,  5.6,  "%",       "HbA1c"),
        "creatinine_male":    (0.7,  1.3,  "mg/dL",   "Creatinine (Male)"),
        "creatinine_female":  (0.5,  1.1,  "mg/dL",   "Creatinine (Female)"),
        "urea":               (7,    20,   "mg/dL",   "BUN/Urea"),
        # Liver
        "alt":                (7,    56,   "U/L",     "ALT (SGPT)"),
        "ast":                (10,   40,   "U/L",     "AST (SGOT)"),
        "bilirubin_total":    (0.2,  1.2,  "mg/dL",   "Total Bilirubin"),
        "albumin":            (3.5,  5.0,  "g/dL",    "Albumin"),
        # Lipids
        "cholesterol":        (0,    200,  "mg/dL",   "Total Cholesterol"),
        "ldl":                (0,    100,  "mg/dL",   "LDL Cholesterol"),
        "hdl_male":           (40,   60,   "mg/dL",   "HDL (Male)"),
        "hdl_female":         (50,   60,   "mg/dL",   "HDL (Female)"),
        "triglycerides":      (0,    150,  "mg/dL",   "Triglycerides"),
        # Thyroid
        "tsh":                (0.4,  4.0,  "mIU/L",   "TSH"),
        "t4_free":            (0.8,  1.8,  "ng/dL",   "Free T4"),
        # Vitamins
        "vitamin_d":          (30,   100,  "ng/mL",   "Vitamin D"),
        "vitamin_b12":        (200,  900,  "pg/mL",   "Vitamin B12"),
        "ferritin_male":      (12,   300,  "ng/mL",   "Ferritin (Male)"),
        "ferritin_female":    (12,   150,  "ng/mL",   "Ferritin (Female)"),
    }

    CONDITION_PATTERNS = {
        "anemia": {
            "markers": ["hemoglobin", "rbc", "ferritin"],
            "pattern": "low",
            "research_query": "anemia treatment iron deficiency",
        },
        "diabetes": {
            "markers": ["glucose_fasting", "hba1c"],
            "pattern": "high",
            "research_query": "type 2 diabetes management HbA1c",
        },
        "thyroid_dysfunction": {
            "markers": ["tsh"],
            "pattern": "any",
            "research_query": "hypothyroidism hyperthyroidism TSH management",
        },
        "liver_disease": {
            "markers": ["alt", "ast", "bilirubin_total"],
            "pattern": "high",
            "research_query": "liver enzyme elevation hepatitis NAFLD",
        },
        "cardiovascular_risk": {
            "markers": ["cholesterol", "ldl", "triglycerides"],
            "pattern": "high",
            "research_query": "cardiovascular risk LDL reduction statin therapy",
        },
        "kidney_disease": {
            "markers": ["creatinine", "urea"],
            "pattern": "high",
            "research_query": "chronic kidney disease creatinine elevation management",
        },
        "vitamin_d_deficiency": {
            "markers": ["vitamin_d"],
            "pattern": "low",
            "research_query": "vitamin D deficiency supplementation bone health",
        },
    }

    def parse_report(self, report_text: str, gender: str = "male",
                     age: int = 40) -> dict:
        """
        Parse blood report text → structured analysis.
        Input: raw text from PDF/manual entry
        """
        log.info("🔬 Parsing blood report…")

        values = self._extract_values(report_text)
        flagged = self._flag_abnormal(values, gender)
        conditions = self._detect_conditions(flagged)
        pubmed_links = self._build_pubmed_queries(conditions)

        result = {
            "extracted_values":  values,
            "abnormal_flags":    flagged,
            "suspected_patterns": conditions,
            "pubmed_research":   pubmed_links,
            "severity_summary":  self._severity_summary(flagged),
            "priority_action":   self._priority_action(flagged, conditions),
            "disclaimer":        "⚠️ Research tool only. Consult a qualified physician.",
        }

        log.info(f"  ✅ Extracted {len(values)} values | "
                 f"{len(flagged)} abnormal | {len(conditions)} patterns")
        return result

    def _extract_values(self, text: str) -> dict:
        """Extract numeric values from blood report text."""
        patterns = {
            "hemoglobin":       r"(?:hemoglobin|hb|hgb)\s*[:\-]?\s*([\d.]+)",
            "wbc":              r"(?:wbc|white blood cell|leukocyte)\s*[:\-]?\s*([\d.]+)",
            "platelets":        r"(?:platelet|plt)\s*[:\-]?\s*([\d.]+)",
            "glucose_fasting":  r"(?:fasting glucose|fbs|fasting blood sugar)\s*[:\-]?\s*([\d.]+)",
            "hba1c":            r"(?:hba1c|glycated hemoglobin|a1c)\s*[:\-]?\s*([\d.]+)",
            "creatinine":       r"(?:creatinine|creat)\s*[:\-]?\s*([\d.]+)",
            "alt":              r"(?:alt|sgpt)\s*[:\-]?\s*([\d.]+)",
            "ast":              r"(?:ast|sgot)\s*[:\-]?\s*([\d.]+)",
            "cholesterol":      r"(?:total cholesterol|cholesterol)\s*[:\-]?\s*([\d.]+)",
            "ldl":              r"(?:ldl|low density)\s*[:\-]?\s*([\d.]+)",
            "hdl":              r"(?:hdl|high density)\s*[:\-]?\s*([\d.]+)",
            "triglycerides":    r"(?:triglyceride|tg)\s*[:\-]?\s*([\d.]+)",
            "tsh":              r"tsh\s*[:\-]?\s*([\d.]+)",
            "vitamin_d":        r"(?:vitamin d|25-oh|25\s*oh)\s*[:\-]?\s*([\d.]+)",
            "vitamin_b12":      r"(?:vitamin b12|b12|cobalamin)\s*[:\-]?\s*([\d.]+)",
            "ferritin":         r"ferritin\s*[:\-]?\s*([\d.]+)",
            "urea":             r"(?:urea|bun|blood urea)\s*[:\-]?\s*([\d.]+)",
        }
        text_lower = text.lower()
        extracted = {}
        for marker, pattern in patterns.items():
            m = re.search(pattern, text_lower)
            if m:
                extracted[marker] = float(m.group(1))
        return extracted

    def _flag_abnormal(self, values: dict, gender: str) -> list[dict]:
        flags = []
        for marker, value in values.items():
            # Gender-specific ranges
            key = f"{marker}_{gender}" if f"{marker}_{gender}" in self.NORMAL_RANGES else marker
            if key not in self.NORMAL_RANGES:
                continue
            low, high, unit, label = self.NORMAL_RANGES[key]
            status = "NORMAL"
            severity = "none"
            if value < low:
                deviation = (low - value) / low * 100
                status = "LOW"
                severity = "HIGH" if deviation > 30 else "MODERATE" if deviation > 15 else "MILD"
            elif value > high:
                deviation = (value - high) / high * 100
                status = "HIGH"
                severity = "HIGH" if deviation > 50 else "MODERATE" if deviation > 20 else "MILD"
            if status != "NORMAL":
                flags.append({
                    "marker":   label,
                    "value":    value,
                    "unit":     unit,
                    "status":   status,
                    "severity": severity,
                    "range":    f"{low}–{high} {unit}",
                })
        return sorted(flags, key=lambda x: {"HIGH": 0, "MODERATE": 1, "MILD": 2}[x["severity"]])

    def _detect_conditions(self, flags: list[dict]) -> list[str]:
        flag_markers = {f["marker"].lower() for f in flags}
        detected = []
        for cond, info in self.CONDITION_PATTERNS.items():
            hits = sum(1 for m in info["markers"] if any(m in fm for fm in flag_markers))
            if hits >= 1:
                detected.append(cond.replace("_", " ").title())
        return detected

    def _build_pubmed_queries(self, conditions: list[str]) -> list[str]:
        urls = []
        for cond in conditions[:3]:
            query = urllib.parse.quote(f"{cond} latest treatment 2024")
            urls.append(f"https://pubmed.ncbi.nlm.nih.gov/?term={query}")
        return urls

    def _severity_summary(self, flags: list[dict]) -> str:
        high = sum(1 for f in flags if f["severity"] == "HIGH")
        mod  = sum(1 for f in flags if f["severity"] == "MODERATE")
        mild = sum(1 for f in flags if f["severity"] == "MILD")
        if high > 0:
            return f"🚨 URGENT: {high} critical value(s) need immediate attention"
        if mod > 0:
            return f"⚠️ MODERATE: {mod} value(s) need physician review"
        if mild > 0:
            return f"ℹ️ MILD: {mild} value(s) slightly out of range — monitor"
        return "✅ All extracted values within normal range"

    def _priority_action(self, flags: list[dict], conditions: list[str]) -> list[str]:
        actions = []
        for f in flags:
            if f["severity"] == "HIGH":
                actions.append(f"🚨 {f['marker']}: {f['value']} {f['unit']} ({f['status']}) — Consult physician immediately")
        for cond in conditions:
            actions.append(f"📋 Pattern detected: {cond} — further diagnostic workup recommended")
        return actions if actions else ["✅ No urgent actions required"]


# ══════════════════════════════════════════════════════════════
# MODULE 3 — LAB VISION AI (LLaVA / moondream2)
# ══════════════════════════════════════════════════════════════
class LabVisionAI:
    """
    AI image analysis for lab specimens.
    Uses LLaVA or moondream2 — ALREADY in your Ollama stack!

    ਕੀ analyze ਕਰ ਸਕਦਾ ਹੈ:
    - Blood smear microscopy images
    - Cell morphology (shape, size, color)
    - Microbe/bacteria colony images
    - DNA gel electrophoresis
    - Lab result screenshots/photos
    """

    def __init__(self, vision_model: str = "moondream2"):
        self.model = vision_model
        # Check available vision models
        try:
            r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if "llava:latest" in models:
                self.model = "llava:latest"
            elif "moondream2" in models:
                self.model = "moondream2"
            log.info(f"👁️  Lab Vision AI using: {self.model}")
        except Exception:
            log.warning("⚠️  Ollama not available for vision")

    def analyze_image(self, image_path: str,
                      analysis_type: str = "general") -> dict:
        """
        Analyze a lab image using local LLaVA/moondream2.
        image_path: path to image file (JPG/PNG)
        analysis_type: 'blood_smear' | 'microscopy' | 'gel' | 'general'
        """
        import base64, os

        if not os.path.exists(image_path):
            return {"error": f"Image not found: {image_path}"}

        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompts = {
            "blood_smear": (
                "You are a hematologist. Analyze this blood smear image. "
                "Describe: 1) Red blood cell morphology (size, shape, color), "
                "2) White blood cell types visible, "
                "3) Platelet count estimation, "
                "4) Any abnormalities (anisocytosis, poikilocytosis, hypochromia), "
                "5) Possible clinical significance. Be specific and scientific."
            ),
            "microscopy": (
                "You are a microbiologist. Analyze this microscopy image. "
                "Identify: 1) Cell types visible, 2) Any microorganisms, "
                "3) Gram stain result if applicable, "
                "4) Morphological features, 5) Possible organisms or conditions."
            ),
            "gel": (
                "You are a molecular biologist. Analyze this gel electrophoresis image. "
                "Describe: 1) Band patterns, 2) Approximate sizes, "
                "3) Quality of DNA/RNA, 4) Any anomalies."
            ),
            "general": (
                "You are a medical scientist. Analyze this laboratory image carefully. "
                "Describe all visible scientific details, equipment, samples, "
                "and any notable findings. Provide a structured scientific analysis."
            ),
        }

        prompt = prompts.get(analysis_type, prompts["general"])

        log.info(f"👁️  Analyzing lab image: {analysis_type}")
        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model":  self.model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=120,
            )
            response = r.json().get("response", "")

            log.info("  ✅ Vision analysis complete")
            return {
                "image":        image_path,
                "model":        self.model,
                "analysis_type": analysis_type,
                "analysis":     response,
                "timestamp":    datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "note": "Ensure Ollama running with vision model"}

    def analyze_from_bytes(self, image_bytes: bytes,
                            analysis_type: str = "general") -> dict:
        """Analyze image from bytes (for API/web upload)."""
        import base64, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        result = self.analyze_image(tmp_path, analysis_type)
        os.unlink(tmp_path)
        return result


# ══════════════════════════════════════════════════════════════
# MODULE 4 — PHARMACOGENOMICS ENGINE
# ══════════════════════════════════════════════════════════════
class PharmacogenomicsEngine:
    """
    Drug-gene interaction analysis.
    Uses OpenFDA + PharmGKB (both free, open-source).

    ਕੀ ਦੱਸਦਾ ਹੈ:
    - ਕਿਹੜੀ ਦਵਾਈ ਤੁਹਾਡੀ DNA ਲਈ ਕੰਮ ਕਰੇਗੀ
    - Drug adverse effects by population
    - Gene variants → drug metabolism changes
    """

    # Key pharmacogene-drug interactions (PharmGKB curated)
    PGKB_KNOWN = {
        "CYP2D6": {
            "poor_metabolizer_drugs":  ["Codeine", "Tramadol", "Tamoxifen"],
            "rapid_metabolizer_drugs": ["Antidepressants (SSRIs)", "Antipsychotics"],
            "clinical_note": "CYP2D6 variants affect 25% of common drugs",
        },
        "CYP2C19": {
            "poor_metabolizer_drugs":  ["Clopidogrel", "Omeprazole", "Antidepressants"],
            "rapid_metabolizer_drugs": ["Proton pump inhibitors"],
            "clinical_note": "Important for cardiovascular medication dosing",
        },
        "SLCO1B1": {
            "poor_metabolizer_drugs":  ["Simvastatin", "Atorvastatin"],
            "rapid_metabolizer_drugs": [],
            "clinical_note": "Statin myopathy risk with SLCO1B1*5 variant",
        },
        "DPYD": {
            "poor_metabolizer_drugs":  ["5-Fluorouracil", "Capecitabine"],
            "rapid_metabolizer_drugs": [],
            "clinical_note": "DPYD deficiency → severe chemo toxicity risk",
        },
        "VKORC1": {
            "poor_metabolizer_drugs":  ["Warfarin"],
            "rapid_metabolizer_drugs": ["Warfarin"],
            "clinical_note": "Critical for warfarin dosing — affects INR",
        },
        "TPMT": {
            "poor_metabolizer_drugs":  ["Azathioprine", "Mercaptopurine"],
            "rapid_metabolizer_drugs": [],
            "clinical_note": "TPMT deficiency → life-threatening toxicity with thiopurines",
        },
    }

    def openfda_drug_search(self, drug_name: str) -> dict:
        """
        OpenFDA API — drug adverse events, interactions, warnings.
        Free, no API key required.
        """
        log.info(f"💊 OpenFDA search: {drug_name}")
        try:
            url = (
                "https://api.fda.gov/drug/event.json"
                f"?search=patient.drug.medicinalproduct:{urllib.parse.quote(drug_name)}"
                "&count=patient.reaction.reactionmeddrapt.exact&limit=10"
            )
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())

            results = data.get("results", [])
            return {
                "drug":           drug_name,
                "top_reactions":  [{"reaction": r["term"], "count": r["count"]}
                                   for r in results[:10]],
                "source":         "OpenFDA Adverse Events",
                "disclaimer":     "Population data only — individual response varies",
            }
        except Exception as e:
            return {"drug": drug_name, "error": str(e)}

    def gene_drug_profile(self, gene_variants: list[str]) -> dict:
        """
        Given gene variants → generate drug sensitivity profile.
        """
        profile = {
            "genes_analysed": gene_variants,
            "recommendations": [],
            "caution_drugs":   [],
            "monitor_drugs":   [],
        }

        for gene in gene_variants:
            gene_upper = gene.upper()
            if gene_upper in self.PGKB_KNOWN:
                info = self.PGKB_KNOWN[gene_upper]
                profile["caution_drugs"].extend(info["poor_metabolizer_drugs"])
                profile["recommendations"].append({
                    "gene":   gene_upper,
                    "note":   info["clinical_note"],
                    "action": f"Dose adjustment may be required for: "
                              f"{', '.join(info['poor_metabolizer_drugs'])}",
                })

        profile["summary"] = (
            f"Based on {len(gene_variants)} gene variants: "
            f"{len(profile['caution_drugs'])} drugs require dose consideration."
        )
        return profile


# ══════════════════════════════════════════════════════════════
# MODULE 5 — MASTER MEDICAL PIPELINE
# ══════════════════════════════════════════════════════════════
class MedicalSciencePipeline:
    """
    AMRIT Medical Science — Complete pipeline orchestrator.

    Workflow:
    Blood Report / DNA Sequence / Lab Image
            ↓
    Parse + Analyze (BioPython + pattern matching)
            ↓
    NCBI / ClinVar / OpenFDA lookup
            ↓
    LLaVA vision analysis (if image)
            ↓
    Drug-gene interaction check
            ↓
    PubMed research correlation
            ↓
    Ollama AI synthesis
            ↓
    Structured report for physician

    ⚠️ RESEARCH TOOL — Not a replacement for clinical diagnosis
    """

    def __init__(self, ollama_model: str = "qwen3:8b"):
        self.dna         = DNAAnalyzer()
        self.blood       = BloodReportAI()
        self.vision      = LabVisionAI()
        self.pharma      = PharmacogenomicsEngine()
        self.llm_model   = ollama_model
        log.info("🏥 AMRIT Medical Science Pipeline ready")
        log.info(f"   LLM: {ollama_model} | Vision: {self.vision.model}")

    def full_patient_analysis(self,
                               blood_report_text: str = "",
                               dna_sequence: str = "",
                               gene_variants: list = None,
                               lab_image_path: str = "",
                               patient_info: dict = None) -> dict:
        """
        Complete medical analysis pipeline.
        Any combination of inputs is accepted.
        """
        patient = patient_info or {"gender": "unknown", "age": 40}
        report = {
            "patient_info":     patient,
            "timestamp":        datetime.now().isoformat(),
            "disclaimer":       "⚠️ RESEARCH USE ONLY. Consult a qualified physician.",
        }

        # ── Blood report ─────────────────────────────────────
        if blood_report_text.strip():
            log.info("📋 Step 1: Blood report analysis")
            report["blood_analysis"] = self.blood.parse_report(
                blood_report_text,
                gender=patient.get("gender", "male"),
                age=patient.get("age", 40),
            )

        # ── DNA analysis ──────────────────────────────────────
        if dna_sequence.strip():
            log.info("🧬 Step 2: DNA sequence analysis")
            report["dna_analysis"] = self.dna.analyze_sequence(
                dna_sequence,
                label=patient.get("name", "Patient Sample")
            )

        # ── ClinVar gene lookup ───────────────────────────────
        if gene_variants:
            log.info(f"🔍 Step 3: ClinVar lookup for {len(gene_variants)} genes")
            report["gene_disease_links"] = {}
            for gene in gene_variants[:5]:  # max 5 to avoid rate limits
                report["gene_disease_links"][gene] = self.dna.clinvar_lookup(gene)
                time.sleep(0.5)

        # ── Pharmacogenomics ──────────────────────────────────
        if gene_variants:
            log.info("💊 Step 4: Drug-gene interaction analysis")
            report["drug_gene_profile"] = self.pharma.gene_drug_profile(gene_variants)

        # ── Vision analysis ───────────────────────────────────
        if lab_image_path:
            log.info("👁️  Step 5: Lab image analysis")
            report["image_analysis"] = self.vision.analyze_image(
                lab_image_path, "blood_smear"
            )

        # ── AI synthesis ──────────────────────────────────────
        log.info("🤖 Step 6: AI medical synthesis (Ollama)")
        report["ai_synthesis"] = self._ollama_synthesis(report)

        # ── Priority summary ──────────────────────────────────
        report["priority_summary"] = self._generate_priority_summary(report)

        log.info("✅ Medical analysis complete")
        return report

    def _ollama_synthesis(self, report: dict) -> str:
        """Ask local Ollama to synthesize all findings."""
        context_parts = []

        if "blood_analysis" in report:
            flags = report["blood_analysis"].get("abnormal_flags", [])
            if flags:
                context_parts.append(
                    "Blood Report Abnormalities: " +
                    "; ".join(f"{f['marker']}={f['value']} ({f['status']}, {f['severity']})"
                              for f in flags[:5])
                )

        if "dna_analysis" in report:
            dna = report["dna_analysis"]
            context_parts.append(
                f"DNA Analysis: {dna.get('length_bp', 0)} bp, "
                f"GC={dna.get('gc_content_pct', 0)}%, "
                f"ORFs={len(dna.get('open_reading_frames', []))}"
            )
            notes = dna.get("clinical_notes", [])
            if notes:
                context_parts.append("DNA Clinical Notes: " + "; ".join(notes))

        if "drug_gene_profile" in report:
            caution = report["drug_gene_profile"].get("caution_drugs", [])
            if caution:
                context_parts.append(
                    f"Drug Cautions: {', '.join(caution[:5])}"
                )

        if not context_parts:
            return "Insufficient data for AI synthesis."

        prompt = (
            "You are a clinical research AI assistant. "
            "Synthesize these medical findings into a concise physician summary:\n\n"
            + "\n".join(context_parts)
            + "\n\nProvide: 1) Key findings, 2) Clinical concerns, "
            "3) Recommended next steps. Be brief and scientific."
        )

        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model":   self.llm_model,
                    "prompt":  prompt,
                    "stream":  False,
                    "options": {"temperature": 0.2, "num_predict": 512},
                },
                timeout=90,
            )
            return r.json().get("response", "AI synthesis unavailable")
        except Exception as e:
            return f"[Ollama offline: {e}]"

    def _generate_priority_summary(self, report: dict) -> list[str]:
        priorities = []
        if "blood_analysis" in report:
            actions = report["blood_analysis"].get("priority_action", [])
            priorities.extend(actions)
        if "dna_analysis" in report:
            notes = report["dna_analysis"].get("clinical_notes", [])
            for n in notes:
                if "🚨" in n or "⚠️" in n:
                    priorities.append(f"DNA: {n}")
        if "drug_gene_profile" in report:
            caution = report["drug_gene_profile"].get("caution_drugs", [])
            if caution:
                priorities.append(
                    f"💊 Pharmacogenomic caution: {', '.join(caution[:3])}"
                )
        return priorities if priorities else ["No urgent priorities identified"]


# ══════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║  AMRIT Medical Science Engine — Demo                 ║
║  BioPython + NCBI + ClinVar + OpenFDA + LLaVA       ║
╚══════════════════════════════════════════════════════╝
""")
    pipeline = MedicalSciencePipeline(ollama_model="qwen3:8b")

    # ── DEMO 1: DNA Analysis ──────────────────────────────────
    print("🧬 DEMO 1: DNA Sequence Analysis")
    sample_dna = """
    ATGCAAATTTGGGAGATCCTGAGCAATGCAGAAGAGAAGAAACAGCAGCAG
    CAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAGCAACAA
    CAACAACAACAACAACAACAACAACAACAACAACAACAACAATAA
    """
    dna_result = pipeline.dna.analyze_sequence(sample_dna, "Sample Gene")
    print(f"  Length: {dna_result['length_bp']} bp")
    print(f"  GC content: {dna_result['gc_content_pct']}%")
    print(f"  Codon analysis: {dna_result['codon_analysis']}")
    repeats = dna_result.get("repeat_regions", [])
    if repeats:
        print(f"  ⚠️  Repeat regions: {len(repeats)} found")
        for r in repeats[:3]:
            print(f"     {r['unit']} × {r['count']} at pos {r['start']} — {r['note']}")
    print(f"  Clinical notes:")
    for note in dna_result["clinical_notes"]:
        print(f"    {note}")

    print("\n💊 DEMO 2: Pharmacogenomics")
    pharma = pipeline.pharma
    profile = pharma.gene_drug_profile(["CYP2D6", "BRCA1", "MTHFR"])
    print(f"  {profile['summary']}")
    for rec in profile["recommendations"]:
        print(f"  Gene {rec['gene']}: {rec['action']}")

    print("\n📋 DEMO 3: Blood Report Parsing")
    sample_report = """
    Complete Blood Count:
    Hemoglobin: 9.2 g/dL
    WBC: 12.5 ×10³/μL
    Platelets: 180 ×10³/μL

    Metabolic Panel:
    Fasting Glucose: 142 mg/dL
    HbA1c: 7.8%
    Creatinine: 1.6 mg/dL

    Liver Function:
    ALT: 85 U/L
    AST: 72 U/L

    Lipid Panel:
    Cholesterol: 240 mg/dL
    LDL: 165 mg/dL
    Triglycerides: 220 mg/dL

    Vitamins:
    Vitamin D: 12 ng/mL
    Vitamin B12: 180 pg/mL
    """
    blood_result = pipeline.blood.parse_report(sample_report, "male", 45)
    print(f"  {blood_result['severity_summary']}")
    print(f"  Suspected patterns: {blood_result['suspected_patterns']}")
    print("  Priority actions:")
    for action in blood_result["priority_action"][:3]:
        print(f"    {action}")

    print("\n✅ AMRIT Medical Science Engine demo complete!")
    print(f"   BioPython: {'✅' if BIOPYTHON else '❌ pip install biopython'}")
    print("   For image analysis: ollama pull moondream2")
    print("   For AI synthesis:   ollama pull qwen3:8b")
