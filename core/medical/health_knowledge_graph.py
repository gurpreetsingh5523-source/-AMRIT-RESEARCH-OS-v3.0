"""
AMRIT RESEARCH OS v4.5
core/medical/health_knowledge_graph.py

Health Knowledge Graph — links Patient, Marker, Gene, Disease and Drug
entities using the existing SQLite-backed KnowledgeGraph engine.

Entity types: Patient, Marker, Gene, Disease, Drug, SNP
"""

from core.knowledge_graph import KnowledgeGraph


class HealthKnowledgeGraph:

    def __init__(self, db_path: str = "data/health_graph.db"):
        self.kg = KnowledgeGraph(db_path=db_path)

    # ─────────────────── ingest ───────────────────

    def add_blood_findings(self, parsed: dict, patient: str = "patient"):
        self.kg.add_node(patient, patient, "Patient")
        for marker, info in parsed.get("markers", {}).items():
            node = f"marker:{marker}"
            self.kg.add_node(node, marker, "Marker")
            self.kg.add_edge(patient, node, f"has_{info['flag'].lower()}")

    def add_dna_findings(self, dna_report: dict, patient: str = "patient"):
        self.kg.add_node(patient, patient, "Patient")
        for f in dna_report.get("genetic_risk", {}).get("findings", []):
            snp = f"snp:{f['rsid']}"
            gene = f"gene:{f['gene']}"
            disease = f"disease:{f['trait']}"
            self.kg.add_node(snp, f["rsid"], "SNP")
            self.kg.add_node(gene, f["gene"], "Gene")
            self.kg.add_node(disease, f["trait"], "Disease")
            self.kg.add_edge(patient, snp, "carries")
            self.kg.add_edge(snp, gene, "located_in")
            self.kg.add_edge(gene, disease, "associated_with", weight=abs(f["risk_score"]) or 0.1)

    def add_drug_findings(self, pgx: dict, patient: str = "patient"):
        self.kg.add_node(patient, patient, "Patient")
        for f in pgx.get("interactions", []):
            gene = f"gene:{f['gene']}"
            drug = f"drug:{f['drug']}"
            self.kg.add_node(gene, f["gene"], "Gene")
            self.kg.add_node(drug, f["drug"], "Drug")
            self.kg.add_edge(gene, drug, f"affects_response_{f['impact']}")

    # ─────────────────── query ───────────────────

    def neighbors(self, node: str) -> list:
        return self.kg.get_neighbors(node)

    def summary(self) -> dict:
        return self.kg.summary()

    def export_json(self, path: str = "reports/json/health_graph.json"):
        return self.kg.export_json(path)
