"""One place that knows how to talk to Claude — and how to do without it.

Every language-model feature in this project is optional. The engine plays,
the tournaments run and the tests pass with no API key present, and the
commentary simply is not there. Keeping that decision in a single module
means no page, level or notebook has to repeat it.

Three details of the current API are easy to get wrong and are handled here:

* **``temperature`` no longer exists** on Claude Opus 5 and its generation —
  sending it returns a 400. Output shape is steered with the system prompt
  and ``effort`` instead.
* **Thinking is on by default** on Opus 5, and thinking tokens are billed
  against ``max_tokens``. A cap tight enough for two sentences of prose would
  truncate the answer before it started, so the cap is generous and brevity
  is asked for in words.
* **A refusal is an HTTP 200**, not an exception. ``stop_reason`` has to be
  checked before reading the content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Claude Opus 5 — the current default. Model ids carry no date suffix.
DEFAULT_MODEL = "claude-opus-5"

# Generous on purpose: thinking tokens are billed against this, and the
# prompts ask for brevity in words rather than by starving the cap.
DEFAULT_MAX_TOKENS = 2048

# Server-side refusal fallback: on a policy decline the API re-runs the same
# request on a fallback model inside the same call. Chess commentary will
# never trip a classifier, but it costs one parameter and removes a failure
# mode, so it is on unless a caller turns it off.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """Raised when a language-model feature is asked for without a client."""


@dataclass
class LLMConfig:
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    # low | medium | high | xhigh | max. Commentary is a short, well-specified
    # writing task, so it does not need the default depth.
    effort: str = "low"
    timeout: float = 30.0
    refusal_fallback: bool = True


def api_key(explicit: str | None = None) -> str | None:
    """The key to use, if there is one."""
    return explicit or os.environ.get("ANTHROPIC_API_KEY") or None


def sdk_installed() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def available(explicit_key: str | None = None) -> bool:
    """True when both the SDK and a credential are present."""
    return sdk_installed() and api_key(explicit_key) is not None


class ClaudeClient:
    """A thin wrapper: prompt in, plain text out.

    Deliberately not a general-purpose SDK wrapper. Everything this project
    asks a model for is a short piece of prose about a chess position, so the
    interface is a prompt and a system prompt and the caller never handles a
    message object.
    """

    def __init__(self, api_key_: str | None = None, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._key = api_key(api_key_)
        self._client = None
        if self._key is not None and sdk_installed():
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._key, timeout=self.config.timeout)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Ask for a completion. Raises :class:`LLMUnavailable` if it cannot."""
        if self._client is None:
            raise LLMUnavailable(
                "No Anthropic client: set ANTHROPIC_API_KEY and install the `anthropic` package."
            )

        request = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "output_config": {"effort": self.config.effort},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            request["system"] = system

        if self.config.refusal_fallback:
            message = self._client.beta.messages.create(
                betas=[FALLBACK_BETA], fallbacks="default", **request
            )
        else:
            message = self._client.messages.create(**request)

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise LLMUnavailable(f"The model declined to answer ({category}).")

        return "".join(block.text for block in message.content if block.type == "text").strip()
