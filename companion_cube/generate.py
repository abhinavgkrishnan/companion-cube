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


SYSTEM_GROUNDING = (
    "You are a Hollow Knight guide. Answer ONLY using the provided guide excerpts. "
    "If the excerpts do not contain the answer, say you don't know — never invent details. "
    "Cite excerpts inline by their [id]."
)

MODE_INSTRUCTIONS = {
    Mode.HOLD_MY_HAND: (
        "Give complete, step-by-step guidance drawn from the excerpts. Be specific and thorough."
    ),
    Mode.GENTLY_NUDGE: (
        "Give only a gentle hint that points the player in the right direction. Do NOT reveal the "
        "full solution, exact locations, item names, or outcomes — nudge, don't spoil."
    ),
}


def build_prompt(query, chunks, mode: Mode) -> tuple[str, str]:
    if chunks:
        excerpts = "\n\n".join(
            f"[{c['chunk_id']}] ({c['doc_title']} / {c['section']}) {c['text']}" for c in chunks
        )
    else:
        excerpts = "(no guide content available at the player's current progress)"
    user = (
        f"{MODE_INSTRUCTIONS[mode]}\n\n"
        f"Guide excerpts:\n{excerpts}\n\n"
        f"Player question: {query}"
    )
    return SYSTEM_GROUNDING, user


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class DryRunLLM:
    def complete(self, system: str, user: str) -> str:
        return (
            "[dry-run: no LLM configured — showing the grounded prompt that would be sent]\n"
            f"--- system ---\n{system}\n--- user ---\n{user}"
        )


class AnthropicLLM:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
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


def generate(query, chunks, mode: Mode, llm: LLM | None = None) -> str:
    llm = llm or default_llm()
    system, user = build_prompt(query, chunks, mode)
    return llm.complete(system, user)
