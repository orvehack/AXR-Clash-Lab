# AXR Clash Lab 🧪⚔️

**AXR Clash Lab** es un laboratorio modular para analizar partidas de Clash Royale, estudiar decisiones y desarrollar una IA en un entorno de simulación. La idea es construir una aplicación de escritorio con una interfaz inspirada en la organización visual de **py-clash-bot**, pero con funciones propias de análisis, entrenamiento y visualización.

> Estado real: la base del proyecto y algunas herramientas de análisis ya existen. La interfaz gráfica final, la integración completa del simulador y el modelo entrenado todavía están pendientes.

## Objetivos

- Registrar resultados, mazos, cambios de trofeos y notas.
- Resumir victorias/derrotas y analizar rivales desde CSV.
- Crear un formato para etiquetar decisiones de partidas y replays.
- Integrar un simulador offline para experimentar con políticas de IA.
- Preparar una ruta de aprendizaje por imitación y, más adelante, entrenamiento por refuerzo.
- Construir una interfaz de escritorio clara para estadísticas, partidas, entrenamiento, modelos y registros.
- Mantener módulos separados para poder probarlos y cambiarlos sin rehacer todo el proyecto.

## Estado actual

### Implementado en el repositorio
- Registro de ejemplo en `data/matches.csv` (los registros incluidos son ficticios).
- Analizador inicial de partidas en `src/analyze_matches.py`.
- Estadísticas reutilizables y CLI en `src/match_stats.py`.
- Pruebas unitarias iniciales en `tests/test_match_stats.py`.
- Plantilla para etiquetar decisiones en `data/decisions_template.csv`.
- Hoja de ruta y arquitectura propuesta en `docs/ROADMAP.md` y `docs/AI_ARCHITECTURE.md`.
- Adaptador de diagnóstico para comprobar la instalación y describir el entorno de RoyaleGym, sin ejecutar acciones de juego, en `src/simulator_adapter.py`.
- Pruebas con un entorno simulado para ese adaptador en `tests/test_simulator_adapter.py`.
- Instrucciones de instalación y diagnóstico para Windows en `docs/ROYALEGYM_SETUP.md`.
- Auditoría inicial de proyectos externos y estrategia de integración en `docs/INTEGRATION_AUDIT.md`.

### Todavía pendiente
- Ejecutar y verificar las pruebas en la PC de desarrollo.
- Confirmar la instalación y API de RoyaleGym en ese entorno.
- Implementar una primera política de IA y evaluación reproducible.
- Diseñar e implementar la interfaz gráfica de AXR.
- Crear herramientas de análisis de video offline y etiquetado asistido.
- Entrenar y evaluar modelos con datos reales autorizados.

## Proyectos externos que estamos estudiando

Estos proyectos tienen responsabilidades diferentes; no se deben mezclar todos sus archivos a ciegas.

| Proyecto | Posible función en AXR |
|---|---|
| [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym) | Entorno de aprendizaje y observaciones/acciones del bot |
| [RoyaleSim](https://github.com/RoyaleGym/RoyaleSim) | Motor de batallas offline |
| [RoyaleLearn](https://github.com/RoyaleGym/RoyaleLearn) | Referencia para entrenamiento |
| [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate) | Referencia para aprendizaje por imitación |
| [RoyaleViser](https://github.com/RoyaleGym/RoyaleViser) | Referencia para visualizar partidas |
| [RoyaleBot](https://github.com/RoyaleGym/RoyaleBot) | Proyecto separado de ejecución de bots; requiere revisión específica antes de considerar cualquier uso |
| [py-clash-bot](https://github.com/pyclashbot/py-clash-bot) | Referencia de organización de la interfaz y módulos de escritorio |
| [ClashRoyaleBuildABot](https://github.com/Pbatch/ClashRoyaleBuildABot) | Investigar componentes reutilizables de percepción/estado y sus dependencias |

La integración se hará por módulos, revisando APIs, licencias y dependencias, y conservando avisos de licencia cuando corresponda. Que un repositorio sea público no significa que su código ya esté integrado en AXR.

## Interfaz prevista

La interfaz propia de AXR aspira a reunir:
- **Panel principal:** estado del proyecto y resumen de estadísticas.
- **Partidas y análisis:** historial, mazos, rivales, resultados y notas.
- **Replays y datos:** anotación manual y herramientas de análisis offline.
- **Laboratorio de IA:** configuración de experimentos, entrenamiento y evaluaciones.
- **Visor de simulaciones:** partidas guardadas y comparaciones entre políticas.
- **Registros y configuración:** diagnósticos, dependencias y preferencias.

La interfaz tomará inspiración visual de py-clash-bot, pero su diseño y funciones se adaptarán al laboratorio de AXR. No se promete compatibilidad visual exacta ni se reutiliza código de UI sin revisar primero sus condiciones de licencia.

## Inicio rápido

Requisitos previstos: Python 3.12 para la integración actual con RoyaleGym; Git.

Consulta:
- [Inicio en Windows](docs/QUICKSTART_WINDOWS.md)
- [Preparación de RoyaleGym](docs/ROYALEGYM_SETUP.md)
- [Arquitectura de IA](docs/AI_ARCHITECTURE.md)
- [Auditoría de integración](docs/INTEGRATION_AUDIT.md)
- [Hoja de ruta](docs/ROADMAP.md)

## Límites y seguridad

AXR está pensado para investigación, análisis offline y simulación. No automatiza partidas competitivas en el cliente oficial ni intenta eludir mecanismos antitrampas. El proyecto no está afiliado, respaldado ni patrocinado por Supercell.
