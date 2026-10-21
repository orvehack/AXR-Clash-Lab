"""AXR compact desktop console inspired by tabbed automation dashboards.

This is an original AXR interface. It does not copy py-clash-bot source code
or control the official game client. Long-running local tasks run in a worker
thread; training is launched only after explicit confirmation.
"""
from __future__ import annotations

import csv
import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RUNS = ROOT / "runs"
MATCHES = DATA / "matches.csv"
DARK, PANEL, TEXT, MUTED, ACCENT = "#101820", "#17232d", "#e7edf2", "#9eb0bf", "#54d6a0"


def read_matches() -> list[dict[str, str]]:
    if not MATCHES.exists():
        return []
    with MATCHES.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def manifests() -> list[tuple[str, str, str]]:
    found = []
    if RUNS.exists():
        for path in sorted(RUNS.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.name not in {"axr_run_manifest.json", "axr_training_status.json", "evaluation.json", "baseline.json"}:
                continue
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
                found.append((path.parent.name, str(obj.get("status", "unknown")), str(path)))
            except (OSError, json.JSONDecodeError):
                found.append((path.parent.name, "JSON inválido", str(path)))
    return found


class CompactAXR(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AXR Clash Lab 0.3.0")
        self.geometry("610x570")
        self.minsize(560, 510)
        self.configure(bg=DARK)
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.vars: dict[str, tk.StringVar] = {
            "steps": tk.StringVar(value="200000"),
            "seed": tk.StringVar(value="7"),
            "envs": tk.StringVar(value="4"),
            "channels": tk.StringVar(value="64"),
            "blocks": tk.StringVar(value="4"),
            "policy_lr": tk.StringVar(value="0.0002"),
            "critic_lr": tk.StringVar(value="0.0002"),
            "checkpoint": tk.StringVar(value="50000"),
            "opponent": tk.StringVar(value="random"),
            "device": tk.StringVar(value="auto"),
            "save_dir": tk.StringVar(value="runs/axr_0_3"),
        }
        self.status = tk.StringVar(value="Listo · investigación offline")
        self._styles()
        self._header()
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        self._home_tab()
        self._training_tab()
        self._matches_tab()
        self._runs_tab()
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(10, 5),
                  background=PANEL, foreground=ACCENT).pack(fill="x", side="bottom")
        self.refresh()
        self.after(120, self._poll)

    def _styles(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", font=("Segoe UI", 9), background=DARK, foreground=TEXT)
        s.configure("TFrame", background=DARK)
        s.configure("Card.TFrame", background=PANEL, padding=10)
        s.configure("TLabel", background=DARK, foreground=TEXT)
        s.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        s.configure("Title.TLabel", font=("Segoe UI Semibold", 17), background=DARK, foreground=TEXT)
        s.configure("TButton", padding=(7, 4))
        s.configure("TNotebook", background=DARK, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(10, 6))
        s.configure("Treeview", rowheight=23, background=PANEL, fieldbackground=PANEL, foreground=TEXT)
        s.configure("Treeview.Heading", background="#263746", foreground=TEXT)

    def _header(self) -> None:
        top = ttk.Frame(self, padding=(12, 10, 12, 6))
        top.pack(fill="x")
        ttk.Label(top, text="AXR CLASH LAB", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="↻ Actualizar", command=self.refresh).pack(side="right")
        ttk.Label(self, text="Consola compacta · simulación y análisis local", foreground=MUTED).pack(anchor="w", padx=14)

    def _tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(frame, text=title)
        return frame

    def _home_tab(self) -> None:
        f = self._tab("Panel")
        ttk.Label(f, text="Estado del laboratorio", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 8))
        self.summary = tk.StringVar(value="Cargando datos…")
        ttk.Label(f, textvariable=self.summary, justify="left", wraplength=520,
                  background=PANEL, padding=12).pack(fill="x")
        ttk.Label(f, text="Acciones rápidas", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(14, 6))
        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Button(row, text="Abrir carpeta runs", command=lambda: self._open(RUNS)).pack(side="left", padx=(0, 5))
        ttk.Button(row, text="Abrir CSV de partidas", command=lambda: self._open(MATCHES)).pack(side="left", padx=5)
        ttk.Button(row, text="Preparar plan", command=self.plan_only).pack(side="left", padx=5)
        ttk.Label(f, text="Los CSV incluidos en el repositorio pueden ser ficticios. Esta pantalla distingue datos locales de resultados verificados.",
                  wraplength=520, foreground=MUTED).pack(anchor="w", pady=(15, 0))

    def _training_tab(self) -> None:
        f = self._tab("IA / PPO")
        f.columnconfigure(1, weight=1)
        fields = [
            ("Pasos", "steps"), ("Semilla", "seed"), ("Entornos paralelos", "envs"),
            ("Canales de red", "channels"), ("Bloques de red", "blocks"),
            ("Learning rate actor", "policy_lr"), ("Learning rate crítico", "critic_lr"),
            ("Checkpoint cada", "checkpoint"),
        ]
        for i, (label, key) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Entry(f, textvariable=self.vars[key], width=16).grid(row=i, column=1, sticky="ew", pady=3)
        row = len(fields)
        ttk.Label(f, text="Oponente").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(f, textvariable=self.vars["opponent"], values=("random", "noop", "self"),
                     state="readonly", width=13).grid(row=row, column=1, sticky="w", pady=3)
        ttk.Label(f, text="Dispositivo").grid(row=row + 1, column=0, sticky="w", pady=3)
        ttk.Combobox(f, textvariable=self.vars["device"], values=("auto", "cpu", "cuda"),
                     state="readonly", width=13).grid(row=row + 1, column=1, sticky="w", pady=3)
        ttk.Label(f, text="Carpeta de salida").grid(row=row + 2, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.vars["save_dir"]).grid(row=row + 2, column=1, sticky="ew", pady=3)
        buttons = ttk.Frame(f)
        buttons.grid(row=row + 3, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        ttk.Button(buttons, text="Guardar plan (no entrena)", command=self.plan_only).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="▶ Ejecutar entrenamiento", command=self.start_training).pack(side="left")
        self.output = tk.Text(f, height=4, bg=PANEL, fg=TEXT, insertbackground=TEXT, wrap="word",
                              relief="flat", font=("Consolas", 8))
        self.output.grid(row=row + 4, column=0, columnspan=2, sticky="nsew", pady=(7, 0))
        f.rowconfigure(row + 4, weight=1)

    def _matches_tab(self) -> None:
        f = self._tab("Partidas")
        self.match_summary = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.match_summary, justify="left").pack(anchor="w", pady=(0, 8))
        self.match_tree = ttk.Treeview(f, columns=("date", "result", "deck", "opp", "delta"),
                                       show="headings", height=12)
        for col, label, width in (("date", "Fecha", 100), ("result", "Resultado", 85),
                                  ("deck", "Tu mazo", 100), ("opp", "Mazo rival", 100), ("delta", "Trofeos", 70)):
            self.match_tree.heading(col, text=label)
            self.match_tree.column(col, width=width, anchor="w")
        self.match_tree.pack(fill="both", expand=True)
        ttk.Label(f, text="No se agregan victorias ficticias: solo se muestran filas del CSV local.",
                  foreground=MUTED).pack(anchor="w", pady=(7, 0))

    def _runs_tab(self) -> None:
        f = self._tab("Experimentos")
        self.run_tree = ttk.Treeview(f, columns=("name", "status", "path"), show="headings", height=14)
        for col, label, width in (("name", "Experimento", 120), ("status", "Estado", 100), ("path", "Manifiesto", 300)):
            self.run_tree.heading(col, text=label)
            self.run_tree.column(col, width=width, anchor="w")
        self.run_tree.pack(fill="both", expand=True)
        ttk.Button(f, text="Abrir manifiesto seleccionado", command=self.open_selected).pack(anchor="w", pady=(8, 0))

    def _read_config(self) -> dict[str, Any]:
        try:
            cfg = {
                "steps": int(self.vars["steps"].get()), "seed": int(self.vars["seed"].get()),
                "n_envs": int(self.vars["envs"].get()), "trunk_channels": int(self.vars["channels"].get()),
                "trunk_blocks": int(self.vars["blocks"].get()), "policy_lr": float(self.vars["policy_lr"].get()),
                "critic_lr": float(self.vars["critic_lr"].get()), "checkpoint_every": int(self.vars["checkpoint"].get()),
            }
        except ValueError as exc:
            raise ValueError("Revisa los campos numéricos: hay un valor inválido.") from exc
        if cfg["steps"] < 1 or cfg["seed"] < 0 or cfg["n_envs"] < 1 or cfg["trunk_channels"] < 1 or cfg["trunk_blocks"] < 1 or cfg["checkpoint_every"] < 1:
            raise ValueError("Pasos, entornos, red y checkpoint deben ser positivos; la semilla no puede ser negativa.")
        if not 0 < cfg["policy_lr"] <= .01 or not 0 < cfg["critic_lr"] <= .01:
            raise ValueError("Las tasas de aprendizaje deben estar entre 0 y 0.01.")
        cfg.update(opponent=self.vars["opponent"].get(), device=self.vars["device"].get(),
                   save_dir=self.vars["save_dir"].get().strip())
        if not cfg["save_dir"]:
            raise ValueError("Indica una carpeta de salida.")
        return cfg

    def _command(self, cfg: dict[str, Any], plan_only: bool) -> list[str]:
        cmd = [sys.executable, "-m", "src.train_agent",
               "--steps", str(cfg["steps"]), "--seed", str(cfg["seed"]),
               "--n-envs", str(cfg["n_envs"]), "--trunk-channels", str(cfg["trunk_channels"]),
               "--trunk-blocks", str(cfg["trunk_blocks"]), "--policy-lr", str(cfg["policy_lr"]),
               "--critic-lr", str(cfg["critic_lr"]), "--checkpoint-every", str(cfg["checkpoint_every"]),
               "--opponent", cfg["opponent"], "--device", cfg["device"], "--save-dir", cfg["save_dir"]]
        if plan_only:
            cmd.append("--plan-only")
        return cmd

    def plan_only(self) -> None:
        try:
            cfg = self._read_config()
            cmd = self._command(cfg, True)
            result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=90)
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
            self._show_output(output or f"El comando terminó con código {result.returncode}.")
            self.status.set("Plan generado" if result.returncode == 0 else "Falló la preparación del plan")
            self.refresh()
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            messagebox.showerror("No se pudo preparar el plan", str(exc), parent=self)

    def start_training(self) -> None:
        try:
            cfg = self._read_config()
        except ValueError as exc:
            messagebox.showerror("Configuración inválida", str(exc), parent=self)
            return
        if not messagebox.askyesno("Confirmar entrenamiento",
                "Esto intentará importar RoyaleGym/RoyaleLearn y ejecutar entrenamiento real. "
                "Puede consumir CPU/GPU y tiempo. Si faltan dependencias, fallará sin entrenar. ¿Continuar?",
                parent=self):
            return
        command = self._command(cfg, False)
        self.status.set("Entrenamiento iniciado…")
        self._show_output("Ejecutando: " + subprocess.list2cmdline(command))
        threading.Thread(target=self._run_process, args=(command,), daemon=True).start()

    def _run_process(self, command: list[str]) -> None:
        try:
            proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.events.put(("process", (proc.returncode, proc.stdout, proc.stderr)))
        except OSError as exc:
            self.events.put(("error", str(exc)))

    def _show_output(self, value: str) -> None:
        self.output.delete("1.0", "end")
        self.output.insert("1.0", value[-12000:])

    def refresh(self) -> None:
        try:
            rows = read_matches()
            wins = sum((r.get("result", "").strip().casefold() in {"win", "won", "victoria", "ganada"}) for r in rows)
            losses = sum((r.get("result", "").strip().casefold() in {"loss", "lost", "derrota", "perdida"}) for r in rows)
            self.summary.set(f"Partidas CSV: {len(rows)}\nVictorias registradas: {wins} · Derrotas registradas: {losses}\n"
                             f"Manifiestos locales: {len(manifests())}\nMotor de simulación: requiere prueba de integración\n"
                             "Entrenamiento ejecutado: solo se confirma leyendo el estado guardado.")
            self.match_summary.set(f"{len(rows)} filas encontradas en {MATCHES.name}. El CSV del repositorio puede contener ejemplos ficticios.")
            for item in self.match_tree.get_children():
                self.match_tree.delete(item)
            for r in rows:
                self.match_tree.insert("", "end", values=(r.get("date", ""), r.get("result", ""),
                    r.get("own_deck", ""), r.get("opponent_deck", ""), r.get("trophy_delta", "")))
            for item in self.run_tree.get_children():
                self.run_tree.delete(item)
            for name, status, path in manifests():
                self.run_tree.insert("", "end", values=(name, status, path))
        except (OSError, csv.Error) as exc:
            self.status.set(f"Error al leer datos: {exc}")

    def open_selected(self) -> None:
        selected = self.run_tree.selection()
        if not selected:
            messagebox.showinfo("Experimentos", "Selecciona un manifiesto primero.", parent=self)
            return
        path = Path(self.run_tree.item(selected[0], "values")[2])
        self._open(path)

    def _open(self, path: Path) -> None:
        try:
            path = path.resolve()
            if not path.exists():
                if path == RUNS.resolve():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    messagebox.showinfo("Todavía no existe", f"No se encontró:\n{path}", parent=self)
                    return
            import os
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("No se pudo abrir", str(exc), parent=self)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "error":
                    self.status.set("No se pudo iniciar el proceso")
                    messagebox.showerror("Entrenamiento", payload, parent=self)
                elif kind == "process":
                    code, stdout, stderr = payload
                    self._show_output((stdout or "") + ("\n" + stderr if stderr else ""))
                    self.status.set("Entrenamiento finalizado" if code == 0 else f"Proceso terminó con código {code}; revisa dependencias/log")
                    self.refresh()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(120, self._poll)


def main() -> int:
    app = CompactAXR()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
