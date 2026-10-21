"""Diagnose the local AXR setup without installing packages or touching game data."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


REQUIRED_PATHS = (
    "src/axr_desktop.py",
    "src/train_agent.py",
    "src/imitate_agent.py",
    "src/royalegym_baseline.py",
    "src/model_registry.py",
    "src/registry_bridge.py",
    "tests",
    ".github/workflows/tests.yml",
)
OPTIONAL_MODULES = ("royalegym", "royalelearn", "royaleimitate", "torch", "numpy")


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def diagnose(root: Path | None = None) -> dict[str, Any]:
    """Return a JSON-friendly report; missing ML packages are warnings, not core failures."""
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    required = {
        relative: (project_root / relative).exists()
        for relative in REQUIRED_PATHS
    }
    optional = {name: _module_available(name) for name in OPTIONAL_MODULES}
    try:
        import tkinter  # noqa: F401
        tkinter_available = True
    except ImportError:
        tkinter_available = False

    python_supported = sys.version_info >= (3, 11)
    missing_paths = [path for path, exists in required.items() if not exists]
    missing_optional = [name for name, available in optional.items() if not available]
    core_ok = python_supported and not missing_paths
    return {
        "project": "AXR Clash Lab",
        "project_root": str(project_root),
        "python": sys.version.split()[0],
        "python_supported_for_core": python_supported,
        "platform": platform.platform(),
        "git_available": shutil.which("git") is not None,
        "tkinter_available": tkinter_available,
        "gui_ready": tkinter_available,
        "required_paths": required,
        "missing_required_paths": missing_paths,
        "optional_ml_modules": optional,
        "missing_optional_ml_modules": missing_optional,
        "core_ready": core_ok,
        "ml_ready": not missing_optional,
        "notes": [
            "This diagnostic does not install dependencies or start training.",
            "Optional ML packages may be installed later in a dedicated virtual environment.",
            "The presence of a package does not prove API compatibility or a successful training run.",
            "If tkinter_available is false, the desktop UI will not open until Python/Tk is repaired."
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Optional repository root")
    parser.add_argument("--strict-ml", action="store_true", help="Return failure if any optional ML module is missing")
    args = parser.parse_args(argv)
    report = diagnose(args.root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["core_ready"]:
        return 1
    if args.strict_ml and not report["ml_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
