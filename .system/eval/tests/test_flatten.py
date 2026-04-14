# .system/eval/tests/test_flatten.py
from pathlib import Path
import subprocess, hashlib, os

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / ".system/eval/scenarios/seed_universe"
SCRIPT = REPO / ".system/eval/baselines/flatten_to_memory_md.py"


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _run(env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.check_output(
        ["python3", str(SCRIPT), "--universe", str(SEED)], env=env,
    ).decode()


def test_flatten_is_deterministic():
    env = {"COSMOCACHE_FLATTEN_NOW": "2026-04-13T00:00:00Z"}
    out1 = _run(env)
    out2 = _run(env)
    assert _sha(out1) == _sha(out2)


def test_flatten_contains_all_planets():
    out = _run()
    for slug in ("planet-react", "planet-sql", "planet-devops"):
        assert slug in out, f"expected {slug} in flattened output"


def test_flatten_contains_creatures_and_distilled_wisdom():
    out = _run()
    assert "Jimbo the React-tor" in out
    assert "Sally the SQLite" in out
    assert "Grom the Deployer" in out
    assert "Distilled Wisdom" in out


def test_flatten_header_has_timestamp():
    out = _run()
    first = out.splitlines()[0]
    assert first.startswith("# Memory (flattened at ")


def test_flatten_deterministic_ordering():
    out = _run()
    idx_devops = out.find("planet-devops")
    idx_react = out.find("planet-react")
    idx_sql = out.find("planet-sql")
    assert idx_devops < idx_react < idx_sql


def test_flatten_out_file_matches_stdout(tmp_path):
    env = os.environ.copy()
    env["COSMOCACHE_FLATTEN_NOW"] = "2026-04-13T00:00:00Z"
    out_file = tmp_path / "out.md"
    subprocess.check_call(
        ["python3", str(SCRIPT), "--universe", str(SEED), "--out", str(out_file)],
        env=env,
    )
    stdout_capture = subprocess.check_output(
        ["python3", str(SCRIPT), "--universe", str(SEED)], env=env,
    ).decode()
    assert out_file.read_text() == stdout_capture


def test_flatten_cli_errors_on_missing_universe():
    result = subprocess.run(
        ["python3", str(SCRIPT), "--universe", "/tmp/does-not-exist-xxx"],
        capture_output=True,
    )
    assert result.returncode != 0
