# .system/eval/tests/test_runner_dry_run.py
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / ".system/eval/runner.py"
CONFIG = REPO / ".system/eval/configs/default.yaml"


def test_dry_run_completes_with_no_network():
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        ["python3", str(RUNNER), "--config", str(CONFIG), "--dry-run"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert "probes planned" in result.stdout.lower()


def test_dry_run_only_probes_subset():
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        ["python3", str(RUNNER), "--config", str(CONFIG), "--dry-run",
         "--only-probes", "react-memoize-stable-reference,neg-kubernetes-decision"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert "2 probes planned" in result.stdout.lower()
