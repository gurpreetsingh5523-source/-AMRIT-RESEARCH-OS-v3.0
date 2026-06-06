#!/usr/bin/env python3
"""
AMRIT RESEARCH OS v3.0
server.py — FastAPI Web Server

Serves:
  GET  /              → Dashboard HTML
  GET  /api/health    → Ollama + system status
  POST /api/run       → Run one research cycle (returns full result JSON)
  GET  /api/memory    → All stored findings
  GET  /api/graph     → Knowledge graph summary

Run:
  python3 server.py
  Open: http://localhost:8000
"""

import sys
import os
import math
import datetime
import logging

# ─── suppress noisy logs in web mode ───
logging.basicConfig(level=logging.WARNING)

# ─── terminal colour helpers ───
_C = {
    "reset": "\033[0m", "bold": "\033[1m",
    "purple": "\033[95m", "teal": "\033[96m",
    "amber": "\033[93m", "red": "\033[91m",
    "dim": "\033[2m", "green": "\033[92m",
}

def _log(msg, kind="info"):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    colours = {
        "start":  _C["bold"] + _C["purple"],
        "step":   _C["amber"],
        "ok":     _C["teal"],
        "ai":     _C["green"],
        "warn":   _C["red"],
        "info":   _C["dim"],
    }
    c = colours.get(kind, _C["dim"])
    prefix = {"start": "▶", "step": "◆", "ok": "✓", "ai": "🤖", "warn": "✗", "info": "·"}.get(kind, "·")
    print(f"  {c}[{ts}] {prefix} {msg}{_C['reset']}", flush=True)

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── ensure project root is on path ───
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.brain import ResearchBrain
from core.memory import MemoryManager
from core.statistics import StatisticalEngine
from core.agents import AgentManager
from core.knowledge_graph import KnowledgeGraph
from core.data_sources import DataCollector
from core.paper_writer import PaperWriter
from core.quantum import QuantumLayer
from core.ai.ollama_client import OllamaClient

app = FastAPI(title="AMRIT Research OS v3.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── shared singletons ───
_memory  = MemoryManager()
_stats   = StatisticalEngine()
_agents  = AgentManager()
_graph   = KnowledgeGraph()
_data    = DataCollector()
_writer  = PaperWriter()
_quantum = QuantumLayer()
_ai      = OllamaClient(model="deepseek-coder-v2:latest")


# ── Models ────────────────────────────────────────────

class RunRequest(BaseModel):
    domain: str = ""
    query:  str = ""


# ── Routes ───────────────────────────────────────────

@app.get("/favicon.ico")
async def favicon():
    # Return a minimal 1×1 transparent ICO so browsers stop logging 404s
    from fastapi.responses import Response
    ico = bytes([
        0,0,1,0,1,0,1,1,0,0,1,0,32,0,40,0,0,0,28,0,0,0,40,0,0,0,
        1,0,0,0,2,0,0,0,1,0,32,0,0,0,0,0,4,0,0,0,0,0,0,0,0,0,0,0,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    ])
    return Response(content=ico, media_type="image/x-icon")

@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
async def apple_icon():
    from fastapi.responses import Response
    return Response(content=b'', media_type="image/png", status_code=204)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = ROOT / "core" / "dashboard" / "index.html"
    return HTMLResponse(content=html_path.read_text(), status_code=200)


@app.get("/api/health")
async def health():
    ollama_ok = _ai.is_available()
    models    = _ai.list_models() if ollama_ok else []
    mem       = _memory.summary()
    return {
        "status":  "ok",
        "ollama":  ollama_ok,
        "models":  models,
        "memory":  mem,
        "quantum": _quantum.status(),
    }


@app.post("/api/run")
async def run_research(req: RunRequest):
    brain  = ResearchBrain()
    domain = req.domain or brain.domain

    print(f"\n{_C['bold']}{_C['purple']}{'─'*52}{_C['reset']}", flush=True)
    _log(f"NEW RESEARCH CYCLE  ·  DOMAIN: {domain.upper()}", "start")
    print(f"{_C['bold']}{_C['purple']}{'─'*52}{_C['reset']}\n", flush=True)

    # ── 1. Hypothesis ──
    _log("Step 01/14 · Hypothesis Generation", "step")
    if _ai.is_available():
        _log("Ollama (deepseek-coder-v2) generating hypothesis…", "ai")
        hypothesis = _ai.generate_hypothesis(domain)
    else:
        _log("Ollama offline — using rule-based brain", "warn")
        hypothesis = brain.generate_hypothesis(domain)
    _log(f"Hypothesis: {hypothesis[:80]}…", "ok")

    # ── 2. Data collection ──
    _log("Step 02/14 · Research Plan", "step")
    _log("Step 03/14 · Data Collection (ArXiv · PubMed · NASA · OpenAlex)", "step")
    search_query = req.query or hypothesis[:80]
    collected = _data.collect_all(search_query, max_per_source=3)
    arxiv_count  = len([x for x in collected.get("arxiv",  []) if "error" not in x])
    pubmed_count = len([x for x in collected.get("pubmed", []) if "error" not in x])
    _log(f"Collected → ArXiv: {arxiv_count}  PubMed: {pubmed_count}", "ok")

    # ── 3. Statistics ──
    _log("Step 04/14 · Statistical Analysis (Monte Carlo · Bayesian · Benford)", "step")
    result = _stats.evaluate(hypothesis)
    _log(f"p-value: {result['p_value']:.4f}  effect: {result['effect_size']:.3f}  verdict: {result['verdict']}", "ok")

    # ── 4. Bayesian / extra stats ──
    bayesian  = _stats.bayesian_update()
    benfords  = result.get("benfords", {})
    corr      = result.get("correlation", {})
    mc        = result.get("monte_carlo", {})
    _log(f"Bayesian posterior: {bayesian.get('posterior', '—')}  π≈{mc.get('pi_estimate', '—')}", "info")

    # ── 5. Scientific reasoning ──
    _log("Step 05/14 · Scientific Reasoning", "step")
    reasoning = brain.scientific_reasoning(hypothesis, result)
    _log("Reasoning complete", "ok")

    # ── 6. Agents ──
    _log("Step 06/14 · Agent Swarm (7 agents reviewing…)", "step")
    reviews = _agents.review(hypothesis, result)
    _log(f"Agents done: {', '.join(reviews.keys())}", "ok")

    # ── 7. Debate ──
    _log("Step 07/14 · Debate Engine (Believer ↔ Skeptic → Judge)", "step")
    debate = _agents.debate(hypothesis, result)
    _log("Debate complete", "ok")

    # ── 8. Peer review ──
    _log("Step 08/14 · Peer Review", "step")
    peer_review = _agents.auto_peer_review(hypothesis, result)

    # ── AI interpretation ──
    ai_interp = ""
    if _ai.is_available():
        _log("AI interpretation (deepseek-coder-v2)…", "ai")
        ai_interp = _ai.analyze_result(hypothesis, result)
        peer_review["ai_interpretation"] = ai_interp
        _log("AI interpretation done", "ok")

    # ── 9. Knowledge graph ──
    _log("Step 09/14 · Knowledge Graph Build", "step")
    _graph.build_from_hypothesis(hypothesis, domain)
    graph_summary = _graph.summary()
    _graph.export_json()
    _log(f"KG → nodes: {graph_summary.get('nodes', 0)}  edges: {graph_summary.get('edges', 0)}", "ok")

    # ── 10. Store memory ──
    _log("Step 10/14 · Memory Store (SQLite)", "step")
    finding_id = _memory.store_result(
        hypothesis, result, domain=domain, dataset="Multi-source"
    )
    for agent_name, review_text in reviews.items():
        _memory.store_agent_review(finding_id, agent_name, review_text)

    if result["verdict"] in ("STRONG SUPPORT", "WEAK SUPPORT"):
        _memory.record_evolution("successful", hypothesis)
        _log(f"Evolution recorded: SUCCESSFUL (finding #{finding_id})", "ok")
    else:
        _memory.record_evolution("failed", hypothesis)
        _log(f"Evolution recorded: FAILED (finding #{finding_id})", "warn")

    # ── 11. Citations ──
    _log("Step 11/14 · Citations", "step")
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
    _log(f"Citations built: {len(sources)}", "ok")

    # ── 12. Paper ──
    _log("Step 12/14 · Paper Generation", "step")
    ai_abstract = ""
    if _ai.is_available():
        _log("AI writing abstract…", "ai")
        ai_abstract = _ai.write_abstract(hypothesis, result)

    paper = _writer.generate_paper(
        hypothesis=hypothesis,
        result=result,
        debate=debate,
        review=peer_review,
        sources=sources[:5],
        domain=domain,
    )
    if ai_abstract:
        paper["abstract"] = ai_abstract

    json_path = _writer.export_json(paper)
    txt_path  = _writer.export_text_pdf(paper)
    _log(f"Paper exported → {json_path}", "ok")

    # ── 13. Quantum ──
    _log("Step 13/14 · Quantum Layer Simulation", "step")
    q_sim    = _quantum.simulate_qubit()
    q_grover = _quantum.grover_search_simulation(512, 42)
    _log(f"Qubit measured: {q_sim.get('measured','—')}  Grover speedup: {q_grover.get('speedup','—')}×", "ok")

    _log("Step 14/14 · Dashboard Update", "step")
    _log(f"CYCLE COMPLETE ✓  domain={domain}  verdict={result['verdict']}", "ok")
    print(f"\n{_C['dim']}{'─'*52}{_C['reset']}\n", flush=True)

    # ── Build response ──
    return JSONResponse({
        "domain":       domain,
        "hypothesis":   hypothesis,
        "ollama_model": "deepseek-coder-v2" if _ai.is_available() else "offline",

        "result": {
            "p_value":     result["p_value"],
            "effect_size": result["effect_size"],
            "verdict":     result["verdict"],
        },

        "monte_carlo": {
            "pi_estimate": mc.get("pi_estimate"),
            "iterations":  mc.get("iterations"),
            "error":       mc.get("error"),
        },

        "bayesian": {
            "posterior": bayesian.get("posterior"),
        },

        "benfords": {
            "verdict": benfords.get("verdict", "—"),
        },

        "correlation": {
            "r": corr.get("r", "—"),
        },

        "agents":  reviews,
        "debate":  debate,
        "peer_review": peer_review,

        "graph": graph_summary,

        "quantum": {
            "prob_0":        q_sim["prob_0"],
            "prob_1":        q_sim["prob_1"],
            "measured":      q_sim["measured"],
            "grover_speedup": q_grover["speedup"],
            "info":          f"VQE: 4 params · Grover N={q_grover['n_items']} → {q_grover['speedup']} speedup",
        },

        "paper_json": json_path,
        "paper_txt":  txt_path,

        "sources": {
            "arxiv":  arxiv_count,
            "pubmed": pubmed_count,
        },

        "memory": _memory.summary(),
    })


@app.get("/api/memory")
async def get_memory():
    return JSONResponse({
        "summary":  _memory.summary(),
        "findings": _memory.get_all_findings(),
        "successful": _memory.get_successful_hypotheses(),
        "failed":     _memory.get_failed_hypotheses(),
        "lessons":    _memory.get_evolution_lessons(),
    })


@app.get("/api/graph")
async def get_graph():
    return JSONResponse(_graph.summary())


# ── Entry point ──────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n╔══════════════════════════════════════════╗")
    print("║  AMRIT RESEARCH OS v3.0 — Web Server    ║")
    print("╚══════════════════════════════════════════╝")
    print("  Dashboard : http://localhost:8000")
    print("  API docs  : http://localhost:8000/docs")
    print("  Health    : http://localhost:8000/api/health\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
