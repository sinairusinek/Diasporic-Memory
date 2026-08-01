#!/usr/bin/env python3
"""Shared Gemini client, caching, and retry for the annotator build scripts.

Two things live here rather than in each script:

  * an on-disk cache keyed by (task, model, prompt hash) — the build is run
    repeatedly while the pipeline is developed, and re-paying for an unchanged
    translation is pure waste;
  * bounded concurrency plus retry, so a 200-page document does not take an
    hour and a single overloaded response does not lose the run.

Provider-specific detail is confined to this file: callers only see
`ask()`, `MODEL` and `Usage`.
"""
import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / "data/annotator/.cache"

# gemini-3-pro-preview is listed by models.list() but returns 404 "no longer
# available"; 3.1 Pro is the live Gemini 3 Pro.
MODEL = os.environ.get("ANNOTATOR_MODEL", "gemini-3.1-pro-preview")
_client = None
_lock = threading.Lock()


def client():
    global _client
    with _lock:
        if _client is None:
            _client = genai.Client()
        return _client


def cache_key(task: str, payload: str) -> str:
    h = hashlib.sha256(f"{task}\x00{MODEL}\x00{payload}".encode("utf-8"))
    return h.hexdigest()


def cache_get(key: str):
    f = CACHE / key[:2] / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def cache_put(key: str, value) -> None:
    f = CACHE / key[:2] / f"{key}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class Usage:
    """Token tally across a run, so the build can report what it cost."""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = self.cached = 0
        self.input = self.output = self.cache_read = self.cache_write = 0

    def add(self, u):
        """Accumulate one Gemini `usage_metadata`.

        Gemini counts cached tokens inside prompt_token_count, so they are
        subtracted out to keep `input` at the full-price share. Thinking
        tokens are billed at the output rate and are not included in
        candidates_token_count, so they are added there. Implicit caching has
        no write charge, so cache_write stays 0.
        """
        with self.lock:
            cached = getattr(u, "cached_content_token_count", 0) or 0
            prompt = getattr(u, "prompt_token_count", 0) or 0
            self.calls += 1
            self.input += max(prompt - cached, 0)
            self.output += ((getattr(u, "candidates_token_count", 0) or 0)
                            + (getattr(u, "thoughts_token_count", 0) or 0))
            self.cache_read += cached

    def hit(self):
        with self.lock:
            self.cached += 1

    def report(self) -> str:
        # Gemini 3 Pro list price, prompts under 200K tokens: $2/M in,
        # $12/M out, $0.20/M for cached input.
        cost = (self.input * 2 + self.cache_read * 0.20
                + self.output * 12) / 1_000_000
        return (f"{self.calls} API calls ({self.cached} served from cache) · "
                f"in {self.input:,} + cache {self.cache_read:,}r · "
                f"out {self.output:,} · ~${cost:.2f}")


def _retryable(e) -> bool:
    if isinstance(e, genai_errors.ServerError):        # 5xx
        return True
    if isinstance(e, genai_errors.ClientError):        # only rate limits
        return getattr(e, "code", None) == 429
    return isinstance(e, (ConnectionError, TimeoutError))


def ask(system, user, task, usage=None, max_tokens=16000, effort="medium",
        cache_system=True, force=False):
    """One completion, cached on disk by prompt content.

    `system` is a list of content blocks (the shape the Anthropic version
    needed to hang cache_control off the last one); Gemini takes a single
    system_instruction, so the blocks are joined. It stays a list because it
    is part of the cache key, and changing the shape would invalidate every
    cached result for no gain.
    """
    key = cache_key(task, json.dumps([system, user], ensure_ascii=False))
    if not force:
        hit = cache_get(key)
        if hit is not None:
            if usage:
                usage.hit()
            return hit["text"]

    instruction = "\n\n".join(b["text"] for b in system if b.get("text"))
    config = types.GenerateContentConfig(
        system_instruction=instruction,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=effort),
    )

    delay = 2.0
    for attempt in range(6):
        try:
            resp = client().models.generate_content(
                model=MODEL, contents=user, config=config)
            break
        except Exception as e:
            if attempt == 5 or not _retryable(e):
                raise
            time.sleep(delay + random.uniform(0, 1.5))
            delay = min(delay * 2, 60)
    else:  # pragma: no cover
        raise RuntimeError("unreachable")

    if usage and resp.usage_metadata:
        usage.add(resp.usage_metadata)

    # A blocked prompt or a safety stop returns HTTP 200 with no candidate
    # text; so does hitting max_output_tokens, which with thinking enabled is
    # a real risk on long pages. Each would otherwise cache as an empty or
    # truncated translation, so fail loudly instead.
    feedback = getattr(resp, "prompt_feedback", None)
    if feedback and getattr(feedback, "block_reason", None):
        raise RuntimeError(f"prompt blocked ({feedback.block_reason}): {task}")
    if not resp.candidates:
        raise RuntimeError(f"no candidate returned: {task}")
    finish = resp.candidates[0].finish_reason
    if finish is not None and finish != types.FinishReason.STOP:
        raise RuntimeError(f"stopped early ({finish.name}): {task}")

    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError(f"empty response: {task}")
    cache_put(key, {"text": text, "model": MODEL, "task": task})
    return text
