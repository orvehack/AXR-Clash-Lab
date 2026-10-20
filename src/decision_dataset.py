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
