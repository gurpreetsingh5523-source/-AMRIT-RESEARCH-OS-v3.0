#!/bin/bash
# ═══════════════════════════════════════════════════════
#  AMRIT RESEARCH OS v4.5 — ਚਲਾਉਣ ਲਈ ਇਹ ਫਾਈਲ
#  ਵਰਤੋਂ:  bash START_AMRIT.sh
# ═══════════════════════════════════════════════════════

echo "╔══════════════════════════════════════════╗"
echo "║   AMRIT RESEARCH OS v4.5 — Starting       ║"
echo "╚══════════════════════════════════════════╝"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 ਨਹੀਂ ਮਿਲਿਆ। ਪਹਿਲਾਂ Python install ਕਰੋ।"
    exit 1
fi
echo "✅ Python3 ਮਿਲਿਆ: $(python3 --version)"

# 2. Install dependencies
echo ""
echo "📦 Dependencies install ਕਰ ਰਿਹਾ ਹਾਂ..."
pip3 install -q fastapi uvicorn requests numpy scipy pandas scikit-learn pyyaml biopython 2>/dev/null
echo "✅ ਮੁੱਖ packages ਤਿਆਰ"

# 3. Check Ollama
echo ""
if command -v ollama &> /dev/null; then
    echo "✅ Ollama ਮਿਲਿਆ"
    # Start ollama if not running
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "▶️  Ollama ਚਾਲੂ ਕਰ ਰਿਹਾ ਹਾਂ..."
        ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi
    echo "✅ Ollama ਚੱਲ ਰਿਹਾ ਹੈ"
else
    echo "⚠️  Ollama ਨਹੀਂ ਮਿਲਿਆ — ਸਿਸਟਮ ਚੱਲੇਗਾ ਪਰ AI features limited"
    echo "   Install: https://ollama.com"
fi

# 4. Create data directories
mkdir -p data reports/pdf reports/json logs

# 5. Start server
echo ""
echo "🚀 AMRIT Server ਚਾਲੂ ਕਰ ਰਿਹਾ ਹਾਂ..."
echo "   Dashboard:  http://localhost:8000"
echo "   API docs:   http://localhost:8000/docs"
echo "   Medical:    http://localhost:8000/core/dashboard/medical_dashboard.html"
echo ""
echo "   (ਬੰਦ ਕਰਨ ਲਈ: Ctrl+C)"
echo ""

# Kill any old server on 8000
kill $(lsof -ti:8000) 2>/dev/null
sleep 1

python3 server.py
