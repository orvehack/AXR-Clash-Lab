"""Contrato de integración de RoyaleGym para AXR Clash Lab.

Ejecuta una prueba breve contra MockEngine: no requiere el motor Rust y no toca
emuladores, ADB ni el cliente oficial. Sirve para detectar cambios en la API antes
de conectar el entrenador. No demuestra que un modelo aprenda ni valida RustEngine.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import math
from collections.abc import Mapping
from typing import Any, Sequence

AGENTS = ("blue", "red")


def _shape(value: Any) -> list[int] | None:
    """Devuelve shape como lista sin depender de NumPy en el módulo base."""
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    try:
        return [int(part) for part in shape]
    except (TypeError, ValueError):
        return None


def summarize_space(space: Any) -> dict[str, Any]:
    """Describe un espacio Gymnasium sin serializar objetos arbitrarios."""
    result: dict[str, Any] = {"type": type(space).__name__}
    shape = _shape(space)
    if shape is not None:
        result["shape"] = shape
    for field in ("n", "dtype", "start"):
        value = getattr(space, field, None)
        if value is not None and isinstance(value, (str, int, float, bool)):
            result[field] = value
    return result


def _require_two_seat_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} debe ser un mapping por asiento; recibido {type(value).__name__}")
    missing = set(AGENTS) - set(value)
    if missing:
        raise ValueError(f"{label} no contiene los asientos requeridos: {sorted(missing)}")
    return value


def _finite_scalar(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} no es un escalar numérico: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} no es finito: {number!r}")
    return number


def _legal_action(observation: Any, action_space: Any) -> tuple[int, dict[str, Any]]:
    """Elige NOOP si está permitido; en caso contrario, la primera acción legal."""
    import numpy as np

    if not isinstance(observation, Mapping):
        raise TypeError("Cada observación debe ser un mapping con action_mask")
    if "action_mask" not in observation:
        raise KeyError("La observación no contiene action_mask")
    mask = np.asarray(observation["action_mask"]).reshape(-1)
    count = getattr(action_space, "n", None)
    if not isinstance(count, int):
        raise TypeError("El espacio de acciones no expone un número discreto 'n'")
    if mask.size != count:
        raise ValueError(f"Máscara de {mask.size} elementos, pero el espacio tiene {count} acciones")
    legal = np.flatnonzero(mask)
    if legal.size == 0:
        raise ValueError("La máscara no permite ninguna acción")
    action = 0 if bool(mask[0]) else int(legal[0])
    if not bool(mask[action]):
        raise AssertionError("El selector produjo una acción ilegal")
    return action, {
        "mask_length": int(mask.size),
        "legal_actions": int(legal.size),
        "selected_action": action,
        "noop_legal": bool(mask[0]),
    }


def run_contract_probe(seed: int = 7, steps: int = 3) -> dict[str, Any]:
    """Comprueba reset, observaciones, máscaras y step usando solo MockEngine."""
    if steps < 1 or steps > 100:
        raise ValueError("--steps debe estar entre 1 y 100")
    if importlib.util.find_spec("royalegym") is None:
        return {
            "ok": False,
            "installed": False,
            "message": "RoyaleGym no está instalado en este Python.",
            "next_step": "Instala las dependencias indicadas en docs/ROYALEGYM_SETUP.md.",
        }

    import numpy as np
    from royalegym import ClashParallelEnv, MockEngine

    try:
        package_version = importlib.metadata.version("royalegym")
    except importlib.metadata.PackageNotFoundError:
        package_version = "source-tree-or-uninstalled"

    env = ClashParallelEnv(engine=MockEngine(), decision_ms=50)
    results: list[dict[str, Any]] = []
    try:
        for index in range(steps):
            observations, reset_infos = env.reset(seed=seed + index)
            observations = _require_two_seat_mapping(observations, "reset observations")
            _require_two_seat_mapping(reset_infos, "reset infos")
            action_map: dict[str, int] = {}
            action_details: dict[str, Any] = {}
            seat_spaces: dict[str, Any] = {}
            for agent in AGENTS:
                action_space = env.action_space(agent)
                observation_space = env.observation_space(agent)
                observation = observations[agent]
                if not isinstance(observation, Mapping):
                    raise TypeError(f"Observación de {agent} no es mapping")
                for key in ("action_mask",):
                    if key not in observation:
                        raise KeyError(f"Observación de {agent} no contiene {key}")
                action, details = _legal_action(observation, action_space)
                action_map[agent] = action
                action_details[agent] = details
                seat_spaces[agent] = {
                    "observation_space": summarize_space(observation_space),
                    "action_space": summarize_space(action_space),
                    "observation_keys": sorted(str(k) for k in observation),
                    "observation_shapes": {
                        str(k): _shape(v) for k, v in observation.items()
                    },
                }

            next_obs, rewards, terminated, truncated, infos = env.step(action_map)
            for label, mapping in (
                ("step observations", next_obs),
                ("rewards", rewards),
                ("terminations", terminated),
                ("truncations", truncated),
                ("step infos", infos),
            ):
                _require_two_seat_mapping(mapping, label)
            reward_values = {
                agent: _finite_scalar(rewards[agent], f"reward[{agent}]")
                for agent in AGENTS
            }
            for agent in AGENTS:
                if not isinstance(terminated[agent], (bool, np.bool_)):
                    raise TypeError(f"terminated[{agent}] no es booleano")
                if not isinstance(truncated[agent], (bool, np.bool_)):
                    raise TypeError(f"truncated[{agent}] no es booleano")
            results.append({
                "episode_index": index,
                "actions": action_details,
                "rewards": reward_values,
                "terminated": {a: bool(terminated[a]) for a in AGENTS},
                "truncated": {a: bool(truncated[a]) for a in AGENTS},
                "seat_spaces": seat_spaces,
            })
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    return {
        "ok": True,
        "installed": True,
        "royalegym_version": package_version,
        "engine": "MockEngine",
        "seed": seed,
        "steps_checked": len(results),
        "scope": [
            "reset/step return shape",
            "two-seat mappings",
            "observation action_mask",
            "legal action selection",
            "finite scalar rewards",
            "termination/truncation boolean types",
        ],
        "limitations": [
            "This checks the Python MockEngine contract only.",
            "It does not verify RustEngine, RoyaleLearn training, or strategic strength.",
        ],
        "results": results,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--steps", type=int, default=3, help="Number of short one-step episodes")
    parser.add_argument("--strict", action="store_true", help="Return exit code 1 if RoyaleGym is missing")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_contract_probe(seed=args.seed, steps=args.steps)
    except Exception as exc:
        result = {
            "ok": False,
            "installed": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "hint": "Revisa la versión instalada de RoyaleGym y conserva este diagnóstico.",
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("ok") and (args.strict or result.get("installed")):
        return 1
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
