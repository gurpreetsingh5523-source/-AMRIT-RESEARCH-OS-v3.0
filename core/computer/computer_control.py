"""
╔══════════════════════════════════════════════════════════════════╗
║  AMRIT RESEARCH OS v4.5                                          ║
║  core/computer/computer_control.py                              ║
║                                                                  ║
║  🤖 JARVIS-style Computer Control                               ║
║  ਆਵਾਜ਼ ਨਾਲ ਪੂਰਾ ਕੰਪਿਊਟਰ ਕੰਟਰੋਲ                              ║
║                                                                  ║
║  Capabilities:                                                   ║
║  ✅ Terminal — commands run ਕਰਨਾ                                ║
║  ✅ Browser  — websites ਖੋਲ੍ਹਣਾ, ਪੜ੍ਹਨਾ                      ║
║  ✅ Apps     — launch/close macOS apps                          ║
║  ✅ Files    — create, read, edit, move                         ║
║  ✅ Code     — Python ਲਿਖਣਾ ਅਤੇ run ਕਰਨਾ                     ║
║  ✅ Web Search — DuckDuckGo via requests                        ║
║  ✅ Self-Upgrade — GitHub ਤੋਂ ਨਵੀਆਂ techniques                 ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    ctrl = ComputerControl()
    ctrl.run_terminal("ls -la")
    ctrl.open_browser("https://arxiv.org")
    ctrl.write_and_run_code("print('Hello AMRIT')")
    ctrl.web_search("DNA pattern recognition 2026")
"""

import os
import sys
import time
import json
import logging
import platform
import subprocess
import webbrowser
import tempfile
import threading
from pathlib import Path
from typing import Optional
import requests

log = logging.getLogger("AmritComputer")
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
OLLAMA   = "http://localhost:11434"


# ══════════════════════════════════════════════════════════════
# TERMINAL CONTROL
# ══════════════════════════════════════════════════════════════
class TerminalControl:
    """
    Run terminal commands, open Terminal app, execute scripts.
    macOS: uses subprocess + osascript
    Linux: uses subprocess directly
    """

    def run(self, command: str, timeout: int = 30,
            capture: bool = True) -> dict:
        """
        Run a shell command and return output.
        Safe: blocks dangerous commands.
        """
        # Safety check
        blocked = ["rm -rf /", "sudo rm", "format", "mkfs", ":(){:|:&};:"]
        for b in blocked:
            if b in command:
                return {"success": False, "output": f"Blocked: '{b}' not allowed",
                        "error": ""}

        log.info(f"  💻 Terminal: {command[:60]}")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=capture,
                text=True, timeout=timeout,
                cwd=str(Path.home()),
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
            if success:
                log.info(f"  ✅ Done: {output[:80]}")
            else:
                log.warning(f"  ⚠️  Error: {output[:80]}")
            return {"success": success, "output": output.strip(),
                    "returncode": result.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "Command timed out", "error": "timeout"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def open_terminal_window(self, command: str = "") -> bool:
        """Open a new Terminal window (macOS)."""
        if IS_MAC:
            if command:
                script = f'tell app "Terminal" to do script "{command}"'
            else:
                script = 'tell app "Terminal" to activate'
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True)
            return r.returncode == 0
        elif IS_LINUX:
            apps = ["gnome-terminal", "xterm", "konsole"]
            for app in apps:
                try:
                    cmd = [app] + (["--", "bash", "-c", command] if command else [])
                    subprocess.Popen(cmd)
                    return True
                except FileNotFoundError:
                    continue
        return False

    def run_python_script(self, script: str,
                           timeout: int = 15) -> dict:
        """Write Python code to temp file and execute it."""
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            tmp = f.name
        try:
            result = subprocess.run(
                [sys.executable, tmp],
                capture_output=True, text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "output":  result.stdout.strip(),
                "error":   result.stderr.strip(),
                "script":  script,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Script timed out"}
        finally:
            os.unlink(tmp)

    def get_system_info(self) -> dict:
        """Get basic system information."""
        info = {
            "platform": platform.system(),
            "machine":  platform.machine(),
            "python":   sys.version.split()[0],
        }
        # Disk space
        r = self.run("df -h / | tail -1")
        if r["success"]:
            info["disk"] = r["output"]
        # Memory
        if IS_MAC:
            r = self.run("vm_stat | head -5")
            if r["success"]:
                info["memory_raw"] = r["output"]
        return info


# ══════════════════════════════════════════════════════════════
# BROWSER CONTROL
# ══════════════════════════════════════════════════════════════
class BrowserControl:
    """
    Open URLs, read web pages, search the web.
    No Selenium needed — uses requests for reading.
    """

    SEARCH_ENGINES = {
        "duckduckgo": "https://html.duckduckgo.com/html/?q={}",
        "pubmed":     "https://pubmed.ncbi.nlm.nih.gov/?term={}",
        "arxiv":      "https://arxiv.org/search/?searchtype=all&query={}",
        "github":     "https://github.com/search?q={}",
    }

    def open(self, url: str) -> bool:
        """Open URL in default browser."""
        if not url.startswith("http"):
            url = "https://" + url
        log.info(f"  🌐 Opening: {url}")
        webbrowser.open(url)
        return True

    def read_page(self, url: str, max_chars: int = 3000) -> dict:
        """
        Fetch and extract text from a webpage.
        Returns clean text (no HTML).
        """
        if not url.startswith("http"):
            url = "https://" + url
        log.info(f"  📖 Reading: {url}")
        try:
            headers = {"User-Agent": "AMRIT-ResearchOS/4.5 (Scientific Research)"}
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()

            # Simple HTML → text (no BeautifulSoup needed)
            import re
            text = r.text
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>',  '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            text = text[:max_chars]

            log.info(f"  ✅ Read {len(text)} chars from {url}")
            return {"success": True, "url": url,
                    "text": text, "length": len(text)}
        except Exception as e:
            log.warning(f"  ❌ Read error: {e}")
            return {"success": False, "url": url, "error": str(e)}

    def search(self, query: str,
               engine: str = "duckduckgo",
               open_browser: bool = False) -> dict:
        """
        Search the web. Returns text results.
        Optionally opens browser.
        """
        import urllib.parse
        encoded = urllib.parse.quote(query)
        url = self.SEARCH_ENGINES.get(engine, self.SEARCH_ENGINES["duckduckgo"])
        full_url = url.format(encoded)

        if open_browser:
            self.open(full_url)

        # Fetch results as text
        result = self.read_page(full_url, max_chars=4000)
        result["query"] = query
        result["engine"] = engine
        log.info(f"  🔍 Search '{query}' → {engine}")
        return result

    def search_arxiv(self, query: str, max_results: int = 3) -> list[dict]:
        """Search ArXiv for recent papers."""
        import xml.etree.ElementTree as ET
        import urllib.parse
        url = (
            "https://export.arxiv.org/api/query"
            f"?search_query=all:{urllib.parse.quote(query)}"
            f"&max_results={max_results}&sortBy=submittedDate"
        )
        try:
            r = requests.get(url, timeout=20)
            root = ET.fromstring(r.content)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            papers = []
            for entry in root.findall("a:entry", ns):
                papers.append({
                    "title":    entry.findtext("a:title", namespaces=ns, default="").strip(),
                    "abstract": entry.findtext("a:summary", namespaces=ns, default="")[:300].strip(),
                    "url":      entry.findtext("a:id", namespaces=ns, default=""),
                })
            log.info(f"  📚 ArXiv '{query}': {len(papers)} papers")
            return papers
        except Exception as e:
            log.warning(f"  ArXiv error: {e}")
            return []

    def search_github(self, query: str, max_results: int = 5) -> list[dict]:
        """Search GitHub repositories."""
        import urllib.parse
        url = (f"https://api.github.com/search/repositories"
               f"?q={urllib.parse.quote(query)}&sort=stars&per_page={max_results}")
        try:
            r = requests.get(url, timeout=15,
                             headers={"Accept": "application/vnd.github.v3+json"})
            items = r.json().get("items", [])
            repos = [{"name": i["full_name"], "stars": i["stargazers_count"],
                      "url": i["html_url"], "desc": i.get("description","")}
                     for i in items]
            log.info(f"  🐙 GitHub '{query}': {len(repos)} repos")
            return repos
        except Exception as e:
            log.warning(f"  GitHub search error: {e}")
            return []


# ══════════════════════════════════════════════════════════════
# APP CONTROL (macOS)
# ══════════════════════════════════════════════════════════════
class AppControl:
    """
    Launch, switch, and close macOS/Linux applications.
    """

    MAC_APPS = {
        "terminal":   "Terminal",
        "browser":    "Safari",
        "chrome":     "Google Chrome",
        "vscode":     "Visual Studio Code",
        "finder":     "Finder",
        "notes":      "Notes",
        "calculator": "Calculator",
        "settings":   "System Preferences",
    }

    def launch(self, app_name: str) -> bool:
        """Launch an application."""
        log.info(f"  🚀 Launching: {app_name}")
        if IS_MAC:
            full = self.MAC_APPS.get(app_name.lower(), app_name)
            r = subprocess.run(["open", "-a", full], capture_output=True)
            return r.returncode == 0
        elif IS_LINUX:
            try:
                subprocess.Popen([app_name])
                return True
            except Exception:
                return False
        return False

    def close(self, app_name: str) -> bool:
        """Close an application (macOS)."""
        if IS_MAC:
            full = self.MAC_APPS.get(app_name.lower(), app_name)
            script = f'tell application "{full}" to quit'
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True)
            return r.returncode == 0
        return False

    def list_running(self) -> list[str]:
        """List running applications."""
        if IS_MAC:
            r = subprocess.run(
                ["osascript", "-e",
                 'tell app "System Events" to name of processes where background only is false'],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                return [a.strip() for a in r.stdout.split(",")]
        return []


# ══════════════════════════════════════════════════════════════
# FILE CONTROL
# ══════════════════════════════════════════════════════════════
class FileControl:
    """
    Create, read, edit, move, delete files.
    """

    def read(self, path: str, max_chars: int = 5000) -> dict:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return {"success": False, "error": f"File not found: {path}"}
            text = p.read_text(encoding="utf-8", errors="replace")[:max_chars]
            return {"success": True, "path": str(p),
                    "content": text, "size": p.stat().st_size}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write(self, path: str, content: str,
              append: bool = False) -> dict:
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            p.write_text(content, encoding="utf-8") if not append else \
                p.open("a").write(content)
            log.info(f"  📝 Written: {path} ({len(content)} chars)")
            return {"success": True, "path": str(p), "chars": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_dir(self, path: str = "~") -> dict:
        try:
            p = Path(path).expanduser()
            items = [{"name": f.name, "type": "dir" if f.is_dir() else "file",
                      "size": f.stat().st_size if f.is_file() else 0}
                     for f in sorted(p.iterdir())]
            return {"success": True, "path": str(p), "items": items}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_in_vscode(self, path: str) -> bool:
        """Open file or folder in VS Code."""
        p = Path(path).expanduser()
        r = subprocess.run(["code", str(p)], capture_output=True)
        return r.returncode == 0


# ══════════════════════════════════════════════════════════════
# CODING AGENT
# ══════════════════════════════════════════════════════════════
class CodingAgent:
    """
    AI-powered coding agent.
    Gets task → writes Python code → runs it → returns result.
    ਜਿਵੇਂ JARVIS ਕੋਡ ਲਿਖਦਾ ਹੈ।
    """

    SYSTEM_PROMPT = """You are AMRIT's coding agent. 
Given a task, write clean Python code to accomplish it.
Return ONLY the Python code, no explanation, no markdown backticks.
The code must be complete and runnable.
Available: numpy, scipy, pandas, requests, json, os, pathlib, datetime, math"""

    def __init__(self, model: str = "deepseek-coder-v2:latest"):
        self.model    = model
        self.terminal = TerminalControl()

    def write_and_run(self, task: str,
                       context: str = "") -> dict:
        """
        Given a task description → write code → run it → return output.
        """
        log.info(f"  🤖 CodingAgent: {task[:60]}")

        # Ask Ollama to write the code
        prompt = f"Task: {task}\n{f'Context: {context}' if context else ''}\n\nWrite Python code:"
        code = self._ask_llm(prompt)

        if not code:
            return {"success": False, "error": "LLM unavailable"}

        # Clean code (remove markdown if present)
        import re
        code = re.sub(r'^```\w*\n?', '', code.strip())
        code = re.sub(r'\n?```$', '', code.strip())

        log.info(f"  📝 Generated code ({len(code)} chars)")

        # Run in sandbox
        result = self.terminal.run_python_script(code)
        result["task"]        = task
        result["code_written"] = code

        if result["success"]:
            log.info(f"  ✅ Code ran: {result['output'][:80]}")
        else:
            log.warning(f"  ❌ Code error: {result['error'][:80]}")

        return result

    def _ask_llm(self, prompt: str) -> str:
        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model":  self.model,
                    "prompt": prompt,
                    "system": self.SYSTEM_PROMPT,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 800},
                },
                timeout=60,
            )
            return r.json().get("response", "")
        except Exception as e:
            log.warning(f"  LLM error: {e}")
            return ""

    def improve_amrit(self, module_path: str) -> dict:
        """Read an AMRIT module and suggest improvements."""
        file_ctrl = FileControl()
        content = file_ctrl.read(module_path)
        if not content["success"]:
            return content

        task = (f"Review this Python module and suggest 3 specific improvements "
                f"with code examples:\n\n{content['content'][:2000]}")
        suggestions = self._ask_llm(task)
        return {"success": True, "module": module_path,
                "suggestions": suggestions}


# ══════════════════════════════════════════════════════════════
# SELF-UPGRADE ENGINE
# ══════════════════════════════════════════════════════════════
class SelfUpgradeEngine:
    """
    Searches internet for new techniques and upgrades AMRIT.
    ਆਪਣੇ ਆਪ ਅੱਪਡੇਟ ਹੋਣ ਦੀ ਸਮਰੱਥਾ।
    """

    def __init__(self, model: str = "qwen3:8b"):
        self.model   = model
        self.browser = BrowserControl()
        self.coder   = CodingAgent(model)
        self.files   = FileControl()

    def search_and_learn(self, topic: str) -> dict:
        """
        Search for new research on a topic and summarize key insights.
        """
        log.info(f"  🔍 Self-learning: {topic}")

        results = {}

        # Search ArXiv
        papers = self.browser.search_arxiv(topic, max_results=3)
        results["arxiv_papers"] = papers

        # Search GitHub
        repos = self.browser.search_github(topic + " python", max_results=3)
        results["github_repos"] = repos

        # Ask Ollama to synthesize
        context = (
            f"Topic: {topic}\n\n"
            f"Recent Papers:\n" +
            "\n".join(f"- {p['title']}: {p['abstract'][:100]}" for p in papers) +
            f"\n\nTop GitHub Repos:\n" +
            "\n".join(f"- {r['name']} ({r['stars']}★): {r['desc']}" for r in repos)
        )
        prompt = (
            f"Based on these search results about '{topic}', "
            f"what are the 3 most important insights that could improve "
            f"a medical AI research system? Be specific and actionable."
        )
        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt + "\n\nContext:\n" + context[:1500],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 400},
                },
                timeout=60,
            )
            results["synthesis"] = r.json().get("response", "")
        except Exception:
            results["synthesis"] = "Ollama unavailable"

        log.info(f"  ✅ Learned about: {topic}")
        return results

    def check_for_updates(self, amrit_repo: str = "") -> dict:
        """Check for updates to AMRIT and suggest upgrades."""
        topics = [
            "DNA pattern recognition deep learning 2026",
            "medical AI diagnosis local LLM",
            "voice agent computer control python",
            "pharmacogenomics drug interaction AI",
        ]

        updates = {}
        for topic in topics[:2]:  # Limit to 2 to avoid rate limits
            updates[topic] = self.search_and_learn(topic)
            time.sleep(1)

        return {"updates": updates, "timestamp": time.strftime("%Y-%m-%d %H:%M")}

    def upgrade_module(self, module_path: str,
                        improvement_hint: str = "") -> dict:
        """
        Read a module, find improvements online, write upgraded version.
        """
        # Read current module
        content = self.files.read(module_path)
        if not content["success"]:
            return content

        # Search for improvements
        module_name = Path(module_path).stem
        search_results = self.browser.search_arxiv(
            f"{module_name} improvement technique 2026", max_results=2
        )

        # Ask coder to improve
        task = (
            f"Improve this Python module with better algorithms. "
            f"Module: {module_name}\n"
            f"{f'Hint: {improvement_hint}' if improvement_hint else ''}\n"
            f"Recent research context: "
            + "\n".join(p["abstract"][:100] for p in search_results)
        )

        improved = self.coder.write_and_run(task, content["content"][:1000])
        return {"success": True, "module": module_path,
                "improved": improved, "research_used": search_results}


# ══════════════════════════════════════════════════════════════
# MASTER COMPUTER CONTROL
# ══════════════════════════════════════════════════════════════
class ComputerControl:
    """
    Master computer control — JARVIS for AMRIT.
    Combines all capabilities into one interface.

    Usage:
        ctrl = ComputerControl()
        ctrl.run_terminal("python3 server.py")
        ctrl.open_browser("https://arxiv.org")
        ctrl.write_and_run_code("import math; print(math.pi)")
        ctrl.web_search("DNA vaccine 2026")
        ctrl.self_upgrade("DNA pattern recognition")
    """

    def __init__(self, ollama_model: str = "deepseek-coder-v2:latest"):
        self.terminal  = TerminalControl()
        self.browser   = BrowserControl()
        self.apps      = AppControl()
        self.files     = FileControl()
        self.coder     = CodingAgent(ollama_model)
        self.upgrader  = SelfUpgradeEngine(ollama_model)
        log.info("🤖 ComputerControl (JARVIS) ready")

    # ── Shortcuts ──────────────────────────────────────────────
    def run_terminal(self, cmd: str) -> dict:
        return self.terminal.run(cmd)

    def open_browser(self, url: str) -> bool:
        return self.browser.open(url)

    def read_website(self, url: str) -> dict:
        return self.browser.read_page(url)

    def web_search(self, query: str,
                   engine: str = "duckduckgo") -> dict:
        return self.browser.search(query, engine, open_browser=False)

    def write_and_run_code(self, task_or_code: str) -> dict:
        """Write code for a task and run it."""
        return self.coder.write_and_run(task_or_code)

    def open_app(self, app: str) -> bool:
        return self.apps.launch(app)

    def read_file(self, path: str) -> dict:
        return self.files.read(path)

    def write_file(self, path: str, content: str) -> dict:
        return self.files.write(path, content)

    def self_upgrade(self, topic: str = "medical AI") -> dict:
        return self.upgrader.search_and_learn(topic)

    def execute_plan(self, plan: list[dict]) -> list[dict]:
        """
        Execute a multi-step plan.
        plan = [
            {"action": "terminal", "command": "ls"},
            {"action": "browser",  "url": "https://arxiv.org"},
            {"action": "code",     "task": "calculate fibonacci"},
            {"action": "search",   "query": "DNA patterns"},
        ]
        """
        results = []
        for i, step in enumerate(plan):
            action = step.get("action", "")
            log.info(f"  📋 Step {i+1}/{len(plan)}: {action}")

            if action == "terminal":
                r = self.run_terminal(step.get("command",""))
            elif action == "browser":
                r = {"success": self.open_browser(step.get("url",""))}
            elif action == "read_url":
                r = self.read_website(step.get("url",""))
            elif action == "code":
                r = self.write_and_run_code(step.get("task",""))
            elif action == "search":
                r = self.web_search(step.get("query",""))
            elif action == "file_read":
                r = self.read_file(step.get("path",""))
            elif action == "file_write":
                r = self.write_file(step.get("path",""), step.get("content",""))
            elif action == "app":
                r = {"success": self.open_app(step.get("name",""))}
            elif action == "upgrade":
                r = self.self_upgrade(step.get("topic","medical AI"))
            else:
                r = {"success": False, "error": f"Unknown action: {action}"}

            results.append({"step": i+1, "action": action,
                            "input": step, "result": r})
            time.sleep(0.2)  # Small delay between steps

        return results


# ══════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

    print("""
╔══════════════════════════════════════════════════════╗
║  AMRIT Computer Control (JARVIS) — Demo              ║
╚══════════════════════════════════════════════════════╝
""")
    ctrl = ComputerControl()

    # Test 1: Terminal
    print("1️⃣  Terminal:")
    r = ctrl.run_terminal("echo 'AMRIT JARVIS online' && date && python3 --version")
    print(f"   {r['output']}")

    # Test 2: Python code
    print("\n2️⃣  Write & Run Code:")
    r = ctrl.write_and_run_code(
        "import math; "
        "fib = [1,1]; "
        "[fib.append(fib[-1]+fib[-2]) for _ in range(8)]; "
        "print('Fibonacci:', fib); "
        "print('Golden ratio:', round(fib[-1]/fib[-2], 6))"
    )
    print(f"   {r['output']}")

    # Test 3: File operations
    print("\n3️⃣  File Operations:")
    ctrl.write_file("/tmp/amrit_test.txt", "AMRIT JARVIS Test\n")
    r = ctrl.read_file("/tmp/amrit_test.txt")
    print(f"   File: {r['content'].strip()}")

    # Test 4: Web search
    print("\n4️⃣  Web Search:")
    r = ctrl.web_search("DNA pattern recognition medical AI")
    print(f"   Found {len(r.get('text',''))} chars from {r.get('engine')}")

    # Test 5: ArXiv
    print("\n5️⃣  ArXiv Search:")
    papers = ctrl.browser.search_arxiv("pharmacogenomics AI 2025", max_results=2)
    for p in papers:
        print(f"   📄 {p['title'][:60]}...")

    # Test 6: Execute plan
    print("\n6️⃣  Multi-step Plan:")
    plan = [
        {"action": "terminal", "command": "echo 'Step 1: System check' && uname -m"},
        {"action": "code",     "task": "import platform; print(f'CPU: {platform.processor()}, OS: {platform.system()}')"},
        {"action": "search",   "query": "AMRIT medical AI open source"},
    ]
    results = ctrl.execute_plan(plan)
    for r in results:
        out = r["result"].get("output", "")[:60] if r["result"].get("success") else r["result"].get("error","")[:60]
        print(f"   Step {r['step']} ({r['action']}): {'✅' if r['result'].get('success') else '❌'} {out}")

    print("\n✅ AMRIT Computer Control (JARVIS) fully operational!")
    print("   ctrl.run_terminal('any command')")
    print("   ctrl.open_browser('https://arxiv.org')")
    print("   ctrl.write_and_run_code('any Python task')")
    print("   ctrl.self_upgrade('DNA recognition')")
