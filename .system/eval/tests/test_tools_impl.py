"""Tests for the universe-scoped file tools."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.tools_impl import run_read_file, run_list_files, dispatch


def test_read_file_returns_content(tmp_path: Path):
    (tmp_path / "planets").mkdir()
    (tmp_path / "planets" / "hello.md").write_text("line1\nline2\nline3")
    raw = run_read_file(tmp_path, {"path": "planets/hello.md"})
    data = json.loads(raw)
    assert data["content"] == "line1\nline2\nline3"
    assert data["total_lines"] == 3


def test_read_file_rejects_escape(tmp_path: Path):
    try:
        run_read_file(tmp_path, {"path": "../../etc/passwd"})
    except ValueError as exc:
        assert "escapes" in str(exc)
        return
    raise AssertionError("should have rejected path traversal")


def test_list_files_lists_recursively(tmp_path: Path):
    (tmp_path / "planets" / "p1").mkdir(parents=True)
    (tmp_path / "planets" / "p1" / "planet.md").write_text("x")
    (tmp_path / "planets" / "p1" / "creatures" / "c.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "planets" / "p1" / "creatures" / "c.md").write_text("y")
    raw = run_list_files(tmp_path, {"path": "planets"})
    data = json.loads(raw)
    assert "planets/p1/planet.md" in data["files"]
    assert "planets/p1/creatures/c.md" in data["files"]


def test_dispatch_unknown_tool(tmp_path: Path):
    raw = dispatch(tmp_path, "nonexistent_tool", {})
    data = json.loads(raw)
    assert "error" in data
