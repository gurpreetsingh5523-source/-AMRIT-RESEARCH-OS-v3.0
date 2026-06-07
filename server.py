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
# Anchor the working directory to the project root so all relative paths
# (reports/, data/vector_store, etc.) resolve consistently no matter where
# the server is launched from.
os.chdir(ROOT)

from core.brain import ResearchBrain, DiscoveryEngine
from core.memory import MemoryManager, VectorMemory, ThreadManager
from core.statistics import StatisticalEngine
from core.agents import (
    AgentManager, SelfCritiqueLoop, DocumentAgent, EmailAgent,
    ResearchPlannerAgent, SkillFactory,
)
from core.knowledge_graph import KnowledgeGraph
from core.data_sources import DataCollector
from core.paper_writer import PaperWriter
from core.quantum import QuantumLayer
from core.models import ModelRouter
from core.tools import ToolManager
from core.sandbox import SandboxExecutor
from core.scheduler import BackgroundScheduler
from core.medical import (
    BloodReportParser, DNARiskPredictor, HealthKnowledgeGraph,
)
from core.ai.ollama_client import OllamaClient

app = FastAPI(title="AMRIT Research OS v4.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── shared singletons ───
_router  = ModelRouter()
_memory  = MemoryManager()
_vmem    = VectorMemory()
_stats   = StatisticalEngine()
_agents  = AgentManager(_router)
_critic  = SelfCritiqueLoop(_router)
_discovery = DiscoveryEngine(_router)
_graph   = KnowledgeGraph()
_data    = DataCollector()
_sandbox = SandboxExecutor()
_tools   = ToolManager(data=_data, sandbox=_sandbox, graph=_graph, vector_memory=_vmem)
_writer  = PaperWriter()
_quantum = QuantumLayer()
_ai      = OllamaClient(model=_router.resolve("research"))

# ─── medical / DNA singletons ───
_blood   = BloodReportParser()
_dna     = DNARiskPredictor()
_health  = HealthKnowledgeGraph()

# ─── document / email agents ───
_docagent = DocumentAgent(_router)
_email    = EmailAgent(_router)

# ─── v4: threads, planner, self-improvement, scheduler ───
_threads   = ThreadManager()
_planner   = ResearchPlannerAgent(_router, data=_data, tools=_tools)
_skills    = SkillFactory(_router, sandbox=_sandbox, vector_memory=_vmem, tools=_tools)
_scheduler = BackgroundScheduler(email_agent=_email, vector_memory=_vmem,
                                 interval_seconds=300)


# ── Models ────────────────────────────────────────────

class RunRequest(BaseModel):
    domain: str = ""
    query:  str = ""


class BloodRequest(BaseModel):
    report: str                 # raw text or a file path


class DNARequest(BaseModel):
    raw: str                    # raw 23andMe/AncestryDNA text or file path
    validate_clinvar: bool = False
    evidence: bool = False


class ToolRequest(BaseModel):
    tool: str
    args: dict = {}


class MemorySearchRequest(BaseModel):
    query: str
    collection: str = "research_notes"
    k: int = 3


class DiscoverRequest(BaseModel):
    statements: list = []       # [{"text": "...", "source": "..."}]


class ChatRequest(BaseModel):
    message: str
    history: list = []          # [{"role": "user"|"assistant", "content": "..."}]
    task: str = "deep_reasoning"
    remember: bool = True       # recall + store conversation in vector memory
    thread_id: str = ""         # optional named thread to persist into


class DocumentRequest(BaseModel):
    text: str
    refine: bool = True
    make_pdf: bool = False


class EmailRequest(BaseModel):
    raw: str                    # pasted email text (with optional From:/Subject:)
    send_reply: bool = False
    reply_to: str = ""
    make_pdf: bool = True


class EmailInboxRequest(BaseModel):
    limit: int = 5
    make_pdf: bool = False
    auto_reply: bool = False


class ThreadCreateRequest(BaseModel):
    name: str
    category: str = "Research"


class PlannerRequest(BaseModel):
    question: str
    gather_evidence: bool = True
    make_pdf: bool = False


class CriticRequest(BaseModel):
    text: str = ""              # an existing answer to critique; OR
    question: str = ""          # a question to answer first, then self-critique
    cycles: int = 2


class SkillRequest(BaseModel):
    name: str
    description: str = ""


class ToolBuildRequest(BaseModel):
    name: str
    description: str
    test_args: dict = {}
    code: str = ""              # optional explicit code (offline-safe)


class LearnRequest(BaseModel):
    note: str = ""


class SchedulerRequest(BaseModel):
    interval_seconds: int = 300


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

    if _vmem.enabled:
        similar = _vmem.recall_similar_research(hypothesis, k=3)
        if similar:
            _log(f"Vector recall: {len(similar)} related prior findings", "ai")

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

    if _vmem.enabled:
        _vmem.remember_finding(hypothesis, result, domain=domain)
        for item in collected.get("arxiv", []):
            if "title" in item and "error" not in item:
                _vmem.remember_paper(item)
        _log("Stored finding + papers in vector memory", "ok")

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
        _log("Self-critique loop (draft → critic → improve)…", "ai")
        refined = _critic.run(ai_abstract, context=f"Hypothesis: {hypothesis}")
        ai_abstract = refined["final_draft"]
        peer_review["critique_score"] = refined["final_score"]
        peer_review["critique_cycles"] = refined["cycles_run"]
        _log(f"Critique done: {refined['cycles_run']} cycle(s), score={refined['final_score']}", "ok")

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


# ── v4: models / tools / memory / discovery ──────────

@app.get("/api/models")
async def get_models():
    return {
        "available": _router.available(),
        "installed": _router.installed_models(),
        "routing": _router.routing_table(),
    }


@app.get("/api/tools")
async def list_tools():
    return {"tools": _tools.list_tools()}


@app.post("/api/tools/execute")
async def execute_tool(req: ToolRequest):
    return JSONResponse(_tools.execute(req.tool, **req.args))


@app.post("/api/memory/search")
async def memory_search(req: MemorySearchRequest):
    if not _vmem.enabled:
        return JSONResponse({"enabled": False, "results": []})
    return JSONResponse({
        "enabled": True,
        "results": _vmem.search(req.collection, req.query, req.k),
        "stats": _vmem.stats(),
    })


@app.post("/api/discover")
async def discover(req: DiscoverRequest):
    return JSONResponse(_discovery.discover(req.statements))


# ── v4: medical / DNA ────────────────────────────────

@app.post("/api/medical/blood")
async def analyse_blood(req: BloodRequest):
    parsed = _blood.parse(req.report)
    if _vmem.enabled and parsed.get("abnormal"):
        _vmem.add("research_notes", f"Blood report: {parsed['summary']}",
                  {"type": "blood_report"})
    return JSONResponse(parsed)


@app.post("/api/medical/dna")
async def analyse_dna(req: DNARequest):
    raw = req.raw
    # allow a file path
    if os.path.exists(raw):
        with open(raw, "r", errors="ignore") as f:
            raw = f.read()
    report = _dna.predict(raw, validate=req.validate_clinvar, evidence=req.evidence)
    return JSONResponse(report)


@app.get("/api/medical/health-graph")
async def health_graph():
    return JSONResponse(_health.summary())


# ── v4: chat / document / email agents ───────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    client = _router.client_for(req.task)
    if not client.is_available():
        return JSONResponse({"ok": False, "reply": "[Ollama offline] Start: ollama serve",
                             "model": "offline", "recalled": 0})

    # ── Long-term recall: pull semantically related past turns ──
    recalled = []
    if req.remember and _vmem.enabled:
        hits = _vmem.search("conversations", req.message, k=3)
        recalled = [h["text"] for h in hits if h.get("text")]

    memory_block = ""
    if recalled:
        memory_block = ("Relevant context from earlier conversations:\n"
                        + "\n".join(f"- {m}" for m in recalled) + "\n\n")

    # Fold short rolling history into the prompt for immediate context
    convo = ""
    for turn in req.history[-6:]:
        role = turn.get("role", "user").upper()
        convo += f"{role}: {turn.get('content','')}\n"
    prompt = (memory_block + convo + f"USER: {req.message}").strip()

    reply = client.chat(
        prompt,
        system="You are AMRIT, a helpful scientific research assistant. "
               "Use any provided context from earlier conversations when relevant. "
               "Be clear and concise.",
    )

    # ── Persist this exchange to vector memory ──
    if req.remember and _vmem.enabled and not reply.startswith("[Ollama"):
        _vmem.add("conversations", f"User: {req.message}\nAMRIT: {reply}",
                  {"type": "chat", "thread": req.thread_id or "default"})

    # ── Persist into the named thread (resumable history) ──
    if req.thread_id and _threads.get(req.thread_id):
        _threads.add_message(req.thread_id, "user", req.message)
        _threads.add_message(req.thread_id, "assistant", reply)

    return JSONResponse({"ok": True, "reply": reply, "model": client.model,
                         "recalled": len(recalled), "thread_id": req.thread_id})


@app.post("/api/document/analyze")
async def document_analyze(req: DocumentRequest):
    analysis = _docagent.analyse(req.text, refine=req.refine)
    pdf_path = ""
    if req.make_pdf and "error" not in analysis:
        from core.reporting import PDFExporter
        pdf_path = PDFExporter().build(
            title="AMRIT Document Analysis",
            subtitle="Generated " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            sections=[
                {"heading": "Summary", "body": analysis.get("summary", "")},
                {"heading": "Key Points", "body":
                    "\n".join(f"- {k}" for k in analysis.get("key_points", []))},
                {"heading": "Claims", "body":
                    "\n".join(f"- {c}" for c in analysis.get("claims", []))},
                {"heading": "Validation", "body": analysis.get("validation", "")},
                {"heading": "Suggestions", "body": analysis.get("suggestions", "")},
            ],
        )
    if _vmem.enabled and "error" not in analysis:
        _vmem.add("research_notes", f"Document: {analysis.get('summary','')}",
                  {"type": "document"})
    analysis["pdf_report"] = pdf_path
    return JSONResponse(analysis)


@app.post("/api/email/analyze")
async def email_analyze(req: EmailRequest):
    result = _email.process(
        raw_email=req.raw,
        send_reply=req.send_reply,
        reply_to=req.reply_to,
        make_pdf=req.make_pdf,
    )
    return JSONResponse(result)


@app.post("/api/email/inbox")
async def email_inbox(req: EmailInboxRequest):
    """Fetch unread emails via IMAP and batch-analyse them.

    Requires IMAP_HOST / IMAP_USER / IMAP_PASS env vars. Replies are only
    sent when auto_reply is True AND SMTP_* env vars are configured.
    """
    result = _email.process_inbox(
        limit=req.limit,
        make_pdf=req.make_pdf,
        auto_reply=req.auto_reply,
    )
    return JSONResponse(result)


@app.get("/api/report/download")
async def download_report(path: str):
    """Download a generated PDF/report by its path (must live under reports/)."""
    from fastapi.responses import FileResponse, Response
    safe_root = (ROOT / "reports").resolve()
    target = (ROOT / path).resolve()
    if not str(target).startswith(str(safe_root)) or not target.exists():
        return Response(content=b"not found", status_code=404)
    return FileResponse(str(target), filename=target.name)


# ── v4: memory threads ───────────────────────────────

@app.get("/api/threads")
async def list_threads():
    return JSONResponse({"categories": _threads.categories(), "threads": _threads.list()})


@app.post("/api/threads")
async def create_thread(req: ThreadCreateRequest):
    return JSONResponse(_threads.create(req.name, req.category))


@app.get("/api/threads/{thread_id}")
async def get_thread(thread_id: str):
    t = _threads.get(thread_id)
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(t)


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    return JSONResponse({"deleted": _threads.delete(thread_id)})


# ── v4: research planner agent ───────────────────────

@app.post("/api/research/plan")
async def research_plan(req: PlannerRequest):
    result = _planner.run(req.question, gather_evidence=req.gather_evidence)
    if req.make_pdf:
        from core.reporting import PDFExporter
        sections = [{"heading": "Question", "body": result["question"]},
                    {"heading": "Plan", "body":
                        "\n".join(f"{i+1}. {p}" for i, p in enumerate(result["plan"]))}]
        for t in result["tasks"]:
            sections.append({"heading": t["task"], "body": t["finding"]})
        sections.append({"heading": "Validated Report", "body": result["report"]})
        result["pdf_report"] = PDFExporter().build(
            title="AMRIT Research Plan & Report",
            subtitle=f"Validation score {result['validation_score']:.2f}",
            sections=sections,
        )
    return JSONResponse(result)


# ── v4: self-critic agent ────────────────────────────

@app.post("/api/critic")
async def self_critic(req: CriticRequest):
    answer = req.text.strip()
    generated = False
    if not answer and req.question:
        client = _router.client_for("deep_reasoning")
        answer = client.chat(req.question,
                             system="Answer the question clearly and rigorously.") \
            if client.is_available() else "[Ollama offline] no answer generated."
        generated = True
    if not answer:
        return JSONResponse({"error": "provide 'text' or 'question'"}, status_code=400)

    loop = SelfCritiqueLoop(_router, cycles=max(1, min(4, req.cycles)))
    result = loop.run(answer, context=req.question)
    return JSONResponse({
        "question": req.question,
        "initial_answer": answer,
        "answer_generated": generated,
        "final_answer": result["final_draft"],
        "final_score": result["final_score"],
        "cycles_run": result["cycles_run"],
        "history": result["history"],
    })


# ── v4: self-learning / skills / tool building ───────

@app.post("/api/learn")
async def self_learn(req: LearnRequest):
    return JSONResponse(_skills.learn(req.note))


@app.get("/api/skills")
async def list_skills():
    return JSONResponse({"skills": _skills.list_skills()})


@app.post("/api/skills")
async def create_skill(req: SkillRequest):
    return JSONResponse(_skills.create_skill(req.name, req.description))


@app.get("/api/tools/built")
async def list_built_tools():
    return JSONResponse({"built_tools": _skills.list_built_tools()})


@app.post("/api/tools/build")
async def build_tool(req: ToolBuildRequest):
    return JSONResponse(_skills.build_tool(
        req.name, req.description, test_args=req.test_args, code=req.code))


# ── v4: background scheduler + notifications ─────────

@app.get("/api/scheduler")
async def scheduler_status():
    return JSONResponse(_scheduler.status())


@app.post("/api/scheduler/start")
async def scheduler_start(req: SchedulerRequest):
    return JSONResponse(_scheduler.start(req.interval_seconds))


@app.post("/api/scheduler/stop")
async def scheduler_stop():
    return JSONResponse(_scheduler.stop())


@app.post("/api/scheduler/run")
async def scheduler_run_now():
    return JSONResponse(_scheduler.run_now())


@app.get("/api/notifications")
async def get_notifications(after: str = ""):
    return JSONResponse({"notifications": _scheduler.notifications(after)})


# ── Entry point ──────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n╔══════════════════════════════════════════╗")
    print("║  AMRIT RESEARCH OS v4.0 — Web Server    ║")
    print("╚══════════════════════════════════════════╝")
    print("  Dashboard : http://localhost:8000")
    print("  API docs  : http://localhost:8000/docs")
    print("  Health    : http://localhost:8000/api/health\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
