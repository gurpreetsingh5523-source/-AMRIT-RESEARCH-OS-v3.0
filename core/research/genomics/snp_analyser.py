"""
AMRIT RESEARCH OS v4.5
core/research/genomics/snp_analyser.py

SNP analyser — parses consumer DNA raw files (23andMe / AncestryDNA)
and scores variants against a curated risk table + ClinVar.

Supported formats:
  23andMe:   rsid<TAB>chromosome<TAB>position<TAB>genotype      (genotype = 'AG')
  AncestryDNA: rsid<TAB>chromosome<TAB>position<TAB>allele1<TAB>allele2
  Lines starting with '#' are ignored.

NOTE: This is a research/education tool, NOT a medical diagnostic.
"""

import os

from .clinvar_reader import ClinVarReader


# Curated risk model: rsID -> {gene, trait, risk_allele, effect}
# Effect scaling: each copy of the risk allele adds `per_allele` to the score.
RISK_MODEL = {
    "rs429358":  {"gene": "APOE",  "trait": "Alzheimer's disease",      "risk_allele": "C", "per_allele": 0.40},
    "rs7412":    {"gene": "APOE",  "trait": "Alzheimer's (protective)", "risk_allele": "T", "per_allele": -0.25},
    "rs1801133": {"gene": "MTHFR", "trait": "Cardiovascular / homocysteine", "risk_allele": "T", "per_allele": 0.20},
    "rs1799945": {"gene": "HFE",   "trait": "Hemochromatosis (iron overload)", "risk_allele": "G", "per_allele": 0.25},
    "rs334":     {"gene": "HBB",   "trait": "Sickle cell trait",        "risk_allele": "T", "per_allele": 0.50},
    "rs9939609": {"gene": "FTO",   "trait": "Obesity / BMI",            "risk_allele": "A", "per_allele": 0.18},
    "rs7903146": {"gene": "TCF7L2","trait": "Type 2 diabetes",          "risk_allele": "T", "per_allele": 0.30},
    "rs1333049": {"gene": "CDKN2B-AS1", "trait": "Coronary artery disease", "risk_allele": "C", "per_allele": 0.22},
}


class SNPAnalyser:

    def __init__(self, clinvar: ClinVarReader = None):
        self.clinvar = clinvar or ClinVarReader()

    # ─────────────────── parsing ───────────────────

    @staticmethod
    def parse_raw(text: str) -> dict:
        """Parse raw DNA text into {rsid: genotype}."""
        genotypes = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("rsid"):
                continue
            parts = line.split("\t") if "\t" in line else line.split()
            if len(parts) < 4:
                continue
            rsid = parts[0].lower()
            if not rsid.startswith("rs"):
                continue
            if len(parts) == 4:          # 23andMe: ...,genotype
                genotype = parts[3].upper()
            else:                         # AncestryDNA: ...,allele1,allele2
                genotype = (parts[3] + parts[4]).upper()
            genotype = genotype.replace("--", "").replace("00", "")
            if genotype:
                genotypes[rsid] = genotype
        return genotypes

    def parse_file(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        with open(path, "r", errors="ignore") as f:
            return self.parse_raw(f.read())

    # ─────────────────── scoring ───────────────────

    def score_variant(self, rsid: str, genotype: str) -> dict:
        model = RISK_MODEL.get(rsid)
        if not model:
            return {}
        risk_allele = model["risk_allele"]
        copies = genotype.upper().count(risk_allele)
        score = round(copies * model["per_allele"], 3)
        level = (
            "elevated" if score >= 0.4 else
            "moderate" if score >= 0.2 else
            "protective" if score < 0 else
            "low"
        )
        return {
            "rsid": rsid,
            "gene": model["gene"],
            "trait": model["trait"],
            "genotype": genotype,
            "risk_allele": risk_allele,
            "risk_allele_copies": copies,
            "risk_score": score,
            "risk_level": level,
        }

    def analyse(self, text: str, validate_clinvar: bool = False) -> dict:
        """Analyse raw DNA text and return per-trait risk findings."""
        genotypes = self.parse_raw(text)
        findings = []
        for rsid in RISK_MODEL:
            if rsid in genotypes:
                v = self.score_variant(rsid, genotypes[rsid])
                if not v:
                    continue
                if validate_clinvar:
                    cv = self.clinvar.variant_significance(rsid)
                    v["clinvar_significance"] = cv.get("significance")
                    v["clinvar_condition"] = cv.get("condition")
                findings.append(v)

        # Aggregate per trait
        trait_scores = {}
        for f in findings:
            trait_scores.setdefault(f["trait"], 0.0)
            trait_scores[f["trait"]] += f["risk_score"]

        return {
            "snps_in_file": len(genotypes),
            "analysed_variants": len(findings),
            "findings": findings,
            "trait_scores": {k: round(v, 3) for k, v in trait_scores.items()},
            "disclaimer": (
                "Research/education only. Not a medical diagnosis. "
                "Consult a clinical geneticist for interpretation."
            ),
        }
