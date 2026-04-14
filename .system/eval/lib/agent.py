"""Agent loop: call API with tools, execute tool_use, feed results back, loop until stop.

Ports the pattern from claw-code's runtime/src/conversation.rs::run_turn to Python.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lib.anthropic_client import BaseClient


@dataclass
class AgentResult:
    text: str
    input_tokens: int
    output_tokens: int
    iterations: int
    tool_calls: int


def run_agent(
    client: BaseClient,
    *,
    system: str,
    user: str,
    tools: list[dict],
    tool_handler: Callable[[str, dict], str],
    model: str,
    temperature: float,
    max_tokens: int,
    max_iterations: int = 12,
) -> AgentResult:
    messages: list[dict] = [{"role": "user", "content": user}]
    total_in = 0
    total_out = 0
    tool_calls = 0
    final_text_parts: list[str] = []

    for i in range(1, max_iterations + 1):
        resp = client.messages_create(
            system=system,
            messages=messages,
            tools=tools,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        total_in += resp.input_tokens
        total_out += resp.output_tokens

        messages.append({"role": "assistant", "content": resp.content_blocks})

        tool_uses = [b for b in resp.content_blocks if b["type"] == "tool_use"]
        if not tool_uses:
            final_text_parts = [b["text"] for b in resp.content_blocks if b["type"] == "text"]
            return AgentResult(
                text="\n".join(final_text_parts).strip(),
                input_tokens=total_in,
                output_tokens=total_out,
                iterations=i,
                tool_calls=tool_calls,
            )

        tool_results = []
        for tu in tool_uses:
            tool_calls += 1
            try:
                output = tool_handler(tu["name"], tu["input"])
                is_error = False
            except Exception as exc:
                output = f"tool error: {exc}"
                is_error = True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": output,
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})

    final_text_parts = [b["text"] for b in resp.content_blocks if b["type"] == "text"]
    return AgentResult(
        text=("\n".join(final_text_parts).strip() or "[max_iterations reached without final answer]"),
        input_tokens=total_in,
        output_tokens=total_out,
        iterations=max_iterations,
        tool_calls=tool_calls,
    )
