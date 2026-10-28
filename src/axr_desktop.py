"""AXR Clash Lab desktop workbench.

A standard-library Tkinter interface for browsing match logs, inspecting
labeled decision data, preparing offline experiments, and reviewing local run
manifests. The GUI does not control the official game client or an emulator.

Launch from the repository root:
    python -m src.axr_desktop
"""
from __future__ import annotations

import csv
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover - platform-specific import guard
    raise SystemExit(
        "AXR Desktop necesita Tkinter. En Windows suele venir con Python; "
        "reinstala Python marcando Tcl/Tk si falta."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"
MATCHES_FILE = DATA_DIR / "matches.csv"
DECISIONS_FILE = DATA_DIR / "decisions_template.csv"
APP_NAME = "AXR Clash Lab"
APP_VERSION = "0.2.0"
DARK = "#101820"
PANEL = "#17232d"
PANEL_ALT = "#1e2e3b"
TEXT = "#e7edf2"
MUTED = "#9eb0bf"
ACCENT = "#54d6a0"
BLUE = "#66b5ff"
ORANGE = "#ffbd69"
RED = "#ff7474"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 20)


@dataclass(frozen=True)
class MatchRecord:
    date: str
    result: str
    own_deck: str
    opponent_deck: str
    trophy_delta: int
    notes: str


@dataclass(frozen=True)
class DecisionRecord:
    match_id: str
    timestamp_seconds: float
    phase: str
    event_type: str
    own_elixir: float | None
    opponent_elixir: float | None
    own_card: str
    own_lane: str
    opponent_card: str
    decision_label: str
    outcome_label: str
    notes: str


@dataclass
class RunCard:
    name: str
    path: Path
    status: str
    details: str
    modified: float


class DataError(ValueError):
    """Raised when a local dataset cannot be interpreted safely."""


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float without allowing malformed CSV data to crash UI."""
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to integer, accepting numeric strings like '12.0'."""
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_result(value: str) -> str:
    """Normalize common Spanish and English labels into win/loss/draw/unknown."""
    normalized = (value or "").strip().casefold()
    if normalized in {"win", "won", "victoria", "ganada", "gané", "ganada"}:
        return "win"
    if normalized in {"loss", "lost", "derrota", "derrota", "perdida", "perdí"}:
        return "loss"
    if normalized in {"draw", "tie", "empate"}:
        return "draw"
    return "unknown"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV using UTF-8 BOM tolerance and provide a useful error."""
    if not path.exists():
        return []
    if not path.is_file():
        raise DataError(f"La ruta no es un archivo: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return []
            return [dict(row) for row in reader]
    except (OSError, csv.Error, UnicodeError) as exc:
        raise DataError(f"No se pudo leer {path.name}: {exc}") from exc


def load_matches(path: Path = MATCHES_FILE) -> list[MatchRecord]:
    """Load match history while tolerating optional columns and bad trophy values."""
    rows = read_csv_rows(path)
    records: list[MatchRecord] = []
    for row in rows:
        records.append(
            MatchRecord(
                date=(row.get("date") or "").strip(),
                result=normalize_result(row.get("result") or ""),
                own_deck=(row.get("own_deck") or "").strip(),
                opponent_deck=(row.get("opponent_deck") or "").strip(),
                trophy_delta=safe_int(row.get("trophy_delta")),
                notes=(row.get("notes") or "").strip(),
            )
        )
    return records


def load_decisions(path: Path = DECISIONS_FILE) -> list[DecisionRecord]:
    """Load decision labels; rows without a timestamp are ignored with a clear error."""
    rows = read_csv_rows(path)
    records: list[DecisionRecord] = []
    for line, row in enumerate(rows, start=2):
        raw_time = (row.get("timestamp_seconds") or "").strip()
        if not raw_time:
            continue
        try:
            timestamp = float(raw_time)
        except ValueError as exc:
            raise DataError(f"Fila {line}: timestamp_seconds no es numérico.") from exc
        if not math.isfinite(timestamp):
            raise DataError(f"Fila {line}: timestamp_seconds debe ser un número finito.")
        if timestamp < 0:
            raise DataError(f"Fila {line}: timestamp_seconds no puede ser negativo.")
        own_raw = (row.get("own_elixir") or "").strip()
        opponent_raw = (row.get("opponent_elixir") or "").strip()
        records.append(
            DecisionRecord(
                match_id=(row.get("match_id") or "").strip(),
                timestamp_seconds=timestamp,
                phase=(row.get("phase") or "unknown").strip(),
                event_type=(row.get("event_type") or "").strip(),
                own_elixir=float(own_raw) if own_raw else None,
                opponent_elixir=float(opponent_raw) if opponent_raw else None,
                own_card=(row.get("own_card") or "").strip(),
                own_lane=(row.get("own_lane") or "").strip(),
                opponent_card=(row.get("opponent_card") or "").strip(),
                decision_label=(row.get("decision_label") or "").strip(),
                outcome_label=(row.get("outcome_label") or "").strip(),
                notes=(row.get("notes") or "").strip(),
            )
        )
    return records


def summarize_matches(records: Iterable[MatchRecord]) -> dict[str, Any]:
    """Return stable, JSON-friendly match metrics for dashboard cards."""
    materialized = list(records)
    wins = sum(row.result == "win" for row in materialized)
    losses = sum(row.result == "loss" for row in materialized)
    draws = sum(row.result == "draw" for row in materialized)
    undecided = len(materialized) - wins - losses - draws
    trophy_delta = sum(row.trophy_delta for row in materialized)
    known = wins + losses + draws
    opponents = Counter(row.opponent_deck or "(sin registrar)" for row in materialized)
    return {
        "total": len(materialized),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "undecided": undecided,
        "win_rate": (wins / known * 100.0) if known else 0.0,
        "trophy_delta": trophy_delta,
        "average_trophy_delta": (trophy_delta / len(materialized)) if materialized else 0.0,
        "opponents": opponents.most_common(8),
    }


def summarize_decisions(records: Iterable[DecisionRecord]) -> dict[str, Any]:
    """Count labels and estimate data coverage without claiming model quality."""
    materialized = list(records)
    return {
        "rows": len(materialized),
        "matches": len({row.match_id for row in materialized if row.match_id}),
        "phases": Counter(row.phase or "unknown" for row in materialized).most_common(),
        "decisions": Counter(row.decision_label or "(sin etiqueta)" for row in materialized).most_common(12),
        "outcomes": Counter(row.outcome_label or "(sin etiqueta)" for row in materialized).most_common(),
        "labeled": sum(bool(row.decision_label) for row in materialized),
        "notes": sum(bool(row.notes) for row in materialized),
    }


def list_runs(path: Path = RUNS_DIR) -> list[RunCard]:
    """Discover run manifests without assuming every run directory is complete."""
    if not path.exists():
        return []
    cards: list[RunCard] = []
    for manifest in sorted(path.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        if manifest.name not in {"axr_run_manifest.json", "axr_training_status.json", "evaluation.json", "baseline.json"}:
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            status = str(payload.get("status", "unknown"))
            plan = payload.get("training_plan", {})
            steps = plan.get("total_steps_requested", plan.get("total_steps", "—"))
            details = f"Pasos: {steps}; archivo: {manifest.name}"
        except (OSError, json.JSONDecodeError, AttributeError):
            status = "invalid"
            details = "No se pudo interpretar el JSON"
        cards.append(
            RunCard(
                name=manifest.parent.name,
                path=manifest,
                status=status,
                details=details,
                modified=manifest.stat().st_mtime,
            )
        )
    return cards


def write_json(path: Path, payload: Any) -> None:
    """Atomically save a JSON document to avoid leaving half-written reports."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def open_path(path: Path) -> None:
    """Open a local file or folder using the platform's default handler."""
    if not path.exists():
        raise FileNotFoundError(path)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class ScrollableFrame(ttk.Frame):
    """Reusable scrollable container for dashboard cards and run details."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=DARK, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class MetricCard(ttk.Frame):
    """Compact metric tile with a title, value and secondary explanation."""

    def __init__(self, master: tk.Misc, title: str, value: str = "—", hint: str = "") -> None:
        super().__init__(master, style="Card.TFrame", padding=14)
        self.value_var = tk.StringVar(value=value)
        ttk.Label(self, text=title.upper(), style="Muted.TLabel").pack(anchor="w")
        ttk.Label(self, textvariable=self.value_var, style="Metric.TLabel").pack(anchor="w", pady=(5, 2))
        ttk.Label(self, text=hint, style="Muted.TLabel", wraplength=220).pack(anchor="w")

    def set_value(self, value: str) -> None:
        self.value_var.set(value)


class BarChart(tk.Canvas):
    """Minimal canvas bar chart; avoids mandatory third-party plotting packages."""

    def __init__(self, master: tk.Misc, height: int = 220, **kwargs: Any) -> None:
        super().__init__(master, height=height, background=PANEL, highlightthickness=0, **kwargs)
        self.values: list[tuple[str, float]] = []
        self.bar_color = ACCENT
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_values(self, values: Iterable[tuple[str, float]], color: str = ACCENT) -> None:
        self.values = list(values)
        self.bar_color = color
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 260)
        height = max(self.winfo_height(), 120)
        if not self.values:
            self.create_text(width / 2, height / 2, text="Sin datos todavía", fill=MUTED, font=FONT)
            return
        left, right, top, bottom = 42, width - 18, 18, height - 42
        chart_height = max(bottom - top, 10)
        max_value = max(max(abs(value) for _, value in self.values), 1.0)
        self.create_line(left, top, left, bottom, fill="#425563")
        self.create_line(left, bottom, right, bottom, fill="#425563")
        count = len(self.values)
        slot = max((right - left) / count, 8)
        bar_width = min(slot * 0.62, 54)
        for index, (label, value) in enumerate(self.values):
            x_center = left + slot * (index + 0.5)
            bar_height = abs(value) / max_value * chart_height
            y0 = bottom - bar_height
            self.create_rectangle(
                x_center - bar_width / 2, y0, x_center + bar_width / 2, bottom,
                fill=self.bar_color, outline="",
            )
            self.create_text(x_center, max(top + 8, y0 - 10), text=f"{value:g}", fill=TEXT, font=("Segoe UI", 8))
            self.create_text(x_center, bottom + 16, text=label[:12], fill=MUTED, font=("Segoe UI", 8))


class AXRApp(tk.Tk):
    """Main application window and navigation controller."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1260x820")
        self.minsize(960, 640)
        self.configure(background=DARK)
        self.matches: list[MatchRecord] = []
        self.decisions: list[DecisionRecord] = []
        self.background_events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.status_var = tk.StringVar(value="Listo · modo local/offline")
        self.selected_match_file = tk.StringVar(value=str(MATCHES_FILE))
        self.selected_decision_file = tk.StringVar(value=str(DECISIONS_FILE))
        self._configure_styles()
        self._build_menu()
        self._build_shell()
        self.refresh_all()
        self.after(150, self._drain_background_events)

    def _build_menu(self) -> None:
        """Build a native menu bar with shortcuts for the main workspace."""
        menu_bar = tk.Menu(self)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Actualizar datos", accelerator="Ctrl+R", command=self.refresh_all)
        file_menu.add_separator()
        file_menu.add_command(label="Abrir carpeta del proyecto", command=lambda: self._safe_open(ROOT))
        file_menu.add_command(label="Abrir carpeta de datos", command=lambda: self._safe_open(DATA_DIR))
        file_menu.add_command(label="Abrir carpeta de experimentos", command=lambda: self._safe_open(RUNS_DIR, create=True))
        file_menu.add_separator()
        file_menu.add_command(label="Salir", accelerator="Alt+F4", command=self.destroy)
        menu_bar.add_cascade(label="Archivo", menu=file_menu)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        tab_labels = ("Inicio", "Partidas", "Decisiones", "Laboratorio IA", "Experimentos guardados", "Datos y configuración")
        for index, label in enumerate(tab_labels):
            view_menu.add_command(
                label=label,
                accelerator=f"Ctrl+{index + 1}",
                command=lambda selected=index: self._select_tab(selected),
            )
        menu_bar.add_cascade(label="Ver", menu=view_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(label="Validar dataset de decisiones", command=self.validate_decisions)
        tools_menu.add_command(label="Guardar diagnóstico", command=self.export_diagnostics)
        tools_menu.add_command(label="Preparar plan de experimento", command=self.save_experiment_plan)
        menu_bar.add_cascade(label="Herramientas", menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="Acerca de AXR Clash Lab", command=self._show_about)
        menu_bar.add_cascade(label="Ayuda", menu=help_menu)
        self.configure(menu=menu_bar)

        self.bind_all("<Control-r>", lambda _event: self.refresh_all())
        self.bind_all("<Control-R>", lambda _event: self.refresh_all())
        for index in range(6):
            self.bind_all(
                f"<Control-Key-{index + 1}>",
                lambda _event, selected=index: self._select_tab(selected),
            )
        self.bind_all("<F1>", lambda _event: self._show_about())

    def _select_tab(self, index: int) -> None:
        """Select a workspace tab if the notebook has been initialized."""
        notebook = getattr(self, "notebook", None)
        if notebook is not None and index < len(notebook.tabs()):
            notebook.select(index)

    def _show_about(self) -> None:
        messagebox.showinfo(
            f"Acerca de {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\\n\\n"
            "Banco de trabajo local para analizar partidas, etiquetar decisiones "
            "y preparar experimentos offline. No automatiza partidas en los "
            "servidores oficiales ni afirma que un entrenamiento se haya ejecutado.",
            parent=self,
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=FONT, background=DARK, foreground=TEXT)
        style.configure("TFrame", background=DARK)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=DARK, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background=PANEL, foreground=ACCENT, font=("Segoe UI Semibold", 23))
        style.configure("Title.TLabel", background=DARK, foreground=TEXT, font=FONT_TITLE)
        style.configure("Subtitle.TLabel", background=DARK, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("TButton", padding=(12, 7), background=PANEL_ALT, foreground=TEXT)
        style.map("TButton", background=[("active", "#304656")])
        style.configure("Accent.TButton", background="#245943", foreground="#ffffff", padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#2e7757")])
        style.configure("TNotebook", background=DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=TEXT, padding=(16, 10))
        style.map("TNotebook.Tab", background=[("selected", PANEL_ALT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28)
        style.configure("Treeview.Heading", background=PANEL_ALT, foreground=TEXT, font=FONT_BOLD)
        style.map("Treeview", background=[("selected", "#2e5d78")])
        style.configure("TEntry", fieldbackground=PANEL_ALT, foreground=TEXT)
        style.configure("TCombobox", fieldbackground=PANEL_ALT, foreground=TEXT)

    def _build_shell(self) -> None:
        header = ttk.Frame(self, padding=(22, 18, 22, 12))
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        ttk.Label(brand, text="AXR CLASH LAB", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            brand,
            text="Laboratorio de estrategias · simulación offline · análisis de decisiones",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Button(header, text="Actualizar datos", command=self.refresh_all).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="▶ Start emulador", style="Accent.TButton", command=self.start_emulator_dialog).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Abrir carpeta del proyecto", command=lambda: self._safe_open(ROOT)).pack(side="right")
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill="x", padx=22)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=22, pady=16)
        self.dashboard_tab = ttk.Frame(self.notebook, padding=12)
        self.matches_tab = ttk.Frame(self.notebook, padding=12)
        self.decisions_tab = ttk.Frame(self.notebook, padding=12)
        self.experiments_tab = ttk.Frame(self.notebook, padding=12)
        self.runs_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.dashboard_tab, text="Inicio")
        self.notebook.add(self.matches_tab, text="Partidas")
        self.notebook.add(self.decisions_tab, text="Decisiones")
        self.notebook.add(self.experiments_tab, text="Laboratorio IA")
        self.notebook.add(self.runs_tab, text="Experimentos guardados")
        self.notebook.add(self.settings_tab, text="Datos y configuración")
        self._build_dashboard()
        self._build_matches()
        self._build_decisions()
        self._build_experiments()
        self._build_runs()
        self._build_settings()
        footer = ttk.Frame(self, padding=(22, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").pack(side="left")
        ttk.Label(footer, text="AXR · sin conexión al cliente oficial", style="Subtitle.TLabel").pack(side="right")

    def start_emulator_dialog(self) -> None:
        """Offer to launch a locally installed emulator; never controls the game."""
        from tkinter import messagebox, simpledialog

        choice = simpledialog.askstring(
            "Iniciar emulador",
            "Escribe el emulador instalado: memu o bluestacks",
            parent=self,
            initialvalue="memu",
        )
        if choice is None:
            return
        normalized = choice.strip().lower()
        if normalized not in {"memu", "bluestacks"}:
            messagebox.showerror(
                "Emulador no válido",
                "Opciones disponibles: memu o bluestacks.",
                parent=self,
            )
            return
        try:
            from src.emulator_manager import launch_emulator
            result = launch_emulator(normalized)
        except (ImportError, OSError, ValueError, FileNotFoundError) as exc:
            messagebox.showerror("No se pudo iniciar", str(exc), parent=self)
            self.status_var.set(f"Error al iniciar emulador: {exc}")
            return
        if result.started:
            self.status_var.set(f"{result.emulator} iniciado · PID {result.pid}")
            messagebox.showinfo(
                "Emulador iniciado",
                f"Se inició {result.emulator}.\n\n"
                "Abre Clash Royale manualmente y comprueba que cargue. "
                "AXR no pulsa botones ni inicia partidas automáticamente.",
                parent=self,
            )
        else:
            self.status_var.set(result.message)
            messagebox.showerror("No se pudo iniciar", result.message, parent=self)

    def _build_dashboard(self) -> None:
        ttk.Label(self.dashboard_tab, text="Resumen del laboratorio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.dashboard_tab,
            text="Métricas de tus CSV locales. Los datos de ejemplo del repositorio son ficticios.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 14))
        metrics = ttk.Frame(self.dashboard_tab)
        metrics.pack(fill="x")
        self.metric_cards = {
            "matches": MetricCard(metrics, "Partidas registradas", "0", "Filas leídas desde el historial"),
            "winrate": MetricCard(metrics, "Victorias", "0%", "Porcentaje entre resultados conocidos"),
            "trophies": MetricCard(metrics, "Cambio de trofeos", "0", "Suma de trophy_delta"),
            "decisions": MetricCard(metrics, "Decisiones etiquetadas", "0", "Filas útiles en el dataset"),
        }
        for index, card in enumerate(self.metric_cards.values()):
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0), pady=4)
            metrics.columnconfigure(index, weight=1)
        chart_row = ttk.Frame(self.dashboard_tab)
        chart_row.pack(fill="both", expand=True, pady=(14, 0))
        left = ttk.Frame(chart_row, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 7))
        right = ttk.Frame(chart_row, style="Card.TFrame", padding=14)
        right.pack(side="left", fill="both", expand=True, padx=(7, 0))
        ttk.Label(left, text="Resultados de partidas", font=FONT_BOLD, background=PANEL).pack(anchor="w")
        self.result_chart = BarChart(left)
        self.result_chart.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(right, text="Rivales más registrados", font=FONT_BOLD, background=PANEL).pack(anchor="w")
        self.opponent_chart = BarChart(right, height=220)
        self.opponent_chart.pack(fill="both", expand=True, pady=(10, 0))
        self.dashboard_note = tk.StringVar(value="Carga un CSV desde Datos y configuración para comenzar.")
        ttk.Label(self.dashboard_tab, textvariable=self.dashboard_note, style="Subtitle.TLabel", wraplength=1000).pack(anchor="w", pady=(12, 0))

    def _build_matches(self) -> None:
        top = ttk.Frame(self.matches_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Historial de partidas", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Importar CSV", command=self.choose_match_file).pack(side="right")
        ttk.Button(top, text="Exportar resumen", command=self.export_match_summary).pack(side="right", padx=8)
        columns = ("date", "result", "own_deck", "opponent_deck", "trophy_delta", "notes")
        self.match_tree = ttk.Treeview(self.matches_tab, columns=columns, show="headings", height=16)
        labels = {
            "date": "Fecha", "result": "Resultado", "own_deck": "Tu mazo",
            "opponent_deck": "Mazo rival", "trophy_delta": "Trofeos", "notes": "Notas",
        }
        widths = {"date": 105, "result": 90, "own_deck": 220, "opponent_deck": 150, "trophy_delta": 85, "notes": 320}
        for column in columns:
            self.match_tree.heading(column, text=labels[column])
            self.match_tree.column(column, width=widths[column], anchor="w")
        yscroll = ttk.Scrollbar(self.matches_tab, orient="vertical", command=self.match_tree.yview)
        xscroll = ttk.Scrollbar(self.matches_tab, orient="horizontal", command=self.match_tree.xview)
        self.match_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.match_tree.pack(fill="both", expand=True, pady=(14, 0))
        xscroll.pack(fill="x")
        ttk.Label(
            self.matches_tab,
            text="Tip: mantén date,result,own_deck,opponent_deck,trophy_delta,notes en el CSV.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(8, 0))

    def _build_decisions(self) -> None:
        top = ttk.Frame(self.decisions_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Dataset de decisiones", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Importar etiquetas", command=self.choose_decision_file).pack(side="right")
        ttk.Button(top, text="Validar y exportar informe", command=self.validate_decisions).pack(side="right", padx=8)
        self.decision_summary = tk.StringVar(value="Sin datos de decisiones cargados.")
        ttk.Label(self.decisions_tab, textvariable=self.decision_summary, style="Subtitle.TLabel", wraplength=1100).pack(anchor="w", pady=12)
        columns = ("match_id", "timestamp", "phase", "card", "lane", "decision", "outcome")
        self.decision_tree = ttk.Treeview(self.decisions_tab, columns=columns, show="headings", height=15)
        labels = {
            "match_id": "Partida", "timestamp": "Tiempo (s)", "phase": "Fase",
            "card": "Carta", "lane": "Carril", "decision": "Decisión", "outcome": "Resultado",
        }
        for column in columns:
            self.decision_tree.heading(column, text=labels[column])
            self.decision_tree.column(column, width=145 if column != "decision" else 220, anchor="w")
        self.decision_tree.pack(fill="both", expand=True)
        ttk.Label(
            self.decisions_tab,
            text="La plantilla vacía no entrena nada por sí sola; primero hacen falta ejemplos etiquetados.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(8, 0))

    def _build_experiments(self) -> None:
        ttk.Label(self.experiments_tab, text="Preparar experimento offline", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.experiments_tab,
            text="Configura el experimento. El modo de planificación solo crea un manifiesto y no entrena.",
            style="Subtitle.TLabel",
            wraplength=1050,
        ).pack(anchor="w", pady=(2, 14))
        form = ttk.Frame(self.experiments_tab, style="Card.TFrame", padding=18)
        form.pack(fill="x", anchor="n")
        self.experiment_vars = {
            "steps": tk.StringVar(value="200000"),
            "seed": tk.StringVar(value="7"),
            "n_envs": tk.StringVar(value="4"),
            "opponent": tk.StringVar(value="random"),
            "device": tk.StringVar(value="auto"),
            "channels": tk.StringVar(value="64"),
            "blocks": tk.StringVar(value="4"),
            "save_dir": tk.StringVar(value=str(RUNS_DIR / "axr_experiment")),
        }
        fields = [
            ("Pasos de entrenamiento", "steps"),
            ("Semilla reproducible", "seed"),
            ("Entornos paralelos", "n_envs"),
            ("Canales de red", "channels"),
            ("Bloques de red", "blocks"),
        ]
        for index, (label, key) in enumerate(fields):
            row, column = divmod(index, 2)
            cell = ttk.Frame(form, style="Card.TFrame")
            cell.grid(row=row, column=column, sticky="ew", padx=(0, 16), pady=8)
            ttk.Label(cell, text=label, background=PANEL).pack(anchor="w")
            ttk.Entry(cell, textvariable=self.experiment_vars[key], width=32).pack(fill="x", pady=(4, 0))
        row = 3
        for label, key, values in [
            ("Oponente", "opponent", ("random", "noop", "self")),
            ("Dispositivo", "device", ("auto", "cpu", "cuda")),
        ]:
            column = 0 if key == "opponent" else 1
            cell = ttk.Frame(form, style="Card.TFrame")
            cell.grid(row=row, column=column, sticky="ew", padx=(0, 16), pady=8)
            ttk.Label(cell, text=label, background=PANEL).pack(anchor="w")
            ttk.Combobox(cell, textvariable=self.experiment_vars[key], values=values, state="readonly").pack(fill="x", pady=(4, 0))
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        folder = ttk.Frame(self.experiments_tab)
        folder.pack(fill="x", pady=12)
        ttk.Label(folder, text="Carpeta del experimento").pack(anchor="w")
        path_row = ttk.Frame(folder)
        path_row.pack(fill="x", pady=(4, 0))
        ttk.Entry(path_row, textvariable=self.experiment_vars["save_dir"]).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Elegir…", command=self.choose_run_folder).pack(side="left", padx=(8, 0))
        actions = ttk.Frame(self.experiments_tab)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Guardar plan solamente", style="Accent.TButton", command=self.save_experiment_plan).pack(side="left")
        ttk.Button(actions, text="Abrir terminal de instrucciones", command=self.show_training_command).pack(side="left", padx=8)
        self.experiment_output = tk.Text(
            self.experiments_tab, height=10, wrap="word", background=PANEL, foreground=TEXT,
            insertbackground=TEXT, relief="flat", padx=12, pady=10, font=("Consolas", 10),
        )
        self.experiment_output.pack(fill="both", expand=True, pady=(8, 0))
        self._set_text(self.experiment_output, "Aquí aparecerá el manifiesto de configuración.\nNo se inicia entrenamiento desde este botón.")

    def _build_runs(self) -> None:
        top = ttk.Frame(self.runs_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Experimentos y resultados locales", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Actualizar", command=self.refresh_runs).pack(side="right")
        ttk.Button(top, text="Abrir archivo seleccionado", command=self.open_selected_run).pack(side="right", padx=8)
        columns = ("name", "status", "details", "modified", "path")
        self.run_tree = ttk.Treeview(self.runs_tab, columns=columns, show="headings", height=17)
        for column, label, width in [
            ("name", "Experimento", 160), ("status", "Estado", 110),
            ("details", "Detalles", 300), ("modified", "Modificado", 170), ("path", "Archivo", 420),
        ]:
            self.run_tree.heading(column, text=label)
            self.run_tree.column(column, width=width, anchor="w")
        self.run_tree.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(
            self.runs_tab,
            text="Se muestran manifiestos e informes locales; la existencia de un archivo no demuestra que el modelo sea bueno.",
            style="Subtitle.TLabel",
            wraplength=1050,
        ).pack(anchor="w", pady=(8, 0))

    def _build_settings(self) -> None:
        ttk.Label(self.settings_tab, text="Archivos y configuración", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.settings_tab,
            text="Selecciona los CSV de trabajo y revisa las rutas detectadas. No se envían datos a ningún servicio.",
            style="Subtitle.TLabel",
            wraplength=1000,
        ).pack(anchor="w", pady=(2, 14))
        self.path_vars = {
            "matches": self.selected_match_file,
            "decisions": self.selected_decision_file,
        }
        for key, label, command in [
            ("matches", "CSV de historial de partidas", self.choose_match_file),
            ("decisions", "CSV de decisiones etiquetadas", self.choose_decision_file),
        ]:
            card = ttk.Frame(self.settings_tab, style="Card.TFrame", padding=14)
            card.pack(fill="x", pady=6)
            ttk.Label(card, text=label, background=PANEL, font=FONT_BOLD).pack(anchor="w")
            line = ttk.Frame(card, style="Card.TFrame")
            line.pack(fill="x", pady=(8, 0))
            ttk.Entry(line, textvariable=self.path_vars[key]).pack(side="left", fill="x", expand=True)
            ttk.Button(line, text="Seleccionar…", command=command).pack(side="left", padx=(8, 0))
        info = ttk.Frame(self.settings_tab, style="Card.TFrame", padding=16)
        info.pack(fill="x", pady=(12, 0))
        ttk.Label(info, text="Rutas del proyecto", background=PANEL, font=FONT_BOLD).pack(anchor="w")
        self.paths_text = tk.Text(info, height=7, wrap="word", background=PANEL, foreground=MUTED, relief="flat")
        self.paths_text.pack(fill="x", pady=(8, 0))
        self._set_text(
            self.paths_text,
            f"Raíz: {ROOT}\nDatos: {DATA_DIR}\nExperimentos: {RUNS_DIR}\nPython: {sys.version.split()[0]}\nPlataforma: {sys.platform}",
        )
        buttons = ttk.Frame(self.settings_tab)
        buttons.pack(fill="x", pady=12)
        ttk.Button(buttons, text="Abrir carpeta de datos", command=lambda: self._safe_open(DATA_DIR)).pack(side="left")
        ttk.Button(buttons, text="Abrir carpeta de experimentos", command=lambda: self._safe_open(RUNS_DIR, create=True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Guardar diagnóstico", command=self.export_diagnostics).pack(side="left")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)

    def _safe_open(self, path: Path, create: bool = False) -> None:
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            open_path(path)
            self._set_status(f"Abierto: {path}")
        except (OSError, FileNotFoundError) as exc:
            messagebox.showerror("No se pudo abrir", str(exc), parent=self)

    def choose_match_file(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, title="Seleccionar historial CSV",
            filetypes=(("CSV", "*.csv"), ("Todos los archivos", "*.*")),
            initialdir=str(DATA_DIR if DATA_DIR.exists() else ROOT),
        )
        if selected:
            self.selected_match_file.set(selected)
            self.refresh_matches()

    def choose_decision_file(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, title="Seleccionar decisiones CSV",
            filetypes=(("CSV", "*.csv"), ("Todos los archivos", "*.*")),
            initialdir=str(DATA_DIR if DATA_DIR.exists() else ROOT),
        )
        if selected:
            self.selected_decision_file.set(selected)
            self.refresh_decisions()

    def choose_run_folder(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Carpeta de salida")
        if selected:
            self.experiment_vars["save_dir"].set(selected)

    def refresh_all(self) -> None:
        self.refresh_matches()
        self.refresh_decisions()
        self.refresh_runs()
        self._set_status(f"Actualizado · {datetime.now().strftime('%H:%M:%S')}")

    def refresh_matches(self) -> None:
        try:
            self.matches = load_matches(Path(self.selected_match_file.get()))
        except (DataError, OSError) as exc:
            messagebox.showerror("Error al leer partidas", str(exc), parent=self)
            self.matches = []
        self._populate_matches()
        self._update_dashboard()

    def _populate_matches(self) -> None:
        for item in self.match_tree.get_children():
            self.match_tree.delete(item)
        for row in self.matches:
            self.match_tree.insert(
                "", "end",
                values=(row.date, row.result, row.own_deck, row.opponent_deck, row.trophy_delta, row.notes),
            )

    def refresh_decisions(self) -> None:
        try:
            self.decisions = load_decisions(Path(self.selected_decision_file.get()))
        except (DataError, OSError, ValueError) as exc:
            messagebox.showerror("Error al leer decisiones", str(exc), parent=self)
            self.decisions = []
        self._populate_decisions()
        self._update_dashboard()

    def _populate_decisions(self) -> None:
        for item in self.decision_tree.get_children():
            self.decision_tree.delete(item)
        for row in self.decisions:
            self.decision_tree.insert(
                "", "end",
                values=(
                    row.match_id, f"{row.timestamp_seconds:.1f}", row.phase,
                    row.own_card, row.own_lane, row.decision_label, row.outcome_label,
                ),
            )
        stats = summarize_decisions(self.decisions)
        self.decision_summary.set(
            f"Filas: {stats['rows']} · Partidas: {stats['matches']} · "
            f"Etiquetadas: {stats['labeled']} · Con notas: {stats['notes']}"
        )

    def _update_dashboard(self) -> None:
        matches = summarize_matches(self.matches)
        decisions = summarize_decisions(self.decisions)
        self.metric_cards["matches"].set_value(str(matches["total"]))
        self.metric_cards["winrate"].set_value(f"{matches['win_rate']:.1f}%")
        self.metric_cards["trophies"].set_value(f"{matches['trophy_delta']:+d}")
        self.metric_cards["decisions"].set_value(str(decisions["labeled"]))
        self.result_chart.set_values([
            ("Victorias", matches["wins"]),
            ("Derrotas", matches["losses"]),
            ("Empates", matches["draws"]),
            ("Sin dato", matches["undecided"]),
        ])
        self.opponent_chart.set_values(matches["opponents"][:6], color=BLUE)
        self.dashboard_note.set(
            f"Historial: {self.selected_match_file.get()} · "
            f"Dataset de decisiones: {self.selected_decision_file.get()}"
        )

    def export_match_summary(self) -> None:
        summary = summarize_matches(self.matches)
        target = filedialog.asksaveasfilename(
            parent=self, title="Guardar resumen",
            defaultextension=".json", initialfile="axr_match_summary.json",
            filetypes=(("JSON", "*.json"),),
        )
        if not target:
            return
        try:
            write_json(Path(target), summary)
            self._set_status(f"Resumen guardado: {target}")
            messagebox.showinfo("Exportación terminada", f"Resumen guardado en:\n{target}", parent=self)
        except OSError as exc:
            messagebox.showerror("Error de exportación", str(exc), parent=self)

    def validate_decisions(self) -> None:
        try:
            rows = read_csv_rows(Path(self.selected_decision_file.get()))
            report = {
                "source": self.selected_decision_file.get(),
                "row_count": len(rows),
                "missing_decision_labels": sum(not (row.get("decision_label") or "").strip() for row in rows),
                "missing_outcome_labels": sum(not (row.get("outcome_label") or "").strip() for row in rows),
                "phases": dict(Counter((row.get("phase") or "unknown").strip() for row in rows)),
                "decisions": dict(Counter((row.get("decision_label") or "(sin etiqueta)").strip() for row in rows)),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "note": "Este informe valida cobertura básica, no calidad de etiquetas ni rendimiento de un modelo.",
            }
        except (DataError, OSError) as exc:
            messagebox.showerror("No se pudo validar", str(exc), parent=self)
            return
        target = filedialog.asksaveasfilename(
            parent=self, title="Guardar informe de decisiones",
            defaultextension=".json", initialfile="axr_decision_report.json",
            filetypes=(("JSON", "*.json"),),
        )
        if not target:
            return
        try:
            write_json(Path(target), report)
            messagebox.showinfo("Validación", f"Informe guardado en:\n{target}", parent=self)
            self._set_status(f"Informe de decisiones guardado: {target}")
        except OSError as exc:
            messagebox.showerror("Error al guardar", str(exc), parent=self)

    def _read_experiment_values(self) -> dict[str, Any]:
        variables = self.experiment_vars
        try:
            steps = int(variables["steps"].get())
            seed = int(variables["seed"].get())
            n_envs = int(variables["n_envs"].get())
            channels = int(variables["channels"].get())
            blocks = int(variables["blocks"].get())
        except ValueError as exc:
            raise ValueError("Los pasos, semilla y parámetros de red deben ser números enteros.") from exc
        if steps < 1:
            raise ValueError("Los pasos deben ser mayores que cero.")
        if n_envs < 1 or channels < 1 or blocks < 1:
            raise ValueError("Entornos, canales y bloques deben ser mayores que cero.")
        if variables["opponent"].get() not in {"random", "noop", "self"}:
            raise ValueError("Oponente inválido.")
        return {
            "total_steps": steps,
            "seed": seed,
            "n_envs": n_envs,
            "trunk_channels": channels,
            "trunk_blocks": blocks,
            "opponent": variables["opponent"].get(),
            "device": variables["device"].get(),
            "save_dir": variables["save_dir"].get().strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def save_experiment_plan(self) -> None:
        try:
            plan = self._read_experiment_values()
            save_dir = Path(plan["save_dir"]).expanduser()
            if not str(save_dir):
                raise ValueError("Elige una carpeta para guardar el plan.")
            manifest = {
                "project": APP_NAME,
                "app_version": APP_VERSION,
                "status": "planned",
                "training_plan": plan,
                "generated_by": "AXR Desktop",
                "warning": "Esto es un plan de configuración; no significa que el entrenamiento se haya ejecutado.",
            }
            target = save_dir / "axr_run_manifest.json"
            write_json(target, manifest)
            self._set_text(
                self.experiment_output,
                json.dumps(manifest, indent=2, ensure_ascii=False)
                + "\n\nNo se inició entrenamiento. Para ejecutarlo, verifica dependencias y revisa docs/ROYALEGYM_SETUP.md.",
            )
            self._set_status(f"Plan guardado: {target}")
            self.refresh_runs()
        except (ValueError, OSError) as exc:
            messagebox.showerror("Configuración inválida", str(exc), parent=self)

    def show_training_command(self) -> None:
        try:
            plan = self._read_experiment_values()
        except ValueError as exc:
            messagebox.showerror("Configuración inválida", str(exc), parent=self)
            return
        command = (
            f'py -m src.train_agent --steps {plan["total_steps"]} '
            f'--seed {plan["seed"]} --n-envs {plan["n_envs"]} '
            f'--opponent {plan["opponent"]} --device {plan["device"]} '
            f'--trunk-channels {plan["trunk_channels"]} '
            f'--trunk-blocks {plan["trunk_blocks"]} '
            f'--save-dir "{plan["save_dir"]}"'
        )
        self._set_text(
            self.experiment_output,
            "Comando sugerido para PowerShell:\n\n"
            + command
            + "\n\nNo lo ejecutes hasta instalar y comprobar RoyaleGym/RoyaleLearn. "
            "El comando es una propuesta de configuración, no un resultado verificado.",
        )
        self._set_status("Comando preparado; no se inició ningún proceso.")

    def refresh_runs(self) -> None:
        for item in self.run_tree.get_children():
            self.run_tree.delete(item)
        try:
            runs = list_runs(RUNS_DIR)
        except OSError as exc:
            self._set_status(f"No se pudieron listar experimentos: {exc}")
            return
        for run in runs:
            modified = datetime.fromtimestamp(run.modified).strftime("%Y-%m-%d %H:%M")
            self.run_tree.insert(
                "", "end",
                values=(run.name, run.status, run.details, modified, str(run.path)),
            )
        if not runs:
            self.run_tree.insert("", "end", values=("—", "sin datos", "Aún no hay manifiestos locales", "—", str(RUNS_DIR)))

    def open_selected_run(self) -> None:
        selection = self.run_tree.selection()
        if not selection:
            messagebox.showinfo("Selecciona un archivo", "Selecciona una fila primero.", parent=self)
            return
        values = self.run_tree.item(selection[0], "values")
        path = Path(values[-1])
        self._safe_open(path)

    def export_diagnostics(self) -> None:
        target = filedialog.asksaveasfilename(
            parent=self, title="Guardar diagnóstico AXR",
            defaultextension=".json", initialfile="axr_diagnostics.json",
            filetypes=(("JSON", "*.json"),),
        )
        if not target:
            return
        payload = {
            "application": APP_NAME,
            "version": APP_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "python": sys.version,
            "platform": sys.platform,
            "root": str(ROOT),
            "paths": {
                "matches_csv": self.selected_match_file.get(),
                "decisions_csv": self.selected_decision_file.get(),
                "runs_dir": str(RUNS_DIR),
            },
            "counts": {
                "matches": len(self.matches),
                "decision_rows": len(self.decisions),
                "run_manifests": len(list_runs(RUNS_DIR)),
            },
            "note": "No credentials or external account data are included.",
        }
        try:
            write_json(Path(target), payload)
            self._set_status(f"Diagnóstico exportado: {target}")
        except OSError as exc:
            messagebox.showerror("Error de diagnóstico", str(exc), parent=self)

    def _drain_background_events(self) -> None:
        """Reserved event queue for future long-running local analysis workers."""
        try:
            while True:
                kind, payload = self.background_events.get_nowait()
                if kind == "status":
                    self._set_status(str(payload))
                elif kind == "error":
                    messagebox.showerror("Tarea en segundo plano", str(payload), parent=self)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(150, self._drain_background_events)


def main() -> int:
    """Start the desktop UI; report startup errors without hiding the traceback."""
    try:
        app = AXRApp()
        app.mainloop()
        return 0
    except tk.TclError as exc:
        print(f"No se pudo iniciar la interfaz gráfica: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
