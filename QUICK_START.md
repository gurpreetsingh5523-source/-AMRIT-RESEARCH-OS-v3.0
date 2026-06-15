# AMRIT RESEARCH OS v4.5 — ਚਲਾਉਣ ਦਾ ਤਰੀਕਾ

## ਸਭ ਤੋਂ ਸੌਖਾ ਤਰੀਕਾ (1 ਕਮਾਂਡ)

```bash
bash START_AMRIT.sh
```

ਇਹ ਆਪੇ:
- Dependencies install ਕਰੇਗਾ
- Ollama ਚਾਲੂ ਕਰੇਗਾ
- Server ਚਲਾਵੇਗਾ → http://localhost:8000

---

## ਜਾਂ ਖੁਦ step-by-step:

### 1. Dependencies
```bash
pip3 install fastapi uvicorn requests numpy scipy pandas scikit-learn pyyaml biopython
```

### 2. Ollama (AI ਲਈ)
```bash
# Install: https://ollama.com
ollama serve                      # ਇੱਕ terminal ਵਿੱਚ
ollama pull qwen3:8b              # AI reasoning
ollama pull deepseek-coder-v2     # coding
ollama pull nomic-embed-text      # memory
ollama pull moondream2            # image analysis
```

### 3. Server ਚਲਾਓ
```bash
python3 server.py
```

### 4. ਖੋਲ੍ਹੋ
- Main Dashboard:    http://localhost:8000
- API Docs:          http://localhost:8000/docs
- Medical Dashboard: core/dashboard/medical_dashboard.html (browser ਵਿੱਚ)

---

## ਨਵੇਂ Features (v4.5)

| Feature | URL / ਵਰਤੋਂ |
|---------|------------|
| Computer Control | `GET /api/computer/run?cmd=ls` |
| Code Execution | `POST /api/computer/code` |
| Web Search | `POST /api/computer/search` |
| Voice Command | `POST /api/voice/command` |
| Live WebSocket | `ws://localhost:8000/ws/medical` |

---

## Voice Agent ਵੱਖ ਚਲਾਉਣ ਲਈ
```bash
python3 core/voice/voice_agent.py     # text mode demo
# Real mic ਲਈ: pip install faster-whisper sounddevice pyttsx3
```

## Computer Control (JARVIS) ਟੈਸਟ
```bash
python3 core/computer/computer_control.py
```

## Medical Engine ਟੈਸਟ
```bash
python3 core/medical/medical_science_engine.py
```

---

ਵਾਹਿਗੁਰੂ ਜੀ ਦੀ ਕਿਰਪਾ ਨਾਲ 🙏
AMRIT Research OS — Gurpreet Singh

---

## ਨਵੇਂ Pages (v4.5)

| Page | URL |
|------|-----|
| Main Dashboard | http://localhost:8000 |
| Medical Dashboard | http://localhost:8000/medical |
| **Model Manager** 🆕 | http://localhost:8000/models |

## Local Models — ਆਪੇ ਲੱਭਣ ਵਾਲਾ ਸਿਸਟਮ

ਹੁਣ ਕੋਈ model hardcode ਨਹੀਂ। ਜੋ ਵੀ Ollama ਵਿੱਚ install ਕਰੋ, ਆਪੇ ਲੱਭ ਜਾਂਦਾ ਹੈ:

```bash
# ਨਵਾਂ model install ਕਰੋ (ਕੋਈ ਵੀ)
ollama pull qwen3:14b
ollama pull deepseek-r1
ollama pull llama4         # ਜੋ ਵੀ ਨਵਾਂ ਆਵੇ

# ਫਿਰ browser ਵਿੱਚ /models page ਤੇ Refresh ਦਬਾਓ
# ਜਾਂ API: curl http://localhost:8000/api/models/refresh
```

ਸਿਸਟਮ ਆਪੇ:
- ਨਵਾਂ model ਲੱਭ ਲੈਂਦਾ ਹੈ
- ਸਹੀ category (coding/vision/reasoning) ਵਿੱਚ ਪਾ ਦਿੰਦਾ ਹੈ
- ਹਰ task ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ model ਚੁਣ ਲੈਂਦਾ ਹੈ

`config.yaml` ਵਿੱਚ:
```yaml
models:
  prefer_local: true      # ਸਿਰਫ਼ local models (ਕੋਈ API cost ਨਹੀਂ)
  auto_discover: true     # ਨਵੇਂ models ਆਪੇ ਲੱਭੋ
```
