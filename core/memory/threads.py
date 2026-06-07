"""
AMRIT RESEARCH OS v4.0
core/memory/threads.py

Conversation Threads — named, persistent memory threads.

Each thread groups a conversation under a category (Research, Business,
Personal, Coding, Amrit Project). Messages are persisted to disk so a
browser session can resume any named thread, and every stored turn is
tagged with the thread id so vector recall can be scoped per thread.

Storage: data/threads.json  (single JSON file, no external deps).
"""

import os
import json
import uuid
import datetime


DEFAULT_CATEGORIES = ["Research", "Business", "Personal", "Coding", "Amrit Project"]

# Seed threads created on first run (matches the examples requested).
SEED_THREADS = [
    {"name": "Amrit Research OS", "category": "Amrit Project"},
    {"name": "Kirpa Agent",       "category": "Personal"},
    {"name": "Email Assistant",   "category": "Business"},
]


class ThreadManager:

    def __init__(self, path: str = "data/threads.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._threads = {}
        self._load()
        if not self._threads:
            for seed in SEED_THREADS:
                self.create(seed["name"], seed["category"])

    # ─────────────────── persistence ───────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self._threads = json.load(f)
            except Exception:
                self._threads = {}

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self._threads, f, indent=2)
        except Exception:
            pass

    # ─────────────────── CRUD ───────────────────

    def categories(self) -> list:
        return list(DEFAULT_CATEGORIES)

    def create(self, name: str, category: str = "Research") -> dict:
        tid = uuid.uuid4().hex[:12]
        thread = {
            "id": tid,
            "name": name.strip() or "Untitled",
            "category": category if category in DEFAULT_CATEGORIES else "Research",
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "messages": [],
        }
        self._threads[tid] = thread
        self._save()
        return thread

    def list(self) -> list:
        """Return thread summaries (no message bodies), newest first."""
        out = [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "created": t["created"],
                "messages": len(t.get("messages", [])),
            }
            for t in self._threads.values()
        ]
        return sorted(out, key=lambda x: x["created"], reverse=True)

    def get(self, thread_id: str) -> dict:
        return self._threads.get(thread_id, {})

    def add_message(self, thread_id: str, role: str, content: str) -> bool:
        t = self._threads.get(thread_id)
        if not t:
            return False
        t["messages"].append({
            "role": role,
            "content": content,
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        # Keep the on-disk history bounded.
        t["messages"] = t["messages"][-200:]
        self._save()
        return True

    def delete(self, thread_id: str) -> bool:
        if thread_id in self._threads:
            del self._threads[thread_id]
            self._save()
            return True
        return False
