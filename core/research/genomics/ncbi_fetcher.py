"""
AMRIT RESEARCH OS v4.0
core/research/genomics/ncbi_fetcher.py

NCBI E-utilities client (free, no API key required).

Endpoints used:
  esearch  - find record IDs in a database (gene, clinvar, snp, pubmed)
  esummary - summarise those records

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/
"""

import json
import time
import urllib.request
import urllib.parse

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class NCBIFetcher:

    def __init__(self, timeout: int = 12, email: str = "amrit@research.os"):
        self.timeout = timeout
        self.email = email

    def _get(self, endpoint: str, params: dict) -> dict:
        params = {**params, "retmode": "json", "email": self.email, "tool": "AmritResearchOS"}
        url = f"{EUTILS}/{endpoint}.fcgi?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def esearch(self, db: str, term: str, retmax: int = 5) -> list:
        """Return a list of record IDs matching `term` in database `db`."""
        try:
            data = self._get("esearch", {"db": db, "term": term, "retmax": retmax})
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception:
            return []

    def esummary(self, db: str, ids: list) -> dict:
        """Return summaries for the given record ids."""
        if not ids:
            return {}
        try:
            time.sleep(0.34)   # respect NCBI 3 req/sec limit
            data = self._get("esummary", {"db": db, "id": ",".join(map(str, ids))})
            return data.get("result", {})
        except Exception:
            return {}

    # ─────────────────── convenience ───────────────────

    def gene_info(self, symbol: str, organism: str = "Homo sapiens") -> dict:
        """Look up a human gene by symbol (e.g. 'MTHFR', 'BRCA1')."""
        ids = self.esearch("gene", f"{symbol}[sym] AND {organism}[orgn]", retmax=1)
        if not ids:
            return {"gene": symbol, "found": False}
        summary = self.esummary("gene", ids)
        rec = summary.get(ids[0], {})
        return {
            "gene": symbol,
            "found": True,
            "uid": ids[0],
            "name": rec.get("name", ""),
            "description": rec.get("description", ""),
            "chromosome": rec.get("chromosome", ""),
            "map_location": rec.get("maplocation", ""),
            "summary": rec.get("summary", "")[:500],
        }

    def disease_genes(self, disease: str, retmax: int = 8) -> list:
        """Find genes associated with a disease/phenotype name."""
        ids = self.esearch("gene", f"{disease}[Disease] AND Homo sapiens[orgn]", retmax=retmax)
        summary = self.esummary("gene", ids)
        out = []
        for uid in ids:
            rec = summary.get(uid, {})
            if rec:
                out.append({
                    "uid": uid,
                    "symbol": rec.get("name", ""),
                    "description": rec.get("description", ""),
                    "chromosome": rec.get("chromosome", ""),
                })
        return out

    def pubmed_evidence(self, query: str, retmax: int = 5) -> list:
        """Return PubMed IDs supporting a gene/disease query."""
        ids = self.esearch("pubmed", query, retmax=retmax)
        return [f"https://pubmed.ncbi.nlm.nih.gov/{pid}/" for pid in ids]
