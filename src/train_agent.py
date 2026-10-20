"""AXR training entry point backed by RoyaleLearn.

Run from the repository root after installing RoyaleGym/RoyaleLearn:
    python -m src.train_agent --steps 200000 --save-dir runs/axr_first
The environment factory must stay at module top level so RoyaleLearn workers can import it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class TrainingPlan:
    total_steps: int
    save_dir: str
    opponent: str
    decision_ms: int
    seed: int
    device: str
    n_envs: int
    trunk_channels: int
    trunk_blocks: int
    steps_per_update: int
    ppo_batch_size: int
    ppo_minibatch_size: int
    ppo_epochs: int
    policy_lr: float
    critic_lr: float
    checkpoint_every: int


def build_env() -> Any:
    """Create AXR's first reproducible, symmetric offline training environment."""
    from royalegym import (
        ClashParallelEnv,
        CombinedReward,
        CrownReward,
        DefaultStateMutator,
        GameOverCondition,
        RustEngine,
        SpatialObsBuilder,
        TileActionParser,
        TowerHPReward,
        WinLossReward,
    )

    deck = [
        "Knight", "Archers", "Giant", "Minions",
        "Fireball", "Zap", "Cannon", "Musketeer",
    ]
    return ClashParallelEnv(
        RustEngine(),
        state_mutator=DefaultStateMutator(decks=[deck, deck]),
        obs_builder=SpatialObsBuilder(),
        action_parser=TileActionParser(),
        reward_fn=CombinedReward([
            (WinLossReward(), 1.0),
            (CrownReward(), 0.2),
            (TowerHPReward(), 0.1),
        ]),
        termination_cond=GameOverCondition(),
        truncation_cond=None,
        decision_ms=500,
    )


def make_plan(args: argparse.Namespace) -> TrainingPlan:
    if args.steps < 1:
        raise ValueError("--steps debe ser mayor que cero")
    if args.n_envs < 1:
        raise ValueError("--n-envs debe ser mayor que cero")
    if args.steps_per_update < 1 or args.ppo_minibatch_size < 1:
        raise ValueError("Los tamaños de lote deben ser positivos")
    if args.ppo_batch_size < args.ppo_minibatch_size:
        raise ValueError("--ppo-batch-size debe ser >= --ppo-minibatch-size")
    if args.opponent not in {"random", "noop", "self"}:
        raise ValueError("Oponente no reconocido: usa random, noop o self")
    if args.device not in {"auto", "cpu", "cuda"}:
        raise ValueError("--device debe ser auto, cpu o cuda")
    return TrainingPlan(
        total_steps=args.steps,
        save_dir=args.save_dir,
        opponent=args.opponent,
        decision_ms=500,
        seed=args.seed,
        device=args.device,
        n_envs=args.n_envs,
        trunk_channels=args.trunk_channels,
        trunk_blocks=args.trunk_blocks,
        steps_per_update=args.steps_per_update,
        ppo_batch_size=args.ppo_batch_size,
        ppo_minibatch_size=args.ppo_minibatch_size,
        ppo_epochs=args.ppo_epochs,
        policy_lr=args.policy_lr,
        critic_lr=args.critic_lr,
        checkpoint_every=args.checkpoint_every,
    )


def write_run_manifest(plan: TrainingPlan, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project": "AXR Clash Lab",
        "purpose": "offline simulator training",
        "status": "planned",
        "created_unix": time.time(),
        "training_plan": asdict(plan),
        "important": [
            "This manifest records configuration, not proof that training completed.",
            "No official game client, emulator, ADB, or live match is controlled.",
        ],
    }
    target = directory / "axr_run_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=200_000, help="Training steps (not number of matches)")
    parser.add_argument("--save-dir", default="runs/axr_first")
    parser.add_argument("--opponent", choices=("random", "noop", "self"), default="random")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--trunk-channels", type=int, default=64)
    parser.add_argument("--trunk-blocks", type=int, default=4)
    parser.add_argument("--steps-per-update", type=int, default=4096)
    parser.add_argument("--ppo-batch-size", type=int, default=4096)
    parser.add_argument("--ppo-minibatch-size", type=int, default=512)
    parser.add_argument("--ppo-epochs", type=int, default=2)
    parser.add_argument("--policy-lr", type=float, default=2e-4)
    parser.add_argument("--critic-lr", type=float, default=2e-4)
    parser.add_argument("--checkpoint-every", type=int, default=50_000)
    parser.add_argument("--plan-only", action="store_true", help="Write config without importing or starting training")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = make_plan(args)
        target_dir = Path(plan.save_dir)
        manifest = write_run_manifest(plan, target_dir)
        print(f"Plan guardado: {manifest}")
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
        if args.plan_only:
            print("Modo plan-only: no se importó RoyaleLearn ni comenzó el entrenamiento.")
            return 0

        from royalelearn import Learner
        learner = Learner(
            build_env,
            opponent=plan.opponent,
            device=plan.device,
            n_envs=plan.n_envs,
            trunk_channels=plan.trunk_channels,
            trunk_blocks=plan.trunk_blocks,
            steps_per_update=plan.steps_per_update,
            ppo_batch_size=plan.ppo_batch_size,
            ppo_minibatch_size=plan.ppo_minibatch_size,
            ppo_epochs=plan.ppo_epochs,
            policy_lr=plan.policy_lr,
            critic_lr=plan.critic_lr,
            checkpoint_every=plan.checkpoint_every,
            save_dir=plan.save_dir,
            seed=plan.seed,
            viser=False,
            log_to_wandb=False,
        )
        started = time.perf_counter()
        learner.learn(total_steps=plan.total_steps)
        learner.save(str(target_dir / "axr_bot"))
        elapsed = time.perf_counter() - started
        status_path = target_dir / "axr_training_status.json"
        status_path.write_text(json.dumps({
            "status": "completed",
            "total_steps_requested": plan.total_steps,
            "elapsed_seconds": elapsed,
            "saved_bot_prefix": str(target_dir / "axr_bot"),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Entrenamiento finalizado. Estado: {status_path}")
        return 0
    except ImportError as exc:
        print(
            f"Dependencia no disponible: {exc}. Instala las dependencias documentadas "
            "en docs/ROYALEGYM_SETUP.md y vuelve a intentarlo.",
            file=sys.stderr,
        )
        return 2
    except (ValueError, OSError) as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
