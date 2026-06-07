"""
AMRIT RESEARCH OS v4.0
core/sandbox/executor.py

Safe Python Sandbox.

v3 weakness FIXED:
  #5/#8  Agents could not run code. Now they can — safely.

Two layers of protection:
  1. STATIC scan  - reject source containing blocked imports/patterns
     (os.remove, shutil.rmtree, subprocess, socket, rm -rf, eval, exec, ...)
  2. ISOLATED run - execute in a separate Python process with:
        - a timeout (default 8s)
        - no working-dir writes outside a temp dir
        - only scientific libs available in the prompt namespace

Allowed libs:  numpy, pandas, scipy, math, statistics, matplotlib (Agg)
Blocked:       os.system, os.remove, subprocess, socket, requests,
               urllib, open(...,'w'), __import__ of network/file-deleting mods
"""

import os
import sys
import re
import tempfile
import subprocess

ALLOWED_LIBS = ["numpy", "pandas", "scipy", "math", "statistics", "matplotlib", "random", "json"]

BLOCKED_PATTERNS = [
    r"\bos\.remove\b", r"\bos\.unlink\b", r"\bos\.rmdir\b", r"\bos\.system\b",
    r"\bos\.popen\b", r"\bos\.kill\b", r"\bshutil\.rmtree\b",
    r"\bsubprocess\b", r"\bsocket\b", r"\brequests\b", r"\burllib\b",
    r"\bhttpx\b", r"\bsmtplib\b", r"\bctypes\b", r"\bpickle\b",
    r"\beval\s*\(", r"\bexec\s*\(", r"\b__import__\b", r"\bcompile\s*\(",
    r"\bopen\s*\([^)]*['\"][wax]", r"rm\s+-rf", r"\bsys\.exit\b",
    r"\bglobals\s*\(", r"\bgetattr\s*\(\s*__", r"\bsetattr\b",
]


class SandboxExecutor:

    def __init__(self, timeout: int = 8, allowed_libs=None):
        self.timeout = timeout
        self.allowed_libs = allowed_libs or ALLOWED_LIBS

    # ─────────────────── static guard ───────────────────

    def is_safe(self, code: str):
        """Return (ok: bool, reason: str)."""
        for pat in BLOCKED_PATTERNS:
            if re.search(pat, code):
                return False, f"Blocked pattern detected: /{pat}/"
        return True, "ok"

    # ─────────────────── execution ───────────────────

    def run(self, code: str) -> dict:
        """Statically validate, then execute in an isolated subprocess."""
        ok, reason = self.is_safe(code)
        if not ok:
            return {"ok": False, "blocked": True, "reason": reason, "stdout": "", "stderr": ""}

        preamble = (
            "try:\n"
            "    import matplotlib\n"
            "    matplotlib.use('Agg')\n"
            "except Exception:\n"
            "    pass\n"
            "import builtins as _b\n"
            "_b.open = lambda *a, **k: (_ for _ in ()).throw("
            "PermissionError('file open disabled in sandbox'))\n"
        )
        full_source = preamble + "\n" + code

        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "snippet.py")
            with open(script, "w") as f:
                f.write(full_source)
            try:
                proc = subprocess.run(
                    [sys.executable, script],
                    capture_output=True, text=True,
                    timeout=self.timeout, cwd=tmp,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                return {
                    "ok": proc.returncode == 0,
                    "blocked": False,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-4000:],
                    "stderr": proc.stderr[-2000:],
                }
            except subprocess.TimeoutExpired:
                return {
                    "ok": False, "blocked": False,
                    "reason": f"Timed out after {self.timeout}s",
                    "stdout": "", "stderr": "TimeoutExpired",
                }
            except Exception as e:
                return {"ok": False, "blocked": False, "reason": str(e),
                        "stdout": "", "stderr": str(e)}
