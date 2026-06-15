"""
AMRIT RESEARCH OS v4.5
core/scheduler.py

Background Scheduler — autonomous recurring jobs.

Default campaign (every 5 minutes):
    Auto Check Inbox -> Analyze -> Store Memory -> Notify User

Runs on a daemon thread so it never blocks the web server. All activity is
recorded as in-memory notifications that the dashboard can poll. Inbox access
uses IMAP_* env vars only; if they are not set the job records a single
"not configured" notice and keeps idling cheaply.
"""

import threading
import datetime


class BackgroundScheduler:

    def __init__(self, email_agent=None, vector_memory=None,
                 interval_seconds: int = 300):
        self.email = email_agent
        self.vmem = vector_memory
        self.interval = max(30, int(interval_seconds))
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.running = False
        self.last_run = None
        self.next_run = None
        self.runs = 0
        self._notifications = []        # newest last

    # ─────────────────── notifications ───────────────────

    def _notify(self, message: str, kind: str = "info"):
        with self._lock:
            self._notifications.append({
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "kind": kind,
                "message": message,
            })
            self._notifications = self._notifications[-100:]

    def notifications(self, unseen_after: str = "") -> list:
        with self._lock:
            items = list(self._notifications)
        if unseen_after:
            items = [n for n in items if n["ts"] > unseen_after]
        return items

    def clear_notifications(self):
        with self._lock:
            self._notifications = []

    # ─────────────────── the job ───────────────────

    def _run_inbox_job(self):
        self.last_run = datetime.datetime.now().isoformat(timespec="seconds")
        self.runs += 1
        if not self.email:
            self._notify("Scheduler: no email agent attached", "warn")
            return
        try:
            result = self.email.process_inbox(limit=5, make_pdf=False, auto_reply=False)
        except Exception as e:
            self._notify(f"Inbox check failed: {e}", "warn")
            return

        if not result.get("configured"):
            self._notify("Inbox check skipped — IMAP not configured "
                         "(set IMAP_HOST/IMAP_USER/IMAP_PASS)", "warn")
            return

        count = result.get("count", 0)
        if count == 0:
            self._notify("Inbox checked — no new unread emails", "ok")
            return

        # Store each analysed email into vector memory and notify per item.
        for item in result.get("items", []):
            a = item.get("analysis", {})
            subject = a.get("subject", "(no subject)")
            sender = a.get("sender", "?")
            urgency = a.get("urgency", "normal")
            if self.vmem and self.vmem.enabled:
                self.vmem.add(
                    "conversations",
                    f"Email from {sender} — {subject}\n"
                    f"Urgency: {urgency}; Category: {a.get('category','')}\n"
                    f"{a.get('suggested_reply','')}",
                    {"type": "inbox_email", "urgency": urgency},
                )
            self._notify(
                f"New email from {sender}: \"{subject}\" "
                f"[{urgency}] — analysed & stored",
                "high" if urgency == "high" else "info",
            )
        self._notify(f"Inbox campaign complete — {count} email(s) processed", "ok")

    # ─────────────────── lifecycle ───────────────────

    def _loop(self):
        while not self._stop.is_set():
            self._run_inbox_job()
            self.next_run = (
                datetime.datetime.now() + datetime.timedelta(seconds=self.interval)
            ).isoformat(timespec="seconds")
            # Sleep in small slices so stop() is responsive.
            self._stop.wait(self.interval)

    def start(self, interval_seconds: int = None) -> dict:
        if interval_seconds:
            self.interval = max(30, int(interval_seconds))
        if self.running:
            return self.status()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self.running = True
        self._thread.start()
        self._notify(f"Scheduler started — checking inbox every "
                     f"{self.interval // 60} min {self.interval % 60} s", "ok")
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        self.running = False
        self._notify("Scheduler stopped", "warn")
        return self.status()

    def run_now(self) -> dict:
        """Trigger one inbox campaign immediately (manual)."""
        self._run_inbox_job()
        return self.status()

    def status(self) -> dict:
        return {
            "running": self.running,
            "interval_seconds": self.interval,
            "runs": self.runs,
            "last_run": self.last_run,
            "next_run": self.next_run if self.running else None,
            "pending_notifications": len(self._notifications),
        }
