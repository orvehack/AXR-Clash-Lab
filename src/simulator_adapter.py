#!/usr/bin/env python3
"""Inspecciona RoyaleGym localmente sin iniciar partidas reales ni ejecutar acciones."""

from __future__ import annotations

import argparse
import importlib.util
import json
from typing import Any


def describe_space(space: Any) -> dict[str, Any] | None:
    """Devuelve una descripción sencilla de un espacio Gym/Gymnasium."""
    if space is None:
        return None
    result: dict[str, Any] = {"type": type(space).__name__, "repr": repr(space)}
    shape = getattr(space, "shape", None)
    if shape is not None:
        try:
            result["shape"] = list(shape)
        except TypeError:
            result["shape"] = str(shape)
    n = getattr(space, "n", None)
    if n is not None:
        result["n"] = n
    return result


def inspect_environment(env: Any, seed: int = 7) -> dict[str, Any]:
    """Resetea un entorno simulado una vez y describe sus interfaces; no hace step()."""
    try:
        reset_result = env.reset(seed=seed)
    except TypeError:
        # Compatibilidad con entornos cuyo reset todavía no acepta seed.
        reset_result = env.reset()

    if isinstance(reset_result, tuple):
        observation = reset_result[0] if reset_result else None
        reset_info = reset_result[1] if len(reset_result) > 1 else {}
    else:
        observation = reset_result
        reset_info = {}

    observation_shape = getattr(observation, "shape", None)
    try:
        observation_shape = list(observation_shape) if observation_shape is not None else None
    except TypeError:
        observation_shape = str(observation_shape)

    return {
        "environment_type": f"{type(env).__module__}.{type(env).__name__}",
        "observation_space": describe_space(getattr(env, "observation_space", None)),
        "action_space": describe_space(getattr(env, "action_space", None)),
        "observation_type": type(observation).__name__,
        "observation_shape": observation_shape,
        "reset_info_type": type(reset_info).__name__,
        "actions_executed": 0,
    }


def probe_royalegym(seed: int = 7) -> dict[str, Any]:
    """Detecta RoyaleGym e inspecciona make_env() si está instalado."""
    if importlib.util.find_spec("royalegym") is None:
        return {
            "installed": False,
            "message": "RoyaleGym no está instalado en este Python. Consulta docs/ROYALEGYM_SETUP.md.",
        }

    from royalegym import make_env  # import diferido: permite usar el proyecto sin RoyaleGym

    env = make_env()
    try:
        result = inspect_environment(env, seed=seed)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    return {"installed": True, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7, help="Semilla para el reset del simulador")
    args = parser.parse_args()
    try:
        result = probe_royalegym(seed=args.seed)
    except Exception as exc:  # muestra diagnóstico de instalación/API sin ocultar el error
        result = {"installed": True, "probe_error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("installed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
