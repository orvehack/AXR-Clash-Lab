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
            if blue_reward > red_reward:
                winner = "blue"
            elif red_reward > blue_reward:
                winner = "red"
            else:
                blue_crowns = _extract_crowns(last_info, "blue")
                red_crowns = _extract_crowns(last_info, "red")
                if blue_crowns is not None and red_crowns is not None:
                    winner = "blue" if blue_crowns > red_crowns else "red" if red_crowns > blue_crowns else "draw"
                else:
                    winner = "draw"
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
