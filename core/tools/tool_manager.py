"""
AMRIT RESEARCH OS v4.5
core/tools/tool_manager.py

Tool-Calling Engine.

v3 weakness FIXED:
  #5  Agents could not use tools. Now there is a registry of callable
      tools and a single entry point:

      tool_manager.execute("search_arxiv", query="quantum batteries")

Registered tools:
  search_arxiv, search_pubmed, search_web, search_openalex,
  calculator, python_sandbox, kg_add, kg_neighbors,
  memory_search, memory_add
"""

import json
import math
import urllib.request
import urllib.parse

from core.data_sources import DataCollector
from core.sandbox import SandboxExecutor


class ToolManager:

    def __init__(self, data=None, sandbox=None, graph=None, vector_memory=None):
        self.data = data or DataCollector()
        self.sandbox = sandbox or SandboxExecutor()
        self.graph = graph
        self.vmem = vector_memory
        self.registry = {
            "search_arxiv":    self._search_arxiv,
            "search_pubmed":   self._search_pubmed,
            "search_openalex": self._search_openalex,
            "search_web":      self._search_web,
            "calculator":      self._calculator,
            "python_sandbox":  self._python_sandbox,
            "kg_add":          self._kg_add,
            "kg_neighbors":    self._kg_neighbors,
            "memory_search":   self._memory_search,
            "memory_add":      self._memory_add,
        }

    # ─────────────────── dispatcher ───────────────────

    def list_tools(self) -> list:
        return sorted(self.registry.keys())

    def execute(self, tool: str, **kwargs) -> dict:
        """Single entry point: tool_manager.execute('search_arxiv', query=...)."""
        fn = self.registry.get(tool)
        if not fn:
            return {"tool": tool, "ok": False, "error": f"Unknown tool '{tool}'",
                    "available": self.list_tools()}
        try:
            result = fn(**kwargs)
            return {"tool": tool, "ok": True, "result": result}
        except TypeError as e:
            return {"tool": tool, "ok": False, "error": f"Bad arguments: {e}"}
        except Exception as e:
            return {"tool": tool, "ok": False, "error": str(e)}

    # ─────────────────── tools ───────────────────

    def _search_arxiv(self, query: str, max_results: int = 5):
        return self.data.search_arxiv(query, max_results)

    def _search_pubmed(self, query: str, max_results: int = 5):
        return self.data.search_pubmed(query, max_results)

    def _search_openalex(self, query: str, max_results: int = 5):
        return self.data.search_openalex(query, max_results)

    def _search_web(self, query: str, max_results: int = 5):
        """DuckDuckGo Instant Answer API (no key, returns related topics)."""
        url = (
            "https://api.duckduckgo.com/?q="
            + urllib.parse.quote(query)
            + "&format=json&no_html=1&skip_disambig=1"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        out = []
        if data.get("AbstractText"):
            out.append({"title": data.get("Heading", ""),
                        "text": data["AbstractText"],
                        "url": data.get("AbstractURL", "")})
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                out.append({"text": topic["Text"], "url": topic.get("FirstURL", "")})
        return out[:max_results]

    def _calculator(self, expression: str):
        """Safe arithmetic evaluator (no names except math functions)."""
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
        value = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307 (sandboxed names)
        return {"expression": expression, "value": value}

    def _python_sandbox(self, code: str):
        return self.sandbox.run(code)

    def _kg_add(self, source: str, target: str, relation: str = "related_to"):
        if not self.graph:
            return {"error": "knowledge graph not attached"}
        self.graph.add_edge(source, target, relation)
        return {"added": [source, relation, target]}

    def _kg_neighbors(self, node: str):
        if not self.graph:
            return {"error": "knowledge graph not attached"}
        return {"node": node, "neighbors": self.graph.get_neighbors(node)}

    def _memory_search(self, query: str, collection: str = "research_notes", k: int = 3):
        if not self.vmem:
            return {"error": "vector memory not attached"}
        return self.vmem.search(collection, query, k)

    def _memory_add(self, text: str, collection: str = "research_notes", metadata: dict = None):
        if not self.vmem:
            return {"error": "vector memory not attached"}
        return {"id": self.vmem.add(collection, text, metadata)}
