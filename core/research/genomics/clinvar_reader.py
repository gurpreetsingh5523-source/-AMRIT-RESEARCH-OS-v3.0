"""
AMRIT RESEARCH OS v4.0
core/research/genomics/clinvar_reader.py

ClinVar reader — maps DNA variants / genes to clinical significance.

Uses NCBI E-utilities against the `clinvar` database (free, no key).
Falls back to a small curated table of well-established variants so the
module is useful even offline.
"""

from .ncbi_fetcher import NCBIFetcher


# Curated, well-established variant -> condition map (offline fallback).
CURATED = {
    "rs7412":    {"gene": "APOE", "condition": "Alzheimer's disease (protective e2)", "significance": "risk-modifier"},
    "rs429358":  {"gene": "APOE", "condition": "Alzheimer's disease (e4 risk)", "significance": "risk-factor"},
    "rs1801133": {"gene": "MTHFR", "condition": "Hyperhomocysteinemia / cardiovascular risk", "significance": "risk-factor"},
    "rs1799945": {"gene": "HFE", "condition": "Hereditary hemochromatosis", "significance": "pathogenic-low-penetrance"},
    "rs334":     {"gene": "HBB", "condition": "Sickle cell anemia", "significance": "pathogenic"},
    "rs80357906":{"gene": "BRCA1", "condition": "Hereditary breast/ovarian cancer", "significance": "pathogenic"},
    "rs28897696":{"gene": "BRCA2", "condition": "Hereditary breast/ovarian cancer", "significance": "pathogenic"},
}


class ClinVarReader:

    def __init__(self, fetcher: NCBIFetcher = None):
        self.ncbi = fetcher or NCBIFetcher()

    def variant_significance(self, rsid: str) -> dict:
        """Return clinical significance for a variant (rsID)."""
        rsid = rsid.lower().strip()
        curated = CURATED.get(rsid)

        ids = self.ncbi.esearch("clinvar", rsid, retmax=1)
        live = {}
        if ids:
            summary = self.ncbi.esummary("clinvar", ids)
            rec = summary.get(ids[0], {})
            if rec:
                germline = rec.get("germline_classification", {})
                live = {
                    "uid": ids[0],
                    "title": rec.get("title", ""),
                    "clinical_significance": germline.get("description", ""),
                    "review_status": germline.get("review_status", ""),
                }

        return {
            "rsid": rsid,
            "curated": curated,
            "clinvar": live or {"note": "no ClinVar record retrieved"},
            "condition": (curated or {}).get("condition", live.get("title", "unknown")),
            "significance": (curated or {}).get("significance",
                                                live.get("clinical_significance", "uncertain")),
        }

    def gene_conditions(self, gene: str) -> dict:
        """List pathogenic conditions linked to a gene via ClinVar."""
        ids = self.ncbi.esearch("clinvar", f"{gene}[gene] AND pathogenic[Clinical_significance]", retmax=5)
        summary = self.ncbi.esummary("clinvar", ids)
        conditions = []
        for uid in ids:
            rec = summary.get(uid, {})
            if rec:
                conditions.append(rec.get("title", ""))
        return {"gene": gene, "pathogenic_variants": conditions}
