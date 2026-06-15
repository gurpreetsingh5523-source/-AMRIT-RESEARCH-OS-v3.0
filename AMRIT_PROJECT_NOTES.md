# 📖 AMRIT RESEARCH OS — PROJECT NOTES
## (ਇਹ ਫਾਈਲ ਸਭ ਤੋਂ ਪਹਿਲਾਂ ਪੜ੍ਹੋ — READ THIS FIRST)

> **ਨੋਟ Claude ਲਈ:** ਜਦੋਂ ਵੀ ਇਹ project ਖੁੱਲ੍ਹੇ, ਕੰਮ ਸ਼ੁਰੂ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ
> ਇਹ ਪੂਰੀ ਫਾਈਲ ਪੜ੍ਹੋ। ਇਹ AMRIT project ਦੀ ਪੂਰੀ ਯਾਦ ਹੈ।
> ਇਹ AMRIT project ਹੈ — ਗੁਰਪ੍ਰੀਤ ਜੀ ਦੇ ਹੋਰ projects ਨਾਲ ਮਿਕਸ ਨਾ ਕਰੋ।

---

## 🎯 PROJECT ਕੀ ਹੈ?

**AMRIT RESEARCH OS** (Autonomous Medical Research Intelligence Technology)
- ਇੱਕ open-source, **100% locally-run** ਮੈਡੀਕਲ AI platform
- ਮਕਸਦ: **ਦੁਨੀਆਂ ਦੇ ਗਰੀਬ ਲੋਕਾਂ ਲਈ ਮੁਫ਼ਤ AI ਡਾਕਟਰ**
- ਭਵਿੱਖ: Raspberry Pi ਤੇ **Robot Doctor (~$150/unit)**
- Sikh philosophy + Punjabi language ਨਾਲ ਜੁੜਿਆ
- Developer: **Gurpreet Singh**
- GitHub: `github.com/gurpreetsingh5523-source/-AMRIT-RESEARCH-OS-v3.0`
- MacBook (Apple M-series) ਤੇ ਬਣ ਰਿਹਾ

---

## 📌 ਮੌਜੂਦਾ Version: **v4.5** (15 ਜੂਨ 2026)

### ਮੁੱਖ ਸਿਧਾਂਤ (Architecture Principles)
1. **Local-first:** Ollama models ਵਰਤੋ, API ਨਹੀਂ (ਕੋਈ cost ਨਹੀਂ)
2. **Doctor approval ਸਾਫਟਵੇਅਰ ਵਿੱਚੋਂ ਹਟਾਇਆ:** System ਪੂਰੀ PDF report ਬਣਾਉਂਦਾ ਹੈ → ਡਾਕਟਰ ਖੁਦ PDF ਪੜ੍ਹ ਕੇ verify ਕਰਦਾ ਹੈ (ਕੰਪਿਊਟਰ ਵਿੱਚ ਨਹੀਂ) → report ਮੈਡੀਕਲ ਸੈਂਟਰ ਨੂੰ email → ਮਰੀਜ਼ ਦਵਾਈ ਲੈਂਦਾ ਹੈ
3. **Honest auditing:** ਗੁਰਪ੍ਰੀਤ ਜੀ ਸਿੱਧੀ ਤਕਨੀਕੀ ਆਲੋਚਨਾ ਪਸੰਦ ਕਰਦੇ ਹਨ — ਝੂਠੀ ਤਾਰੀਫ਼ ਨਹੀਂ
4. **Verify before assuming:** ਹਮੇਸ਼ਾ repo clone/ਪੜ੍ਹ ਕੇ ਜਵਾਬ ਦਿਓ, ਅੰਦਾਜ਼ਾ ਨਾ ਲਾਓ
5. **AMRIT ਦੇ ਅੰਦਰਲੇ agents ਇੱਕ-ਦੂਜੇ ਤੋਂ ਸਿੱਖਣ/evolve ਕਰਨ — ਇਹ intended ਹੈ**

---

## ✅ ਜੋ ਬਣ ਚੁੱਕਾ ਹੈ (40 modules, ਸਾਰੇ tested)

### Core Research
- 14-step research pipeline (`research_brain.py`)
- Statistical engine — **ਅਸਲ scipy** (t-test, ANOVA, chi-square, Pearson) — fake ਨਹੀਂ
- Discovery engine (contradiction detection)
- Paper writer, Quantum layer (qubit sim)

### 7-Agent Swarm
- agent_manager, planner, critic, email, document, self_heal, self_improvement

### Medical Engine
- `medical_science_engine.py` — DNA + Blood + Pharmacogenomics + Vision (LLaVA)
- `medical_integration.py` — PatternAnalyzer + PDF + Email dispatch
- blood_report_parser, dna_risk_predictor, pharmacogenomics, health_knowledge_graph
- Genomics: ncbi_fetcher, clinvar_reader, snp_analyser

### v4.5 ਨਵੇਂ Features
- 🤖 `computer_control.py` — JARVIS (terminal, browser, code exec, self-upgrade)
- 🎤 `voice_agent.py` — ਆਵਾਜ਼ ਕੰਟਰੋਲ (Punjabi+Hindi+English)
- ⚡ Realtime: `event_bus.py`, `patient_timeline.py`, `alert_engine.py`
- 🔄 `model_loader.py` — ਨਵੇਂ Ollama models ਆਪੇ ਲੱਭਦਾ + categorize
- 🧠 `project_memory.py` — project-isolated memory + self-learning
- 🗄️ `turbovec_memory.py` — TurboVec vector memory (16x compressed)

### Memory + Self-Learning
- `memory_manager.py` — SQLite (findings, evolution, reviews)
- `self_improvement.py` — `learn()`, `create_skill()`, `build_tool()` (SkillFactory)
- `self_heal.py` — `self_check()`, `heal_exception()`, `ensure_dependencies()`
- `project_memory.py` — ਹਰ project ਵੱਖ + mistakes/lessons/future-plans

### Dashboards (3) + 60+ API endpoints + WebSocket
- Main: `localhost:8000` | Medical: `/medical` | Models: `/models`

### Infra
- MIT License ✅
- `START_AMRIT.sh` (1-command run)
- `PUSH_v4.5.sh` + `PUSH_v4.5_with_release.sh` (GitHub auto-push)

---

## ⚠️ ਗਲਤੀਆਂ ਜੋ ਦੁਬਾਰਾ ਨਹੀਂ ਕਰਨੀਆਂ

1. **server.py ਵਿੱਚ `Request` import ਭੁੱਲਣਾ** → FastAPI Pydantic models ਵਰਤੋ
2. **Stats ਵਿੱਚ fake `random.uniform` p-value** (v1 ਦੀ ਗਲਤੀ) → scipy.stats ਵਰਤੋ
3. **Repo ਪੜ੍ਹੇ ਬਿਨਾਂ ਜਵਾਬ ਦੇਣਾ** → ਪਹਿਲਾਂ clone ਕਰੋ
4. **ਪ੍ਰੋਜੈਕਟ ਮਿਕਸ ਕਰਨਾ** → ਹਰ project ਵੱਖ ਰੱਖੋ
5. **Redis/PostgreSQL/TimescaleDB ਦੀ ਸਿਫਾਰਸ਼** (ਦੂਜੇ AI ਦੀ ਗਲਤੀ) → SQLite ਕਾਫ਼ੀ ਹੈ; PDF+email ਪਹਿਲਾਂ ਤੋਂ ਮੌਜੂਦ ਸਨ

---

## 🔮 ਅਗਲੇ ਕਦਮ (FUTURE PLANS)

### v5.0 — Autonomous Medical OS (3 ਮਹੀਨੇ) 🔴 HIGH
- Self-evolving DNA engine (ਹਰ ਰਾਤ NCBI ਤੋਂ ਨਵੇਂ patterns ਸਿੱਖੇ)
- Symptom → Differential Diagnosis engine
- Multi-disease detection from single CBC
- WhatsApp bot (photo ਭੇਜੋ → report ਆਵੇ) 🟡

### v5.5 — Sensors (6 ਮਹੀਨੇ) 🟡
- Apple Watch / wearable data
- USB lab device integration (i-STAT, ECG)
- Camera blood smear analysis (LLaVA fine-tune)

### v6.0 — Robot Doctor (12-18 ਮਹੀਨੇ) ⚪
- Raspberry Pi 5 / Jetson Nano deployment
- Offline-only, solar-powered, $50-150/unit
- LISTEN → EXAMINE → TEST → DIAGNOSE → REPORT → LEARN

---

## 🛠️ Tech Stack

| Layer | Tool |
|-------|------|
| LLM | Ollama: qwen3:8b (reasoning), deepseek-coder-v2 (coding) |
| Vision | LLaVA / moondream2 |
| STT | faster-whisper | TTS | Kokoro-82M ONNX |
| Embeddings | nomic-embed-text |
| Vector Memory | TurboVec (Rust SIMD, Apple M-series) |
| Backend | FastAPI + Uvicorn + WebSocket |
| DB | SQLite (per-project isolated) |
| Data | NCBI, OpenFDA, PharmGKB, ClinVar, ArXiv, PubMed |

---

## 👤 ਗੁਰਪ੍ਰੀਤ ਜੀ ਦਾ ਕੰਮ ਕਰਨ ਦਾ ਤਰੀਕਾ

- Multi-session deep-build conversations (design + debug + architecture ਇੱਕੋ thread ਵਿੱਚ)
- Multi-agent review framing (Architect, Engineer, Reviewer, Optimizer)
- ਪੰਜਾਬੀ ਵਿੱਚ ਗੱਲ ਕਰਦੇ ਹਨ — ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ
- Live terminal output ਸ਼ੇਅਰ ਕਰਕੇ modules validate ਕਰਦੇ ਹਨ
- External research (papers, repos) ਨੂੰ codebase ਵਿੱਚ integrate ਕਰਨਾ ਚਾਹੁੰਦੇ ਹਨ
- ਮੈਂ (Claude) GitHub ਤੇ ਸਿੱਧਾ push ਨਹੀਂ ਕਰ ਸਕਦਾ — script ਬਣਾ ਕੇ ਦਿੰਦਾ ਹਾਂ, ਉਹ ਆਪਣੇ Mac ਤੋਂ ਚਲਾਉਂਦੇ ਹਨ

---

*ਆਖਰੀ ਅਪਡੇਟ: 15 ਜੂਨ 2026 · v4.5 · ਵਾਹਿਗੁਰੂ ਜੀ ਦੀ ਕਿਰਪਾ 🙏*
