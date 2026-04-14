"""Phase 3 entry point: score a single planet against a probe subset."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

from lib.anthropic_client import BaseClient
from lib.scoring import parse_judge_response, aggregate

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent


@dataclass
class PlanetScore:
    planet_slug: str
    accuracy_mean: float
    input_tokens_mean: float
    input_tokens_p95: float
    n_probes: int


def score_planet(
    planet_slug: str,
    universe_dir: Path,
    probe_subset: list[str],
    client: BaseClient,
    judge_model: str,
    sut_model: str,
    sut_temperature: float = 0.0,
    sut_max_tokens: int = 1024,
    judge_temperature: float = 0.0,
    judge_max_tokens: int = 256,
) -> PlanetScore:
    probes_all = yaml.safe_load((EVAL_ROOT / "scenarios/probes.yaml").read_text())["probes"]
    selected = [p for p in probes_all if p["id"] in set(probe_subset)]

    gloss = (universe_dir / "enigma/glossary.md").read_text()
    system = (
        f"You are Claude. The cosmocache SessionStart hook has injected:\n\n{gloss}\n\n"
        "Answer from the planet's files; if nothing matches, say so."
    )

    judge_tmpl = (EVAL_ROOT / "prompts/judge.txt").read_text()

    scores, tokens = [], []
    for probe in selected:
        user = probe["question"]
        ans = client.complete(system=system, user=user, model=sut_model,
                              temperature=sut_temperature, max_tokens=sut_max_tokens)
        j = client.complete(system="", user=judge_tmpl.format(
            question=probe["question"], expected_fact=probe["expected_fact"], answer=ans.text),
            model=judge_model, temperature=judge_temperature, max_tokens=judge_max_tokens)
        scores.append(parse_judge_response(j.text).score)
        tokens.append(ans.input_tokens)

    agg = aggregate(scores, tokens)
    return PlanetScore(
        planet_slug=planet_slug,
        accuracy_mean=agg.accuracy_mean,
        input_tokens_mean=agg.input_tokens_mean,
        input_tokens_p95=agg.input_tokens_p95,
        n_probes=len(selected),
    )
