"""
AMRIT RESEARCH OS v4.0
core/agents/self_heal.py

SELF-HEALING AUTONOMOUS AGENT
=============================
Gives the system the power to keep ITSELF alive and healthy so that anyone who
clones this repo can run it with ZERO maintenance — no paid support, no manual
fixes. This is the "survival mode" that fixes the system's own problems.

Four powers
-----------
  1. ensure_dependencies()  — detect & auto-install missing Python libraries
                              (maps import-name → pip-name, installs to --user).
  2. self_check()           — diagnose: compile every .py file, check Ollama,
                              check imports; returns a structured health report.
  3. heal_exception()       — catch a runtime error, locate the offending file,
                              ask the local LLM for a precise search/replace
                              fix, BACK UP the file, apply, re-validate with
                              py_compile, and ROLL BACK automatically if the
                              patch does not compile.
  4. survival_mode()        — run a full check and auto-repair everything that
                              can be repaired; safe to call at every boot.

Safety guarantees
-----------------
  * Only files INSIDE the project root are ever modified.
  * Every patch is backed up first (data/self_heal/backups/<ts>__<file>).
  * A patch is kept ONLY if the file still compiles; otherwise it is rolled
    back to the backup automatically.
  * Every action is appended to an audit log (data/self_heal/heal_log.jsonl).
  * Nothing here deletes user data or touches files outside the repo.
"""

import os
import re
import sys
import json
import shutil
import logging
import importlib
import subprocess
import traceback
import datetime
import py_compile
from pathlib import Path

log = logging.getLogger("AmritSelfHeal")

# import-name → pip-package-name (when they differ)
IMPORT_TO_PIP = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "Crypto": "pycryptodome",
    "OpenSSL": "pyopenssl",
    "dateutil": "python-dateutil",
    "google.protobuf": "protobuf",
    "turbovec": "turbovec",
}

# stdlib / built-ins we must never try to pip-install
_NEVER_INSTALL = {
    "os", "sys", "re", "json", "math", "time", "datetime", "logging",
    "subprocess", "pathlib", "typing", "collections", "itertools",
    "functools", "importlib", "traceback", "tempfile", "shutil",
    "random", "statistics", "urllib", "io", "csv", "sqlite3", "threading",
    "asyncio", "hashlib", "uuid", "glob", "string", "copy", "enum",
}

PATCH_SYSTEM = (
    "You are a senior Python engineer repairing a running program. You are "
    "given a source file and the runtime error it produced. Output ONE precise "
    "fix as an exact search/replace block and NOTHING else, in this format:\n"
    "<<<SEARCH>>>\n"
    "<exact lines copied verbatim from the file that contain the bug>\n"
    "<<<REPLACE>>>\n"
    "<the corrected lines>\n"
    "<<<END>>>\n"
    "Rules: the SEARCH text must appear EXACTLY once in the file, copied "
    "character-for-character. Keep the change minimal. No explanations, no "
    "markdown fences, no extra text."
)


class SelfHealingAgent:

    def __init__(self, router=None, root: str = None,
                 state_dir: str = "data/self_heal", allow_install: bool = True):
        self.router = router          # ModelRouter (optional; offline-safe)
        self.root = Path(root or Path(__file__).resolve().parents[2]).resolve()
        self.state_dir = Path(state_dir)
        self.backup_dir = self.state_dir / "backups"
        self.log_path = self.state_dir / "heal_log.jsonl"
        self.allow_install = allow_install
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────── audit ───────────────────

    def _audit(self, action: str, detail: dict):
        rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
               "action": action, **detail}
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return rec

    def history(self, limit: int = 50) -> list:
        if not self.log_path.exists():
            return []
        out = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        return out[-limit:]

    # ─────────────── 1. dependency healing ───────────────

    @staticmethod
    def _pip_name(module: str) -> str:
        if module in IMPORT_TO_PIP:
            return IMPORT_TO_PIP[module]
        return module.split(".")[0]

    def _pip_install(self, pip_name: str) -> dict:
        if not self.allow_install:
            return {"ok": False, "package": pip_name, "reason": "install disabled"}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--user", pip_name],
                capture_output=True, text=True, timeout=300,
            )
            ok = proc.returncode == 0
            res = {"ok": ok, "package": pip_name,
                   "stderr": (proc.stderr or "")[-400:] if not ok else ""}
            self._audit("pip_install", res)
            return res
        except Exception as e:
            res = {"ok": False, "package": pip_name, "reason": str(e)}
            self._audit("pip_install", res)
            return res

    def ensure_dependencies(self, modules) -> dict:
        """Make sure each import name is importable; auto-install if missing."""
        installed, already, failed = [], [], []
        for module in modules:
            top = module.split(".")[0]
            if top in _NEVER_INSTALL:
                already.append(module)
                continue
            try:
                importlib.import_module(module)
                already.append(module)
            except Exception:
                res = self._pip_install(self._pip_name(module))
                if res.get("ok"):
                    importlib.invalidate_caches()
                    try:
                        importlib.import_module(module)
                        installed.append(module)
                    except Exception:
                        failed.append(module)
                else:
                    failed.append(module)
        return {"installed": installed, "already_present": already, "failed": failed}

    def heal_missing_module(self, module_name: str) -> dict:
        """Install a single missing module (e.g. from an ImportError)."""
        return self.ensure_dependencies([module_name])

    # ─────────────── 2. self diagnosis ───────────────

    def _iter_py_files(self):
        for p in self.root.rglob("*.py"):
            parts = set(p.parts)
            if ".git" in parts or "__pycache__" in parts:
                continue
            yield p

    def self_check(self) -> dict:
        """Compile every file + check Ollama; return a health report."""
        broken = []
        total = 0
        for p in self._iter_py_files():
            total += 1
            try:
                py_compile.compile(str(p), doraise=True)
            except py_compile.PyCompileError as e:
                broken.append({"file": str(p.relative_to(self.root)),
                               "error": str(e.msg if hasattr(e, "msg") else e)[:300]})
            except Exception as e:
                broken.append({"file": str(p.relative_to(self.root)),
                               "error": str(e)[:300]})

        ollama_ok = False
        if self.router is not None:
            try:
                ollama_ok = self.router.available()
            except Exception:
                ollama_ok = False

        report = {
            "healthy": len(broken) == 0,
            "files_scanned": total,
            "syntax_errors": broken,
            "ollama_available": ollama_ok,
        }
        self._audit("self_check", {"healthy": report["healthy"],
                                   "broken": len(broken)})
        return report

    # ─────────────── 3. runtime error healing ───────────────

    def _ask_patch(self, file_text: str, error_text: str) -> str:
        if self.router is None:
            return ""
        try:
            client = self.router.client_for("coding")
            if not client.is_available():
                return ""
            prompt = (
                f"RUNTIME ERROR:\n{error_text}\n\n"
                f"SOURCE FILE:\n{file_text}\n\n"
                "Give exactly one search/replace fix."
            )
            out = client.chat(prompt, system=PATCH_SYSTEM).strip()
            return "" if out.startswith("[Ollama") or out.startswith("[Error") else out
        except Exception:
            return ""

    @staticmethod
    def _parse_patch(raw: str):
        m = re.search(r"<<<SEARCH>>>\s*\n(.*?)\n<<<REPLACE>>>\s*\n(.*?)\n<<<END>>>",
                      raw, re.DOTALL)
        if not m:
            return None
        return m.group(1), m.group(2)

    def _locate_project_frame(self, tb_text: str):
        """Find the deepest traceback frame that lives inside the project."""
        hits = re.findall(r'File "([^"]+)", line (\d+)', tb_text)
        for path, _line in reversed(hits):
            try:
                rp = Path(path).resolve()
            except Exception:
                continue
            if str(rp).startswith(str(self.root)) and rp.suffix == ".py" and rp.exists():
                return rp
        return None

    def _backup(self, path: Path) -> Path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = str(path.relative_to(self.root)).replace(os.sep, "__")
        dest = self.backup_dir / f"{ts}__{safe}"
        shutil.copy2(path, dest)
        return dest

    def heal_exception(self, exc: BaseException = None, tb_text: str = "",
                       max_attempts: int = 2) -> dict:
        """
        Attempt to repair the source file that raised `exc`.
        Returns {ok, file, applied, reason, backup}.
        """
        if tb_text:
            error_text = tb_text
        elif exc is not None:
            error_text = "".join(traceback.format_exception(
                type(exc), exc, exc.__traceback__))
        else:
            error_text = "".join(traceback.format_exc())

        # If it's a missing dependency, fix that first — no code patch needed.
        miss = re.search(r"No module named ['\"]([\w\.]+)['\"]", error_text)
        if miss:
            res = self.heal_missing_module(miss.group(1))
            ok = bool(res.get("installed"))
            out = {"ok": ok, "kind": "dependency", "module": miss.group(1),
                   "detail": res}
            self._audit("heal_exception", out)
            return out

        target = self._locate_project_frame(error_text)
        if target is None:
            out = {"ok": False, "kind": "code", "reason": "no project file in traceback"}
            self._audit("heal_exception", out)
            return out

        original = target.read_text(encoding="utf-8")
        for attempt in range(1, max_attempts + 1):
            raw = self._ask_patch(original, error_text)
            patch = self._parse_patch(raw) if raw else None
            if not patch:
                continue
            search, replace = patch
            if search not in original:
                continue
            if original.count(search) != 1:
                continue

            backup = self._backup(target)
            patched = original.replace(search, replace, 1)
            target.write_text(patched, encoding="utf-8")

            # validate — keep only if it still compiles
            try:
                py_compile.compile(str(target), doraise=True)
                out = {"ok": True, "kind": "code",
                       "file": str(target.relative_to(self.root)),
                       "attempt": attempt, "backup": str(backup)}
                self._audit("heal_exception", out)
                return out
            except Exception as e:
                shutil.copy2(backup, target)   # rollback
                error_text = error_text + f"\n[patch attempt {attempt} failed: {e}]"

        out = {"ok": False, "kind": "code",
               "file": str(target.relative_to(self.root)),
               "reason": "no valid compiling patch produced"}
        self._audit("heal_exception", out)
        return out

    def guard(self, fn, *args, **kwargs):
        """Run fn; if it raises, try to self-heal once and retry."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            healed = self.heal_exception(exc)
            if healed.get("ok"):
                importlib.invalidate_caches()
                return fn(*args, **kwargs)   # retry once after a successful heal
            raise

    # ─────────────── 4. survival mode ───────────────

    def survival_mode(self, ensure=None) -> dict:
        """
        Full boot-time self-repair:
          - make sure core dependencies are present (auto-install)
          - run a self-check
          - attempt to heal any syntax-broken file
        Safe to call on every startup; never raises.
        """
        result = {"dependencies": {}, "check": {}, "repairs": []}
        try:
            core_deps = list(ensure or [
                "numpy", "scipy", "fastapi", "uvicorn", "yaml", "requests",
            ])
            result["dependencies"] = self.ensure_dependencies(core_deps)

            check = self.self_check()
            result["check"] = check

            for item in check.get("syntax_errors", []):
                fake_tb = (f'File "{self.root / item["file"]}", line 1\n'
                           f'{item["error"]}')
                repair = self.heal_exception(tb_text=fake_tb)
                result["repairs"].append({"file": item["file"], **repair})

            result["ok"] = True
        except Exception as e:
            result["ok"] = False
            result["error"] = str(e)
        self._audit("survival_mode", {"ok": result.get("ok"),
                                      "broken": len(result.get("check", {})
                                                    .get("syntax_errors", []))})
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    agent = SelfHealingAgent()
    print(json.dumps(agent.self_check(), indent=2)[:1200])
