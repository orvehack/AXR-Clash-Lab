"""AXR emulator launcher: detect and start an installed Android emulator.

This module only launches/manages emulator processes. It does not tap the screen,
queue matches, play cards, or automate the official game's competitive client.

Windows examples:
    py -m src.emulator_manager detect
    py -m src.emulator_manager start --emulator memu
    py -m src.emulator_manager start --emulator bluestacks
    py -m src.emulator_manager status
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class EmulatorCandidate:
    name: str
    executable: Path
    launch_args: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class LaunchResult:
    emulator: str
    executable: str
    started: bool
    pid: int | None
    message: str


def _existing(paths: Sequence[str]) -> list[Path]:
    """Expand environment variables and return unique existing executable paths."""
    found: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        candidate = Path(os.path.expandvars(raw)).expanduser()
        key = str(candidate).casefold()
        if key not in seen and candidate.is_file():
            found.append(candidate)
            seen.add(key)
    return found


def discover_memu() -> list[EmulatorCandidate]:
    """Find common MEmu installations without assuming one fixed install folder."""
    candidates = _existing([
        r"%ProgramFiles%\Microvirt\MEmu\MEmu.exe",
        r"%ProgramFiles(x86)%\Microvirt\MEmu\MEmu.exe",
        r"C:\Program Files\Microvirt\MEmu\MEmu.exe",
        r"C:\Program Files (x86)\Microvirt\MEmu\MEmu.exe",
        r"D:\Microvirt\MEmu\MEmu.exe",
    ])
    path_hit = shutil.which("MEmu")
    if path_hit:
        candidates.extend(_existing([path_hit]))
    return [
        EmulatorCandidate("memu", path, (), "MEmu GUI executable")
        for path in _dedupe_paths(candidates)
    ]


def discover_bluestacks() -> list[EmulatorCandidate]:
    """Find BlueStacks 5 HD-Player in common installation locations."""
    candidates = _existing([
        r"%ProgramFiles%\BlueStacks_nxt\HD-Player.exe",
        r"%ProgramFiles(x86)%\BlueStacks_nxt\HD-Player.exe",
        r"C:\Program Files\BlueStacks_nxt\HD-Player.exe",
        r"C:\Program Files (x86)\BlueStacks_nxt\HD-Player.exe",
    ])
    path_hit = shutil.which("HD-Player")
    if path_hit:
        candidates.extend(_existing([path_hit]))
    return [
        EmulatorCandidate(
            "bluestacks", path, (),
            "BlueStacks 5; a particular instance may require vendor-specific arguments",
        )
        for path in _dedupe_paths(candidates)
    ]


def discover_emulators() -> dict[str, list[EmulatorCandidate]]:
    """Return detected supported emulators; empty lists mean not found."""
    return {"memu": discover_memu(), "bluestacks": discover_bluestacks()}


def _dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()).casefold()
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def find_candidate(name: str) -> EmulatorCandidate:
    """Select the first detected installation or raise a useful error."""
    key = name.strip().lower()
    detected = discover_emulators()
    if key not in detected:
        raise ValueError(f"Emulador no soportado: {name}. Opciones: {', '.join(detected)}")
    if not detected[key]:
        raise FileNotFoundError(
            f"No se encontró {key}. Instálalo o revisa su ruta; "
            "AXR no descargará ni instalará software automáticamente."
        )
    return detected[key][0]


def launch_emulator(name: str, extra_args: Sequence[str] = ()) -> LaunchResult:
    """Start an emulator GUI process; no game interaction is performed."""
    candidate = find_candidate(name)
    args = [str(candidate.executable), *candidate.launch_args, *extra_args]
    try:
        process = subprocess.Popen(
            args,
            cwd=str(candidate.executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    except OSError as exc:
        return LaunchResult(
            emulator=candidate.name,
            executable=str(candidate.executable),
            started=False,
            pid=None,
            message=f"No se pudo iniciar el emulador: {exc}",
        )
    return LaunchResult(
        emulator=candidate.name,
        executable=str(candidate.executable),
        started=True,
        pid=process.pid,
        message="Emulador iniciado. Abre el juego manualmente y verifica que cargue bien.",
    )


def process_status() -> dict[str, object]:
    """Return a lightweight status using tasklist on Windows or ps elsewhere."""
    if os.name == "nt":
        command = ["tasklist", "/FO", "CSV", "/NH"]
        names = {"memu.exe": "memu", "hd-player.exe": "bluestacks"}
    else:
        command = ["ps", "-A", "-o", "comm="]
        names = {"memu": "memu", "hd-player": "bluestacks"}
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "error": str(exc), "running": []}
    output = completed.stdout.casefold()
    running = sorted({
        label for process_name, label in names.items()
        if process_name in output
    })
    return {"available": True, "running": running}


def diagnostics() -> dict[str, object]:
    """Report OS and detected paths without collecting account or game data."""
    detected = discover_emulators()
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "checked_at_unix": time.time(),
        "emulators": {
            name: [str(item.executable) for item in candidates]
            for name, candidates in detected.items()
        },
        "process_status": process_status(),
        "scope": "emulator launch only; no game input or match automation",
    }


def print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("detect", help="List detected emulator executables")
    subparsers.add_parser("status", help="Show whether a supported emulator appears to run")
    subparsers.add_parser("diagnostics", help="Print local environment diagnostics")
    start = subparsers.add_parser("start", help="Launch an installed emulator GUI")
    start.add_argument("--emulator", required=True, choices=("memu", "bluestacks"))
    start.add_argument(
        "--arg", action="append", default=[],
        help="Optional vendor-specific argument; can be repeated",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "detect":
            data = {
                name: [asdict(item) | {"executable": str(item.executable)} for item in items]
                for name, items in discover_emulators().items()
            }
            print_json(data)
            return 0
        if args.command == "status":
            print_json(process_status())
            return 0
        if args.command == "diagnostics":
            print_json(diagnostics())
            return 0
        if args.command == "start":
            result = launch_emulator(args.emulator, args.arg)
            print_json(asdict(result))
            return 0 if result.started else 1
    except (OSError, ValueError, FileNotFoundError) as exc:
        print_json({"error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
