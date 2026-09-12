"""Model backends and the cost governor.

Two backends, one interface:

  AnthropicBackend  calls the API over stdlib urllib, no SDK dependency.
  FileBackend       writes each prompt to disk and reads the answer back from
                    disk. That makes every model-dependent stage runnable by
                    any external agent, including an assistant session with no
                    API key, without changing the pipeline.

The budget governor meters every call before dispatch. When the remaining
budget cannot cover the next stage the cycle halts and reports partial
results rather than overrunning (finding F30).
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WORK = Path(__file__).parent / "work"

# Rough list prices per million tokens, used only for metering.
PRICES = {
    "cheap": {"in": 1.00, "out": 5.00},
    "strong": {"in": 3.00, "out": 15.00},
}


class PendingResponse(Exception):
    """Raised by FileBackend when an answer has not been written yet."""

    def __init__(self, task_id: str, path: Path):
        super().__init__(f"awaiting response for {task_id} at {path}")
        self.task_id = task_id
        self.path = path


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    limit_usd: float = 5.0
    spent_usd: float = 0.0
    calls: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)

    def charge(self, tier: str, in_tokens: int, out_tokens: int,
               label: str = "") -> float:
        p = PRICES.get(tier, PRICES["cheap"])
        cost = (in_tokens / 1e6) * p["in"] + (out_tokens / 1e6) * p["out"]
        self.spent_usd += cost
        self.calls += 1
        self.log.append({"label": label, "tier": tier, "in": in_tokens,
                         "out": out_tokens, "usd": round(cost, 5)})
        if self.spent_usd > self.limit_usd:
            raise BudgetExceeded(
                f"spent ${self.spent_usd:.2f} of ${self.limit_usd:.2f} budget")
        return cost

    def can_afford(self, tier: str, in_tokens: int, out_tokens: int) -> bool:
        p = PRICES.get(tier, PRICES["cheap"])
        cost = (in_tokens / 1e6) * p["in"] + (out_tokens / 1e6) * p["out"]
        return (self.spent_usd + cost) <= self.limit_usd

    def summary(self) -> dict[str, Any]:
        return {"calls": self.calls, "spent_usd": round(self.spent_usd, 4),
                "limit_usd": self.limit_usd,
                "remaining_usd": round(self.limit_usd - self.spent_usd, 4)}


def task_id(label: str, payload: Any) -> str:
    h = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode())
    return f"{re.sub(r'[^a-z0-9_.-]+', '-', label.lower())}-{h.hexdigest()[:10]}"


class FileBackend:
    """Prompts out, structured answers in. The pipeline never blocks on a key."""

    def __init__(self, root: Path = WORK):
        self.root = Path(root)
        self.prompts = self.root / "prompts"
        self.responses = self.root / "responses"
        for d in (self.prompts, self.responses):
            d.mkdir(parents=True, exist_ok=True)

    def request(self, label: str, system: str, user: str, *,
                tier: str = "cheap", schema: dict | None = None,
                meta: dict | None = None) -> Any:
        tid = task_id(label, {"s": system, "u": user})
        rpath = self.responses / f"{tid}.json"
        if rpath.exists():
            return json.loads(rpath.read_text())
        ppath = self.prompts / f"{tid}.json"
        if not ppath.exists():
            ppath.write_text(json.dumps({
                "task_id": tid, "label": label, "tier": tier,
                "system": system, "user": user,
                "output_schema": schema or {},
                "meta": meta or {},
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, indent=2))
        raise PendingResponse(tid, ppath)

    def pending(self) -> list[Path]:
        done = {p.stem for p in self.responses.glob("*.json")}
        return sorted(p for p in self.prompts.glob("*.json") if p.stem not in done)


class AnthropicBackend:
    """Direct HTTPS call. Used automatically when ANTHROPIC_API_KEY is set."""

    MODELS = {"cheap": "claude-haiku-4-5-20251001", "strong": "claude-sonnet-5"}
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str | None = None, models: dict | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("no ANTHROPIC_API_KEY")
        self.models = {**self.MODELS, **(models or {})}

    def request(self, label: str, system: str, user: str, *,
                tier: str = "cheap", schema: dict | None = None,
                meta: dict | None = None, max_tokens: int = 4000,
                temperature: float = 1.0, retries: int = 3) -> Any:
        body = {
            "model": self.models.get(tier, self.models["cheap"]),
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Stable prefix first so the cache prefix never moves (F30).
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
        }
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.URL, data=data, headers={
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        })
        last = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    out = json.loads(r.read())
                text = "".join(b.get("text", "") for b in out.get("content", []))
                return {"text": text, "usage": out.get("usage", {}),
                        "parsed": extract_json(text)}
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 500, 502, 503, 529):
                    time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError as e:
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"anthropic request failed: {last}")


def make_backend(prefer_api: bool = True):
    if prefer_api and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicBackend()
        except RuntimeError:
            pass
    return FileBackend()


FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


def extract_json(text: str) -> Any:
    """Pull the first JSON value out of a model response, fenced or bare."""
    if not text:
        return None
    m = FENCE.search(text)
    candidates = [m.group(1)] if m else []
    candidates.append(text)
    for c in candidates:
        c = c.strip()
        try:
            return json.loads(c)
        except ValueError:
            pass
        for opener, closer in (("[", "]"), ("{", "}")):
            i, j = c.find(opener), c.rfind(closer)
            if i != -1 and j > i:
                try:
                    return json.loads(c[i:j + 1])
                except ValueError:
                    continue
    return None
