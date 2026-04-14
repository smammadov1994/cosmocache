"""read_file tool scoped to a universe directory. Mirrors claw-code's tools/src/lib.rs pattern."""
from __future__ import annotations
import json
from pathlib import Path

READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read a text file from the cosmocache universe. Use this to load glossary, "
        "planet.md, creature files, or generation summaries. Returns JSON with the "
        "file content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path inside the universe directory (e.g. 'planets/planet-react/planet.md').",
            },
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}

LIST_FILES_TOOL = {
    "name": "list_files",
    "description": "List files under a directory inside the universe (recursive, one path per line).",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path inside the universe directory."}
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}


def _safe_resolve(universe_dir: Path, rel: str) -> Path:
    candidate = (universe_dir / rel).resolve()
    root = universe_dir.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError(f"path escapes universe root: {rel}")
    return candidate


def run_read_file(universe_dir: Path, input: dict) -> str:
    rel = input["path"]
    offset = input.get("offset", 0)
    limit = input.get("limit")
    path = _safe_resolve(universe_dir, rel)
    if not path.is_file():
        return json.dumps({"error": f"not a file: {rel}"})
    text = path.read_text()
    lines = text.splitlines()
    start = min(offset, len(lines))
    end = min(start + limit, len(lines)) if limit else len(lines)
    selected = "\n".join(lines[start:end])
    return json.dumps(
        {
            "file_path": str(path),
            "content": selected,
            "num_lines": end - start,
            "start_line": start,
            "total_lines": len(lines),
        }
    )


def run_list_files(universe_dir: Path, input: dict) -> str:
    rel = input["path"]
    path = _safe_resolve(universe_dir, rel)
    if not path.is_dir():
        return json.dumps({"error": f"not a directory: {rel}"})
    entries = []
    for p in sorted(path.rglob("*")):
        if p.is_file():
            entries.append(str(p.relative_to(universe_dir)))
    return json.dumps({"files": entries})


def dispatch(universe_dir: Path, name: str, input: dict) -> str:
    if name == "read_file":
        return run_read_file(universe_dir, input)
    if name == "list_files":
        return run_list_files(universe_dir, input)
    return json.dumps({"error": f"unsupported tool: {name}"})


TOOL_DEFS = [READ_FILE_TOOL, LIST_FILES_TOOL]
