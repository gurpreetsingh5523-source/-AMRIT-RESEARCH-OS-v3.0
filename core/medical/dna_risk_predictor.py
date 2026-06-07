"""
AMRIT RESEARCH OS v4.0
core/medical/dna_risk_predictor.py

DNA Risk Predictor — the orchestrator for the medical/DNA module.

Pipeline:
  raw DNA  -> SNPAnalyser (genotypes + curated risk scoring)
           -> ClinVar validation (optional, live NCBI)
           -> Pharmacogenomics (drug-gene response)
           -> PubMed evidence links (optional)
           -> consolidated risk report

DISCLAIMER: Research/education only. NOT a medical diagnosis.
"""

from core.research.genomics import SNPAnalyser, ClinVarReader, NCBIFetcher
from core.medical.pharmacogenomics import Pharmacogenomics


class DNARiskPredictor:

    def __init__(self):
        self.ncbi = NCBIFetcher()
        self.clinvar = ClinVarReader(self.ncbi)
        self.snp = SNPAnalyser(self.clinvar)
        self.pgx = Pharmacogenomics()

    def predict(self, raw_dna: str, validate: bool = False, evidence: bool = False) -> dict:
        """Produce a consolidated genetic risk + drug-response report."""
        genotypes = self.snp.parse_raw(raw_dna)
        genetic_risk = self.snp.analyse(raw_dna, validate_clinvar=validate)
        drug_response = self.pgx.analyse(genotypes)

        # Rank traits by risk score
        ranked = sorted(
            genetic_risk.get("trait_scores", {}).items(),
            key=lambda kv: kv[1], reverse=True,
        )

        # Optional PubMed evidence for the top trait
        evidence_links = []
        if evidence and ranked:
            top_trait = ranked[0][0]
            evidence_links = self.ncbi.pubmed_evidence(top_trait, retmax=3)

        return {
            "snps_parsed": len(genotypes),
            "genetic_risk": genetic_risk,
            "drug_response": drug_response,
            "ranked_risks": [{"trait": t, "score": s} for t, s in ranked],
            "top_concern": ranked[0][0] if ranked else None,
            "evidence": evidence_links,
            "disclaimer": (
                "Research/education only. NOT a medical diagnosis. "
                "Genetic risk is probabilistic — consult a clinical geneticist."
            ),
        }
