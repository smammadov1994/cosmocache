"""Parse judge responses and aggregate scores."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass


@dataclass
class JudgeResponse:
    score: float
    reason: str


@dataclass
class Aggregate:
    accuracy_mean: float
    input_tokens_mean: float
    input_tokens_p95: float


_JSON_RE = re.compile(r"\{[^{}]*\"score\"[^{}]*\}", re.DOTALL)


def parse_judge_response(text: str) -> JudgeResponse:
    m = _JSON_RE.search(text)
    if m is None:
        return JudgeResponse(score=0.0, reason="malformed judge response")
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return JudgeResponse(score=0.0, reason="unparseable judge response")
    score = float(d.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    reason = str(d.get("reason", ""))[:500]
    return JudgeResponse(score=score, reason=reason)


def aggregate(scores: list[float], input_tokens: list[int]) -> Aggregate:
    n = len(scores)
    if n == 0:
        return Aggregate(accuracy_mean=0.0, input_tokens_mean=0.0, input_tokens_p95=0.0)
    accuracy_mean = sum(scores) / n
    tokens_mean = sum(input_tokens) / len(input_tokens) if input_tokens else 0.0
    s = sorted(input_tokens)
    idx = min(len(s) - 1, max(0, int(round(0.95 * (len(s) - 1)))))
    p95 = float(s[idx])
    return Aggregate(accuracy_mean=accuracy_mean, input_tokens_mean=tokens_mean, input_tokens_p95=p95)
