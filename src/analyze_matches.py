#!/usr/bin/env python3
"""Summarize a CSV match log without connecting to or controlling the game."""

import argparse
import csv
from collections import Counter
from pathlib import Path


def analyze(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print("No hay partidas registradas todavía.")
        return

    results = Counter(row.get("result", "").strip().lower() for row in rows)
    wins = results["win"]
    losses = results["loss"]
    decided = wins + losses
    trophy_delta = sum(int(row.get("trophy_delta") or 0) for row in rows)

    print(f"Partidas registradas: {len(rows)}")
    print(f"Victorias: {wins}")
    print(f"Derrotas: {losses}")
    if decided:
        print(f"Porcentaje de victorias: {wins / decided * 100:.1f}%")
    else:
        print("Porcentaje de victorias: sin resultados win/loss reconocidos")
    print(f"Cambio total de trofeos registrado: {trophy_delta:+d}")

    by_opponent = Counter(
        row.get("opponent_deck", "Sin especificar").strip() or "Sin especificar"
        for row in rows
    )
    print("\nArquetipos/mazos rivales más registrados:")
    for deck, count in by_opponent.most_common():
        print(f"  {deck}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=Path("data/matches.csv"),
        help="Ruta al CSV (por defecto: data/matches.csv)",
    )
    args = parser.parse_args()
    if not args.csv_path.is_file():
        raise SystemExit(f"No se encontró el archivo: {args.csv_path}")
    analyze(args.csv_path)


if __name__ == "__main__":
    main()
