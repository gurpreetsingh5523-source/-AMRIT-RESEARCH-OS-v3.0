"""
AMRIT RESEARCH OS v4.0
core/agents/email_agent.py

Email Agent — read -> analyse -> suggest -> report (PDF) -> send.

Reading:
  - paste mode: pass the raw email text directly (default, no credentials)
  - IMAP mode : fetch unread emails if IMAP_* env vars are configured

Analysis:
  - intent / category, urgency, sentiment
  - key action items
  - DocumentAgent deep analysis of the body
  - a suggested reply draft

Output:
  - structured analysis dict
  - a PDF report (via the dependency-free PDFExporter)
  - optional: send the report / reply via SMTP (if SMTP_* env vars set)

SECURITY: credentials are read ONLY from environment variables, never logged.
Set them in your shell before sending:
    export SMTP_HOST=smtp.gmail.com SMTP_PORT=587
    export SMTP_USER=you@gmail.com  SMTP_PASS=app-password
    export IMAP_HOST=imap.gmail.com IMAP_USER=you@gmail.com IMAP_PASS=app-password
"""

import os
import re
import ssl
import smtplib
import datetime
from email.message import EmailMessage

from core.models.router import ModelRouter
from core.agents.document_agent import DocumentAgent
from core.reporting import PDFExporter


URGENCY = re.compile(r"\b(urgent|asap|immediately|deadline|today|critical|important)\b", re.I)
POSITIVE = re.compile(r"\b(thanks|great|appreciate|happy|good|excellent|pleased)\b", re.I)
NEGATIVE = re.compile(r"\b(issue|problem|fail|delay|concern|unhappy|complaint|sorry|wrong)\b", re.I)


class EmailAgent:

    def __init__(self, router: ModelRouter = None):
        self.router = router or ModelRouter()
        self.doc = DocumentAgent(self.router)
        self.pdf = PDFExporter()

    # ─────────────────── READ ───────────────────

    @staticmethod
    def parse_pasted(raw: str) -> dict:
        """Parse a pasted email. Recognises From:/Subject: headers if present."""
        sender, subject, body = "", "", raw
        lines = raw.splitlines()
        header_end = 0
        for i, ln in enumerate(lines[:12]):
            low = ln.lower()
            if low.startswith("from:"):
                sender = ln.split(":", 1)[1].strip(); header_end = i + 1
            elif low.startswith("subject:"):
                subject = ln.split(":", 1)[1].strip(); header_end = i + 1
            elif low.startswith(("to:", "date:", "cc:")):
                header_end = i + 1
        if header_end:
            body = "\n".join(lines[header_end:]).strip() or raw
        return {"sender": sender, "subject": subject, "body": body}

    def fetch_unread_imap(self, limit: int = 5) -> list:
        """Fetch unread emails via IMAP if IMAP_* env vars are set."""
        host = os.environ.get("IMAP_HOST")
        user = os.environ.get("IMAP_USER")
        pw = os.environ.get("IMAP_PASS")
        if not (host and user and pw):
            return [{"error": "IMAP not configured (set IMAP_HOST/IMAP_USER/IMAP_PASS)"}]
        import imaplib
        import email as email_lib
        out = []
        try:
            M = imaplib.IMAP4_SSL(host)
            M.login(user, pw)
            M.select("INBOX")
            _, data = M.search(None, "UNSEEN")
            ids = data[0].split()[:limit]
            for num in ids:
                _, msg_data = M.fetch(num, "(RFC822)")
                msg = email_lib.message_from_bytes(msg_data[0][1])
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_payload(decode=True).decode(errors="ignore")
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")
                out.append({
                    "sender": msg.get("From", ""),
                    "subject": msg.get("Subject", ""),
                    "body": body.strip(),
                })
            M.logout()
        except Exception as e:
            return [{"error": f"IMAP error: {e}"}]
        return out

    # ─────────────────── ANALYSE ───────────────────

    @staticmethod
    def _sentiment(text: str) -> str:
        pos, neg = len(POSITIVE.findall(text)), len(NEGATIVE.findall(text))
        if neg > pos:
            return "negative"
        if pos > neg:
            return "positive"
        return "neutral"

    def analyse(self, email: dict) -> dict:
        """Analyse a single parsed email dict {sender, subject, body}."""
        body = email.get("body", "")
        subject = email.get("subject", "")
        combined = f"{subject}\n{body}".strip()

        urgency = "high" if URGENCY.search(combined) else "normal"
        sentiment = self._sentiment(combined)

        category = self._ask(
            "fast_tasks",
            f"Classify this email in ONE word (e.g. request, complaint, inquiry, "
            f"update, sales, scheduling):\n\n{combined[:1500]}",
            "You classify emails. Reply with a single word.",
        ) or "general"

        action_items_raw = self._ask(
            "planning",
            f"List the action items this email asks of the recipient, one per line:\n\n{combined[:2500]}",
            "You extract action items. One per line. If none, write 'None'.",
        )
        action_items = [l.strip("-• \t") for l in action_items_raw.splitlines() if l.strip()][:8] \
            if action_items_raw else []

        # Deep analysis of the body via DocumentAgent
        doc_analysis = self.doc.analyse(body, refine=False) if len(body) > 120 else {}

        suggested_reply = self._ask(
            "research",
            f"Write a concise, professional reply to this email:\n\n{combined[:2500]}",
            "You are an executive assistant. Write a ready-to-send reply. Be courteous and clear.",
        ) or "Thank you for your email. We have received it and will respond shortly."

        return {
            "sender": email.get("sender", ""),
            "subject": subject,
            "category": category.split()[0].lower() if category else "general",
            "urgency": urgency,
            "sentiment": sentiment,
            "action_items": action_items,
            "analysis": doc_analysis,
            "suggested_reply": suggested_reply,
        }

    def _ask(self, task: str, prompt: str, system: str) -> str:
        client = self.router.client_for(task)
        if not client.is_available():
            return ""
        out = client.chat(prompt, system=system).strip()
        return "" if out.startswith("[Ollama") or out.startswith("[Error") else out

    # ─────────────────── REPORT (PDF) ───────────────────

    def build_report(self, analysis: dict, filename: str = "") -> str:
        doc = analysis.get("analysis", {}) or {}
        sections = [
            {"heading": "Email", "body":
                f"From: {analysis.get('sender','-')}\n"
                f"Subject: {analysis.get('subject','-')}\n"
                f"Category: {analysis.get('category','-')}   "
                f"Urgency: {analysis.get('urgency','-')}   "
                f"Sentiment: {analysis.get('sentiment','-')}"},
            {"heading": "Action Items", "body":
                "\n".join(f"- {a}" for a in analysis.get("action_items", [])) or "None detected."},
        ]
        if doc.get("summary"):
            sections.append({"heading": "Summary", "body": doc["summary"]})
        if doc.get("validation"):
            sections.append({"heading": "Analysis & Validation", "body": doc["validation"]})
        if doc.get("suggestions"):
            sections.append({"heading": "Suggestions", "body": doc["suggestions"]})
        sections.append({"heading": "Suggested Reply", "body": analysis.get("suggested_reply", "")})

        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"email_report_{ts}.pdf"
        return self.pdf.build(
            title="AMRIT Email Agent — Analysis Report",
            subtitle="Generated " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            sections=sections,
            filename=filename,
        )

    # ─────────────────── SEND (SMTP) ───────────────────

    def send_email(self, to_addr: str, subject: str, body: str,
                   attachment_path: str = "") -> dict:
        """Send an email via SMTP using SMTP_* env vars."""
        host = os.environ.get("SMTP_HOST")
        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER")
        pw = os.environ.get("SMTP_PASS")
        if not (host and user and pw):
            return {"sent": False, "reason": "SMTP not configured "
                    "(set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS)"}
        if not to_addr:
            return {"sent": False, "reason": "no recipient address"}

        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                data = f.read()
            msg.add_attachment(data, maintype="application", subtype="pdf",
                               filename=os.path.basename(attachment_path))
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(user, pw)
                s.send_message(msg)
            return {"sent": True, "to": to_addr, "attachment": bool(attachment_path)}
        except Exception as e:
            return {"sent": False, "reason": str(e)}

    # ─────────────────── FULL PIPELINE ───────────────────

    def process(self, raw_email: str, send_reply: bool = False,
                reply_to: str = "", make_pdf: bool = True) -> dict:
        """read -> analyse -> report -> (optional) send."""
        email = self.parse_pasted(raw_email)
        analysis = self.analyse(email)

        pdf_path = ""
        if make_pdf:
            pdf_path = self.build_report(analysis)

        send_result = {"sent": False, "reason": "send_reply not requested"}
        if send_reply:
            recipient = reply_to or email.get("sender", "")
            send_result = self.send_email(
                to_addr=recipient,
                subject=f"Re: {email.get('subject','')}",
                body=analysis.get("suggested_reply", ""),
                attachment_path=pdf_path,
            )

        return {
            "email": email,
            "analysis": analysis,
            "pdf_report": pdf_path,
            "send_result": send_result,
        }

    def process_inbox(self, limit: int = 5, make_pdf: bool = False,
                      auto_reply: bool = False) -> dict:
        """Fetch unread emails via IMAP and batch-analyse each one.

        Returns {configured, count, error, items:[{email, analysis,
        pdf_report, send_result}]}. Reading/sending use IMAP_*/SMTP_* env
        vars only; nothing is sent unless auto_reply is True AND SMTP is set.
        """
        emails = self.fetch_unread_imap(limit=limit)
        if emails and isinstance(emails[0], dict) and "error" in emails[0]:
            return {"configured": False, "count": 0,
                    "error": emails[0]["error"], "items": []}

        items = []
        for em in emails:
            analysis = self.analyse(em)
            pdf_path = self.build_report(analysis) if make_pdf else ""
            send_result = {"sent": False, "reason": "auto_reply disabled"}
            if auto_reply:
                send_result = self.send_email(
                    to_addr=em.get("sender", ""),
                    subject=f"Re: {em.get('subject','')}",
                    body=analysis.get("suggested_reply", ""),
                    attachment_path=pdf_path,
                )
            items.append({
                "email": em,
                "analysis": analysis,
                "pdf_report": pdf_path,
                "send_result": send_result,
            })
        return {"configured": True, "count": len(items), "error": "", "items": items}

