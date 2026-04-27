import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / ".system/eval"))

from propose_distillation import propose_distillation  # noqa: E402
from lib.anthropic_client import StubClient, CompletionResult  # noqa: E402


CREATURE_INPUT = """\
---
name: Sally the SQLite
abilities: queries, indexes, vacuum
---

## Journal

Today I learned about CTEs. CTEs are great. Then I learned them again.
Indexes need to be on the columns you actually filter on. Did you know
SQLite stores everything in one file? VACUUM compacts that file. I
learned about EXPLAIN QUERY PLAN. EXPLAIN QUERY PLAN shows you scans.
"""


def test_propose_returns_distilled_markdown_string():
    distilled_response = """---
name: Sally the SQLite
abilities: queries, indexes, vacuum
---

## Distilled Wisdom

- Index columns you filter on
- VACUUM compacts the file
- EXPLAIN QUERY PLAN shows scans
"""
    stub = StubClient(default=CompletionResult(
        text=distilled_response, input_tokens=200, output_tokens=80,
    ))
    result = propose_distillation(
        creature_text=CREATURE_INPUT,
        client=stub,
        model="claude-haiku-4-5-20251001",
    )
    assert "Distilled Wisdom" in result
    assert "Sally the SQLite" in result
    assert len(result) < len(CREATURE_INPUT)


def test_propose_strips_markdown_code_fences_if_present():
    fenced = "```markdown\n---\nname: x\n---\n## Distilled Wisdom\nfact\n```"
    stub = StubClient(default=CompletionResult(
        text=fenced, input_tokens=10, output_tokens=10,
    ))
    result = propose_distillation(
        creature_text=CREATURE_INPUT, client=stub,
        model="claude-haiku-4-5-20251001",
    )
    assert "```" not in result
    assert result.lstrip().startswith("---")


def test_propose_raises_if_response_loses_frontmatter():
    stub = StubClient(default=CompletionResult(
        text="just plain text with no frontmatter",
        input_tokens=10, output_tokens=10,
    ))
    import pytest
    with pytest.raises(ValueError, match="frontmatter"):
        propose_distillation(
            creature_text=CREATURE_INPUT, client=stub,
            model="claude-haiku-4-5-20251001",
        )
