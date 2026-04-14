"""Thin wrapper around the Anthropic SDK, mockable in tests."""
from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class RawResponse:
    """Normalized shape of a single messages.create call, including tool_use blocks."""
    content_blocks: list[dict] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class BaseClient:
    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        raise NotImplementedError

    def messages_create(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> RawResponse:
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

    def messages_create(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> RawResponse:
        kwargs = dict(
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools
        resp = self._client.messages.create(**kwargs)
        blocks: list[dict] = []
        for b in resp.content:
            t = getattr(b, "type", None)
            if t == "text":
                blocks.append({"type": "text", "text": b.text})
            elif t == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)})
        return RawResponse(
            content_blocks=blocks,
            stop_reason=resp.stop_reason or "",
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )


class StubClient(BaseClient):
    def __init__(self, responses: dict[str, CompletionResult] | None = None, default: CompletionResult | None = None):
        self.responses = responses or {}
        self.default = default or CompletionResult(text="[stub answer]", input_tokens=100, output_tokens=50)
        self.calls: list[dict] = []
        self.raw_responses: list[RawResponse] = []

    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        self.calls.append({"system": system, "user": user, "model": model})
        return self.responses.get(user, self.default)

    def messages_create(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> RawResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools, "model": model})
        if self.raw_responses:
            return self.raw_responses.pop(0)
        return RawResponse(
            content_blocks=[{"type": "text", "text": self.default.text}],
            stop_reason="end_turn",
            input_tokens=self.default.input_tokens,
            output_tokens=self.default.output_tokens,
        )
