# AXR Clash Lab 🧪⚔️

**AXR Clash Lab** es un laboratorio modular para analizar partidas de Clash Royale, preparar datos de decisiones, lanzar un emulador Android local y desarrollar agentes de IA mediante simulación offline.

La aplicación de escritorio de AXR tiene una interfaz propia inspirada en patrones comunes de paneles de control. **No copia archivos fuente, imágenes ni rutinas internas de py-clash-bot.**

> **Estado honesto:** el repositorio contiene módulos iniciales de estadísticas, preparación de datos, interfaz, evaluación, configuración de entrenamiento y gestión de emuladores. La compatibilidad real con cada versión de RoyaleGym/RoyaleLearn y la ejecución en el PC del usuario todavía requieren pruebas.

## Funciones y módulos

| Ruta | Responsabilidad |
|---|---|
| `src/axr_desktop.py` | Interfaz de escritorio y paneles locales |
| `src/doctor.py` | Diagnóstico local sin instalar paquetes ni ejecutar el juego |
| `scripts/first_run_windows.ps1` | Primera comprobación guiada de Windows 11: entorno virtual, pruebas y planes de prueba |
| `src/match_stats.py` | Métricas de partidas y trofeos desde CSV |
| `src/analyze_matches.py` | Analizador inicial por CLI |
| `src/decision_dataset.py` | Validación y auditoría de ejemplos etiquetados |
| `src/simulator_adapter.py` | Diagnóstico de instalación y espacios de RoyaleGym sin ejecutar acciones |
| `src/royalegym_contract.py` | Prueba corta de contrato `reset/step` con `MockEngine` y acciones legales |
| `src/royalegym_baseline.py` | Agentes de referencia y evaluación offline |
| `src/model_registry.py` | Model artifact manifests, SHA-256 fingerprints, paired evaluation, and uncertainty-aware promotion gates. |
| `src/registry_bridge.py` | Converts baseline JSON results to registry JSONL, skipping unverified outcomes. |
| `src/imitate_agent.py` | Replay-to-imitation pipeline; creates an actor artifact for PPO warm-start. |
| `src/train_agent.py` | Configuración y punto de entrada de entrenamiento |
| `src/emulator_manager.py` | Detección, diagnóstico y lanzamiento local de MEmu/BlueStacks |
| `data/matches.csv` | Partidas de ejemplo ficticias |
| `data/decisions_template.csv` | Plantilla para decisiones etiquetadas |
| `tests/` | Pruebas unitarias de los contratos locales |
| `.github/workflows/tests.yml` | Flujo de pruebas de GitHub Actions |

## Primera ejecución en Windows 11

Para preparar el proyecto sin instalar todavía PyTorch ni las dependencias grandes de IA, abre PowerShell en la carpeta del repositorio y ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\first_run_windows.ps1
```

El cambio de política solo dura en esa ventana de PowerShell. El script crea `.venv`, ejecuta el diagnóstico, las pruebas offline y los modos `--plan-only`; después te pregunta si quieres abrir la interfaz. **No instala el stack de entrenamiento ni demuestra que RoyaleGym funcione.** Consulta [la guía paso a paso](docs/QUICKSTART_WINDOWS.md) si prefieres hacerlo manualmente.

Diagnóstico manual:

```powershell
.\.venv\Scripts\python.exe -m src.doctor
```

## Lanzamiento de emuladores

AXR tiene un botón **▶ Start emulador** en la cabecera de la interfaz. El botón pregunta si quieres abrir MEmu o BlueStacks 5 y lanza el ejecutable local detectado. También puedes usar la CLI de abajo. No instala el emulador ni inicia sesión o partida.

Desde PowerShell, en la raíz del repositorio:

```powershell
py -m src.emulator_manager detect
py -m src.emulator_manager diagnostics
py -m src.emulator_manager start --emulator memu
# O para BlueStacks 5:
py -m src.emulator_manager start --emulator bluestacks
py -m src.emulator_manager status
```

Si el emulador está instalado en una ruta no estándar, hay que configurar esa ruta en `src/emulator_manager.py` antes de usarlo. El usuario debe abrir el juego manualmente. El módulo no automatiza clics, despliegue de cartas, cola de partidas ni otras acciones del cliente oficial.

## Análisis y datos

```powershell
py -m unittest discover -s tests -v
py -m src.match_stats data/matches.csv
py -m src.decision_dataset data/decisions_template.csv
# Si RoyaleGym está instalado, comprueba su API Python de forma offline:
py -m src.royalegym_contract --steps 3
```

Los datos incluidos en `data/matches.csv` son **ficticios** y solo sirven para probar la estructura. No representan el historial real del usuario.

## Simulación y entrenamiento

AXR estudia estos proyectos por separado y con revisión de APIs/licencias:

- [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym): entorno de simulación.
- [RoyaleSim](https://github.com/RoyaleGym/RoyaleSim): motor de batallas.
- [RoyaleLearn](https://github.com/RoyaleGym/RoyaleLearn): entrenamiento.
- [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate): aprendizaje por imitación.
- [RoyaleViser](https://github.com/RoyaleGym/RoyaleViser): visualización de batallas guardadas.
- [ClashRoyaleBuildABot](https://github.com/Pbatch/ClashRoyaleBuildABot): referencia para investigar percepción/estado.
- [py-clash-bot](https://github.com/pyclashbot/py-clash-bot): referencia de funciones y organización de interfaz.

La presencia de un módulo de entrenamiento no significa que ya exista un modelo entrenado. Primero hay que instalar dependencias, verificar la API y ejecutar pruebas y experimentos reproducibles.

## Documentación

- [Inicio en Windows](docs/QUICKSTART_WINDOWS.md)
- [Preparación de RoyaleGym](docs/ROYALEGYM_SETUP.md)
- [Arquitectura de IA](docs/AI_ARCHITECTURE.md)
- [Auditoría de integración](docs/INTEGRATION_AUDIT.md)
- [Hoja de ruta](docs/ROADMAP.md)
- [Auditoría de py-clash-bot y emuladores](docs/PYCLASHBOT_RESEARCH.md)
- [Matriz de extracción técnica y pendientes](docs/EXTRACTION_MATRIX.md)
- [Prueba de contrato de RoyaleGym](docs/ROYALEGYM_SETUP.md)

## Licencias y límites

La licencia de py-clash-bot es **NC-CL-1.0** para el código y CC BY-NC-SA 4.0 para assets/documentación; por ello este repositorio no copia sus archivos fuente ni sus recursos gráficos. Se revisarán las licencias individuales antes de cualquier reutilización de código.

AXR se centra en investigación, análisis offline y simulación. No implementa evasión de antitrampas ni automatización de partidas competitivas en el cliente oficial. No está afiliado, respaldado ni patrocinado por Supercell.


## Auditoría de código y modelos cooperativos

- [Auditoría profunda y stack de IA](docs/DEEP_CODE_AUDIT_AND_AI_STACK.md): revisión de módulos actuales, riesgos de integración y arquitectura recomendada.
- [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate): opción para aprender de demostraciones y crear un actor inicial que luego se afina con PPO.
- [RoyaleViser](https://github.com/RoyaleGym/RoyaleViser): visor de partidas simuladas, no un modelo de IA.

El flujo cooperativo previsto es: dataset auditado → imitación → warm-start PPO → self-play/evaluación → promoción sólo si mejora al baseline. La integración de warm-start ya está disponible en `src/train_agent.py` mediante `--warm-start <carpeta-de-actor>`. Requiere un artefacto compatible creado por RoyaleImitate. Aún no se ha ejecutado el entrenamiento en Windows.


### Imitación → PPO

Primero valida la configuración sin descargar datos ni importar modelos:

```powershell
python -m src.imitate_agent --plan-only --matches 25 --out-dir runs/axr_imitation_smoke
```

Después de instalar las dependencias de imitación, prueba con un lote pequeño:

```powershell
python -m src.imitate_agent --matches 25 --epochs 2 --out-dir runs/axr_imitation_smoke
python -m src.train_agent --plan-only --steps 10000 --save-dir runs/axr_ppo_smoke --warm-start runs/axr_imitation_smoke/axr_imitation_actor
```

No es necesario empezar con miles de partidas. Primero hay que confirmar que el motor, los formatos de replay, la validación de demostraciones y la compatibilidad del actor funcionan.


### Model registry and promotion gates

AXR can record evaluation outcomes in JSONL and compare a candidate against a baseline using the same held-out seeds. It refuses promotion when there are too few paired evaluations, when the candidate does not reach the required score, when its improvement is too small, or when a deterministic 95% paired-bootstrap interval still includes zero.

Example:

```powershell
python -m src.model_registry compare --evaluations runs/evaluations.jsonl --candidate axr-v2 --baseline axr-v1 --opponent league-v1 --minimum-pairs 30
```

The command returns a non-zero exit code if promotion gates are not met. This is intentional: insufficient evidence must not be treated as success. The registry does not execute or validate the model itself. Simulator episodes without verifiable terminal crown counts are marked `unknown` instead of being mislabeled as wins based on shaped reward.

To import a saved baseline evaluation into the registry (only verified blue-seat outcomes are imported):

```powershell
py -m src.royalegym_baseline --agent lane-pressure --opponent random --episodes 30 --seed 5000 --output runs/axr_eval.json
py -m src.registry_bridge --input runs/axr_eval.json --model-id axr-lane-v1 --opponent-id random-v1 --output runs/evaluations.jsonl
```

The first command still requires a working RoyaleGym installation. The bridge does not invent results: `unknown` and `limit` episodes are skipped, and duplicate seeds are rejected.
