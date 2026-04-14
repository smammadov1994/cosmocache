from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".system/eval"))

from lib.scoring import parse_judge_response, aggregate  # noqa: E402


def test_parses_clean_json():
    r = parse_judge_response('{"score": 1.0, "reason": "exact match"}')
    assert r.score == 1.0
    assert r.reason == "exact match"


def test_parses_json_with_surrounding_prose():
    r = parse_judge_response('Here is my score:\n{"score": 0.5, "reason": "partial"}\ndone.')
    assert r.score == 0.5


def test_clamps_out_of_range():
    r = parse_judge_response('{"score": 1.7, "reason": "over"}')
    assert r.score == 1.0
    r2 = parse_judge_response('{"score": -0.2, "reason": "under"}')
    assert r2.score == 0.0


def test_aggregate_computes_mean_and_p95():
    scores = [1.0, 1.0, 0.5, 1.0, 0.0, 1.0, 0.5]
    input_tokens = [100, 200, 300, 400, 500, 600, 700]
    agg = aggregate(scores, input_tokens)
    assert abs(agg.accuracy_mean - (sum(scores) / len(scores))) < 1e-6
    assert agg.input_tokens_mean == sum(input_tokens) / len(input_tokens)
    assert agg.input_tokens_p95 >= 600
