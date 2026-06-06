"""
AMRIT RESEARCH OS v3.0
core/ai/ollama_client.py

Ollama Local AI Integration:
- qwen3:14b (default — best for 16GB M5)
- Any installed Ollama model
- Streaming support
- Fallback if Ollama not running
"""

import urllib.request
import urllib.error
import json


OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"


class OllamaClient:

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE):
        self.model = model
        self.base_url = base_url

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def list_models(self) -> list:
        """List all installed models."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as r:
                data = json.loads(r.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat(self, prompt: str, system: str = "", stream: bool = False) -> str:
        """
        Send a prompt to Ollama and get a response.
        Falls back to a placeholder if Ollama is not available.
        """
        if not self.is_available():
            return (
                f"[Ollama offline] Local AI unavailable. "
                f"Start with: ollama serve"
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_ctx": 4096,
            },
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
                return data.get("message", {}).get("content", "No response")
        except urllib.error.URLError as e:
            return f"[Ollama error] {e}"
        except Exception as e:
            return f"[Error] {e}"

    def generate_hypothesis(self, domain: str) -> str:
        """Use local AI to generate a research hypothesis."""
        system = (
            "You are a brilliant research scientist. "
            "Generate a single precise, testable scientific hypothesis. "
            "Be specific, concise, one sentence only."
        )
        prompt = f"Generate a novel research hypothesis in the domain of: {domain}"
        response = self.chat(prompt, system=system)
        return response.strip().strip('"')

    def analyze_result(self, hypothesis: str, stats: dict) -> str:
        """Use local AI to interpret statistical results."""
        system = (
            "You are a senior research analyst. "
            "Interpret statistical results in plain scientific language. "
            "Be concise — 2-3 sentences max."
        )
        prompt = (
            f"Hypothesis: {hypothesis}\n"
            f"p-value: {stats.get('p_value')}\n"
            f"effect_size: {stats.get('effect_size')}\n"
            f"Verdict: {stats.get('verdict')}\n\n"
            f"Provide scientific interpretation."
        )
        return self.chat(prompt, system=system)

    def debate_argument(self, role: str, hypothesis: str, stats: dict) -> str:
        """Generate a debate argument from a specific agent role."""
        system = (
            f"You are playing the role of {role} in a scientific debate. "
            f"Present your argument in 2 sentences. Be direct."
        )
        prompt = (
            f"Hypothesis: {hypothesis}\n"
            f"Statistical verdict: {stats.get('verdict')}\n"
            f"p-value: {stats.get('p_value')}\n"
            f"Argue from your role: {role}"
        )
        return self.chat(prompt, system=system)

    def write_abstract(self, hypothesis: str, result: dict) -> str:
        """Generate a paper abstract using local AI."""
        system = (
            "You are a scientific paper writer. "
            "Write a concise abstract (3-4 sentences) for a research paper."
        )
        prompt = (
            f"Hypothesis: {hypothesis}\n"
            f"Result: {result.get('verdict')}, p={result.get('p_value')}, "
            f"effect_size={result.get('effect_size')}\n\n"
            f"Write a professional abstract."
        )
        return self.chat(prompt, system=system)
