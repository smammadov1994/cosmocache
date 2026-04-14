# Cosmocache Eval Harness

Benchmarks cosmocache against a fair flat-`memory.md` baseline.

## Quickstart

```bash
cd /Users/bot/universe/.system/eval
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# dry-run: walks every probe, hits no API
python runner.py --config configs/default.yaml --dry-run

# live run: requires ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY=sk-ant-...
python runner.py --config configs/default.yaml
```

Results land in `results/<run-id>/`. The generated `report.md` has the
numbers you want.

## Layout

See the design spec at `../docs/specs/2026-04-13-phase-2-eval-harness-design.md`.

## Running tests

```bash
.system/eval/tests/run-tests.sh
```
