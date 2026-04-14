"""Tests for the agent loop."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.agent import run_agent
from lib.anthropic_client import StubClient, RawResponse


def test_agent_exits_when_no_tool_use():
    client = StubClient()
    client.raw_responses = [
        RawResponse(
            content_blocks=[{"type": "text", "text": "hello"}],
            stop_reason="end_turn",
            input_tokens=50,
            output_tokens=10,
        )
    ]
    res = run_agent(
        client, system="s", user="u", tools=[], tool_handler=lambda n, i: "",
        model="m", temperature=0, max_tokens=100,
    )
    assert res.text == "hello"
    assert res.iterations == 1
    assert res.tool_calls == 0
    assert res.input_tokens == 50


def test_agent_executes_tool_and_continues():
    client = StubClient()
    client.raw_responses = [
        RawResponse(
            content_blocks=[{"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a.md"}}],
            stop_reason="tool_use",
            input_tokens=100,
            output_tokens=20,
        ),
        RawResponse(
            content_blocks=[{"type": "text", "text": "final answer"}],
            stop_reason="end_turn",
            input_tokens=150,
            output_tokens=30,
        ),
    ]
    calls = []
    def handler(name, inp):
        calls.append((name, inp))
        return "file contents here"
    res = run_agent(
        client, system="s", user="u", tools=[{"name": "read_file"}], tool_handler=handler,
        model="m", temperature=0, max_tokens=100,
    )
    assert res.text == "final answer"
    assert res.iterations == 2
    assert res.tool_calls == 1
    assert calls == [("read_file", {"path": "a.md"})]
    assert res.input_tokens == 250
    assert res.output_tokens == 50


def test_agent_respects_max_iterations():
    client = StubClient()
    client.raw_responses = [
        RawResponse(
            content_blocks=[{"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}],
            stop_reason="tool_use",
            input_tokens=10,
            output_tokens=5,
        )
        for i in range(10)
    ]
    res = run_agent(
        client, system="s", user="u", tools=[{"name": "x"}], tool_handler=lambda n, i: "ok",
        model="m", temperature=0, max_tokens=100, max_iterations=3,
    )
    assert res.iterations == 3
    assert res.tool_calls == 3
