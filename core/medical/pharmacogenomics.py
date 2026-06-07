"""
AMRIT RESEARCH OS v4.0
core/medical/pharmacogenomics.py

Pharmacogenomics — predicts drug response from genotype using
well-established gene-drug guidance (CPIC-style, simplified).

DISCLAIMER: Educational tool. Not prescribing guidance.
"""


# rsID -> guidance. Each entry maps the risk/variant allele to a drug effect.
PGX_RULES = {
    "rs4244285": {  # CYP2C19*2
        "gene": "CYP2C19", "variant_allele": "A",
        "drug": "Clopidogrel",
        "effect": "Reduced activation -> lower antiplatelet effect; consider alternative.",
    },
    "rs1799853": {  # CYP2C9*2
        "gene": "CYP2C9", "variant_allele": "T",
        "drug": "Warfarin",
        "effect": "Slower metabolism -> lower warfarin dose may be required.",
    },
    "rs9923231": {  # VKORC1
        "gene": "VKORC1", "variant_allele": "T",
        "drug": "Warfarin",
        "effect": "Increased sensitivity -> reduced warfarin dose requirement.",
    },
    "rs3892097": {  # CYP2D6*4
        "gene": "CYP2D6", "variant_allele": "A",
        "drug": "Codeine",
        "effect": "Poor metabolism -> reduced analgesia from codeine.",
    },
    "rs4149056": {  # SLCO1B1
        "gene": "SLCO1B1", "variant_allele": "C",
        "drug": "Simvastatin",
        "effect": "Increased myopathy risk -> consider lower statin dose.",
    },
    "rs1142345": {  # TPMT*3C
        "gene": "TPMT", "variant_allele": "C",
        "drug": "Azathioprine / 6-MP",
        "effect": "Reduced activity -> myelosuppression risk; lower thiopurine dose.",
    },
}


class Pharmacogenomics:

    def analyse(self, genotypes: dict) -> dict:
        """
        genotypes: {rsid: 'AG', ...}  (as produced by SNPAnalyser.parse_raw)
        Returns drug-gene interaction findings.
        """
        findings = []
        for rsid, rule in PGX_RULES.items():
            gt = genotypes.get(rsid)
            if not gt:
                continue
            copies = gt.upper().count(rule["variant_allele"])
            if copies == 0:
                impact = "normal"
            elif copies == 1:
                impact = "intermediate"
            else:
                impact = "high"
            findings.append({
                "rsid": rsid,
                "gene": rule["gene"],
                "drug": rule["drug"],
                "genotype": gt,
                "variant_allele_copies": copies,
                "impact": impact,
                "guidance": rule["effect"] if copies > 0 else "Standard dosing expected.",
            })
        return {
            "analysed": len(findings),
            "interactions": findings,
            "actionable": [f for f in findings if f["variant_allele_copies"] > 0],
            "disclaimer": "Educational only. Not prescribing guidance. Consult a clinician/pharmacist.",
        }
