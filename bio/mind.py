"""The mind: a thin client for any OpenAI-compatible chat endpoint.

Used only as a mutagen. The dish never waits on it.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from . import config


class Dormant(Exception):
    """No key, no model, no mind."""


class MindError(Exception):
    pass


class Mind:
    def __init__(self, model: str | None = None):
        self.model = model or config.MODEL
        self.key = config.API_KEY
        self.base = (config.BASE_URL or "").rstrip("/")
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_latency = 0.0
        self.last_error: str | None = None

    @property
    def awake(self) -> bool:
        # Local endpoints don't need a key.
        return bool(self.key) or "localhost" in self.base or "127.0.0.1" in self.base

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        if "openrouter" in self.base:
            h["HTTP-Referer"] = "https://github.com/oddurs/biotic"
            h["X-Title"] = "biotic"
        return h

    def think(
        self, system: str, user: str, *, temperature: float | None = None, max_tokens: int = 1400, timeout: float = 120
    ) -> str:
        if not self.awake:
            raise Dormant("no OPENROUTER_API_KEY (put it in .env)")
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": config.MUTAGEN_TEMP if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            self.base + "/chat/completions",
            data=json.dumps(body).encode(),
            headers=self._headers(),
            method="POST",
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            self.last_error = f"HTTP {e.code}: {detail}"
            raise MindError(self.last_error) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            self.last_error = f"{type(e).__name__}: {e}"
            raise MindError(self.last_error) from None
        self.last_latency = time.time() - t0
        self.calls += 1
        usage = data.get("usage") or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            self.last_error = f"odd reply: {json.dumps(data)[:300]}"
            raise MindError(self.last_error) from None
        self.last_error = None
        return text

    def models(self) -> list[dict]:
        req = urllib.request.Request(self.base + "/models", headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        return data.get("data", data if isinstance(data, list) else [])
