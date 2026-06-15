"""
AMRIT RESEARCH OS v4.5
core/paper_writer/paper_writer.py

Paper Generator:
  - Title, Abstract, Methods, Results, Discussion, References
  - Auto Citation (APA, MLA, IEEE)
  - JSON export
  - Text-based PDF export (no heavy dependencies)
"""

import os
import json
import datetime


class PaperWriter:

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(f"{output_dir}/pdf", exist_ok=True)
        os.makedirs(f"{output_dir}/json", exist_ok=True)

    # ─────────────────── Auto Citation ───────────────────

    def cite_apa(
        self,
        authors: list,
        year: int,
        title: str,
        journal: str = "",
        doi: str = "",
    ) -> str:
        author_str = ", ".join(authors) if authors else "Unknown Author"
        doi_str = f" https://doi.org/{doi}" if doi else ""
        return f"{author_str} ({year}). {title}. {journal}{doi_str}".strip(". ") + "."

    def cite_mla(
        self,
        authors: list,
        year: int,
        title: str,
        journal: str = "",
    ) -> str:
        author_str = authors[0] if authors else "Unknown"
        return (
            f'{author_str}. "{title}." {journal}, {year}.'
            if journal
            else f'{author_str}. "{title}." {year}.'
        )

    def cite_ieee(
        self,
        authors: list,
        year: int,
        title: str,
        journal: str = "",
        doi: str = "",
    ) -> str:
        author_str = ", ".join(authors) if authors else "Unknown"
        doi_str = f", doi: {doi}" if doi else ""
        return (
            f'{author_str}, "{title}," {journal}, {year}{doi_str}.'
            if journal
            else f'{author_str}, "{title}," {year}{doi_str}.'
        )

    def auto_cite(
        self,
        sources: list,
    ) -> dict:
        """
        sources: list of dicts with keys:
            authors (list), year (int), title (str), journal (str), doi (str)
        """
        citations = {"apa": [], "mla": [], "ieee": []}
        for s in sources:
            a = s.get("authors", [])
            y = s.get("year", datetime.datetime.now().year)
            t = s.get("title", "Untitled")
            j = s.get("journal", "")
            d = s.get("doi", "")
            citations["apa"].append(self.cite_apa(a, y, t, j, d))
            citations["mla"].append(self.cite_mla(a, y, t, j))
            citations["ieee"].append(self.cite_ieee(a, y, t, j, d))
        return citations

    # ─────────────────── Paper Sections ───────────────────

    def generate_paper(
        self,
        hypothesis: str,
        result: dict,
        debate: dict,
        review: dict,
        sources: list = None,
        domain: str = "",
    ) -> dict:
        """Generate a full research paper as a structured dict."""
        now = datetime.datetime.now()
        verdict = result.get("verdict", "UNKNOWN")
        p_value = result.get("p_value", "N/A")
        effect_size = result.get("effect_size", "N/A")

        title = (
            f"Investigating {domain} Patterns: "
            f"A Computational Research Analysis"
            if domain
            else "Computational Research Analysis: A Systematic Study"
        )

        abstract = (
            f"This study investigates the hypothesis: \"{hypothesis}\". "
            f"Using a multi-source data collection pipeline (ArXiv, PubMed, NASA, OpenAlex) "
            f"and a multi-agent statistical evaluation framework, we found "
            f"p-value={p_value} and effect_size={effect_size}. "
            f"The overall verdict is: {verdict}."
        )

        methods = (
            "Data was collected from six academic sources. "
            "Statistical analysis included Monte Carlo simulation, Bayesian updating, "
            "Benford's Law test, Pearson correlation, and linear regression. "
            "A multi-agent debate (Believer vs Skeptic) was conducted, "
            "followed by automated peer review."
        )

        results_text = (
            f"Statistical Results:\n"
            f"  p-value       : {p_value}\n"
            f"  effect_size   : {effect_size}\n"
            f"  Verdict       : {verdict}\n\n"
            f"Debate Outcome:\n"
            f"  {debate.get('judge_verdict', 'N/A')}\n"
            f"  Confidence    : {debate.get('confidence', 'N/A')}"
        )

        discussion = (
            f"The results {('support' if 'SUPPORT' in verdict else 'do not support')} "
            f"the original hypothesis. "
            f"Reviewer notes: {review.get('methodology_check', '')} "
            f"Skeptical concerns: {review.get('bias_check', '')}"
        )

        paper = {
            "title": title,
            "date": now.strftime("%Y-%m-%d %H:%M"),
            "hypothesis": hypothesis,
            "abstract": abstract,
            "methods": methods,
            "results": results_text,
            "discussion": discussion,
            "references": self.auto_cite(sources or []),
        }
        return paper

    # ─────────────────── Export ───────────────────

    def export_json(self, paper: dict, filename: str = "") -> str:
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"paper_{ts}.json"
        path = os.path.join(self.output_dir, "json", filename)
        with open(path, "w") as f:
            json.dump(paper, f, indent=2)
        return path

    def export_text_pdf(self, paper: dict, filename: str = "") -> str:
        """Export paper as a plain text file (acts as PDF placeholder)."""
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"paper_{ts}.txt"
        path = os.path.join(self.output_dir, "pdf", filename)
        lines = [
            "=" * 70,
            "AMRIT RESEARCH OS v4.5 — Research Paper",
            "=" * 70,
            f"Title      : {paper.get('title', '')}",
            f"Date       : {paper.get('date', '')}",
            "",
            "ABSTRACT",
            "-" * 40,
            paper.get("abstract", ""),
            "",
            "METHODS",
            "-" * 40,
            paper.get("methods", ""),
            "",
            "RESULTS",
            "-" * 40,
            paper.get("results", ""),
            "",
            "DISCUSSION",
            "-" * 40,
            paper.get("discussion", ""),
            "",
            "REFERENCES (APA)",
            "-" * 40,
        ]
        for ref in paper.get("references", {}).get("apa", []):
            lines.append(f"  {ref}")
        lines.append("=" * 70)
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path
