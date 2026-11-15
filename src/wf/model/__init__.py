"""The model port: how the workflow talks to a language model.

The engine depends only on `ModelPort` and the plain dataclasses below. Adapters
implement the port for one provider each. Nothing outside this package imports a
provider SDK, so swapping a provider is a config change, not a code change.

Adapters:
- `ollama`: a local model served by Ollama. No cloud terms apply.
- `anthropic-api`: the Claude API, billed per token, authenticated with an API key.

Not an adapter, on purpose: the Claude Code subscription. It stays blocked until
it has written approval (see `BLOCKED_PROVIDERS`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


class ModelError(RuntimeError):
    """A model call failed. The message never contains credentials."""


class ProviderNotAllowed(ModelError):
    """The configured provider is not enabled for this workflow."""


@dataclass(frozen=True)
class Message:
    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class ModelRequest:
    system: str
    messages: tuple[Message, ...]
    max_tokens: int = 1024


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int | None = None


class ModelPort(Protocol):
    name: str

    def complete(self, request: ModelRequest) -> ModelResponse: ...


# A transport posts JSON and returns the parsed JSON body. Injected so tests run offline.
Transport = Callable[[str, dict[str, str], dict], dict]

BLOCKED_PROVIDERS: dict[str, str] = {
    "claude-code-subscription": (
        "claude-code-subscription is not enabled. It needs written approval from "
        "Anthropic and the TCO before it can be used. See the compliance review."
    ),
}


def _registry() -> dict[str, Callable[..., ModelPort]]:
    # Imported here so the port module has no provider imports at load time.
    from wf.model.anthropic_api import AnthropicAPIModel
    from wf.model.ollama import OllamaModel

    return {"ollama": OllamaModel, "anthropic-api": AnthropicAPIModel}


def known_providers() -> list[str]:
    return sorted(_registry())


def build_model(cfg, env: dict[str, str], transport: Transport | None = None) -> ModelPort:
    """Create the adapter named in `cfg` (a `wf.config.ModelConfig`)."""
    if cfg.provider in BLOCKED_PROVIDERS:
        raise ProviderNotAllowed(BLOCKED_PROVIDERS[cfg.provider])
    registry = _registry()
    if cfg.provider not in registry:
        raise ProviderNotAllowed(
            f"unknown model provider {cfg.provider!r}; choose one of {known_providers()}"
        )
    return registry[cfg.provider](cfg, env=env, transport=transport)
