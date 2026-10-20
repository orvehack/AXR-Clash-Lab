#!/usr/bin/env python3
"""Estadísticas reproducibles de un registro CSV de partidas; funciona offline."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = {"result", "opponent_deck", "trophy_delta"}
WIN_LABELS = {"win", "won", "victoria", "victorias"}
LOSS_LABELS = {"loss", "lost", "derrota", "derrotas"}


@dataclass(frozen=True)
class MatchSummary:
    total: int
    wins: int
    losses: int
    undecided: int
    trophy_delta: int
    opponent_counts: dict[str, int]

    @property
    def decided(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float | None:
        if not self.decided:
            return None
        return self.wins / self.decided * 100


def summarize_rows(rows: Iterable[dict[str, str]]) -> MatchSummary:
    total = wins = losses = undecided = trophy_delta = 0
    opponents: Counter[str] = Counter()

    for line_number, row in enumerate(rows, start=2):
        total += 1
        result = (row.get("result") or "").strip().casefold()
        if result in WIN_LABELS:
            wins += 1
        elif result in LOSS_LABELS:
            losses += 1
        else:
            undecided += 1

        raw_delta = (row.get("trophy_delta") or "0").strip()
        try:
            trophy_delta += int(raw_delta)
        except ValueError as exc:
            raise ValueError(
                f"trophy_delta debe ser un entero en la fila {line_number}: {raw_delta!r}"
            ) from exc

        deck = (row.get("opponent_deck") or "").strip() or "Sin especificar"
        opponents[deck] += 1

    return MatchSummary(
        total=total,
        wins=wins,
        losses=losses,
        undecided=undecided,
        trophy_delta=trophy_delta,
        opponent_counts=dict(opponents.most_common()),
    )


def load_summary(path: Path) -> MatchSummary:
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("El CSV está vacío o no contiene encabezados.")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError("Faltan columnas obligatorias: " + ", ".join(sorted(missing)))
        return summarize_rows(reader)


def print_summary(summary: MatchSummary) -> None:
    print(f"Partidas registradas: {summary.total}")
    print(f"Victorias: {summary.wins}")
    print(f"Derrotas: {summary.losses}")
    print(f"Sin resultado reconocido: {summary.undecided}")
    if summary.win_rate is None:
        print("Porcentaje de victorias: N/D (sin victorias/derrotas reconocidas)")
    else:
        print(f"Porcentaje de victorias: {summary.win_rate:.1f}%")
    print(f"Cambio neto de trofeos registrado: {summary.trophy_delta:+d}")
    print("\nMazos/arquetipos rivales registrados:")
    if not summary.opponent_counts:
        print("  (ninguno)")
    else:
        for deck, count in summary.opponent_counts.items():
            print(f"  {deck}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=Path("data/matches.csv"),
        help="Ruta al CSV (por defecto: data/matches.csv)",
    )
    args = parser.parse_args()
    try:
        print_summary(load_summary(args.csv_path))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
