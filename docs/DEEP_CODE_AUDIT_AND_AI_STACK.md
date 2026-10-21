# Auditoría profunda del código y del stack de IA

Fecha de revisión: 2026-10-20. Esta auditoría se basa en lectura de archivos del repositorio y del código upstream consultado. **No equivale a ejecutar el proyecto**: todavía no se han validado en Windows las dependencias, el motor Rust, el entrenamiento ni la interfaz.

## Hallazgos prioritarios en AXR Clash Lab

### 1. `src/train_agent.py`: problemas encontrados y correcciones aplicadas
- **Corregido:** se consolidó `write_run_manifest` en una única definición.
- **Corregido:** el bloque de entrada se movió al final del archivo, después de las funciones auxiliares.
- **Corregido:** las escrituras de JSON, JSONL y Markdown usan saltos de línea reales.
- **Corregido:** se añadió la importación de `os` para recopilar `cpu_count`.
- La rutina de plan/preflight debe distinguir con claridad entre un plan guardado, una prueba técnica y un entrenamiento terminado. Un manifiesto no demuestra que el agente haya aprendido.

**Pruebas añadidas, aún pendientes de ejecución confirmada:** `tests/test_train_agent.py` cubre argumentos, manifiesto, eventos y tarjeta de experimento. También se añadió soporte opcional de `--warm-start` y exportación del actor mediante RoyaleImitate.

### 2. Dataset y evaluación
- `src/decision_dataset.py` ya cubre validación, huellas de filas, duplicados, balance de etiquetas, particiones agrupadas, detección de fuga y exportación de auditoría. Antes de conectarlo a una red neuronal, hay que acordar un esquema de observación/acción que corresponda exactamente al entorno de entrenamiento.
- `src/match_stats.py` resume resultados humanos; `src/royalegym_baseline.py` evalúa políticas del simulador. No mezclar esas dos fuentes como si fueran la misma distribución: una partida registrada y un episodio simulado deben llevar etiquetas de origen distintas.
- El baseline debe seguir siendo el control de comparación. No declarar que una red es mejor por una única partida ni por recompensa de entrenamiento: usar semillas reservadas, varias partidas, tasa de victoria con intervalo de confianza, coronas y métricas de calidad de datos.
- **Corrección aplicada en `src/royalegym_baseline.py`:** al terminar un episodio, las coronas disponibles determinan el resultado. Si el entorno no informa coronas terminales, el resultado queda como `unknown`; la recompensa moldeada no se trata como una victoria real.
- **Corrección aplicada en `src/model_registry.py`:** la promoción también requiere que el límite inferior de un intervalo bootstrap pareado del 95% sea mayor que cero. Es una barrera conservadora, no una garantía universal.

### 3. Contrato del simulador
- `src/simulator_adapter.py` es una sonda diagnóstica, no un adaptador completo de decisiones.
- `src/royalegym_contract.py` prueba un contrato de dos asientos, máscaras y llamadas `step` con `MockEngine`. Eso es útil para detectar incompatibilidades de API, pero **no valida el motor Rust ni el realismo de las partidas**.
- El entorno upstream actual define observaciones por asiento con `action_mask`; cada acción elegida debe respetar la máscara. La implementación actual de RoyaleGym declara `ClashParallelEnv`, además de wrappers Gym y vectoriales. AXR debe fijar versiones compatibles antes de comparar resultados de distintas revisiones.

### 4. UI y emuladores
- `src/axr_desktop.py` ya tiene paneles de dashboard, partidas, decisiones, experimentos, ejecuciones y ajustes.
- `src/emulator_manager.py` es principalmente un lanzador/diagnóstico. Encontrar el ejecutable no equivale a seleccionar correctamente una instancia concreta ni a verificar que ADB esté conectado.
- Conviene separar la UI de los trabajos largos: la interfaz muestra estado y logs; los procesos de entrenamiento escriben eventos estructurados y archivos de resultado. No bloquear el hilo principal de Tkinter.

## Modelos de IA que sí conviene combinar

### A. Baseline heurístico de AXR
Código local: [`src/royalegym_baseline.py`](../src/royalegym_baseline.py).

Rol: referencia barata, control de humo y política de reserva. No es una IA avanzada; sirve para comprobar que una red mejora algo medible.

### B. PPO / aprendizaje por refuerzo — RoyaleLearn + RoyaleGym
Fuentes: [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym), [RoyaleLearn](https://github.com/RoyaleGym/RoyaleLearn).

Rol: modelo principal que aprende mediante episodios simulados. El proyecto actual ya tiene `src/train_agent.py` como entrada de entrenamiento prevista. El entorno usa una máscara de acciones legales y puede jugar contra oponentes de referencia o contra versiones anteriores de sí mismo.

Riesgo: el entrenamiento todavía no está verificado en el equipo del usuario. El rendimiento en un motor de simulación no prueba rendimiento en el cliente oficial.

### C. Aprendizaje por imitación — RoyaleImitate
Fuente: [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate).

Rol: enseñar una política inicial a partir de demostraciones, antes de afinarla con PPO. La API upstream consultada ofrece `record`, `from_replays`, `clone` y `save_actor`; el artefacto guarda huellas y observaciones de prueba para comprobar compatibilidad. Su README muestra explícitamente el flujo: entrenar una política, guardar el actor y usar `extensions={"warm_start": {"init": {"path": ..., "sha256": ...}}}` en el siguiente `Learner`.

**Integración propuesta:** demostraciones permitidas → shards con partición de validación → clonación supervisada → artefacto verificado → warm start de PPO → evaluación contra el baseline y oponentes guardados. No usar datos de validación para entrenar ni asumir que una demostración es buena sólo porque ganó.

### D. Self-play y liga de oponentes
Fuente: implementación de `OpponentPool` en [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym).

Rol: enfrentar la política actual con versiones anteriores y rivales de referencia, evitando que aprenda sólo a vencer a un rival débil. Mantener snapshots y semillas, y promover una versión sólo si supera la evaluación predefinida.

### E. RoyaleViser — visualización, no un modelo
Fuente: [RoyaleViser](https://github.com/RoyaleGym/RoyaleViser).

Rol: observar batallas simuladas en vivo o reproducir archivos guardados. Complementa la UI AXR, pero no toma decisiones ni entrena por sí mismo. La UI puede abrirlo como herramienta opcional después de confirmar instalación.

### F. Modelo de visión para vídeos/repeticiones
Rol futuro: detectar cartas, elixir, temporizadores y eventos en vídeos que el usuario proporcione y tenga derecho a analizar. Mantenerlo separado del actor PPO: primero convierte imágenes en observaciones estructuradas y registra confianza/errores; sólo después se usa para construir datos etiquetados. No conectar todavía detección de pantalla a automatización de partidas competitivas.

### G. Modelos externos de investigación
- [FirstLight_CR](https://github.com/Jaasssoooonnnnn/FirstLight_CR) describe una arquitectura de imitación + PPO self-play, evaluación por parejas y política recurrente. Es una referencia técnica interesante, pero usa su propio motor/datos/modelos y una configuración de juego concreta; no se puede enchufar directamente al actor de RoyaleLearn.
- [ClashAI](https://github.com/vegetableleaf/ClashAI) describe una pipeline de replays, imitación y RL con motor propio. Sus dependencias, datos y licencia de cada componente requieren una auditoría independiente antes de reutilizar código.
- [MSU-AI/clash-royale-gym](https://github.com/MSU-AI/clash-royale-gym) presenta un entorno antiguo de investigación con observación de píxeles y documentación que advierte que parte del ejemplo puede estar desactualizada. Mantenerlo como referencia histórica, no como dependencia principal.

No se deben copiar pesos, código o datasets sin verificar licencia, formato de observaciones, compatibilidad del motor y procedencia de los datos.

## Arquitectura cooperativa recomendada

```text
Vídeos/repeticiones autorizados ──> extractor/etiquetador ──> dataset auditado
                                                        │
                                                        v
Baseline heurístico ─────────────────────────────> evaluación comparativa
                                                        ^
                                                        │
dataset de demostraciones ──> RoyaleImitate ──> actor inicial
                                                        │
                                                        v
                                              RoyaleLearn / PPO
                                                        │
                                             self-play / liga
                                                        │
                                                        v
                                           evaluación por semillas
                                                        │
                                  promoción sólo si supera el baseline
                                                        │
                                                        v
                                  RoyaleViser + panel de experimentos AXR
```

No recomiendo mezclar directamente probabilidades/logits de redes distintas: pueden usar entradas, escalas y semánticas de acción diferentes. La cooperación inicial debe ser por etapas y con contratos claros: imitación inicializa PPO; la heurística sirve de referencia/respaldo; self-play genera presión de entrenamiento; el evaluador decide qué checkpoint conservar; visión produce datos y no manda acciones directamente.

## Próximos pasos técnicos
1. Probar en CI la limpieza de `src/train_agent.py` antes de lanzar entrenamientos largos.
2. **Añadido:** `src/imitate_agent.py` prepara shards desde replays y ejecuta `RoyaleImitate.clone`; exporta el actor y un informe. Las pruebas de argumentos están en `tests/test_imitate_agent.py`.
3. **Añadido:** `src/registry_bridge.py` conecta los JSON de `royalegym_baseline.py` con `model_registry.py`, omitiendo resultados `unknown`/`limit` y rechazando semillas duplicadas. Falta ejecutar la integración en un entorno RoyaleGym instalado.
4. Registrar versiones de RoyaleGym/RoyaleLearn/RoyaleImitate/RoyaleSim, configuración del entorno, huella del modelo y métricas.
5. Conectar la UI a estado/logs de entrenamiento sin bloquearla.
6. Sólo después, integrar visión para vídeos y comparar su estado extraído contra anotaciones humanas.
7. **Añadido:** `src/doctor.py` comprueba el entorno sin instalar nada; `scripts/first_run_windows.ps1` prepara `.venv`, ejecuta las pruebas offline y valida los planes sin descargar modelos. El flujo de GitHub Actions ahora también ejecuta estas comprobaciones de humo. El resultado de CI debe revisarse en GitHub antes de considerar el paso validado.

## Fuentes primarias revisadas
- [RoyaleGym README](https://github.com/RoyaleGym/RoyaleGym)
- [RoyaleGym environment](https://github.com/RoyaleGym/RoyaleGym/blob/main/royalegym/env.py)
- [RoyaleGym action masks](https://github.com/RoyaleGym/RoyaleGym/blob/main/royalegym/action.py)
- [RoyaleLearn Learner API](https://github.com/RoyaleGym/RoyaleLearn/blob/main/royalelearn/learner.py)
- [RoyaleImitate README](https://github.com/RoyaleGym/RoyaleImitate)
- [RoyaleImitate cloning API](https://github.com/RoyaleGym/RoyaleImitate/blob/main/royaleimitate/cloning.py)
- [RoyaleImitate actor artifacts](https://github.com/RoyaleGym/RoyaleImitate/blob/main/royaleimitate/artifacts.py)
- [RoyaleViser README](https://github.com/RoyaleGym/RoyaleViser)
- [FirstLight_CR README](https://github.com/Jaasssoooonnnnn/FirstLight_CR)
- [ClashAI README](https://github.com/vegetableleaf/ClashAI)
- [MSU-AI Clash Royale Gym](https://github.com/MSU-AI/clash-royale-gym)


## Nueva pieza añadida: registro y selección de modelos

- `src/model_registry.py` registra evaluaciones JSONL, resume resultados, crea manifiestos de artefactos con SHA-256 y compara modelos por semillas comunes con una barrera bootstrap pareada del 95%.
- `src/registry_bridge.py` convierte informes de evaluación del baseline en registros JSONL y no importa episodios sin resultado verificable.
- `tests/test_registry_bridge.py` cubre conversión de resultados válidos, omisión de episodios no clasificados, rechazo de semillas duplicadas y validación del nombre del agente fuente.
- `src/doctor.py` y `scripts/first_run_windows.ps1` agregan una primera comprobación local guiada sin instalar todavía el stack pesado de IA.
- `tests/test_model_registry.py` cubre ida y vuelta JSONL, umbral mínimo de pruebas pareadas, promoción, semillas duplicadas, huellas de artefactos y un caso donde la mejora aparente no basta por incertidumbre.
- La promoción queda en `unverified` por defecto. La comparación no ejecuta modelos, no crea resultados falsos y no sustituye una evaluación real del simulador.
- Para una primera prueba real, el evaluador existente debe exportar resultados con `model_id`, `seed`, `opponent_id`, `outcome` y, cuando existan, coronas y duración. Luego se pueden comparar checkpoints en condiciones pareadas.

Comando previsto:

```powershell
python -m src.model_registry compare --evaluations runs/evaluations.jsonl --candidate axr-v2 --baseline axr-v1 --opponent league-v1 --minimum-pairs 30
```

Todavía falta conectar el evaluador de RoyaleGym a este formato y ejecutar las pruebas.
