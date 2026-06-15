"""
AMRIT RESEARCH OS v4.5
core/models/model_loader.py

🔄 Dynamic Model Loader & Auto-Categorizer

ਸਮੱਸਿਆ ਜੋ ਹੱਲ ਕਰਦਾ ਹੈ:
  - ਹਰ ਰੋਜ਼ ਨਵੇਂ models launch ਹੁੰਦੇ ਹਨ
  - v3 ਵਿੱਚ ਵੱਡੇ models hardcoded ਸਨ
  - ਹੁਣ: ਜੋ ਵੀ model Ollama ਵਿੱਚ install ਕਰੋ — ਆਪੇ ਲੱਭ ਜਾਂਦਾ ਹੈ
    ਅਤੇ ਆਪੇ ਸਹੀ category (coding/reasoning/vision...) ਵਿੱਚ ਆ ਜਾਂਦਾ ਹੈ

ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ:
  1. Ollama ਤੋਂ ਸਾਰੇ installed models ਲੱਭਦਾ ਹੈ (live)
  2. ਹਰ model ਨੂੰ ਨਾਮ ਦੇ ਆਧਾਰ ਤੇ auto-categorize ਕਰਦਾ ਹੈ
  3. ਹਰ task ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ available model ਚੁਣਦਾ ਹੈ
  4. ਕੋਈ model ਨਾ ਹੋਵੇ ਤਾਂ graceful fallback

ਵਰਤੋਂ:
    from core.models.model_loader import DynamicModelLoader
    loader = DynamicModelLoader()
    loader.refresh()                          # latest installed models
    print(loader.available_models())          # ਸਾਰੇ models
    model = loader.best_for("coding")         # ਸਭ ਤੋਂ ਵਧੀਆ coding model
    loader.prefer_local(True)                 # local models preferred
"""

import logging
import requests
import re
from typing import Optional

log = logging.getLogger("AmritModelLoader")

OLLAMA_BASE = "http://localhost:11434"


# ══════════════════════════════════════════════════════════════
# AUTO-CATEGORIZATION RULES
# ══════════════════════════════════════════════════════════════
# ਹਰ model ਨੂੰ ਨਾਮ ਦੇ keyword ਨਾਲ category ਮਿਲਦੀ ਹੈ।
# ਨਵਾਂ model ਆਵੇ — ਇਹ rules ਆਪੇ ਉਸਨੂੰ ਪਛਾਣ ਲੈਂਦੇ ਹਨ।

CATEGORY_KEYWORDS = {
    "vision": [
        "llava", "vision", "moondream", "bakllava", "minicpm-v",
        "qwen2-vl", "qwen2.5-vl", "llama3.2-vision", "pixtral", "gemma3",
    ],
    "embedding": [
        "embed", "nomic-embed", "mxbai", "bge-", "snowflake-arctic-embed",
        "all-minilm", "paraphrase",
    ],
    "coding": [
        "coder", "code", "deepseek-coder", "qwen2.5-coder", "codellama",
        "codegemma", "starcoder", "codestral", "granite-code", "stable-code",
    ],
    "deep_reasoning": [
        "r1", "deepseek-r1", "qwq", "reasoning", "marco-o1", "o1",
        "qwen3", "deepseek-v3", "thinking",
    ],
    "research": [
        "mistral", "mixtral", "command-r", "aya", "nemotron",
    ],
    "planning": [
        "gemma", "phi", "granite",
    ],
    "fast_tasks": [
        "llama3.2", "llama3.1", "llama3", "tinyllama", "smollm",
        "qwen2.5", "qwen2", "phi3", "phi-2", "stablelm",
    ],
}

# Task → preferred categories (in order). If exact category empty,
# fall back to general chat models.
TASK_CATEGORY_PRIORITY = {
    "deep_reasoning": ["deep_reasoning", "research", "coding", "fast_tasks"],
    "coding":         ["coding", "deep_reasoning", "fast_tasks"],
    "fast_tasks":     ["fast_tasks", "planning", "coding"],
    "research":       ["research", "deep_reasoning", "fast_tasks"],
    "planning":       ["planning", "fast_tasks", "research"],
    "embedding":      ["embedding"],
    "vision":         ["vision"],
    "medical":        ["deep_reasoning", "research", "coding", "fast_tasks"],
    "general":        ["fast_tasks", "research", "coding", "deep_reasoning"],
}

# Model size hints (bigger = more capable but slower)
SIZE_PATTERN = re.compile(r"(\d+\.?\d*)\s*b", re.IGNORECASE)


class DynamicModelLoader:
    """
    Auto-discovers all installed Ollama models and routes tasks
    to the best one. No hardcoding — works with ANY model.
    """

    def __init__(self, base_url: str = OLLAMA_BASE,
                 prefer_local: bool = True):
        self.base_url     = base_url
        self._prefer_local = prefer_local
        self._models: list[dict] = []      # [{name, size_gb, params_b, category}]
        self._categorized: dict[str, list] = {}
        self._cache: dict[str, str] = {}   # task -> resolved model
        self.refresh()

    # ── Discover installed models ─────────────────────────────
    def refresh(self) -> int:
        """
        Ollama ਤੋਂ ਸਾਰੇ installed models ਲੱਭੋ ਅਤੇ categorize ਕਰੋ।
        Returns number of models found.
        """
        self._models = []
        self._categorized = {cat: [] for cat in CATEGORY_KEYWORDS}
        self._cache = {}

        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            raw_models = r.json().get("models", [])
        except Exception as e:
            log.warning(f"⚠️  Ollama ਨਹੀਂ ਮਿਲਿਆ ({e}) — ਕੋਈ local model ਨਹੀਂ")
            return 0

        for m in raw_models:
            name      = m.get("name", "")
            size_bytes= m.get("size", 0)
            size_gb   = round(size_bytes / 1e9, 2)

            # Extract parameter size from name or details
            params_b = self._extract_params(name, m.get("details", {}))
            category = self._categorize(name)

            entry = {
                "name":      name,
                "size_gb":   size_gb,
                "params_b":  params_b,
                "category":  category,
            }
            self._models.append(entry)
            self._categorized[category].append(entry)

        # Sort each category by capability (bigger params first)
        for cat in self._categorized:
            self._categorized[cat].sort(
                key=lambda x: x["params_b"], reverse=True
            )

        log.info(f"🔄 {len(self._models)} models ਲੱਭੇ → categorized")
        for cat, models in self._categorized.items():
            if models:
                names = ", ".join(m["name"] for m in models[:3])
                log.info(f"   {cat:15} : {names}")

        return len(self._models)

    # ── Categorize a single model by name ─────────────────────
    def _categorize(self, name: str) -> str:
        """Model ਦਾ ਨਾਮ ਦੇਖ ਕੇ category ਚੁਣੋ।"""
        name_lower = name.lower()

        # Check each category's keywords (order matters: vision/embed first)
        for category in ["embedding", "vision", "coding",
                         "deep_reasoning", "research", "planning", "fast_tasks"]:
            for keyword in CATEGORY_KEYWORDS[category]:
                if keyword in name_lower:
                    return category

        # Unknown model → treat as general fast_task
        return "fast_tasks"

    # ── Extract parameter count ───────────────────────────────
    @staticmethod
    def _extract_params(name: str, details: dict) -> float:
        """Model ਦੇ parameters (billions) ਕੱਢੋ — capability ਦਾ ਅੰਦਾਜ਼ਾ।"""
        # Try details first
        param_size = details.get("parameter_size", "")
        if param_size:
            m = SIZE_PATTERN.search(str(param_size))
            if m:
                return float(m.group(1))
        # Try name (e.g. "qwen3:8b" -> 8)
        m = SIZE_PATTERN.search(name)
        if m:
            return float(m.group(1))
        return 0.0

    # ── Best model for a task ─────────────────────────────────
    def best_for(self, task: str) -> Optional[str]:
        """
        ਇਸ task ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ available model ਦਿਓ।
        ਕੋਈ ਨਾ ਹੋਵੇ ਤਾਂ None।
        """
        if task in self._cache:
            return self._cache[task]

        priority = TASK_CATEGORY_PRIORITY.get(task, TASK_CATEGORY_PRIORITY["general"])

        for category in priority:
            models = self._categorized.get(category, [])
            if models:
                chosen = models[0]["name"]   # biggest in category
                self._cache[task] = chosen
                log.info(f"  ✅ {task} → {chosen} ({category})")
                return chosen

        # Absolute fallback: any model at all
        if self._models:
            chosen = self._models[0]["name"]
            self._cache[task] = chosen
            return chosen

        return None

    # ── Queries ───────────────────────────────────────────────
    def available_models(self) -> list[str]:
        """ਸਾਰੇ installed models ਦੇ ਨਾਮ।"""
        return [m["name"] for m in self._models]

    def models_by_category(self) -> dict:
        """Category-wise organized models."""
        return {
            cat: [m["name"] for m in models]
            for cat, models in self._categorized.items()
            if models
        }

    def model_info(self, name: str) -> Optional[dict]:
        """ਕਿਸੇ model ਦੀ ਜਾਣਕਾਰੀ।"""
        return next((m for m in self._models if m["name"] == name), None)

    def has_model(self, name: str) -> bool:
        """ਕੀ ਇਹ model installed ਹੈ? (loose match)"""
        name_lower = name.lower()
        return any(name_lower in m["name"].lower() for m in self._models)

    def prefer_local(self, value: bool = True) -> None:
        """Local models ਨੂੰ priority ਦਿਓ (default: True)।"""
        self._prefer_local = value
        self._cache = {}  # reset cache

    # ── Dashboard / config summary ────────────────────────────
    def summary(self) -> dict:
        """Dashboard ਜਾਂ API ਲਈ ਪੂਰਾ summary।"""
        return {
            "total_models":   len(self._models),
            "ollama_online":  len(self._models) > 0,
            "by_category":    self.models_by_category(),
            "task_routing":   {
                task: self.best_for(task)
                for task in TASK_CATEGORY_PRIORITY
            },
            "all_models":     [
                {"name": m["name"], "size_gb": m["size_gb"],
                 "params_b": m["params_b"], "category": m["category"]}
                for m in self._models
            ],
        }

    def suggest_install(self) -> list[str]:
        """
        ਜੇ ਕੋਈ ਜ਼ਰੂਰੀ category ਖਾਲੀ ਹੈ ਤਾਂ install ਕਰਨ ਲਈ models ਦੱਸੋ।
        """
        suggestions = []
        recommended = {
            "deep_reasoning": "ollama pull qwen3:8b",
            "coding":         "ollama pull deepseek-coder-v2",
            "fast_tasks":     "ollama pull llama3.2",
            "embedding":      "ollama pull nomic-embed-text",
            "vision":         "ollama pull moondream",
        }
        for category, cmd in recommended.items():
            if not self._categorized.get(category):
                suggestions.append(cmd)
        return suggestions


# ══════════════════════════════════════════════════════════════
# DEMO / TEST
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("""
╔══════════════════════════════════════════════════════╗
║  AMRIT Dynamic Model Loader — Auto-Discovery         ║
╚══════════════════════════════════════════════════════╝
""")

    loader = DynamicModelLoader()

    models = loader.available_models()
    if not models:
        print("⚠️  Ollama offline ਜਾਂ ਕੋਈ model ਨਹੀਂ।")
        print("\n   ਚਾਲੂ ਕਰੋ:  ollama serve")
        print("   Install:    ollama pull qwen3:8b")
        print("\n   ਜਦੋਂ models install ਹੋਣ, ਇਹ loader ਆਪੇ ਲੱਭ ਲਵੇਗਾ!")
    else:
        print(f"✅ {len(models)} models ਲੱਭੇ:\n")
        for cat, names in loader.models_by_category().items():
            print(f"  {cat:15} : {', '.join(names)}")

        print("\n📋 Task Routing (ਹਰ task ਲਈ ਚੁਣਿਆ model):")
        for task in ["deep_reasoning", "coding", "fast_tasks",
                     "research", "vision", "embedding", "medical"]:
            chosen = loader.best_for(task)
            print(f"  {task:15} → {chosen or 'ਕੋਈ ਨਹੀਂ'}")

        suggestions = loader.suggest_install()
        if suggestions:
            print("\n💡 ਇਹ categories ਖਾਲੀ ਹਨ — install ਕਰੋ:")
            for s in suggestions:
                print(f"   {s}")

    print("\n✅ ਨਵਾਂ model install ਕਰੋ → loader.refresh() → ਆਪੇ ਲੱਭ ਜਾਵੇਗਾ!")
