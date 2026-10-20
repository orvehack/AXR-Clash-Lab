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


# ---------------------------------------------------------------------------
# Extended analysis API
# These functions are intentionally pure where possible so the GUI, scripts,
# tests, and future report generator can share the same calculations.
# ---------------------------------------------------------------------------

from datetime import date
from math import sqrt
from statistics import fmean, median
from typing import Any, Sequence


@dataclass(frozen=True)
class MatchRecord:
    """Normalized match row used by higher-level analytics."""

    index: int
    date_text: str
    result: str
    own_deck: str
    opponent_deck: str
    trophy_delta: int
    notes: str


@dataclass(frozen=True)
class DeckPerformance:
    """Outcome summary for a deck or archetype."""

    deck: str
    games: int
    wins: int
    losses: int
    undecided: int
    win_rate: float | None
    trophy_delta: int
    average_trophy_delta: float


@dataclass(frozen=True)
class StreakSummary:
    """Current and longest result streaks in chronological order."""

    current_kind: str | None
    current_length: int
    longest_win_streak: int
    longest_loss_streak: int
    known_results: int


@dataclass(frozen=True)
class PeriodComparison:
    """Side-by-side comparison of two match-log periods."""

    first_label: str
    second_label: str
    first_games: int
    second_games: int
    first_win_rate: float | None
    second_win_rate: float | None
    win_rate_change_points: float | None
    first_trophies: int
    second_trophies: int
    trophy_change: int


def _normalize_label(value: str | None) -> str:
    return (value or "").strip().casefold()


def normalize_match_result(value: str | None) -> str:
    """Map common English and Spanish labels to stable result keys."""
    normalized = _normalize_label(value)
    if normalized in WIN_LABELS | {"ganada", "ganado", "gané"}:
        return "win"
    if normalized in LOSS_LABELS | {"perdida", "perdido", "perdí"}:
        return "loss"
    if normalized in {"draw", "tie", "empate", "igualada"}:
        return "draw"
    return "unknown"


def parse_match_rows(rows: Iterable[dict[str, str]]) -> list[MatchRecord]:
    """Convert CSV dictionaries into normalized, validated records."""
    records: list[MatchRecord] = []
    for index, row in enumerate(rows, start=2):
        raw_delta = (row.get("trophy_delta") or "0").strip()
        try:
            delta = int(raw_delta)
        except ValueError as exc:
            raise ValueError(
                f"trophy_delta debe ser entero en la fila {index}: {raw_delta!r}"
            ) from exc
        records.append(
            MatchRecord(
                index=index,
                date_text=(row.get("date") or "").strip(),
                result=normalize_match_result(row.get("result")),
                own_deck=(row.get("own_deck") or "").strip(),
                opponent_deck=(row.get("opponent_deck") or "").strip() or "Sin especificar",
                trophy_delta=delta,
                notes=(row.get("notes") or "").strip(),
            )
        )
    return records


def load_records(path: Path) -> list[MatchRecord]:
    """Load a complete normalized history, preserving UTF-8 BOM compatibility."""
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("El CSV no contiene encabezados.")
        missing = {"result", "trophy_delta", "opponent_deck"} - set(reader.fieldnames)
        if missing:
            raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
        return parse_match_rows(reader)


def filter_records(
    records: Iterable[MatchRecord],
    result: str | None = None,
    opponent: str | None = None,
    own_deck: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    min_trophy_delta: int | None = None,
    max_trophy_delta: int | None = None,
    text_query: str | None = None,
) -> list[MatchRecord]:
    """Filter records by result, deck, dates, trophy change, or free-text notes."""
    wanted_result = normalize_match_result(result) if result else None
    wanted_opponent = (opponent or "").strip().casefold()
    wanted_deck = (own_deck or "").strip().casefold()
    query = (text_query or "").strip().casefold()
    filtered: list[MatchRecord] = []
    for record in records:
        if wanted_result and record.result != wanted_result:
            continue
        if wanted_opponent and wanted_opponent not in record.opponent_deck.casefold():
            continue
        if wanted_deck and wanted_deck not in record.own_deck.casefold():
            continue
        if start_date and record.date_text and record.date_text < start_date:
            continue
        if end_date and record.date_text and record.date_text > end_date:
            continue
        if min_trophy_delta is not None and record.trophy_delta < min_trophy_delta:
            continue
        if max_trophy_delta is not None and record.trophy_delta > max_trophy_delta:
            continue
        if query:
            searchable = " ".join(
                (record.date_text, record.own_deck, record.opponent_deck, record.notes)
            ).casefold()
            if query not in searchable:
                continue
        filtered.append(record)
    return filtered


def deck_performance(records: Iterable[MatchRecord], field: str = "own_deck") -> list[DeckPerformance]:
    """Rank decks by sample size, then win rate, without hiding small samples."""
    if field not in {"own_deck", "opponent_deck"}:
        raise ValueError("field debe ser own_deck u opponent_deck")
    buckets: dict[str, list[MatchRecord]] = {}
    for record in records:
        key = getattr(record, field).strip() or "Sin especificar"
        buckets.setdefault(key, []).append(record)
    summaries: list[DeckPerformance] = []
    for deck, games in buckets.items():
        wins = sum(row.result == "win" for row in games)
        losses = sum(row.result == "loss" for row in games)
        undecided = len(games) - wins - losses
        decided = wins + losses
        trophies = sum(row.trophy_delta for row in games)
        summaries.append(
            DeckPerformance(
                deck=deck,
                games=len(games),
                wins=wins,
                losses=losses,
                undecided=undecided,
                win_rate=(100 * wins / decided) if decided else None,
                trophy_delta=trophies,
                average_trophy_delta=trophies / len(games),
            )
        )
    return sorted(
        summaries,
        key=lambda item: (
            item.win_rate is not None,
            item.win_rate if item.win_rate is not None else -1,
            item.games,
        ),
        reverse=True,
    )


def result_streaks(records: Iterable[MatchRecord]) -> StreakSummary:
    """Calculate streaks in the order supplied; callers should sort chronologically."""
    current_kind: str | None = None
    current_length = 0
    longest_wins = longest_losses = 0
    run_kind: str | None = None
    run_length = 0
    known = 0
    for record in records:
        kind = record.result
        if kind not in {"win", "loss"}:
            run_kind, run_length = None, 0
            current_kind, current_length = None, 0
            continue
        known += 1
        if kind == run_kind:
            run_length += 1
        else:
            run_kind, run_length = kind, 1
        if kind == "win":
            longest_wins = max(longest_wins, run_length)
        else:
            longest_losses = max(longest_losses, run_length)
        current_kind, current_length = run_kind, run_length
    return StreakSummary(current_kind, current_length, longest_wins, longest_losses, known)


def moving_win_rate(
    records: Sequence[MatchRecord],
    window: int = 20,
) -> list[dict[str, Any]]:
    """Return rolling win-rate points for the last N decisive games at each point."""
    if window < 1:
        raise ValueError("window debe ser mayor que cero")
    decisive: list[MatchRecord] = []
    points: list[dict[str, Any]] = []
    for record in records:
        if record.result not in {"win", "loss"}:
            continue
        decisive.append(record)
        segment = decisive[-window:]
        wins = sum(item.result == "win" for item in segment)
        points.append(
            {
                "index": record.index,
                "date": record.date_text,
                "games_in_window": len(segment),
                "wins": wins,
                "win_rate": 100.0 * wins / len(segment),
            }
        )
    return points


def daily_trophy_series(records: Iterable[MatchRecord]) -> list[dict[str, Any]]:
    """Aggregate trophy deltas by date and calculate a running cumulative total."""
    daily: Counter[str] = Counter()
    for record in records:
        key = record.date_text or "Sin fecha"
        daily[key] += record.trophy_delta
    running = 0
    result: list[dict[str, Any]] = []
    for day, delta in sorted(daily.items()):
        running += delta
        result.append({"date": day, "delta": delta, "cumulative": running})
    return result


def compare_periods(
    first: Iterable[MatchRecord],
    second: Iterable[MatchRecord],
    first_label: str = "Periodo A",
    second_label: str = "Periodo B",
) -> PeriodComparison:
    """Compare two pre-filtered periods; no causal inference is implied."""
    a = list(first)
    b = list(second)
    sa = summarize_rows(
        {"result": row.result, "opponent_deck": row.opponent_deck, "trophy_delta": str(row.trophy_delta)}
        for row in a
    )
    sb = summarize_rows(
        {"result": row.result, "opponent_deck": row.opponent_deck, "trophy_delta": str(row.trophy_delta)}
        for row in b
    )
    change = None if sa.win_rate is None or sb.win_rate is None else sb.win_rate - sa.win_rate
    return PeriodComparison(
        first_label=first_label,
        second_label=second_label,
        first_games=sa.total,
        second_games=sb.total,
        first_win_rate=sa.win_rate,
        second_win_rate=sb.win_rate,
        win_rate_change_points=change,
        first_trophies=sa.trophy_delta,
        second_trophies=sb.trophy_delta,
        trophy_change=sb.trophy_delta - sa.trophy_delta,
    )


def bootstrap_win_rate_interval(
    records: Sequence[MatchRecord],
    repetitions: int = 2000,
    confidence: float = 0.95,
    seed: int = 7,
) -> tuple[float, float] | None:
    """Estimate a bootstrap interval for win rate using only decisive records.

    This is descriptive and assumes sampled games are reasonably representative.
    It is not a guarantee of future performance, especially with tiny datasets.
    """
    import random

    if repetitions < 100:
        raise ValueError("repetitions debe ser al menos 100")
    if not 0 < confidence < 1:
        raise ValueError("confidence debe estar entre 0 y 1")
    decisive = [row for row in records if row.result in {"win", "loss"}]
    if not decisive:
        return None
    rng = random.Random(seed)
    rates: list[float] = []
    for _ in range(repetitions):
        sample = [rng.choice(decisive) for _ in range(len(decisive))]
        rates.append(100.0 * sum(row.result == "win" for row in sample) / len(sample))
    rates.sort()
    tail = (1 - confidence) / 2
    low_index = max(0, min(len(rates) - 1, int(tail * len(rates))))
    high_index = max(0, min(len(rates) - 1, int((1 - tail) * len(rates)) - 1))
    return rates[low_index], rates[high_index]


def summarize_session(records: Iterable[MatchRecord]) -> dict[str, Any]:
    """Produce a combined JSON-friendly report for the desktop dashboard."""
    materialized = list(records)
    base = summarize_rows(
        {"result": row.result, "opponent_deck": row.opponent_deck, "trophy_delta": str(row.trophy_delta)}
        for row in materialized
    )
    return {
        "summary": {
            "total": base.total,
            "wins": base.wins,
            "losses": base.losses,
            "undecided": base.undecided,
            "decided": base.decided,
            "win_rate": base.win_rate,
            "trophy_delta": base.trophy_delta,
        },
        "own_decks": [vars(item) for item in deck_performance(materialized, "own_deck")],
        "opponents": [vars(item) for item in deck_performance(materialized, "opponent_deck")],
        "streaks": vars(result_streaks(materialized)),
        "moving_win_rate": moving_win_rate(materialized),
        "daily_trophies": daily_trophy_series(materialized),
        "win_rate_interval_95": bootstrap_win_rate_interval(materialized),
    }


def export_records_csv(records: Iterable[MatchRecord], target: Path) -> int:
    """Export normalized records as UTF-8 CSV; returns the number of rows."""
    materialized = list(records)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("date", "result", "own_deck", "opponent_deck", "trophy_delta", "notes"),
        )
        writer.writeheader()
        for row in materialized:
            writer.writerow({
                "date": row.date_text,
                "result": row.result,
                "own_deck": row.own_deck,
                "opponent_deck": row.opponent_deck,
                "trophy_delta": row.trophy_delta,
                "notes": row.notes,
            })
    return len(materialized)


def export_session_json(records: Iterable[MatchRecord], target: Path) -> Path:
    """Write the full analysis bundle to a JSON file."""
    import json

    payload = summarize_session(records)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    temporary.replace(target)
    return target


def validate_date_range(start_date: str | None, end_date: str | None) -> None:
    """Validate optional ISO dates early, so filter mistakes are not silent."""
    for name, raw in (("start_date", start_date), ("end_date", end_date)):
        if raw:
            try:
                date.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(f"{name} debe usar YYYY-MM-DD: {raw!r}") from exc
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date no puede ser posterior a end_date")


def format_percentage(value: float | None) -> str:
    """Format an optional percentage without inventing a value for empty data."""
    return "N/D" if value is None else f"{value:.1f}%"


def quality_flags(records: Iterable[MatchRecord]) -> list[str]:
    """Return actionable data-quality warnings for sparse or suspicious logs."""
    materialized = list(records)
    warnings: list[str] = []
    if not materialized:
        return ["No hay partidas; importa un CSV antes de interpretar métricas."]
    missing_dates = sum(not row.date_text for row in materialized)
    missing_decks = sum(not row.own_deck for row in materialized)
    unknown_results = sum(row.result == "unknown" for row in materialized)
    if missing_dates:
        warnings.append(f"{missing_dates} partida(s) sin fecha.")
    if missing_decks:
        warnings.append(f"{missing_decks} partida(s) sin mazo propio.")
    if unknown_results:
        warnings.append(f"{unknown_results} resultado(s) sin etiqueta reconocida.")
    if len(materialized) < 20:
        warnings.append("Muestra pequeña: la tasa de victoria puede variar mucho.")
    if all(row.trophy_delta == 0 for row in materialized):
        warnings.append("Todos los cambios de trofeos son cero; revisa si están registrados.")
    return warnings


def render_text_report(records: Iterable[MatchRecord]) -> str:
    """Build a human-readable report suitable for CLI or a saved text file."""
    materialized = list(records)
    bundle = summarize_session(materialized)
    summary = bundle["summary"]
    lines = [
        "AXR CLASH LAB — INFORME DE PARTIDAS",
        "=" * 42,
        f"Partidas: {summary['total']}",
        f"Victorias: {summary['wins']}",
        f"Derrotas: {summary['losses']}",
        f"Resultados no decisivos/desconocidos: {summary['undecided']}",
        f"Tasa de victoria: {format_percentage(summary['win_rate'])}",
        f"Cambio neto de trofeos: {summary['trophy_delta']:+d}",
        "",
        "MAZOS PROPIOS",
    ]
    for item in bundle["own_decks"]:
        lines.append(
            f"- {item['deck']}: {item['games']} partidas, "
            f"{format_percentage(item['win_rate'])}, {item['trophy_delta']:+d} trofeos"
        )
    lines.extend(["", "RIVALES"])
    for item in bundle["opponents"][:10]:
        lines.append(
            f"- {item['deck']}: {item['games']} partidas, "
            f"{format_percentage(item['win_rate'])}"
        )
    lines.extend(["", "CALIDAD DE DATOS"])
    lines.extend(f"- {warning}" for warning in quality_flags(materialized))
    return "\\n".join(lines)


def write_text_report(records: Iterable[MatchRecord], target: Path) -> Path:
    """Persist a readable report, creating parent directories when needed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_text_report(records) + "\\n", encoding="utf-8")
    return target
