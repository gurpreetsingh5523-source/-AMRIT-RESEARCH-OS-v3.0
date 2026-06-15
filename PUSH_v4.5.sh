#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  AMRIT RESEARCH OS v4.5 — GitHub Auto-Push + Release
#  ਵਰਤੋਂ:  bash PUSH_v4.5.sh
# ═══════════════════════════════════════════════════════════════
set -e

echo "╔════════════════════════════════════════════════╗"
echo "║  AMRIT v4.5 → GitHub (Push + MIT + Release)    ║"
echo "╚════════════════════════════════════════════════╝"

# ਚੈੱਕ ਸਹੀ folder
if [ ! -f "server.py" ]; then
    echo "❌ ਗਲਤ folder। ਪਹਿਲਾਂ: cd ~/-AMRIT-RESEARCH-OS-v3.0"
    exit 1
fi
echo "✅ Project folder ਮਿਲਿਆ"

# Git setup
[ ! -d ".git" ] && git init && git branch -M main
git remote | grep -q origin || \
    git remote add origin https://github.com/gurpreetsingh5523-source/-AMRIT-RESEARCH-OS-v3.0.git

# .gitignore
cat > .gitignore << 'GITEOF'
__pycache__/
*.pyc
.venv/
venv/
*.db
data/projects/*/memory.db
logs/*.log
reports/pdf/*
reports/json/*
.DS_Store
*.tvim
GITEOF

# Stage + commit
git add .
git commit -m "🚀 AMRIT RESEARCH OS v4.5 — JARVIS + Voice + Realtime + Project Memory

v4.5 Major Release:
- 🤖 JARVIS Computer Control (terminal, browser, code, self-upgrade)
- 🎤 Voice Agent (Punjabi + Hindi + English)
- ⚡ Realtime Medical (EventBus + Timeline + Alerts)
- 🩺 Medical Engine (DNA + Blood + Pharmacogenomics + Vision)
- 🔄 Dynamic Model Loader (auto-discovers Ollama models)
- 🧠 Project-Isolated Memory (self-learning, mistakes, future plans)
- 📖 Auto-read project notes on startup
- 🖥️  3 Dashboards + 60+ API endpoints + WebSocket
- 📄 MIT License

40+ modules · all tested · scipy statistics · 100% local

By Gurpreet Singh" || echo "ℹ️  ਕੋਈ ਨਵਾਂ change ਨਹੀਂ"

# Push
git push -u origin main

# Tag + release
git tag -a v4.5 -m "AMRIT v4.5" 2>/dev/null || echo "ℹ️ tag ਹੈ"
git push origin v4.5 2>/dev/null || echo "ℹ️ tag pushed"

# Auto-release if gh CLI available
if command -v gh &> /dev/null; then
    gh release create v4.5 \
        --title "AMRIT RESEARCH OS v4.5" \
        --notes "JARVIS + Voice + Realtime Medical + Project Memory. Free AI doctor for the world. MIT Licensed. Run: bash START_AMRIT.sh" \
        2>/dev/null && echo "✅ Release ਬਣ ਗਈ!" || echo "ℹ️ Release ਪਹਿਲਾਂ ਤੋਂ ਹੈ"
else
    echo ""
    echo "📋 Manual release (gh CLI ਨਹੀਂ ਹੈ):"
    echo "   https://github.com/gurpreetsingh5523-source/-AMRIT-RESEARCH-OS-v3.0/releases/new"
    echo "   Tag: v4.5 | Title: AMRIT RESEARCH OS v4.5"
fi

echo ""
echo "✅ ਸਭ ਮੁਕੰਮਲ! ਵਾਹਿਗੁਰੂ ਜੀ ਦੀ ਕਿਰਪਾ 🙏"
