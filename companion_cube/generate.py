"""Prompt assembly and generation.

Chunks here are Qdrant payload dicts. DryRunLLM prints the assembled prompt so the pipeline runs
with no key; AnthropicLLM (Claude) is used automatically when a key is available via the environment
or the gitignored .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

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


def build_prompt(query, chunks, mode: Mode, game: str, progress: str = "") -> tuple[str, str]:
    system = PERSONA.get(game, PERSONA["hollow_knight"]) + GROUNDING
    if chunks:
        excerpts = "\n\n".join(f"({c['doc_title']} / {c['section']}) {c['text']}" for c in chunks)
    else:
        excerpts = "(no lore is available at the seeker's current progress)"
    user = (
        f"{MODE_INSTRUCTIONS[mode]}\n\n"
        f"Where the seeker stands: {progress or 'the very beginning of the journey'}\n\n"
        f"Guide excerpts:\n{excerpts}\n\n"
        f"The seeker asks: {query}"
    )
    return system, user


class LLM(Protocol):
    def complete(self, system: str, user: str, history: list | None = None) -> str: ...


class DryRunLLM:
    def complete(self, system: str, user: str, history: list | None = None) -> str:
        hist = "\n".join(f"[{m['role']}] {m['content'][:60]}" for m in (history or []))
        return (
            "[dry-run: no LLM configured — showing the grounded prompt that would be sent]\n"
            f"--- history ---\n{hist}\n--- system ---\n{system}\n--- user ---\n{user}"
        )


class AnthropicLLM:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, system: str, user: str, history: list | None = None) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[*(history or []), {"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")


def default_llm() -> LLM:
    load_env()
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return AnthropicLLM()
        except Exception:
            pass
    return DryRunLLM()


def generate(query, chunks, mode: Mode, game: str = "hollow_knight", progress: str = "",
             history: list | None = None, llm: LLM | None = None) -> str:
    llm = llm or default_llm()
    system, user = build_prompt(query, chunks, mode, game, progress)
    return llm.complete(system, user, history)
