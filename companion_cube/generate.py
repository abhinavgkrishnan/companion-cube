"""Prompt assembly and generation.

Chunks here are Qdrant payload dicts. The default model is Gemini Flash (server GEMINI_API_KEY);
build_llm() also accepts a user's own provider + key (Anthropic, OpenAI, Gemini, or OpenRouter) for
BYOK. DryRunLLM prints the assembled prompt when no key is configured.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, Protocol

import httpx

from .models import Mode

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


PERSONA = {
    "hollow_knight": (
        "You are the Guide of Hallownest — an ancient, knowing voice aiding a small vessel, whom you "
        "address as \"little ghost\". Speak with quiet, lyrical gravity in the mood of Hollow Knight."
    ),
    "silksong": (
        "You are the Weaver of Pharloom — a wry, watchful voice aiding a pilgrim of the needle, whom you "
        "address as \"little weaver\". Speak with the crimson, silken texture of Silksong."
    ),
}

GROUNDING = (
    " Ground every claim ONLY in the provided guide excerpts — never invent specifics. If they do not "
    "hold what the seeker asks, it lies beyond where they have yet walked: say so in character, that it "
    "is a matter for a later time, and point them gently toward a next step that fits where they stand. "
    "Tailor what you surface to the seeker's marked progress, favouring what is reachable now. Stay in "
    "voice; be clear and useful; keep it fairly brief."
)

MODE_INSTRUCTIONS = {
    Mode.HOLD_MY_HAND: "Give complete, step-by-step guidance drawn from the excerpts, in your voice.",
    Mode.GENTLY_NUDGE: (
        "Give only a gentle, riddling hint that points the way — never the full solution, exact "
        "locations, item names, or outcomes."
    ),
}


def build_prompt(query, chunks, mode: Mode, game: str, progress: str = "", collected: str = "") -> tuple[str, str]:
    system = PERSONA.get(game, PERSONA["hollow_knight"]) + GROUNDING
    if chunks:
        excerpts = "\n\n".join(f"({c['doc_title']} / {c['section']}) {c['text']}" for c in chunks)
    else:
        excerpts = "(no lore is available at the seeker's current progress)"
    # `collected` is a separate, informational checklist (mask shards, tools, charms, ...) — never a
    # permission set. It doesn't affect which excerpts were retrieved (the gate already ran on
    # `progress`/completed beats alone), so it's flagged explicitly as awareness-only to keep the
    # model from treating it as another spoiler boundary to reason about.
    collected_line = (
        f"Items and upgrades the seeker has already collected (for awareness only — this does NOT "
        f"gate or expand what you may say, the excerpts above are already the full extent of what's "
        f"safe to draw on; use it only to avoid pointlessly re-suggesting something they already "
        f"hold): {collected}\n\n"
        if collected else ""
    )
    user = (
        f"{MODE_INSTRUCTIONS[mode]}\n\n"
        f"Where the seeker stands: {progress or 'the very beginning of the journey'}\n\n"
        f"{collected_line}"
        f"Guide excerpts:\n{excerpts}\n\n"
        f"The seeker asks: {query}"
    )
    return system, user


MAX_TOKENS = 1024
TIMEOUT = 60
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6", "openai": "gpt-4o-mini",
    "openrouter": "openai/gpt-4o-mini", "gemini": DEFAULT_GEMINI_MODEL,
}


# one keep-alive client for every provider call — a fresh TLS handshake per query costs 100-300ms
_http = httpx.Client(timeout=TIMEOUT)


def _sse_data(line: str) -> str | None:
    return line[6:] if line.startswith("data: ") else None


class LLM(Protocol):
    def complete(self, system: str, user: str, history: list | None = None) -> str: ...
    def stream(self, system: str, user: str, history: list | None = None) -> Iterator[str]: ...


class DryRunLLM:
    def complete(self, system: str, user: str, history: list | None = None) -> str:
        hist = "\n".join(f"[{m['role']}] {m['content'][:60]}" for m in (history or []))
        return (
            "[dry-run: no LLM configured — showing the grounded prompt that would be sent]\n"
            f"--- history ---\n{hist}\n--- system ---\n{system}\n--- user ---\n{user}"
        )

    def stream(self, system: str, user: str, history: list | None = None) -> Iterator[str]:
        yield self.complete(system, user, history)


class GeminiLLM:
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
        self._key, self._model = api_key, model

    def _payload(self, system: str, user: str, history: list | None) -> dict:
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in (history or [])]
        contents.append({"role": "user", "parts": [{"text": user}]})
        return {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                # thinking off: flash thinks by default and its thought tokens count against
                # maxOutputTokens, truncating answers mid-sentence (and adding latency)
                "generationConfig": {"maxOutputTokens": MAX_TOKENS,
                                     "thinkingConfig": {"thinkingBudget": 0}}}

    @staticmethod
    def _text(data: dict) -> str:
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)

    def complete(self, system: str, user: str, history: list | None = None) -> str:
        r = _http.post(f"{GEMINI_BASE}/models/{self._model}:generateContent",
                       params={"key": self._key}, json=self._payload(system, user, history))
        r.raise_for_status()
        text = self._text(r.json())
        if not text:
            raise RuntimeError(f"empty gemini response: {r.text[:200]}")
        return text

    def stream(self, system: str, user: str, history: list | None = None) -> Iterator[str]:
        with _http.stream("POST", f"{GEMINI_BASE}/models/{self._model}:streamGenerateContent",
                          params={"key": self._key, "alt": "sse"},
                          json=self._payload(system, user, history)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                data = _sse_data(line)
                if data:
                    text = self._text(json.loads(data))
                    if text:
                        yield text


class OpenAICompatLLM:
    """OpenAI-style chat completions — also serves OpenRouter (same schema, different base URL)."""

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")

    def _messages(self, system: str, user: str, history: list | None) -> list:
        return [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": user}]

    def complete(self, system: str, user: str, history: list | None = None) -> str:
        r = _http.post(f"{self._base}/chat/completions",
                       headers={"Authorization": f"Bearer {self._key}"},
                       json={"model": self._model, "messages": self._messages(system, user, history),
                             "max_tokens": MAX_TOKENS})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def stream(self, system: str, user: str, history: list | None = None) -> Iterator[str]:
        with _http.stream("POST", f"{self._base}/chat/completions",
                          headers={"Authorization": f"Bearer {self._key}"},
                          json={"model": self._model, "messages": self._messages(system, user, history),
                                "max_tokens": MAX_TOKENS, "stream": True}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                data = _sse_data(line)
                if not data or data == "[DONE]":
                    continue
                delta = (json.loads(data).get("choices") or [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6") -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    def complete(self, system: str, user: str, history: list | None = None) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[*(history or []), {"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    def stream(self, system: str, user: str, history: list | None = None) -> Iterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[*(history or []), {"role": "user", "content": user}],
        ) as s:
            yield from s.text_stream


def build_llm(provider: str | None = None, api_key: str | None = None, model: str | None = None) -> LLM:
    """A user's own provider + key (BYOK) when both are given; otherwise the server default."""
    provider = (provider or "").lower().strip()
    if provider and api_key:
        model = model or DEFAULT_MODELS.get(provider)
        if provider == "anthropic":
            return AnthropicLLM(api_key=api_key, model=model or "claude-sonnet-4-6")
        if provider == "gemini":
            return GeminiLLM(api_key, model or DEFAULT_GEMINI_MODEL)
        if provider == "openai":
            return OpenAICompatLLM(api_key, model or "gpt-4o-mini", "https://api.openai.com/v1")
        if provider == "openrouter":
            return OpenAICompatLLM(api_key, model or "openai/gpt-4o-mini", "https://openrouter.ai/api/v1")
    return default_llm()


def default_llm() -> LLM:
    load_env()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        return GeminiLLM(gemini_key)
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return AnthropicLLM()
        except Exception:
            pass
    return DryRunLLM()


def generate(query, chunks, mode: Mode, game: str = "hollow_knight", progress: str = "",
             history: list | None = None, llm: LLM | None = None, collected: str = "") -> str:
    llm = llm or default_llm()
    system, user = build_prompt(query, chunks, mode, game, progress, collected)
    return llm.complete(system, user, history)


def generate_stream(query, chunks, mode: Mode, game: str = "hollow_knight", progress: str = "",
                    history: list | None = None, llm: LLM | None = None, collected: str = "") -> Iterator[str]:
    llm = llm or default_llm()
    system, user = build_prompt(query, chunks, mode, game, progress, collected)
    return llm.stream(system, user, history)
