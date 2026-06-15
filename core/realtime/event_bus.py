"""
AMRIT RESEARCH OS v4.5
core/realtime/event_bus.py

Simple pub/sub event bus — modules ਆਪਸ ਵਿੱਚ communicate ਕਰਦੇ ਹਨ।
No Redis needed — pure Python threading.

Usage:
    bus = EventBus()
    bus.subscribe("alert.critical", my_handler)
    bus.publish("alert.critical", {"patient": "P001", "value": 7.2})

Events:
    patient.new          → ਨਵਾਂ patient data ਆਇਆ
    patient.analysed     → Medical pipeline complete
    alert.critical       → Critical value detected
    alert.moderate       → Moderate alert
    report.generated     → PDF ready
    report.dispatched    → Sent to medical center
    lab.value            → New lab reading
    doctor.approved      → Doctor approved prescription
"""

import threading
import logging
import time
from typing import Callable, Any
from collections import defaultdict
from datetime import datetime

log = logging.getLogger("AmritEventBus")


class Event:
    def __init__(self, topic: str, data: dict, source: str = "system"):
        self.topic     = topic
        self.data      = data
        self.source    = source
        self.timestamp = datetime.now().isoformat()
        self.id        = f"{topic}_{int(time.time()*1000)}"

    def __repr__(self):
        return f"Event({self.topic}, source={self.source}, ts={self.timestamp})"


class EventBus:
    """
    Thread-safe publish/subscribe event bus.
    All handlers run in background threads — non-blocking.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history:     list[Event] = []
        self._lock         = threading.Lock()
        self._max_history  = 200
        log.info("⚡ EventBus online")

    # ── Subscribe ─────────────────────────────────────────────
    def subscribe(self, topic: str, handler: Callable) -> None:
        """Register handler for a topic. Supports wildcards: 'alert.*'"""
        with self._lock:
            self._subscribers[topic].append(handler)
        log.debug(f"  📡 Subscribed {handler.__name__} → {topic}")

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic] = [
                    h for h in self._subscribers[topic] if h != handler
                ]

    # ── Publish ───────────────────────────────────────────────
    def publish(self, topic: str, data: dict, source: str = "system") -> None:
        """
        Publish event. All matching handlers called in background threads.
        Matches exact topic AND wildcard (e.g. 'alert.*' matches 'alert.critical')
        """
        event = Event(topic, data, source)

        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            handlers = []
            # Exact match
            handlers.extend(self._subscribers.get(topic, []))
            # Wildcard match: 'alert.*' matches 'alert.critical'
            prefix = topic.split(".")[0]
            handlers.extend(self._subscribers.get(f"{prefix}.*", []))
            # Global wildcard
            handlers.extend(self._subscribers.get("*", []))

        for handler in handlers:
            t = threading.Thread(
                target=self._safe_call,
                args=(handler, event),
                daemon=True,
            )
            t.start()

    def _safe_call(self, handler: Callable, event: Event) -> None:
        try:
            handler(event)
        except Exception as e:
            log.error(f"  ❌ Handler {handler.__name__} error on {event.topic}: {e}")

    # ── History & Stats ───────────────────────────────────────
    def recent(self, topic: str = None, n: int = 20) -> list[Event]:
        with self._lock:
            events = self._history if topic is None else [
                e for e in self._history
                if e.topic == topic or e.topic.startswith(topic.rstrip("*"))
            ]
            return events[-n:]

    def stats(self) -> dict:
        with self._lock:
            topic_counts: dict[str, int] = defaultdict(int)
            for e in self._history:
                topic_counts[e.topic] += 1
            return {
                "total_events":   len(self._history),
                "topics":         dict(topic_counts),
                "subscribers":    {t: len(h) for t, h in self._subscribers.items()},
            }


# Global singleton
_bus: EventBus | None = None

def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
