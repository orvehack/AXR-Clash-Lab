# AXR Clash Lab 🧪⚔️

**AXR Clash Lab** es un laboratorio modular para analizar partidas de Clash Royale, preparar datos de decisiones, lanzar un emulador Android local y desarrollar agentes de IA mediante simulación offline.

La aplicación de escritorio de AXR tiene una interfaz propia inspirada en patrones comunes de paneles de control. **No copia archivos fuente, imágenes ni rutinas internas de py-clash-bot.**

> **Estado honesto:** el repositorio contiene módulos iniciales de estadísticas, preparación de datos, interfaz, evaluación, configuración de entrenamiento y gestión de emuladores. La compatibilidad real con cada versión de RoyaleGym/RoyaleLearn y la ejecución en el PC del usuario todavía requieren pruebas.

## Funciones y módulos

| Ruta | Responsabilidad |
|---|---|
| `src/axr_desktop.py` | Interfaz de escritorio y paneles locales |
| `src/match_stats.py` | Métricas de partidas y trofeos desde CSV |
| `src/analyze_matches.py` | Analizador inicial por CLI |
| `src/decision_dataset.py` | Validación y auditoría de ejemplos etiquetados |
| `src/simulator_adapter.py` | Diagnóstico de instalación y espacios de RoyaleGym |
| `src/royalegym_baseline.py` | Agentes de referencia y evaluación offline |
| `src/train_agent.py` | Configuración y punto de entrada de entrenamiento |
| `src/emulator_manager.py` | Detección, diagnóstico y lanzamiento local de MEmu/BlueStacks |
| `data/matches.csv` | Partidas de ejemplo ficticias |
| `data/decisions_template.csv` | Plantilla para decisiones etiquetadas |
| `tests/` | Pruebas unitarias de los contratos locales |
| `.github/workflows/tests.yml` | Flujo de pruebas de GitHub Actions |

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

## Licencias y límites

La licencia de py-clash-bot es **NC-CL-1.0** para el código y CC BY-NC-SA 4.0 para assets/documentación; por ello este repositorio no copia sus archivos fuente ni sus recursos gráficos. Se revisarán las licencias individuales antes de cualquier reutilización de código.

AXR se centra en investigación, análisis offline y simulación. No implementa evasión de antitrampas ni automatización de partidas competitivas en el cliente oficial. No está afiliado, respaldado ni patrocinado por Supercell.
