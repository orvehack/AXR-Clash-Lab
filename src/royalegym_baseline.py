#!/usr/bin/env python3
"""AXR offline baseline agents and reproducible RoyaleGym evaluation.

This module only talks to a local RoyaleGym environment. It never connects to an
Android emulator, ADB, or the official Clash Royale client.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class BattleResult:
    seed: int
    winner: str
    blue_reward: float
    red_reward: float
    blue_crowns: int | None
    red_crowns: int | None
    decisions: int
    duration_seconds: float


@dataclass(frozen=True)
class EvaluationSummary:
    agent: str
    opponent: str
    episodes: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    mean_blue_crowns: float
    mean_red_crowns: float
    mean_decisions: float
    mean_duration_seconds: float
    total_blue_reward: float
    total_red_reward: float
    seed_start: int
    results: tuple[BattleResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_legal_indices(mask: Any) -> list[int]:
    """Return indices marked legal by a one-dimensional action mask."""
    try:
        import numpy as np
        array = np.asarray(mask).reshape(-1)
        return [int(i) for i in np.flatnonzero(array)]
    except ImportError:
        if hasattr(mask, "tolist"):
            mask = mask.tolist()
        return [i for i, value in enumerate(mask) if bool(value)]


def legal_actions(observation: Mapping[str, Any]) -> list[int]:
    """Read the legal-action mask from a RoyaleGym observation."""
    mask = observation.get("action_mask")
    if mask is None:
        raise KeyError("La observación no contiene 'action_mask'.")
    actions = _as_legal_indices(mask)
    if not actions:
        # A malformed/terminal observation should not be silently treated as wait.
        raise ValueError("La máscara de acciones no contiene ninguna acción legal.")
    return actions


class RandomLegalAgent:
    """Uniformly samples a legal action; useful as a baseline opponent."""

    name = "random-legal"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def act(self, observation: Mapping[str, Any]) -> int:
        return self.rng.choice(legal_actions(observation))


class LanePressureAgent:
    """A transparent hand-coded baseline that prefers legal card plays near bridges.

    RoyaleGym's default TileActionParser maps action IDs 1..2304 to:
      action = 1 + slot * 576 + y * 18 + x
    Action 0 means wait. This agent is deliberately simple, not a trained model.
    """

    name = "lane-pressure"

    def __init__(self, seed: int = 0, wait_probability: float = 0.08) -> None:
        if not 0.0 <= wait_probability <= 1.0:
            raise ValueError("wait_probability debe estar entre 0 y 1.")
        self.rng = random.Random(seed)
        self.wait_probability = wait_probability

    @staticmethod
    def decode(action: int) -> tuple[int, int, int] | None:
        if action == 0:
            return None
        if action < 0 or action > 2304:
            # Ability-button and custom-parser action formats are not guessed.
            return None
        encoded = action - 1
        slot = encoded // 576
        tile = encoded % 576
        y, x = divmod(tile, 18)
        return slot, x, y

    @staticmethod
    def score(action: int) -> float:
        decoded = LanePressureAgent.decode(action)
        if decoded is None:
            return -1.0 if action == 0 else -0.25
        _slot, x, y = decoded
        # Favor legal deployments around the river/bridges and avoid edge spam.
        bridge_distance = min(abs(x - 4), abs(x - 13))
        lane_score = 1.0 / (1.0 + bridge_distance)
        front_score = 1.0 - abs(y - 14.0) / 31.0
        centrality = 1.0 - abs(x - 8.5) / 17.0
        return 1.8 * front_score + 1.1 * lane_score + 0.15 * centrality

    def act(self, observation: Mapping[str, Any]) -> int:
        actions = legal_actions(observation)
        if 0 in actions and self.rng.random() < self.wait_probability:
            return 0
        plays = [action for action in actions if action != 0]
        if not plays:
            return 0
        # Random tie-break noise prevents the policy from always selecting one tile.
        return max(plays, key=lambda action: self.score(action) + self.rng.random() * 0.18)


def make_agent(name: str, seed: int = 0) -> RandomLegalAgent | LanePressureAgent:
    normalized = name.strip().casefold()
    if normalized in {"random", "random-legal"}:
        return RandomLegalAgent(seed)
    if normalized in {"lane-pressure", "lane", "baseline"}:
        return LanePressureAgent(seed)
    raise ValueError(f"Agente desconocido: {name!r}. Usa 'lane-pressure' o 'random'.")


def _extract_crowns(info: Any, seat: str) -> int | None:
    if not isinstance(info, Mapping):
        return None
    own = info.get(seat)
    if not isinstance(own, Mapping):
        return None
    value = own.get("own_crowns")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def play_episode(
    env: Any,
    blue_agent: Any,
    red_agent: Any,
    seed: int,
    max_decisions: int = 1000,
) -> BattleResult:
    """Run one bounded offline episode and return metrics for both seats."""
    if max_decisions < 1:
        raise ValueError("max_decisions debe ser mayor que cero.")
    started = time.perf_counter()
    reset = env.reset(seed=seed)
    if not isinstance(reset, tuple) or len(reset) < 1:
        raise TypeError("env.reset() debe devolver (observations, info).")
    observations = reset[0]
    last_info: Any = reset[1] if len(reset) > 1 else {}
    blue_reward = red_reward = 0.0
    winner = "limit"
    decisions = 0

    for decisions in range(1, max_decisions + 1):
        if not isinstance(observations, Mapping):
            raise TypeError("Las observaciones deben estar indexadas por asiento.")
        actions = {
            "blue": int(blue_agent.act(observations["blue"])),
            "red": int(red_agent.act(observations["red"])),
        }
        observations, rewards, terminated, truncated, last_info = env.step(actions)
        if isinstance(rewards, Mapping):
            blue_reward += float(rewards.get("blue", 0.0))
            red_reward += float(rewards.get("red", 0.0))
        blue_done = bool(terminated.get("blue", False) or truncated.get("blue", False))
        red_done = bool(terminated.get("red", False) or truncated.get("red", False))
        if blue_done or red_done:
            # Prefer terminal crown counts over shaped rewards: a reward function may
            # award intermediate progress and is not necessarily the match result.
            blue_crowns = _extract_crowns(last_info, "blue")
            red_crowns = _extract_crowns(last_info, "red")
            if blue_crowns is not None and red_crowns is not None:
                winner = (
                    "blue" if blue_crowns > red_crowns
                    else "red" if red_crowns > blue_crowns
                    else "draw"
                )
            else:
                # Do not invent a win/loss from shaped rewards when the environment
                # does not expose a terminal result. Keep the episode unclassified.
                winner = "unknown"
            break

    return BattleResult(
        seed=seed,
        winner=winner,
        blue_reward=blue_reward,
        red_reward=red_reward,
        blue_crowns=_extract_crowns(last_info, "blue"),
        red_crowns=_extract_crowns(last_info, "red"),
        decisions=decisions,
        duration_seconds=time.perf_counter() - started,
    )


def evaluate(
    env_factory: Callable[[], Any],
    agent_name: str = "lane-pressure",
    opponent_name: str = "random",
    episodes: int = 10,
    seed_start: int = 1000,
    max_decisions: int = 1000,
) -> EvaluationSummary:
    """Evaluate a policy against a baseline on fixed, reproducible seeds."""
    if episodes < 1:
        raise ValueError("episodes debe ser mayor que cero.")
    results: list[BattleResult] = []
    env = env_factory()
    try:
        for offset in range(episodes):
            seed = seed_start + offset
            blue = make_agent(agent_name, seed=seed * 2 + 1)
            red = make_agent(opponent_name, seed=seed * 2 + 2)
            results.append(play_episode(env, blue, red, seed, max_decisions))
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    wins = sum(result.winner == "blue" for result in results)
    losses = sum(result.winner == "red" for result in results)
    draws = sum(result.winner == "draw" for result in results)
    known_blue = [r.blue_crowns for r in results if r.blue_crowns is not None]
    known_red = [r.red_crowns for r in results if r.red_crowns is not None]
    return EvaluationSummary(
        agent=agent_name,
        opponent=opponent_name,
        episodes=episodes,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=100.0 * wins / episodes,
        mean_blue_crowns=statistics.fmean(known_blue) if known_blue else 0.0,
        mean_red_crowns=statistics.fmean(known_red) if known_red else 0.0,
        mean_decisions=statistics.fmean(r.decisions for r in results),
        mean_duration_seconds=statistics.fmean(r.duration_seconds for r in results),
        total_blue_reward=sum(r.blue_reward for r in results),
        total_red_reward=sum(r.red_reward for r in results),
        seed_start=seed_start,
        results=tuple(results),
    )


def _royalegym_factory() -> Any:
    from royalegym import make_env
    return make_env()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="lane-pressure", choices=("lane-pressure", "random"))
    parser.add_argument("--opponent", default="random", choices=("lane-pressure", "random"))
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--max-decisions", type=int, default=1000)
    parser.add_argument("--output", type=Path, help="Opcional: guardar métricas completas en JSON.")
    args = parser.parse_args(argv)

    try:
        summary = evaluate(
            _royalegym_factory,
            agent_name=args.agent,
            opponent_name=args.opponent,
            episodes=args.episodes,
            seed_start=args.seed,
            max_decisions=args.max_decisions,
        )
    except ImportError as exc:
        parser.error(f"No se pudo importar RoyaleGym: {exc}. Consulta docs/ROYALEGYM_SETUP.md.")
    except Exception as exc:
        parser.error(f"Falló la evaluación: {type(exc).__name__}: {exc}")

    payload = summary.to_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nResultados guardados en: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Extended evaluation and experiment-reporting utilities
# ---------------------------------------------------------------------------

import csv
import hashlib
from datetime import datetime, timezone
from itertools import combinations


@dataclass(frozen=True)
class ConfidenceInterval:
    """Normal-approximation interval with an explicit sample-size warning."""

    estimate: float
    lower: float
    upper: float
    confidence: float
    sample_size: int
    method: str = "Wilson score interval"


def win_rate_interval(wins: int, games: int, confidence_z: float = 1.96) -> ConfidenceInterval | None:
    """Compute a Wilson interval for a binomial win rate in percentage points."""
    if games < 0 or wins < 0 or wins > games:
        raise ValueError("Se requiere 0 <= wins <= games")
    if games == 0:
        return None
    p = wins / games
    z = confidence_z
    denominator = 1 + z * z / games
    center = (p + z * z / (2 * games)) / denominator
    margin = z * ((p * (1 - p) / games + z * z / (4 * games * games)) ** 0.5) / denominator
    return ConfidenceInterval(
        estimate=100 * p,
        lower=max(0.0, 100 * (center - margin)),
        upper=min(100.0, 100 * (center + margin)),
        confidence=0.95 if abs(z - 1.96) < 0.001 else 0.0,
        sample_size=games,
    )


def results_by_seed(results: Sequence[BattleResult]) -> dict[int, BattleResult]:
    """Index results by seed and reject duplicates that could hide bad bookkeeping."""
    indexed: dict[int, BattleResult] = {}
    for result in results:
        if result.seed in indexed:
            raise ValueError(f"Semilla duplicada en resultados: {result.seed}")
        indexed[result.seed] = result
    return indexed


def compare_evaluations(
    first: EvaluationSummary,
    second: EvaluationSummary,
) -> dict[str, Any]:
    """Compare two policies with a shared-seed paired report when possible."""
    first_by_seed = results_by_seed(first.results)
    second_by_seed = results_by_seed(second.results)
    shared = sorted(set(first_by_seed) & set(second_by_seed))
    first_wins = sum(first_by_seed[seed].winner == "blue" for seed in shared)
    second_wins = sum(second_by_seed[seed].winner == "blue" for seed in shared)
    first_rewards = [first_by_seed[seed].blue_reward for seed in shared]
    second_rewards = [second_by_seed[seed].blue_reward for seed in shared]
    paired_reward_deltas = [
        second_by_seed[seed].blue_reward - first_by_seed[seed].blue_reward for seed in shared
    ]
    return {
        "first_agent": first.agent,
        "second_agent": second.agent,
        "shared_seeds": shared,
        "shared_seed_count": len(shared),
        "first_shared_wins": first_wins,
        "second_shared_wins": second_wins,
        "first_shared_win_rate": 100 * first_wins / len(shared) if shared else None,
        "second_shared_win_rate": 100 * second_wins / len(shared) if shared else None,
        "paired_mean_reward_delta": statistics.fmean(paired_reward_deltas) if paired_reward_deltas else None,
        "paired_reward_deltas": paired_reward_deltas,
        "warning": "A small number of seeds gives noisy comparisons; rerun with a larger fixed seed set.",
    }


def bootstrap_mean_interval(
    values: Sequence[float],
    repetitions: int = 2000,
    confidence: float = 0.95,
    seed: int = 7,
) -> tuple[float, float] | None:
    """Bootstrap a mean interval without adding a NumPy dependency."""
    if repetitions < 100:
        raise ValueError("repetitions debe ser al menos 100")
    if not 0 < confidence < 1:
        raise ValueError("confidence debe estar entre 0 y 1")
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(values) for _ in range(len(values)))
        for _ in range(repetitions)
    )
    lower = int(((1 - confidence) / 2) * repetitions)
    upper = min(repetitions - 1, int((1 - (1 - confidence) / 2) * repetitions) - 1)
    return means[lower], means[upper]


def summarize_result_quality(results: Sequence[BattleResult]) -> dict[str, Any]:
    """Flag incomplete episodes and suspiciously uniform or missing metrics."""
    warnings: list[str] = []
    if not results:
        return {"warnings": ["No hay resultados para evaluar."], "episodes": 0}
    limits = sum(result.winner == "limit" for result in results)
    unknown = sum(result.winner == "unknown" for result in results)
    missing_crowns = sum(result.blue_crowns is None or result.red_crowns is None for result in results)
    if limits:
        warnings.append(f"{limits} episodios alcanzaron max_decisions sin ganador.")
    if unknown:
        warnings.append(
            f"{unknown} episodios terminaron sin resultado verificable por coronas; "
            "no se clasificaron usando recompensas moldeadas."
        )
    if missing_crowns:
        warnings.append(f"{missing_crowns} episodios no reportaron coronas para ambos asientos.")
    if len({result.seed for result in results}) != len(results):
        warnings.append("Hay semillas repetidas; revisa la reproducibilidad del registro.")
    if all(result.decisions == 1 for result in results):
        warnings.append("Todos los episodios terminaron en una decisión; revisa el contrato del entorno.")
    if len(results) < 30:
        warnings.append("Muestra pequeña: no interpretes una tasa alta como evidencia suficiente.")
    return {
        "episodes": len(results),
        "unique_seeds": len({result.seed for result in results}),
        "limit_episodes": limits,
        "unknown_outcome_episodes": unknown,
        "missing_crown_records": missing_crowns,
        "warnings": warnings,
    }


def evaluation_report(summary: EvaluationSummary) -> dict[str, Any]:
    """Build a report bundle with uncertainty and data-quality checks."""
    payload = summary.to_dict()
    interval = win_rate_interval(summary.wins, summary.episodes)
    payload["win_rate_interval"] = asdict(interval) if interval else None
    payload["quality"] = summarize_result_quality(summary.results)
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["interpretation"] = [
        "This is an offline simulator result, not live-game performance.",
        "A baseline's win rate depends on the environment, action parser, reward, and opponent.",
        "Compare agents on the same fixed seeds and report the sample size.",
    ]
    return payload


def export_results_csv(results: Iterable[BattleResult], path: Path) -> int:
    """Export per-episode metrics to CSV for spreadsheet review."""
    materialized = list(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "seed", "winner", "blue_reward", "red_reward", "blue_crowns",
                "red_crowns", "decisions", "duration_seconds",
            ),
        )
        writer.writeheader()
        for result in materialized:
            writer.writerow(asdict(result))
    return len(materialized)


def save_evaluation_bundle(summary: EvaluationSummary, output_dir: Path) -> dict[str, str]:
    """Persist machine-readable summary, per-episode CSV, and a readable report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evaluation.json"
    csv_path = output_dir / "episodes.csv"
    markdown_path = output_dir / "EVALUATION.md"
    payload = evaluation_report(summary)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    export_results_csv(summary.results, csv_path)
    interval = payload.get("win_rate_interval")
    interval_text = (
        f"{interval['lower']:.1f}%–{interval['upper']:.1f}%" if interval else "N/D"
    )
    lines = [
        "# AXR offline evaluation",
        "",
        f"- Agent: {summary.agent}",
        f"- Opponent: {summary.opponent}",
        f"- Episodes: {summary.episodes}",
        f"- Wins/losses/draws: {summary.wins}/{summary.losses}/{summary.draws}",
        f"- Win rate: {summary.win_rate:.1f}%",
        f"- Wilson interval (95%): {interval_text}",
        f"- Mean blue crowns: {summary.mean_blue_crowns:.3f}",
        f"- Mean red crowns: {summary.mean_red_crowns:.3f}",
        f"- Mean decisions: {summary.mean_decisions:.1f}",
        f"- Mean episode duration: {summary.mean_duration_seconds:.3f}s",
        "",
        "## Quality checks",
        "",
    ]
    quality = payload["quality"]
    lines.extend(f"- {warning}" for warning in quality["warnings"] or ["No automatic warnings."])
    lines.extend([
        "",
        "## Interpretation limits",
        "",
        "- Results only describe the simulator and the tested seeds.",
        "- A high score against a random agent is not proof of competitive strength.",
        "- Compare against multiple baselines and keep held-out seeds.",
    ])
    markdown_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}


def read_evaluation_json(path: Path) -> dict[str, Any]:
    """Read an evaluation report and validate its minimum structure."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("El informe JSON debe ser un objeto.")
    required = {"agent", "opponent", "episodes", "wins", "losses", "draws", "win_rate"}
    missing = required - payload.keys()
    if missing:
        raise ValueError("Faltan campos en el informe: " + ", ".join(sorted(missing)))
    if int(payload["episodes"]) < 0:
        raise ValueError("episodes no puede ser negativo.")
    return payload


def compare_report_files(paths: Sequence[Path]) -> dict[str, Any]:
    """Compare saved evaluation JSONs for experiment tracking."""
    reports = [read_evaluation_json(path) for path in paths]
    ranked = sorted(
        reports,
        key=lambda report: (
            float(report.get("win_rate", 0)),
            float(report.get("mean_blue_crowns", 0)),
            -float(report.get("mean_duration_seconds", 0)),
        ),
        reverse=True,
    )
    return {
        "reports": [
            {
                "agent": report["agent"],
                "opponent": report["opponent"],
                "episodes": report["episodes"],
                "win_rate": report["win_rate"],
                "mean_blue_crowns": report.get("mean_blue_crowns"),
                "mean_duration_seconds": report.get("mean_duration_seconds"),
            }
            for report in ranked
        ],
        "ranking_note": "Ranking descriptivo; compare seed sets and confidence intervals before conclusions.",
    }


def result_fingerprint(summary: EvaluationSummary) -> str:
    """Hash normalized per-episode results to detect changes in saved experiments."""
    normalized = [
        {
            "seed": item.seed,
            "winner": item.winner,
            "blue_reward": round(item.blue_reward, 8),
            "red_reward": round(item.red_reward, 8),
            "blue_crowns": item.blue_crowns,
            "red_crowns": item.red_crowns,
            "decisions": item.decisions,
        }
        for item in sorted(summary.results, key=lambda item: item.seed)
    ]
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def pairwise_agent_pairs(names: Sequence[str]) -> list[tuple[str, str]]:
    """Generate unique non-self matchup pairs for a future round-robin evaluator."""
    unique = list(dict.fromkeys(name.strip() for name in names if name.strip()))
    return list(combinations(unique, 2))


def validate_evaluation_arguments(episodes: int, seed: int, max_decisions: int) -> list[str]:
    """Validate evaluation settings and return warnings before compute begins."""
    if episodes < 1:
        raise ValueError("episodes debe ser mayor que cero")
    if seed < 0:
        raise ValueError("seed debe ser no negativo")
    if max_decisions < 1:
        raise ValueError("max_decisions debe ser mayor que cero")
    warnings: list[str] = []
    if episodes < 30:
        warnings.append("Menos de 30 episodios: la incertidumbre estadística será alta.")
    if episodes > 5000:
        warnings.append("Evaluación extensa: considera guardar resultados por lotes.")
    if max_decisions < 100:
        warnings.append("Límite de decisiones bajo; muchas partidas podrían quedar truncadas.")
    return warnings


def write_round_robin_manifest(names: Sequence[str], output: Path, episodes: int, seed: int) -> Path:
    """Plan a reproducible set of pairings without automatically running them."""
    pairs = pairwise_agent_pairs(names)
    manifest = {
        "status": "planned",
        "agents": list(dict.fromkeys(name.strip() for name in names if name.strip())),
        "pairings": [{"blue": first, "red": second} for first, second in pairs],
        "episodes_per_pair": episodes,
        "seed_start": seed,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warning": "This is a matchup plan, not evidence that any battle was executed.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    return output
