#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMRIT RESEARCH OS v3.0
main.py — Autonomous Research Loop

Flow:
  Create hypothesis → Collect data → Analyse → Debate
  → Verify → Store memory → Generate paper → Dashboard
"""

import sys
import os
import logging
import datetime

# ─────────────────── Logging setup ───────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("AmritResearchOS")

# ─────────────────── Imports ───────────────────
from core.brain import ResearchBrain
from core.memory import MemoryManager
from core.statistics import StatisticalEngine
from core.agents import AgentManager
from core.knowledge_graph import KnowledgeGraph
from core.data_sources import DataCollector
from core.paper_writer import PaperWriter
from core.dashboard import Dashboard
from core.quantum import QuantumLayer
from core.ai.ollama_client import OllamaClient


class AmritResearchOS:

    def __init__(self, domain: str = ""):
        log.info("Initialising AMRIT RESEARCH OS v3.0 ...")
        self.brain = ResearchBrain()
        self.memory = MemoryManager()
        self.stats = StatisticalEngine()
        self.agents = AgentManager()
        self.graph = KnowledgeGraph()
        self.data = DataCollector()
        self.writer = PaperWriter()
        self.dash = Dashboard()
        self.quantum = QuantumLayer()
        self.ai = OllamaClient(model="deepseek-coder-v2:latest")
        self.domain = domain or self.brain.domain
        # Log AI status
        if self.ai.is_available():
            models = self.ai.list_models()
            log.info(f"Ollama online — Models: {', '.join(models[:4])}")
        else:
            log.warning("Ollama offline — using rule-based fallbacks")

    # ─────────────────── Autonomous Research Loop ───────────────────

    def run(self, query: str = ""):
        self.dash.log_event("Research OS started")

        # ── Step 1: Generate Hypothesis ──
        # Use local AI if available, else rule-based
        if self.ai.is_available():
            hypothesis = self.ai.generate_hypothesis(self.domain)
            log.info(f"AI Hypothesis (qwen3:14b): {hypothesis}")
        else:
            hypothesis = self.brain.generate_hypothesis(self.domain)
            log.info(f"Hypothesis: {hypothesis}")
        self.dash.log_event(f"Hypothesis generated: {hypothesis[:60]}...")

        # ── Step 2: Research Plan ──
        plan = self.brain.generate_research_plan(hypothesis)
        log.info("Research plan created")

        # ── Step 3: Collect Data ──
        search_query = query or hypothesis[:80]
        log.info(f"Collecting data for: {search_query}")
        self.dash.log_event("Collecting data from 6 sources ...")
        collected = self.data.collect_all(search_query, max_per_source=3)
        arxiv_count = len(collected.get("arxiv", []))
        pubmed_count = len(collected.get("pubmed", []))
        log.info(f"Collected — ArXiv: {arxiv_count}, PubMed: {pubmed_count}")
        self.dash.log_event(f"Data collected: ArXiv={arxiv_count}, PubMed={pubmed_count}")

        # ── Step 4: Statistical Analysis ──
        log.info("Running statistical analysis ...")
        self.dash.log_event("Running statistics ...")
        result = self.stats.evaluate(hypothesis)
        log.info(f"Stats: p={result['p_value']}, effect={result['effect_size']}, verdict={result['verdict']}")

        # ── Step 5: Scientific Reasoning ──
        reasoning = self.brain.scientific_reasoning(hypothesis, result)
        log.info(f"Reasoning verdict: {reasoning['verdict']}")

        # ── Step 6: Multi-Agent Review ──
        log.info("Running multi-agent review ...")
        self.dash.log_event("Multi-agent swarm running ...")
        reviews = self.agents.review(hypothesis, result)

        # ── Step 7: AI Debate ──
        log.info("Running AI debate engine ...")
        self.dash.log_event("AI Debate: Believer vs Skeptic ...")
        debate = self.agents.debate(hypothesis, result)
        log.info(f"Debate: {debate['judge_verdict']}")

        # ── Step 8: Peer Review ──
        peer_review = self.agents.auto_peer_review(hypothesis, result)

        # ── AI Interpretation ──
        if self.ai.is_available():
            ai_interpretation = self.ai.analyze_result(hypothesis, result)
            log.info(f"AI Interpretation: {ai_interpretation[:80]}...")
            peer_review["ai_interpretation"] = ai_interpretation

        # ── Step 9: Knowledge Graph ──
        log.info("Building knowledge graph ...")
        self.graph.build_from_hypothesis(hypothesis, self.domain)
        graph_summary = self.graph.summary()
        self.graph.export_json()
        self.dash.log_event(f"Knowledge graph: {graph_summary['nodes']} nodes, {graph_summary['edges']} edges")

        # ── Step 10: Store Memory ──
        log.info("Storing results in memory ...")
        finding_id = self.memory.store_result(
            hypothesis, result, domain=self.domain, dataset="Multi-source"
        )
        for agent_name, review_text in reviews.items():
            self.memory.store_agent_review(finding_id, agent_name, review_text)

        # Self-evolution: record lesson
        if result["verdict"] in ("STRONG SUPPORT", "WEAK SUPPORT"):
            self.memory.record_evolution("successful", hypothesis)
        else:
            self.memory.record_evolution("failed", hypothesis)

        # ── Step 11: Auto Citations ──
        sources = []
        for item in collected.get("arxiv", []):
            if "title" in item and "error" not in item:
                sources.append({
                    "authors": ["ArXiv Authors"],
                    "year": datetime.datetime.now().year,
                    "title": item["title"],
                    "journal": "ArXiv Preprint",
                    "doi": "",
                })
        citations = self.writer.auto_cite(sources[:5])
        self.memory.update_citations(
            finding_id,
            apa="; ".join(citations["apa"][:3]),
            mla="; ".join(citations["mla"][:3]),
            ieee="; ".join(citations["ieee"][:3]),
        )

        # ── Step 12: Generate Paper ──
        log.info("Generating research paper ...")
        self.dash.log_event("Generating paper ...")

        # Use AI-generated abstract if available
        if self.ai.is_available():
            ai_abstract = self.ai.write_abstract(hypothesis, result)
            peer_review["ai_abstract"] = ai_abstract

        paper = self.writer.generate_paper(
            hypothesis=hypothesis,
            result=result,
            debate=debate,
            review=peer_review,
            sources=sources[:5],
            domain=self.domain,
        )
        json_path = self.writer.export_json(paper)
        pdf_path = self.writer.export_text_pdf(paper)
        log.info(f"Paper saved: {json_path}")
        log.info(f"Report saved: {pdf_path}")
        self.dash.log_event(f"Paper exported: {pdf_path}")

        # ── Step 13: Quantum Layer Status ──
        q_status = self.quantum.status()
        q_sim = self.quantum.simulate_qubit()

        # ── Step 14: Dashboard ──
        memory_summary = self.memory.summary()
        self.dash.render(
            memory_summary=memory_summary,
            graph_summary=graph_summary,
            stats_result=result,
            agent_reviews=reviews,
            debate_result=debate,
        )

        # ── Final Summary ──
        print("\n📋 RESEARCH SUMMARY")
        print("─" * 50)
        print(f"  Hypothesis : {hypothesis}")
        print(f"  Verdict    : {result['verdict']}")
        print(f"  Debate     : {debate['judge_verdict']}")
        print(f"  Paper JSON : {json_path}")
        print(f"  Paper TXT  : {pdf_path}")
        print(f"  KG Nodes   : {graph_summary['nodes']}")
        print(f"  Quantum    : {q_status['mode']}")
        print(f"  Qubit Sim  : |0⟩={q_sim['prob_0']} |1⟩={q_sim['prob_1']} → {q_sim['measured']}")
        print("─" * 50)

        log.info("Research loop complete.")
        return {
            "hypothesis": hypothesis,
            "result": result,
            "debate": debate,
            "paper_json": json_path,
            "paper_txt": pdf_path,
            "graph": graph_summary,
        }


# ─────────────────── Entry Point ───────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AMRIT RESEARCH OS v3.0")
    parser.add_argument("--domain", type=str, default="", help="Research domain")
    parser.add_argument("--query", type=str, default="", help="Custom search query")
    args = parser.parse_args()

    os_instance = AmritResearchOS(domain=args.domain)
    os_instance.run(query=args.query)
