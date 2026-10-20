"""AXR training entry point backed by RoyaleLearn.

Run from the repository root after installing RoyaleGym/RoyaleLearn:
    python -m src.train_agent --steps 200000 --save-dir runs/axr_first
The environment factory must stay at module top level so RoyaleLearn workers can import it.
"""
from __future__ import annotations

import argparse
import json
import os
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
    warm_start: str | None = None


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
        warm_start=args.warm_start,
    )


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
    parser.add_argument("--warm-start", default=None, help="Carpeta de actor RoyaleImitate validado para inicializar PPO")
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

        extensions: dict[str, Any] = {}
        if plan.warm_start:
            from royaleimitate.artifacts import artifact_digest

            warm_start_path = Path(plan.warm_start)
            if not warm_start_path.is_dir():
                raise ValueError(f"--warm-start no es una carpeta válida: {warm_start_path}")
            extensions = {
                "warm_start": {
                    "init": {
                        "path": str(warm_start_path),
                        "sha256": artifact_digest(warm_start_path),
                    }
                }
            }

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
            extensions=extensions,
        )
        started = time.perf_counter()
        learner.learn(total_steps=plan.total_steps)
        learner.save(str(target_dir / "axr_bot"))
        actor_artifact: dict[str, Any]
        try:
            from royaleimitate import save_actor

            artifact_path = target_dir / "axr_actor"
            digest = save_actor(learner, artifact_path, seed=plan.seed)
            actor_artifact = {"path": str(artifact_path), "sha256": digest}
        except ImportError:
            actor_artifact = {
                "status": "not_exported",
                "reason": "RoyaleImitate no está instalado; el checkpoint PPO sí se guardó.",
            }
        elapsed = time.perf_counter() - started
        status_path = target_dir / "axr_training_status.json"
        status_path.write_text(json.dumps({
            "status": "completed",
            "total_steps_requested": plan.total_steps,
            "elapsed_seconds": elapsed,
            "saved_bot_prefix": str(target_dir / "axr_bot"),
            "warm_start": plan.warm_start,
            "actor_artifact": actor_artifact,
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


# Experiment bookkeeping and configuration helpers

import hashlib
import platform
import random
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Mapping


SUPPORTED_OPPONENTS = {"random", "noop", "self"}
SUPPORTED_DEVICES = {"auto", "cpu", "cuda"}


@dataclass(frozen=True)
class ResourceEstimate:
    """Transparent rough estimate; it is not a performance guarantee."""

    total_steps: int
    env_count: int
    rollout_steps_per_env: int
    approximate_samples_per_update: int
    estimated_updates: int
    checkpoint_count: int


def estimate_training_resources(plan: TrainingPlan) -> ResourceEstimate:
    """Estimate update/checkpoint counts from the current configuration."""
    if plan.steps_per_update <= 0:
        raise ValueError("steps_per_update debe ser positivo")
    if plan.n_envs <= 0:
        raise ValueError("n_envs debe ser positivo")
    samples = plan.steps_per_update * plan.n_envs
    updates = (plan.total_steps + plan.steps_per_update - 1) // plan.steps_per_update
    checkpoints = (
        (plan.total_steps + plan.checkpoint_every - 1) // plan.checkpoint_every
        if plan.checkpoint_every > 0 else 0
    )
    return ResourceEstimate(
        total_steps=plan.total_steps,
        env_count=plan.n_envs,
        rollout_steps_per_env=plan.steps_per_update,
        approximate_samples_per_update=samples,
        estimated_updates=updates,
        checkpoint_count=checkpoints,
    )


def validate_training_plan(plan: TrainingPlan) -> list[str]:
    """Return warnings that deserve review before launching a long experiment."""
    warnings: list[str] = []
    if plan.total_steps < 10_000:
        warnings.append("La corrida es muy corta para evaluar aprendizaje; úsala como prueba técnica.")
    if plan.total_steps > 10_000_000:
        warnings.append("Corrida grande: estima tiempo y espacio en disco antes de empezar.")
    if plan.n_envs > 16:
        warnings.append("Muchos entornos paralelos pueden consumir bastante memoria.")
    if plan.ppo_batch_size % plan.ppo_minibatch_size:
        warnings.append("ppo_batch_size no es múltiplo de ppo_minibatch_size.")
    if plan.checkpoint_every < 1:
        warnings.append("No se guardarán checkpoints periódicos.")
    if plan.policy_lr > 0.001 or plan.critic_lr > 0.001:
        warnings.append("Tasa de aprendizaje alta; considera comparar con una tasa menor.")
    if plan.trunk_channels < 16:
        warnings.append("Red pequeña: puede ser insuficiente para observaciones complejas.")
    if plan.trunk_channels > 256:
        warnings.append("Red grande: puede incrementar mucho el consumo de memoria.")
    if plan.device == "cuda":
        warnings.append("Se solicitó CUDA; verifica que PyTorch y el controlador lo soporten.")
    warnings.append("La configuración no demuestra que el modelo vaya a aprender una estrategia ganadora.")
    return warnings


def experiment_fingerprint(plan: TrainingPlan) -> str:
    """Stable SHA-256 identifier for comparing configuration-equivalent runs."""
    encoded = json.dumps(asdict(plan), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def environment_diagnostics() -> dict[str, Any]:
    """Collect non-sensitive Python/platform diagnostics without network access."""
    return {
        "python_version": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() if "os" in globals() else None,
        "cwd": str(Path.cwd()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _git_revision() -> str | None:
    """Return the local revision if Git is installed and this folder is a repository."""
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True, capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def write_run_manifest(plan: TrainingPlan, directory: Path) -> Path:
    """Replace the base manifest writer with richer reproducibility metadata."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project": "AXR Clash Lab",
        "purpose": "offline simulator training",
        "status": "planned",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_plan": asdict(plan),
        "experiment_fingerprint": experiment_fingerprint(plan),
        "resource_estimate": asdict(estimate_training_resources(plan)),
        "environment": environment_diagnostics(),
        "git_revision": _git_revision(),
        "warnings": validate_training_plan(plan),
        "important": [
            "This manifest records configuration, not proof that training completed.",
            "No official game client, emulator, ADB, or live match is controlled.",
            "Evaluation on held-out seeds is required before comparing policies.",
        ],
    }
    target = directory / "axr_run_manifest.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def append_jsonl_event(path: Path, event: Mapping[str, Any]) -> None:
    """Append one structured local event for later progress visualization."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **dict(event),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl_events(path: Path) -> list[dict[str, Any]]:
    """Read progress events while reporting the exact malformed line."""
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido en línea {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"La línea {line_number} no contiene un objeto JSON.")
            events.append(value)
    return events


def summarize_progress_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize step/loss/reward events emitted by future training callbacks."""
    step_values: list[int] = []
    rewards: list[float] = []
    losses: list[float] = []
    for event in events:
        if "step" in event:
            try:
                step_values.append(int(event["step"]))
            except (TypeError, ValueError):
                pass
        for key, bucket in (("reward", rewards), ("loss", losses)):
            if key in event:
                try:
                    value = float(event[key])
                    if value == value and abs(value) != float("inf"):
                        bucket.append(value)
                except (TypeError, ValueError):
                    pass
    return {
        "event_count": len(events),
        "first_step": min(step_values) if step_values else None,
        "last_step": max(step_values) if step_values else None,
        "reward_samples": len(rewards),
        "mean_reward": sum(rewards) / len(rewards) if rewards else None,
        "last_reward": rewards[-1] if rewards else None,
        "loss_samples": len(losses),
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "last_loss": losses[-1] if losses else None,
    }


def write_experiment_card(plan: TrainingPlan, directory: Path) -> Path:
    """Write a Markdown experiment card for reviewing a run in GitHub."""
    directory.mkdir(parents=True, exist_ok=True)
    resources = estimate_training_resources(plan)
    warnings = validate_training_plan(plan)
    lines = [
        "# AXR experiment card",
        "",
        f"- Created: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Fingerprint: `{experiment_fingerprint(plan)}`",
        f"- Requested steps: {plan.total_steps:,}",
        f"- Parallel environments: {plan.n_envs}",
        f"- Opponent: {plan.opponent}",
        f"- Device: {plan.device}",
        f"- Seed: {plan.seed}",
        "",
        "## Approximate workload",
        "",
        f"- Samples per update: {resources.approximate_samples_per_update:,}",
        f"- Estimated updates: {resources.estimated_updates:,}",
        f"- Checkpoints expected: {resources.checkpoint_count:,}",
        "",
        "## Review warnings",
        "",
    ]
    lines.extend(f"- {warning}" for warning in warnings)
    lines.extend([
        "",
        "## Evaluation checklist",
        "",
        "- [ ] Record package versions and code revision.",
        "- [ ] Run the same held-out seeds against the random baseline.",
        "- [ ] Report win rate with sample size, not just a single result.",
        "- [ ] Compare reward and crown metrics as well as win rate.",
        "- [ ] Confirm the final model checkpoint exists and can be loaded.",
        "- [ ] Preserve the manifest and raw evaluation JSON.",
    ])
    target = directory / "EXPERIMENT_CARD.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def seed_everything(seed: int) -> dict[str, Any]:
    """Seed Python and optional NumPy/PyTorch without requiring them for plan mode."""
    if seed < 0:
        raise ValueError("seed no puede ser negativo")
    random.seed(seed)
    seeded = {"python_random": True, "seed": seed, "numpy": False, "torch": False}
    try:
        import numpy as np
        np.random.seed(seed)
        seeded["numpy"] = True
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        seeded["torch"] = True
    except ImportError:
        pass
    return seeded


def verify_output_directory(path: Path, minimum_free_mb: int = 512) -> dict[str, Any]:
    """Check writability and available disk space before a long local run."""
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".axr_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise OSError(f"No se puede escribir en {path}: {exc}") from exc
    usage = shutil.disk_usage(path)
    free_mb = usage.free / (1024 * 1024)
    return {
        "path": str(path.resolve()),
        "writable": True,
        "free_bytes": usage.free,
        "free_mb": round(free_mb, 1),
        "minimum_free_mb": minimum_free_mb,
        "enough_space": free_mb >= minimum_free_mb,
    }


def write_preflight_report(plan: TrainingPlan, directory: Path) -> Path:
    """Combine configuration, filesystem, environment, and warning checks."""
    directory.mkdir(parents=True, exist_ok=True)
    try:
        storage = verify_output_directory(directory)
        storage_error = None
    except OSError as exc:
        storage = {}
        storage_error = str(exc)
    payload = {
        "status": "preflight_only",
        "plan": asdict(plan),
        "fingerprint": experiment_fingerprint(plan),
        "resources": asdict(estimate_training_resources(plan)),
        "warnings": validate_training_plan(plan),
        "storage": storage,
        "storage_error": storage_error,
        "environment": environment_diagnostics(),
        "git_revision": _git_revision(),
        "next_step": "Review warnings and install/verify RoyaleGym before training.",
    }
    target = directory / "axr_preflight.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    raise SystemExit(main())
