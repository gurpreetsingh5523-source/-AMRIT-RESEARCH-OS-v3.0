"""
AMRIT RESEARCH OS v4.0
core/models/router.py

Multi-Model Brain — route each task to the best available model.

v3 weakness FIXED:
  #7  Everything used a single model (deepseek-coder-v2).
      Now tasks are routed to specialised models, with automatic
      fallback to whatever is actually installed in Ollama.

Task categories -> preferred models (first installed one wins):
  deep_reasoning : qwen3, deepseek-r1, deepseek-coder-v2
  coding         : deepseek-coder-v2, qwen2.5-coder
  fast_tasks     : llama3.2, llama3, deepseek-coder-v2
  research       : mistral, llama3.1, deepseek-coder-v2
  planning       : gemma3, gemma2, llama3.2, deepseek-coder-v2
  embedding      : nomic-embed-text, mxbai-embed-large
  vision         : llava, llama3.2-vision
"""

from core.ai.ollama_client import OllamaClient


# Ordered preference lists. The router picks the FIRST model that is
# actually installed; otherwise it falls back to `default_model`.
TASK_PREFERENCES = {
    "deep_reasoning": ["qwen3:14b", "qwen3:8b", "deepseek-r1", "deepseek-coder-v2:latest"],
    "coding":         ["deepseek-coder-v2:latest", "qwen2.5-coder", "deepseek-coder-v2:16b-lite-instruct-q4_K_M"],
    "fast_tasks":     ["llama3.2", "llama3", "deepseek-coder-v2:16b-lite-instruct-q4_K_M", "deepseek-coder-v2:latest"],
    "research":       ["mistral", "llama3.1", "deepseek-coder-v2:latest"],
    "planning":       ["gemma3", "gemma2", "llama3.2", "deepseek-coder-v2:latest"],
    "embedding":      ["nomic-embed-text:latest", "nomic-embed-text", "mxbai-embed-large"],
    "vision":         ["llava:7b", "llava", "llama3.2-vision"],
}


class ModelRouter:
    """Resolves a task category to an OllamaClient backed by the best model."""

    def __init__(self, default_model: str = "deepseek-coder-v2:latest"):
        self.default_model = default_model
        self._probe = OllamaClient(model=default_model)
        self._installed = set(self._probe.list_models()) if self._probe.is_available() else set()
        self._clients = {}          # model_name -> OllamaClient
        self._resolved = {}         # task -> model_name (cache)

    # ─────────────────── resolution ───────────────────

    def resolve(self, task: str) -> str:
        """Return the model name chosen for a task category."""
        if task in self._resolved:
            return self._resolved[task]

        chosen = self.default_model
        for candidate in TASK_PREFERENCES.get(task, []):
            if candidate in self._installed:
                chosen = candidate
                break
        else:
            # No exact match: try a loose prefix match against installed models
            for candidate in TASK_PREFERENCES.get(task, []):
                base = candidate.split(":")[0]
                match = next((m for m in self._installed if m.startswith(base)), None)
                if match:
                    chosen = match
                    break
            else:
                # Fall back to default if installed, else any installed model
                if self.default_model not in self._installed and self._installed:
                    chosen = sorted(self._installed)[0]

        self._resolved[task] = chosen
        return chosen

    def client_for(self, task: str) -> OllamaClient:
        """Return a cached OllamaClient for the model chosen for this task."""
        model = self.resolve(task)
        if model not in self._clients:
            self._clients[model] = OllamaClient(model=model)
        return self._clients[model]

    def route(self, task: str, prompt: str, system: str = "") -> str:
        """Convenience: route a prompt to the best model for `task`."""
        return self.client_for(task).chat(prompt, system=system)

    # ─────────────────── introspection ───────────────────

    def available(self) -> bool:
        return bool(self._installed)

    def installed_models(self) -> list:
        return sorted(self._installed)

    def routing_table(self) -> dict:
        return {task: self.resolve(task) for task in TASK_PREFERENCES}
