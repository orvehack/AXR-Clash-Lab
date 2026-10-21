"""Bridge offline RoyaleGym baseline JSON reports into the AXR model registry.

Only episodes with a verifiable terminal outcome are imported. Episodes marked
"unknown" or "limit" are skipped rather than converted into fabricated draws.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from src.model_registry import Evaluation, append_evaluations


OUTCOME_MAP = {"blue": "win", "red": "loss", "draw": "draw"}


def convert_baseline_report(
    payload: dict[str, Any],
    model_id: str,
    opponent_id: str,
    expected_agent: str | None = None,
) -> tuple[list[Evaluation], dict[str, Any]]:
    """Convert a royalegym_baseline summary into registry records and import stats."""
    if not model_id.strip() or not opponent_id.strip():
        raise ValueError("model_id y opponent_id son obligatorios")
    source_agent = payload.get("agent")
    if expected_agent and source_agent != expected_agent:
        raise ValueError(
            f"El reporte es del agente {source_agent!r}, no del esperado {expected_agent!r}"
        )
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("El JSON no contiene una lista 'results' de episodios")

    converted: list[Evaluation] = []
    skipped: dict[str, int] = {}
    seen_seeds: set[int] = set()
    for index, raw in enumerate(results, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"El episodio {index} no es un objeto JSON")
        try:
            seed = int(raw["seed"])
            winner = str(raw["winner"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"El episodio {index} no tiene seed/winner válidos") from exc
        if seed < 0:
            raise ValueError(f"El episodio {index} tiene una semilla negativa")
        if seed in seen_seeds:
            raise ValueError(f"Semilla duplicada en el reporte: {seed}")
        seen_seeds.add(seed)

        outcome = OUTCOME_MAP.get(winner)
        if outcome is None:
            skipped[winner] = skipped.get(winner, 0) + 1
            continue

        def optional_int(key: str) -> int | None:
            value = raw.get(key)
            if value is None:
                return None
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"El episodio {index} tiene {key} inválido") from exc
            if number < 0:
                raise ValueError(f"El episodio {index} tiene {key} negativo")
            return number

        duration = raw.get("duration_seconds")
        try:
            duration_value = float(duration) if duration is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError(f"El episodio {index} tiene duration_seconds inválido") from exc

        record = Evaluation(
            model_id=model_id,
            seed=seed,
            opponent_id=opponent_id,
            outcome=outcome,
            own_crowns=optional_int("blue_crowns"),
            opponent_crowns=optional_int("red_crowns"),
            duration_seconds=duration_value,
        )
        errors = record.validate()
        if errors:
            raise ValueError(f"Episodio {index}: {'; '.join(errors)}")
        converted.append(record)

    return converted, {
        "source_agent": source_agent,
        "expected_agent": expected_agent,
        "source_agent_verified": (source_agent == expected_agent) if expected_agent else False,
        "source_opponent": payload.get("opponent"),
        "episodes_in_report": len(results),
        "records_imported": len(converted),
        "episodes_skipped_by_outcome": skipped,
        "model_id": model_id,
        "opponent_id": opponent_id,
        "note": "Registry records describe the blue seat only; pass --expected-agent to verify the source agent name before import.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON generado por royalegym_baseline")
    parser.add_argument("--model-id", required=True, help="Identificador/versionado del agente que jugó como blue")
    parser.add_argument("--opponent-id", required=True, help="Identificador del oponente que jugó como red")
    parser.add_argument("--expected-agent", default=None, help="Nombre exacto de --agent en el informe original; falla si no coincide")
    parser.add_argument("--output", type=Path, default=Path("runs/evaluations.jsonl"))
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("El archivo de entrada debe contener un objeto JSON")
        records, report = convert_baseline_report(payload, args.model_id, args.opponent_id, args.expected_agent)
        count = append_evaluations(args.output, records)
        report["output"] = str(args.output)
        report["records_appended"] = count
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
