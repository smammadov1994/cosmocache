"""Thin wrapper around the Anthropic SDK, mockable in tests."""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int


class BaseClient:
    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        raise NotImplementedError


class AnthropicClient(BaseClient):
    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        resp = self._client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return CompletionResult(
            text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )


class StubClient(BaseClient):
    def __init__(self, responses: dict[str, CompletionResult] | None = None, default: CompletionResult | None = None):
        self.responses = responses or {}
        self.default = default or CompletionResult(text="[stub answer]", input_tokens=100, output_tokens=50)
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        self.calls.append({"system": system, "user": user, "model": model})
        return self.responses.get(user, self.default)
