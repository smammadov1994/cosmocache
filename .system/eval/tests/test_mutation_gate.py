import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from mutation_tick import gate, GateResult  # noqa: E402


@dataclass
class S:
    accuracy_mean: float
    input_tokens_mean: float
    n_probes: int = 5


def test_gate_passes_when_accuracy_holds_and_tokens_drop():
    base = S(accuracy_mean=0.90, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.90, input_tokens_mean=800.0)
    r = gate(base, mut)
    assert r.passed is True
    assert "tokens" in r.reason.lower()


def test_gate_passes_when_accuracy_rises_and_tokens_drop():
    base = S(accuracy_mean=0.80, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.95, input_tokens_mean=900.0)
    assert gate(base, mut).passed is True


def test_gate_rejects_when_accuracy_drops():
    base = S(accuracy_mean=0.90, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.80, input_tokens_mean=500.0)  # tokens way down
    r = gate(base, mut)
    assert r.passed is False
    assert "accuracy" in r.reason.lower()


def test_gate_rejects_when_tokens_rise_even_with_accuracy_gain():
    base = S(accuracy_mean=0.80, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.95, input_tokens_mean=1100.0)
    r = gate(base, mut)
    assert r.passed is False
    assert "token" in r.reason.lower()


def test_gate_rejects_when_tokens_equal_no_savings():
    base = S(accuracy_mean=0.90, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.90, input_tokens_mean=1000.0)
    r = gate(base, mut)
    assert r.passed is False  # need a strict drop in tokens


def test_gate_passes_with_floating_point_slop():
    # mutant accuracy is 1e-9 lower due to float arithmetic — should still pass
    base = S(accuracy_mean=0.9, input_tokens_mean=1000.0)
    mut = S(accuracy_mean=0.9 - 1e-9, input_tokens_mean=900.0)
    assert gate(base, mut).passed is True
