"""
services/event_bus.py — Lightweight synchronous/async event bus.

Publishes typed events throughout the system so components stay decoupled.
Any module can publish an event; any module can subscribe without knowing
about the publisher.

Built-in event types:
    task.created        task.planned        task.assigned
    task.completed      task.failed
    agent.started       agent.completed     agent.failed
    tool.called         tool.succeeded      tool.failed
    memory.stored       memory.retrieved
    user.message        ai.response
    workflow.started    workflow.completed  workflow.failed
    analytics.record

Usage:
    from services.event_bus import bus, Event

    # Subscribe
    @bus.on("task.completed")
    def handle_completion(event: Event):
        print(event.data)

    # Publish
    bus.emit("task.completed", data={"task_id": "123", "result": "..."})
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

log = logging.getLogger("services.event_bus")


@dataclass
class Event:
    topic:      str
    data:       dict          = field(default_factory=dict)
    event_id:   str           = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp:  float         = field(default_factory=time.time)
    source:     str           = ""
    trace_id:   str           = ""        # link to observability tracer

    def to_dict(self) -> dict:
        return asdict(self)


class EventBus:
    """
    Thread-safe pub/sub event bus with:
    - Synchronous handlers (called in publisher thread by default)
    - Async handlers run in a background thread
    - Event history (last N events per topic, configurable)
    - Wildcard subscriptions via "*"
    """

    def __init__(self, history_size: int = 200) -> None:
        self._handlers:  dict[str, list[Callable]] = defaultdict(list)
        self._history:   list[Event]               = []
        self._history_size = history_size
        self._lock       = threading.RLock()
        self._executor   = None    # lazy thread pool

    # ── Subscribe ─────────────────────────────────────────────────────────────
    def on(self, topic: str, handler: Callable = None):
        """
        Register a handler for a topic.  Can be used as decorator:

            @bus.on("task.completed")
            def h(event): ...

        or directly:

            bus.on("task.completed", my_handler)
        """
        def _register(fn: Callable) -> Callable:
            with self._lock:
                self._handlers[topic].append(fn)
            log.debug("Subscribed %s to '%s'", fn.__name__, topic)
            return fn

        if handler is not None:
            return _register(handler)
        return _register

    def off(self, topic: str, handler: Callable) -> None:
        with self._lock:
            self._handlers[topic] = [h for h in self._handlers[topic] if h is not handler]

    # ── Publish ───────────────────────────────────────────────────────────────
    def emit(
        self,
        topic:    str,
        data:     dict   = None,
        source:   str    = "",
        trace_id: str    = "",
        async_:   bool   = False,
    ) -> Event:
        """
        Emit an event to all subscribers of *topic* and "*".
        If async_=True, handlers run in a background thread.
        """
        event = Event(
            topic    = topic,
            data     = data or {},
            source   = source,
            trace_id = trace_id,
        )

        # Record history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history.pop(0)
            handlers = list(self._handlers.get(topic, []))
            handlers += list(self._handlers.get("*", []))

        if not handlers:
            return event

        if async_:
            self._dispatch_async(handlers, event)
        else:
            self._dispatch(handlers, event)

        return event

    def _dispatch(self, handlers: list[Callable], event: Event) -> None:
        for h in handlers:
            try:
                h(event)
            except Exception as e:
                log.error("Handler %s raised on '%s': %s", h.__name__, event.topic, e)

    def _dispatch_async(self, handlers: list[Callable], event: Event) -> None:
        import concurrent.futures
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=4, thread_name_prefix="event-bus"
            )
        for h in handlers:
            self._executor.submit(self._safe_call, h, event)

    @staticmethod
    def _safe_call(handler: Callable, event: Event) -> None:
        try:
            handler(event)
        except Exception as e:
            log.error("Async handler %s raised on '%s': %s", handler.__name__, event.topic, e)

    # ── Query ─────────────────────────────────────────────────────────────────
    def history(self, topic: str = "", limit: int = 50) -> list[dict]:
        with self._lock:
            events = self._history[-limit:]
        if topic:
            events = [e for e in events if e.topic == topic]
        return [e.to_dict() for e in reversed(events)]

    def topics(self) -> list[str]:
        with self._lock:
            return sorted(self._handlers.keys())

    def subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._handlers.get(topic, []))


# ── Singleton ─────────────────────────────────────────────────────────────────
bus = EventBus()

# ── Built-in cross-cutting subscribers ────────────────────────────────────────
@bus.on("*")
def _log_all(event: Event) -> None:
    """Log every event at DEBUG level for observability."""
    log.debug("[bus] %s  src=%s  data_keys=%s",
              event.topic, event.source or "-",
              list(event.data.keys())[:5])
