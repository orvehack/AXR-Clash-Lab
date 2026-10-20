"""Validate and summarize AXR's manually labeled decision dataset."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REQUIRED = (
    "match_id", "timestamp_seconds", "phase", "event_type",
    "own_elixir", "opponent_elixir", "own_card", "own_lane",
    "opponent_card", "decision_label", "outcome_label", "notes",
)
PHASES = {"opening", "single_elixir", "double_elixir", "overtime", "unknown"}
ELIXIR_MIN, ELIXIR_MAX = 0.0, 10.0


@dataclass(frozen=True)
class DatasetReport:
    path: str
    rows: int
    valid_rows: int
    invalid_rows: int
    unique_matches: int
    phase_counts: dict[str, int]
    decision_counts: dict[str, int]
    outcome_counts: dict[str, int]
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _float_cell(row: dict[str, str], column: str, line: int, issues: list[str]) -> float | None:
    raw = (row.get(column) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        issues.append(f"Fila {line}: {column} debe ser numérico, recibido {raw!r}.")
        return None
    if not ELIXIR_MIN <= value <= ELIXIR_MAX:
        issues.append(f"Fila {line}: {column} fuera del rango {ELIXIR_MIN}..{ELIXIR_MAX}.")
    return value


def validate_rows(rows: Iterable[dict[str, str]], path: str = "<memoria>") -> DatasetReport:
    issues: list[str] = []
    phase_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    match_ids: set[str] = set()
    total = valid = 0

    for line, row in enumerate(rows, start=2):
        total += 1
        issue_count_before = len(issues)
        for column in REQUIRED:
            if column not in row:
                issues.append(f"Fila {line}: falta la columna {column!r}.")
            elif column not in {"notes", "opponent_card", "own_card", "opponent_elixir"} and not (row.get(column) or "").strip():
                issues.append(f"Fila {line}: {column} no puede estar vacío.")

        match_id = (row.get("match_id") or "").strip()
        if match_id:
            match_ids.add(match_id)

        timestamp = _float_cell(row, "timestamp_seconds", line, issues)
        if timestamp is not None and timestamp < 0:
            issues.append(f"Fila {line}: timestamp_seconds no puede ser negativo.")

        for col in ("own_elixir", "opponent_elixir"):
            _float_cell(row, col, line, issues)

        phase = (row.get("phase") or "").strip().casefold()
        if phase and phase not in PHASES:
            issues.append(f"Fila {line}: fase desconocida {phase!r}; opciones: {', '.join(sorted(PHASES))}.")

        decision = (row.get("decision_label") or "").strip().casefold()
        outcome = (row.get("outcome_label") or "").strip().casefold()
        if decision:
            decision_counts[decision] += 1
        if outcome:
            outcome_counts[outcome] += 1
        if phase:
            phase_counts[phase] += 1

        if len(issues) == issue_count_before:
            valid += 1

    return DatasetReport(
        path=path,
        rows=total,
        valid_rows=valid,
        invalid_rows=total - valid,
        unique_matches=len(match_ids),
        phase_counts=dict(phase_counts.most_common()),
        decision_counts=dict(decision_counts.most_common()),
        outcome_counts=dict(outcome_counts.most_common()),
        issues=tuple(issues),
    )


def load_and_validate(path: Path) -> DatasetReport:
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("El CSV no tiene encabezados.")
        missing = set(REQUIRED) - set(reader.fieldnames)
        if missing:
            raise ValueError("Faltan encabezados obligatorios: " + ", ".join(sorted(missing)))
        return validate_rows(reader, str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", type=Path, default=Path("data/decisions_template.csv"))
    parser.add_argument("--json", type=Path, help="Guardar informe JSON.")
    args = parser.parse_args()
    try:
        report = load_and_validate(args.csv_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if report.invalid_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Extended dataset preparation utilities
# ---------------------------------------------------------------------------

import hashlib
import random
from collections import defaultdict
from typing import Any


@dataclass(frozen=True)
class SplitReport:
    """Reproducible dataset split sizes and output paths."""

    train_rows: int
    validation_rows: int
    test_rows: int
    seed: int
    group_by_match: bool
    outputs: dict[str, str]


@dataclass(frozen=True)
class FeatureSchema:
    """Describes fields that may be used by a future imitation-learning model."""

    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    target_column: str
    excluded_columns: tuple[str, ...]


DEFAULT_FEATURE_SCHEMA = FeatureSchema(
    numeric_features=("timestamp_seconds", "own_elixir", "opponent_elixir"),
    categorical_features=("phase", "event_type", "own_card", "own_lane", "opponent_card"),
    target_column="decision_label",
    excluded_columns=("notes", "outcome_label"),
)


def stable_row_fingerprint(row: dict[str, str]) -> str:
    """Hash a normalized row to detect accidental duplicates without storing secrets."""
    canonical = "\\x1f".join((row.get(column) or "").strip() for column in REQUIRED)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def duplicate_rows(rows: Iterable[dict[str, str]]) -> dict[str, list[int]]:
    """Return duplicate fingerprints and their one-based data-row positions."""
    positions: dict[str, list[int]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        positions[stable_row_fingerprint(row)].append(line)
    return {key: lines for key, lines in positions.items() if len(lines) > 1}


def label_coverage(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Measure missing labels, notes, and metadata independently."""
    materialized = list(rows)
    count = len(materialized)
    fields = ("decision_label", "outcome_label", "phase", "event_type", "own_card", "own_elixir", "opponent_elixir")
    report: dict[str, Any] = {"rows": count, "fields": {}}
    for field in fields:
        present = sum(bool((row.get(field) or "").strip()) for row in materialized)
        report["fields"][field] = {
            "present": present,
            "missing": count - present,
            "coverage_percent": (100.0 * present / count) if count else 0.0,
        }
    report["unique_matches"] = len({(row.get("match_id") or "").strip() for row in materialized if (row.get("match_id") or "").strip()})
    report["unique_decisions"] = len({(row.get("decision_label") or "").strip().casefold() for row in materialized if (row.get("decision_label") or "").strip()})
    return report


def class_balance(rows: Iterable[dict[str, str]], column: str = "decision_label") -> dict[str, Any]:
    """Return label counts and majority-class baseline accuracy."""
    if column not in REQUIRED:
        raise ValueError(f"Columna desconocida: {column}")
    materialized = list(rows)
    counts = Counter((row.get(column) or "").strip() or "(sin etiqueta)" for row in materialized)
    total = len(materialized)
    majority = max(counts.values(), default=0)
    return {
        "column": column,
        "total": total,
        "classes": dict(counts.most_common()),
        "majority_class": counts.most_common(1)[0][0] if counts else None,
        "majority_baseline_accuracy": (majority / total) if total else None,
        "imbalance_ratio": (majority / min(counts.values())) if counts and min(counts.values()) else None,
    }


def grouped_split(
    rows: Iterable[dict[str, str]],
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    seed: int = 7,
    group_by_match: bool = True,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Split rows deterministically; group-by-match avoids replay leakage.

    This split is intended for offline research. For small datasets, some classes
    may appear in only one partition; inspect class_balance after splitting.
    """
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction debe estar entre 0 y 1")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction debe estar entre 0 y 1")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction debe ser menor que 1")
    materialized = [dict(row) for row in rows]
    rng = random.Random(seed)
    if group_by_match:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for index, row in enumerate(materialized):
            key = (row.get("match_id") or "").strip() or f"__row_{index}"
            groups[key].append(row)
        keys = list(groups)
        rng.shuffle(keys)
        train_end = int(len(keys) * train_fraction)
        val_end = train_end + int(len(keys) * validation_fraction)
        train_keys, validation_keys, test_keys = set(keys[:train_end]), set(keys[train_end:val_end]), set(keys[val_end:])
        train = [row for key in keys if key in train_keys for row in groups[key]]
        validation = [row for key in keys if key in validation_keys for row in groups[key]]
        test = [row for key in keys if key in test_keys for row in groups[key]]
    else:
        rng.shuffle(materialized)
        train_end = int(len(materialized) * train_fraction)
        val_end = train_end + int(len(materialized) * validation_fraction)
        train, validation, test = materialized[:train_end], materialized[train_end:val_end], materialized[val_end:]
    return train, validation, test


def write_rows(path: Path, rows: Iterable[dict[str, str]]) -> int:
    """Write rows with the canonical schema and return the number of examples."""
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({column: (row.get(column) or "").strip() for column in REQUIRED})
    return len(materialized)


def split_to_directory(
    rows: Iterable[dict[str, str]],
    output_dir: Path,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    seed: int = 7,
    group_by_match: bool = True,
) -> SplitReport:
    """Create train/validation/test CSV files and a JSON split manifest."""
    materialized = [dict(row) for row in rows]
    train, validation, test = grouped_split(
        materialized, train_fraction, validation_fraction, seed, group_by_match
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "train": output_dir / "train.csv",
        "validation": output_dir / "validation.csv",
        "test": output_dir / "test.csv",
    }
    counts = {
        "train": write_rows(paths["train"], train),
        "validation": write_rows(paths["validation"], validation),
        "test": write_rows(paths["test"], test),
    }
    report = SplitReport(
        train_rows=counts["train"],
        validation_rows=counts["validation"],
        test_rows=counts["test"],
        seed=seed,
        group_by_match=group_by_match,
        outputs={key: str(value) for key, value in paths.items()},
    )
    manifest = {
        **asdict(report),
        "source_rows": len(materialized),
        "warning": "Small datasets may produce unstable metrics; inspect label balance.",
    }
    (output_dir / "split_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8"
    )
    return report


def class_weights(rows: Iterable[dict[str, str]], column: str = "decision_label") -> dict[str, float]:
    """Compute inverse-frequency weights normalized around one."""
    counts = Counter((row.get(column) or "").strip() for row in rows if (row.get(column) or "").strip())
    if not counts:
        return {}
    total = sum(counts.values())
    number_of_classes = len(counts)
    return {label: total / (number_of_classes * count) for label, count in counts.items()}


def validate_outcome_vocabulary(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Report outcome labels that need human review rather than silently rewriting them."""
    materialized = list(rows)
    observed = Counter((row.get("outcome_label") or "").strip().casefold() for row in materialized)
    recommended = {"positive", "negative", "neutral", "unknown"}
    unexpected = sorted(label for label in observed if label and label not in recommended)
    return {
        "observed": dict(observed.most_common()),
        "recommended": sorted(recommended),
        "unexpected": unexpected,
        "requires_review": bool(unexpected),
    }


def dataset_card(rows: Iterable[dict[str, str]], source: str = "unknown") -> dict[str, Any]:
    """Create a compact provenance card for experiment reproducibility."""
    materialized = [dict(row) for row in rows]
    report = validate_rows(materialized, source)
    fingerprints = [stable_row_fingerprint(row) for row in materialized]
    return {
        "dataset_name": Path(source).name if source != "<memoria>" else "in-memory",
        "source": source,
        "row_count": len(materialized),
        "valid_rows": report.valid_rows,
        "invalid_rows": report.invalid_rows,
        "unique_matches": report.unique_matches,
        "duplicate_row_groups": len(duplicate_rows(materialized)),
        "content_sha256": hashlib.sha256("".join(fingerprints).encode("ascii")).hexdigest(),
        "label_coverage": label_coverage(materialized),
        "decision_balance": class_balance(materialized, "decision_label"),
        "outcome_vocabulary": validate_outcome_vocabulary(materialized),
        "feature_schema": asdict(DEFAULT_FEATURE_SCHEMA),
        "limitations": [
            "A valid CSV does not prove that labels are correct.",
            "Synthetic examples must not be mixed with human gameplay labels without provenance.",
            "Rows from one match should remain in one split to reduce data leakage.",
        ],
    }


def read_raw_rows(path: Path) -> list[dict[str, str]]:
    """Read a canonical CSV while preserving original strings for validation."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("El CSV no contiene encabezados.")
        missing = set(REQUIRED) - set(reader.fieldnames)
        if missing:
            raise ValueError("Faltan encabezados: " + ", ".join(sorted(missing)))
        return [dict(row) for row in reader]


def export_dataset_card(path: Path, target: Path) -> Path:
    """Validate a dataset and save its provenance/quality card."""
    rows = read_raw_rows(path)
    payload = dataset_card(rows, str(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    temporary.replace(target)
    return target


def suggest_labeling_priority(rows: Iterable[dict[str, str]], limit: int = 25) -> list[dict[str, Any]]:
    """Prioritize rows for manual review; does not invent labels or auto-correct data."""
    if limit < 1:
        raise ValueError("limit debe ser mayor que cero")
    materialized = list(rows)
    priorities: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(materialized, start=2):
        score = 0
        reasons: list[str] = []
        if not (row.get("decision_label") or "").strip():
            score += 5
            reasons.append("sin decision_label")
        if not (row.get("outcome_label") or "").strip():
            score += 3
            reasons.append("sin outcome_label")
        if not (row.get("phase") or "").strip():
            score += 2
            reasons.append("sin fase")
        for field in ("own_elixir", "opponent_elixir"):
            value = (row.get(field) or "").strip()
            if value:
                try:
                    numeric = float(value)
                    if not ELIXIR_MIN <= numeric <= ELIXIR_MAX:
                        score += 3
                        reasons.append(f"{field} fuera de rango")
                except ValueError:
                    score += 3
                    reasons.append(f"{field} no numérico")
        if reasons:
            priorities.append((score, index, {"row": index, "priority": score, "reasons": reasons, "match_id": row.get("match_id", "")}))
    priorities.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in priorities[:limit]]
