"""
AMRIT RESEARCH OS v3.0
core/ai/ollama_client.py

Ollama Local AI Integration:
- qwen3:14b (default — best for 16GB M5)
- Any installed Ollama model
- Fallback if Ollama not running
"""

import urllib.request
import urllib.error
import json


OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-coder-v2:latest"


class OllamaClient:

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE):
        self.model = model
        self.base_url = base_url

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def list_models(self) -> list:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as r:
                data = json.loads(r.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat(self, prompt: str, system: str = "") -> str:
        if not self.is_available():
            return "[Ollama offline] Run: ollama serve"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 4096},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
                return data.get("message", {}).get("content", "No response").strip()
        except Exception as e:
            return f"[Ollama error] {e}"

    def generate_hypothesis(self, domain: str) -> str:
        return self.chat(
            f"Generate a single novel testable research hypothesis in: {domain}. One sentence only.",
            system="You are a brilliant research scientist. Be specific and concise.",
        )

    def analyze_result(self, hypothesis: str, stats: dict) -> str:
        return self.chat(
            f"Hypothesis: {hypothesis}\np-value: {stats.get('p_value')}\n"
            f"effect_size: {stats.get('effect_size')}\nVerdict: {stats.get('verdict')}\n\n"
            f"Provide 2-sentence scientific interpretation.",
            system="You are a senior research analyst. Be concise.",
        )

    def debate_argument(self, role: str, hypothesis: str, stats: dict) -> str:
        return self.chat(
            f"Hypothesis: {hypothesis}\nVerdict: {stats.get('verdict')}\n"
            f"Argue from role: {role} in 2 sentences.",
            system=f"You are the {role} in a scientific debate. Be direct.",
        )

    def write_abstract(self, hypothesis: str, result: dict) -> str:
        return self.chat(
            f"Hypothesis: {hypothesis}\nResult: {result.get('verdict')}, "
            f"p={result.get('p_value')}, effect_size={result.get('effect_size')}\n\n"
            f"Write a 3-sentence scientific abstract.",
            system="You are a scientific paper writer. Be professional.",
        )
