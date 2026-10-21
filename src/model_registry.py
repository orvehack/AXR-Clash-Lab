"""Auditable model registry and promotion gates for offline AXR experiments.

The registry never claims a model is better from training reward alone. Promotion requires
paired evaluation records from the same held-out seeds and explicit minimum sample sizes.
This module stores metadata only; it does not load or execute model weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Evaluation:
    model_id: str
    seed: int
    opponent_id: str
    outcome: str
    own_crowns: int | None = None
    opponent_crowns: int | None = None
    duration_seconds: float | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.model_id.strip():
            errors.append("model_id no puede estar vacío")
        if not self.opponent_id.strip():
            errors.append("opponent_id no puede estar vacío")
        if self.outcome not in {"win", "loss", "draw"}:
            errors.append("outcome debe ser win, loss o draw")
        if self.seed < 0:
            errors.append("seed no puede ser negativa")
        for field_name, value in (("own_crowns", self.own_crowns),
                                  ("opponent_crowns", self.opponent_crowns)):
            if value is not None and value < 0:
                errors.append(f"{field_name} no puede ser negativo")
        if self.duration_seconds is not None:
            if not math.isfinite(self.duration_seconds) or self.duration_seconds < 0:
                errors.append("duration_seconds debe ser finito y no negativo")
        return errors


def load_evaluations(path: Path) -> list[Evaluation]:
    if not path.exists():
        return []
    rows: list[Evaluation] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                row = Evaluation(**raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"Registro inválido en línea {line_number}: {exc}") from exc
            errors = row.validate()
            if errors:
                raise ValueError(f"Línea {line_number}: {'; '.join(errors)}")
            rows.append(row)
    return rows


def append_evaluations(path: Path, evaluations: Sequence[Evaluation]) -> int:
    if not evaluations:
        return 0
    for item in evaluations:
        errors = item.validate()
        if errors:
            raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        for item in evaluations:
            handle.write(json.dumps(asdict(item), sort_keys=True, ensure_ascii=False) + "\n")
    return len(evaluations)


def summarize(evaluations: Sequence[Evaluation], model_id: str, opponent_id: str) -> dict[str, Any]:
    rows = [row for row in evaluations if row.model_id == model_id and row.opponent_id == opponent_id]
    wins = sum(row.outcome == "win" for row in rows)
    losses = sum(row.outcome == "loss" for row in rows)
    draws = sum(row.outcome == "draw" for row in rows)
    decided = wins + losses
    return {
        "model_id": model_id,
        "opponent_id": opponent_id,
        "games": len(rows),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate_all_games": wins / len(rows) if rows else None,
        "win_rate_decided": wins / decided if decided else None,
        "mean_own_crowns": (
            sum(row.own_crowns for row in rows if row.own_crowns is not None)
            / sum(row.own_crowns is not None for row in rows)
            if any(row.own_crowns is not None for row in rows) else None
        ),
        "seeds": sorted({row.seed for row in rows}),
    }


def _bootstrap_mean_interval(
    values: Sequence[float],
    repetitions: int = 2000,
    confidence: float = 0.95,
    seed: int = 7,
) -> tuple[float, float] | None:
    """Deterministic percentile-bootstrap CI for paired per-seed score deltas."""
    if repetitions < 100:
        raise ValueError("repetitions debe ser al menos 100")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence debe estar entre 0 y 1")
    if not values:
        return None
    rng = random.Random(seed)
    sample_size = len(values)
    means = sorted(
        statistics.fmean(rng.choice(values) for _ in range(sample_size))
        for _ in range(repetitions)
    )
    lower_index = max(0, int(((1.0 - confidence) / 2.0) * repetitions))
    upper_index = min(
        repetitions - 1,
        int((1.0 - (1.0 - confidence) / 2.0) * repetitions) - 1,
    )
    return means[lower_index], means[upper_index]


def paired_comparison(
    evaluations: Sequence[Evaluation],
    candidate_id: str,
    baseline_id: str,
    opponent_id: str,
    minimum_pairs: int = 30,
    required_win_rate: float = 0.55,
    required_delta: float = 0.05,
) -> dict[str, Any]:
    if minimum_pairs < 1:
        raise ValueError("minimum_pairs debe ser al menos 1")
    if not 0.0 <= required_win_rate <= 1.0:
        raise ValueError("required_win_rate debe estar entre 0 y 1")
    if not 0.0 <= required_delta <= 1.0:
        raise ValueError("required_delta debe estar entre 0 y 1")

    def index(model_id: str) -> dict[int, Evaluation]:
        selected: dict[int, Evaluation] = {}
        for row in evaluations:
            if row.model_id != model_id or row.opponent_id != opponent_id:
                continue
            if row.seed in selected:
                raise ValueError(f"Semilla duplicada {row.seed} para {model_id} vs {opponent_id}")
            selected[row.seed] = row
        return selected

    candidate = index(candidate_id)
    baseline = index(baseline_id)
    common = sorted(set(candidate) & set(baseline))
    if len(common) < minimum_pairs:
        return {
            "candidate_id": candidate_id,
            "baseline_id": baseline_id,
            "opponent_id": opponent_id,
            "paired_games": len(common),
            "minimum_pairs": minimum_pairs,
            "candidate_win_rate": None,
            "baseline_win_rate": None,
            "delta": None,
            "promote": False,
            "reason": "insufficient_paired_evaluations",
            "common_seeds": common,
        }

    def score(row: Evaluation) -> float:
        return {"win": 1.0, "draw": 0.5, "loss": 0.0}[row.outcome]

    cand_score = sum(score(candidate[seed]) for seed in common) / len(common)
    base_score = sum(score(baseline[seed]) for seed in common) / len(common)
    delta = cand_score - base_score
    paired_deltas = [score(candidate[seed]) - score(baseline[seed]) for seed in common]
    interval = _bootstrap_mean_interval(paired_deltas)
    lower_bound, upper_bound = interval if interval is not None else (None, None)
    score_gate = cand_score >= required_win_rate
    delta_gate = delta >= required_delta
    uncertainty_gate = lower_bound is not None and lower_bound > 0.0
    promote = score_gate and delta_gate and uncertainty_gate
    if promote:
        reason = "gates_passed"
    elif not uncertainty_gate:
        reason = "paired_uncertainty_too_high"
    else:
        reason = "promotion_gates_not_met"
    return {
        "candidate_id": candidate_id,
        "baseline_id": baseline_id,
        "opponent_id": opponent_id,
        "paired_games": len(common),
        "minimum_pairs": minimum_pairs,
        "candidate_win_rate": cand_score,
        "baseline_win_rate": base_score,
        "delta": delta,
        "paired_delta_ci_95": {"lower": lower_bound, "upper": upper_bound},
        "required_win_rate": required_win_rate,
        "required_delta": required_delta,
        "confidence_gate": "95% paired bootstrap lower bound must be > 0",
        "promote": promote,
        "reason": reason,
        "common_seeds": common,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_model_manifest(
    model_id: str,
    artifact_path: Path,
    output_path: Path,
    model_family: str,
    parent_model_id: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    if not model_id.strip() or not model_family.strip():
        raise ValueError("model_id y model_family son obligatorios")
    if not artifact_path.exists():
        raise FileNotFoundError(f"No existe el artefacto: {artifact_path}")
    files = [artifact_path] if artifact_path.is_file() else sorted(
        path for path in artifact_path.rglob("*") if path.is_file()
    )
    if not files:
        raise ValueError("El artefacto no contiene archivos")
    artifact_root = artifact_path if artifact_path.is_dir() else artifact_path.parent
    entries = [
        {"path": str(path.relative_to(artifact_root)), "size_bytes": path.stat().st_size,
         "sha256": sha256_file(path)}
        for path in files
    ]
    manifest = {
        "schema_version": 1,
        "model_id": model_id,
        "model_family": model_family,
        "parent_model_id": parent_model_id,
        "artifact_path": str(artifact_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": entries,
        "notes": notes,
        "promotion_status": "unverified",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent,
                                         delete=False) as handle:
            temporary = handle.name
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, output_path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("compare", help="Comparar candidato y baseline por semillas comunes")
    check.add_argument("--evaluations", type=Path, required=True)
    check.add_argument("--candidate", required=True)
    check.add_argument("--baseline", required=True)
    check.add_argument("--opponent", required=True)
    check.add_argument("--minimum-pairs", type=int, default=30)
    check.add_argument("--required-win-rate", type=float, default=0.55)
    check.add_argument("--required-delta", type=float, default=0.05)
    args = parser.parse_args(argv)
    try:
        rows = load_evaluations(args.evaluations)
        result = paired_comparison(rows, args.candidate, args.baseline, args.opponent,
                                   args.minimum_pairs, args.required_win_rate, args.required_delta)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["promote"] else 1
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
