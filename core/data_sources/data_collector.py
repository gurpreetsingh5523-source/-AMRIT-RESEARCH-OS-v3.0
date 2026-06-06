"""
AMRIT RESEARCH OS v3.0
core/data_sources/data_collector.py

Data Collection Layer:
  - ArXiv
  - PubMed
  - NASA
  - OpenAlex
  - Semantic Scholar
  - CrossRef

Dataset Reliability Scores:
  NASA = 95%, PubMed = 98%, ArXiv = 85%,
  OpenAlex = 80%, Semantic Scholar = 82%, CrossRef = 88%
"""

import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET


RELIABILITY_SCORES = {
    "NASA": 95,
    "PubMed": 98,
    "ArXiv": 85,
    "OpenAlex": 80,
    "SemanticScholar": 82,
    "CrossRef": 88,
}


class DataCollector:

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    # ─────────────────── ArXiv ───────────────────

    def search_arxiv(self, query: str, max_results: int = 5) -> list:
        """Search ArXiv for papers."""
        q = urllib.parse.quote(query)
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=all:{q}&max_results={max_results}"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            root = ET.fromstring(data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            for entry in root.findall("atom:entry", ns):
                results.append({
                    "source": "ArXiv",
                    "reliability": RELIABILITY_SCORES["ArXiv"],
                    "title": entry.findtext("atom:title", "", ns).strip(),
                    "summary": entry.findtext("atom:summary", "", ns).strip()[:200],
                    "link": entry.findtext("atom:id", "", ns).strip(),
                })
            return results
        except Exception as e:
            return [{"source": "ArXiv", "error": str(e)}]

    # ─────────────────── PubMed ───────────────────

    def search_pubmed(self, query: str, max_results: int = 5) -> list:
        """Search PubMed for papers."""
        q = urllib.parse.quote(query)
        search_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&term={q}&retmax={max_results}&retmode=json"
        )
        try:
            with urllib.request.urlopen(search_url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ids = data.get("esearchresult", {}).get("idlist", [])
            results = []
            for pmid in ids:
                results.append({
                    "source": "PubMed",
                    "reliability": RELIABILITY_SCORES["PubMed"],
                    "pmid": pmid,
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
            return results
        except Exception as e:
            return [{"source": "PubMed", "error": str(e)}]

    # ─────────────────── NASA ───────────────────

    def search_nasa(self, query: str, max_results: int = 5) -> list:
        """Search NASA Technical Reports Server."""
        q = urllib.parse.quote(query)
        url = (
            f"https://ntrs.nasa.gov/api/citations/search"
            f"?keyword={q}&rows={max_results}"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                results.append({
                    "source": "NASA",
                    "reliability": RELIABILITY_SCORES["NASA"],
                    "title": item.get("title", ""),
                    "abstract": item.get("abstract", "")[:200],
                    "id": item.get("id", ""),
                })
            return results
        except Exception as e:
            return [{"source": "NASA", "error": str(e)}]

    # ─────────────────── OpenAlex ───────────────────

    def search_openalex(self, query: str, max_results: int = 5) -> list:
        """Search OpenAlex for scholarly works."""
        q = urllib.parse.quote(query)
        url = (
            f"https://api.openalex.org/works?search={q}"
            f"&per-page={max_results}&mailto=amrit@research.os"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                results.append({
                    "source": "OpenAlex",
                    "reliability": RELIABILITY_SCORES["OpenAlex"],
                    "title": item.get("title", ""),
                    "doi": item.get("doi", ""),
                    "year": item.get("publication_year", ""),
                    "cited_by": item.get("cited_by_count", 0),
                })
            return results
        except Exception as e:
            return [{"source": "OpenAlex", "error": str(e)}]

    # ─────────────────── Semantic Scholar ───────────────────

    def search_semantic_scholar(self, query: str, max_results: int = 5) -> list:
        """Search Semantic Scholar."""
        q = urllib.parse.quote(query)
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={q}&limit={max_results}&fields=title,abstract,year,citationCount"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("data", []):
                results.append({
                    "source": "SemanticScholar",
                    "reliability": RELIABILITY_SCORES["SemanticScholar"],
                    "title": item.get("title", ""),
                    "year": item.get("year", ""),
                    "citations": item.get("citationCount", 0),
                })
            return results
        except Exception as e:
            return [{"source": "SemanticScholar", "error": str(e)}]

    # ─────────────────── CrossRef ───────────────────

    def search_crossref(self, query: str, max_results: int = 5) -> list:
        """Search CrossRef for DOI metadata."""
        q = urllib.parse.quote(query)
        url = (
            f"https://api.crossref.org/works?query={q}&rows={max_results}"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("message", {}).get("items", []):
                title_list = item.get("title", [""])
                results.append({
                    "source": "CrossRef",
                    "reliability": RELIABILITY_SCORES["CrossRef"],
                    "title": title_list[0] if title_list else "",
                    "doi": item.get("DOI", ""),
                    "publisher": item.get("publisher", ""),
                })
            return results
        except Exception as e:
            return [{"source": "CrossRef", "error": str(e)}]

    # ─────────────────── Collect All ───────────────────

    def collect_all(self, query: str, max_per_source: int = 3) -> dict:
        """Collect from all sources."""
        return {
            "arxiv": self.search_arxiv(query, max_per_source),
            "pubmed": self.search_pubmed(query, max_per_source),
            "nasa": self.search_nasa(query, max_per_source),
            "openalex": self.search_openalex(query, max_per_source),
            "semantic_scholar": self.search_semantic_scholar(query, max_per_source),
            "crossref": self.search_crossref(query, max_per_source),
        }

    def reliability_score(self, source: str) -> int:
        return RELIABILITY_SCORES.get(source, 30)
