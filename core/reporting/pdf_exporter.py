"""
AMRIT RESEARCH OS v4.0
core/reporting/pdf_exporter.py

Dependency-free PDF generator.

No reportlab / fpdf required — this writes a valid PDF 1.4 file directly,
using the built-in Helvetica fonts. Supports:
  - a title
  - multiple sections (heading + body)
  - automatic word-wrap and multi-page flow
  - bold headings

Good enough for research reports, email-agent reports and health reports.
"""

import os
import datetime


# Approx character width for Helvetica at a given font size (monospace-ish estimate).
def _wrap(text: str, max_chars: int):
    """Word-wrap a paragraph to a max character width per line."""
    out = []
    for raw_line in text.split("\n"):
        if not raw_line.strip():
            out.append("")
            continue
        words = raw_line.split(" ")
        line = ""
        for w in words:
            if len(line) + len(w) + 1 <= max_chars:
                line = (line + " " + w).strip()
            else:
                if line:
                    out.append(line)
                # hard-break very long words
                while len(w) > max_chars:
                    out.append(w[:max_chars])
                    w = w[max_chars:]
                line = w
        if line:
            out.append(line)
    return out


def _esc(s: str) -> str:
    """Escape characters special to PDF text strings."""
    return (
        s.replace("\\", "\\\\")
         .replace("(", "\\(")
         .replace(")", "\\)")
    )


def _sanitize(s: str) -> str:
    """Keep PDF-safe Latin-1 text (drop emoji / non-encodable chars)."""
    if s is None:
        return ""
    try:
        return s.encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return "".join(ch if ord(ch) < 256 else "?" for ch in s)


class PDFExporter:

    PAGE_W = 612          # US Letter, points
    PAGE_H = 792
    MARGIN = 56
    LINE_H = 15
    BODY_SIZE = 10
    HEAD_SIZE = 13
    TITLE_SIZE = 18
    MAX_CHARS = 92        # chars per line at body size

    def __init__(self, output_dir: str = "reports/pdf"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ─────────────────── public API ───────────────────

    def build(self, title: str, sections: list, filename: str = "",
              subtitle: str = "") -> str:
        """
        sections: list of {"heading": str, "body": str}
        Returns the path to the written PDF.
        """
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{ts}.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        path = os.path.join(self.output_dir, filename)

        # Build a flat list of (text, size, bold) lines, then paginate.
        lines = []
        lines.append((_sanitize(title), self.TITLE_SIZE, True))
        if subtitle:
            lines.append((_sanitize(subtitle), self.BODY_SIZE, False))
        lines.append(("", self.BODY_SIZE, False))

        for sec in sections:
            heading = _sanitize(sec.get("heading", ""))
            body = _sanitize(sec.get("body", ""))
            if heading:
                lines.append((heading, self.HEAD_SIZE, True))
            for wl in _wrap(body, self.MAX_CHARS):
                lines.append((wl, self.BODY_SIZE, False))
            lines.append(("", self.BODY_SIZE, False))

        pages = self._paginate(lines)
        pdf_bytes = self._render(pages)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return path

    # ─────────────────── layout ───────────────────

    def _paginate(self, lines):
        usable = self.PAGE_H - 2 * self.MARGIN
        per_page = int(usable // self.LINE_H)
        pages, cur = [], []
        for ln in lines:
            cur.append(ln)
            if len(cur) >= per_page:
                pages.append(cur)
                cur = []
        if cur:
            pages.append(cur)
        return pages or [[("", self.BODY_SIZE, False)]]

    def _content_stream(self, page_lines) -> str:
        parts = ["BT", f"/F1 {self.BODY_SIZE} Tf",
                 f"1 0 0 1 {self.MARGIN} {self.PAGE_H - self.MARGIN} Tm",
                 f"{self.LINE_H} TL"]
        for text, size, bold in page_lines:
            font = "F2" if bold else "F1"
            parts.append(f"/{font} {size} Tf")
            parts.append(f"({_esc(text)}) Tj")
            parts.append("T*")
        parts.append("ET")
        return "\n".join(parts)

    def _render(self, pages) -> bytes:
        objects = []     # list of raw object bodies (without "N 0 obj")
        # Object numbering plan:
        #   1: Catalog
        #   2: Pages
        #   3: Font Helvetica (F1)
        #   4: Font Helvetica-Bold (F2)
        #   then per page: Page object + Content object
        n_pages = len(pages)
        page_obj_ids = []
        content_obj_ids = []
        next_id = 5
        for _ in range(n_pages):
            page_obj_ids.append(next_id); next_id += 1
            content_obj_ids.append(next_id); next_id += 1

        kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)

        objects.append((1, "<< /Type /Catalog /Pages 2 0 R >>"))
        objects.append((2, f"<< /Type /Pages /Count {n_pages} /Kids [{kids}] >>"))
        objects.append((3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        objects.append((4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"))

        for i in range(n_pages):
            content = self._content_stream(pages[i])
            cbytes = content.encode("latin-1", "replace")
            page_body = (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {self.PAGE_W} {self.PAGE_H}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {content_obj_ids[i]} 0 R >>"
            )
            objects.append((page_obj_ids[i], page_body))
            stream_obj = (
                f"<< /Length {len(cbytes)} >>\nstream\n{content}\nendstream"
            )
            objects.append((content_obj_ids[i], stream_obj))

        # Assemble file with xref table
        objects.sort(key=lambda o: o[0])
        out = b"%PDF-1.4\n"
        offsets = {}
        for obj_id, body in objects:
            offsets[obj_id] = len(out)
            out += f"{obj_id} 0 obj\n{body}\nendobj\n".encode("latin-1", "replace")

        xref_pos = len(out)
        total = len(objects) + 1
        out += f"xref\n0 {total}\n".encode("latin-1")
        out += b"0000000000 65535 f \n"
        for obj_id in range(1, total):
            out += f"{offsets.get(obj_id, 0):010d} 00000 n \n".encode("latin-1")
        out += (
            f"trailer\n<< /Size {total} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF"
        ).encode("latin-1")
        return out
