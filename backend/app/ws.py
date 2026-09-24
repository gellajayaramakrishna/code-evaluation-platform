from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self._subs: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def topic(self, kind: str, ident: str | int) -> str:
        return f"{kind}:{ident}"

    async def connect(self, ws: WebSocket, topic: str) -> None:
        await ws.accept()
        async with self._lock:
            self._subs[topic].add(ws)

    async def disconnect(self, ws: WebSocket, topic: str) -> None:
        async with self._lock:
            self._subs[topic].discard(ws)
            if not self._subs[topic]:
                self._subs.pop(topic, None)

    async def publish(self, topic: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._subs.get(topic, ()))
        dead = []
        text = json.dumps(payload, default=str)
        for ws in sockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._subs.get(topic, set()).discard(ws)

    def publish_sync(self, topic: str, payload: dict) -> None:
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.publish(topic, payload), loop)


hub = Hub()
