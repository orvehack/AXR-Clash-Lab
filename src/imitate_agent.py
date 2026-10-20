"""Build an imitation actor from public human replays, ready for PPO warm-start.

Example:
    python -m src.imitate_agent --matches 100 --out-dir runs/axr_imitation_smoke

This only reconstructs battles in the offline RoyaleGym engine; it does not control the official
client or play live matches. Keep the actor artifact directory intact for --warm-start.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from src.train_agent import build_env


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=100, help="Number of compatible replays to reconstruct")
    parser.add_argument("--data-dir", default=None, help="Existing folder with replays/*.parquet")
    parser.add_argument("--cache-dir", default=None, help="Optional Hugging Face cache directory")
    parser.add_argument("--out-dir", default="runs/axr_imitation", help="Output folder for shards and actor artifact")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--trunk-channels", type=int, default=64)
    parser.add_argument("--trunk-blocks", type=int, default=4)
    parser.add_argument("--plan-only", action="store_true", help="Validate and print plan without importing optional ML packages")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.matches < 1:
        errors.append("--matches debe ser mayor que cero")
    if args.epochs < 1:
        errors.append("--epochs debe ser mayor que cero")
    if args.batch_size < 1:
        errors.append("--batch-size debe ser mayor que cero")
    if args.learning_rate <= 0:
        errors.append("--learning-rate debe ser positivo")
    if args.seed < 0:
        errors.append("--seed no puede ser negativo")
    if args.n_envs < 1:
        errors.append("--n-envs debe ser mayor que cero")
    if args.trunk_channels < 1 or args.trunk_blocks < 1:
        errors.append("Los tamaños de la red deben ser positivos")
    if args.data_dir and not Path(args.data_dir).is_dir():
        errors.append(f"--data-dir no existe o no es carpeta: {args.data_dir}")
    return errors


def build_learner(args: argparse.Namespace, save_dir: Path) -> Any:
    """Create the same policy shape used by train_agent so warm-start can be compatible."""
    from royalelearn import Learner

    return Learner(
        build_env,
        opponent="random",
        device=args.device,
        n_envs=args.n_envs,
        trunk_channels=args.trunk_channels,
        trunk_blocks=args.trunk_blocks,
        seed=args.seed,
        save_dir=str(save_dir),
        log_to_wandb=False,
        viser=False,
        resume=False,
    )


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    from royaleimitate import clone, from_replays

    output = Path(args.out_dir)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    learner = build_learner(args, output / "learner_config")
    shards = from_replays(
        learner,
        output / "demonstrations",
        matches=args.matches,
        data_dir=args.data_dir,
        cache_dir=args.cache_dir,
    )
    actor_dir = output / "axr_imitation_actor"
    digest = clone(
        learner,
        shards,
        actor_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    report = {
        "status": "imitation_actor_created",
        "pipeline": "RoyaleImitate.from_replays -> RoyaleImitate.clone",
        "source": "local IL_Replay parquet" if args.data_dir else "IL_Replay dataset via Hugging Face cache",
        "requested_matches": args.matches,
        "shards_directory": str(shards),
        "actor_directory": str(actor_dir),
        "actor_sha256": digest,
        "seed": args.seed,
        "epochs_max": args.epochs,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "next_command": (
            f'python -m src.train_agent --steps 200000 --save-dir runs/axr_ppo '
            f'--warm-start "{actor_dir}"'
        ),
        "caveat": "Creation of an imitation artifact is not evidence that it beats the baseline.",
    }
    report_path = output / "imitation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    errors = validate_args(args)
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 2
    if args.plan_only:
        print(json.dumps({
            "status": "plan_only",
            "args": vars(args),
            "next_step": "Install compatible RoyaleGym, RoyaleLearn and RoyaleImitate extras before running.",
        }, indent=2, ensure_ascii=False))
        return 0
    try:
        run_pipeline(args)
        return 0
    except ImportError as exc:
        print(
            f"Dependencia opcional no disponible: {exc}. Consulta docs/ROYALEGYM_SETUP.md.",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        print(f"Error en la pipeline de imitación: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
