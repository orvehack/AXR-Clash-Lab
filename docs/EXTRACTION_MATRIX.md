# Matriz de extracción técnica para AXR Clash Lab

Fecha de revisión: 2026-10-20.

Este documento separa lo que se observó en repositorios públicos, lo que conviene implementar de forma independiente y lo que aún debe probarse en Windows. **No significa que el código de terceros se haya copiado a AXR.**

## 1. py-clash-bot: qué encontramos en el código

Fuentes inspeccionadas directamente:

- [README](https://github.com/pyclashbot/py-clash-bot/blob/master/README.md)
- [pyproject.toml](https://github.com/pyclashbot/py-clash-bot/blob/master/pyproject.toml)
- [emulators/bluestacks.py](https://github.com/pyclashbot/py-clash-bot/blob/master/pyclashbot/emulators/bluestacks.py)
- [emulators/memu.py](https://github.com/pyclashbot/py-clash-bot/blob/master/pyclashbot/emulators/memu.py)
- [interface/config.py](https://github.com/pyclashbot/py-clash-bot/blob/master/pyclashbot/interface/config.py)
- [bot/fight.py](https://github.com/pyclashbot/py-clash-bot/blob/master/pyclashbot/bot/fight.py)

### Arquitectura observada

1. **Controladores por emulador.** BlueStacks y MEmu tienen clases separadas. Eso permite que el resto de la aplicación llame a una interfaz común sin asumir que todos los emuladores arrancan igual.
2. **BlueStacks específico por instancia.** El controlador lee configuración del registro y de bluestacks.conf, localiza el puerto ADB de la instancia y utiliza un serial dirigido a esa instancia. Encontrar HD-Player.exe por sí solo no equivale a seleccionar una instancia concreta.
3. **MEmu mediante pymemuc.** El controlador consulta VMs, encuentra o crea una instancia administrada y aplica configuración de resolución/recursos. La captura de pantalla se basa en ADB y decodificación de imágenes con OpenCV/NumPy.
4. **Configuración de interfaz basada en datos.** interface/config.py define estructuras dataclass para estadísticas, trabajos, radios y combos. Así se puede construir parte de la UI a partir de definiciones, en lugar de duplicar a mano cada control.
5. **Reconocimiento de pantalla y máquina de estados.** bot/fight.py y bot/state_detect.py muestran una arquitectura basada en capturas, comprobaciones visuales y pasos de estado. Es una implementación frágil ante cambios de interfaz y está vinculada al cliente del juego.
6. **Dependencias declaradas.** El paquete inspeccionado requiere Python >=3.12,<3.13 y declara OpenCV, NumPy, pymemuc, psutil, Pillow, pypresence y ttkbootstrap. No conviene copiar todas esas dependencias sin comprobar cuáles necesita AXR realmente.

### Qué adaptar a AXR de manera independiente

- Interfaz común EmulatorBackend con operaciones limitadas a detectar, iniciar, consultar estado y cerrar de forma segura.
- Rutas configurables, selección explícita de instancia y diagnósticos legibles.
- Catálogo de paneles/estadísticas declarativo para reducir código UI repetido.
- Captura de imágenes para **análisis offline** de capturas y vídeos aportados por el usuario.
- Registro estructurado de eventos, errores, tiempos de inicio y resultados de diagnóstico.

No se trasladan coordenadas de combate, selección automática de cartas, colas de partidas ni rutinas de juego competitivo. El objetivo es mantener separada la utilidad de emulador del laboratorio de IA offline.

## 2. RoyaleGym: interfaz real a verificar

El README consultado anuncia un simulador determinista con motor Rust, API de Gymnasium/PettingZoo, pasos de simulación de 50 ms y un espacio de acciones de 2305 movimientos. Documenta la instalación con pip install "royalegym[all]" y un ejemplo basado en make_env() y play_battle(). El README actual menciona Python 3.12, 3.13 y 3.14 en sus insignias, por lo que la guía de instalación debe seguir la versión publicada y no una nota antigua.

AXR ya tiene src/simulator_adapter.py, que intenta importar make_env, hacer un único reset y describir los espacios. No ejecuta step(). Este adaptador es una sonda diagnóstica; **todavía no es una integración de entrenamiento completa**.

Antes de conectar el entrenador hay que confirmar en el entorno instalado:
- forma, tipo y claves de las observaciones;
- tipo y máscara de acciones legales;
- formato de reset() y step();
- cómo se guardan y vuelven a cargar las batallas;
- si la API instalada coincide con la versión documentada.

## 3. Estado de AXR y trabajo pendiente

| Área | Estado en el repositorio | Siguiente trabajo |
|---|---|---|
| UI de escritorio | Existe src/axr_desktop.py y botón para lanzar emulador | Mejorar selección de ruta/instancia, estados visibles y logs |
| Lanzamiento de emulador | src/emulator_manager.py detecta rutas comunes y lanza el proceso GUI | Configuración persistente, instancias, pruebas en Windows real |
| Estadísticas | Existe módulo de métricas CSV | Validación de entradas, reportes y pruebas con datos reales anonimizados |
| Dataset de decisiones | Existe validador/plantilla | Esquema versionado, procedencia, división train/validation/test |
| Adaptador RoyaleGym | `src/simulator_adapter.py` solo inspecciona reset/espacios; `src/royalegym_contract.py` añade una prueba breve con `MockEngine` y acciones legales | Ejecutar el contrato en el PC, después probar RustEngine y RoyaleLearn |
| Entrenamiento | Existe punto de entrada/configuración | Confirmar API, ejecutar baseline, guardar checkpoints y curvas |
| Análisis visual | No debe darse por terminado solo por tener dependencias | Pipeline offline para imágenes/vídeos y conjunto de evaluación etiquetado |
| Calidad | Hay tests y workflow de CI | Ejecutar CI y resolver fallos; aún no se afirma que todo pase |

## 4. Orden recomendado de implementación

1. **Controlador de emuladores configurable**: configuración JSON, rutas personalizadas, selección explícita de instancia y pruebas con procesos simulados.
2. **Capa de eventos/logs**: mensajes uniformes entre UI, gestor de emulador, análisis y entrenador.
3. **Integración real con RoyaleGym**: entorno de prueba, observaciones y acciones tipadas, con pruebas de contrato.
4. **Baseline reproducible**: agente aleatorio o scripted en simulador, resultados en CSV/JSON y semillas guardadas.
5. **Datos y aprendizaje por imitación**: esquema de decisiones versionado, validación de fugas de datos y métricas.
6. **Percepción offline**: detectar elementos de capturas/vídeos y medir precisión contra etiquetas; no conectar el detector a automatización de partidas competitivas.
7. **Pulido de UI**: estados del sistema, logs en vivo, barra de progreso y mensajes de error accionables.

## 5. Licencias y límites

El repositorio py-clash-bot declara licencia de código NC-CL-1.0 y licencia CC BY-NC-SA 4.0 para assets/documentación. pymemuc es un proyecto separado y debe revisarse bajo sus propios términos antes de incorporar dependencia o código. RoyaleGym declara MIT en su README. AXR debe conservar atribución cuando corresponda y revisar la licencia del repositorio concreto antes de reutilizar código.

## 6. Verificación pendiente

- Los archivos fuente mencionados fueron leídos en GitHub; no se ha hecho una auditoría línea por línea de todo el repositorio upstream.
- No se ha ejecutado AXR en el PC del usuario ni se han probado las rutas de MEmu/BlueStacks allí.
- No se afirma que la suite de tests o el entrenamiento ya hayan pasado.
- Los siguientes commits deben privilegiar contratos comprobables y pruebas, no aumentar líneas artificialmente.


## 7. Revisión adicional del código de RoyaleGym

También se inspeccionaron directamente `royalegym/env.py`, `royalegym/action.py`, `royalegym/selfplay.py` y `pyproject.toml` del repositorio upstream.

Hallazgos relevantes para la integración:

- `ClashParallelEnv` es un entorno PettingZoo de dos asientos: `blue` y `red`. Su `reset()` devuelve observaciones e información por asiento; `step()` devuelve cinco mappings: observaciones, recompensas, terminaciones, truncamientos e información.
- Las observaciones incluyen `action_mask`; la política debe escoger una acción válida. El espacio de acciones básico es `Discrete(2305)`: NOOP más combinaciones de carta/posición. El propio proyecto documenta variantes con acciones de habilidad.
- `MockEngine` es una implementación de referencia en Python, no debe confundirse con el motor Rust ni con una simulación fiel del cliente real.
- `RoyaleGym` declara extras separados para simulador Rust, entrenamiento, visualización e imitación. AXR no debe asumir que instalar solo el paquete base instala todos esos componentes.
- `royalegym_contract.py` se añadió a AXR para validar el contrato básico de la API con `MockEngine`; comprueba las dos plazas, la máscara de acciones, una acción permitida, recompensas finitas y tipos de terminación. La prueba **no se ha ejecutado todavía** y no sustituye las pruebas con RustEngine.

Comando cuando el entorno esté instalado:

```powershell
py -m src.royalegym_contract --steps 3
```

Este comando es una prueba offline breve. Si falta RoyaleGym o cambia la API, imprime un diagnóstico JSON; no controla emuladores ni el juego oficial.


## 8. Revisión de RoyaleLearn y compatibilidad del entrenador

Se inspeccionaron `RoyaleLearn/README.md`, `royalelearn/learner.py` y su `pyproject.toml`.

- El patrón público documentado es `Learner(build_env, ...).learn(total_steps=...)`; la función de entorno debe estar definida en el nivel superior de un módulo importable para que los workers puedan reconstruirla.
- La clase `Learner` acepta los parámetros principales usados por `src/train_agent.py`, incluidos `opponent`, `n_envs`, `device`, `checkpoint_every`, los tamaños PPO, tasas de aprendizaje, `seed`, `viser` y `log_to_wandb`.
- El entrenador de AXR crea un `ClashParallelEnv` con `RustEngine` y `DefaultStateMutator`; los nombres de las cartas son aceptados por el mutador, que los resuelve contra el catálogo del motor.
- El paquete `royalelearn` base separa las dependencias de PyTorch en el extra `[torch]`; la instalación completa recomendada por los repositorios es `pip install "royalegym[all]"`.

Esto mejora la confianza en que la forma general del punto de entrada coincide con la API pública, pero **no demuestra que el entrenamiento de AXR se ejecute correctamente**. Quedan pendientes la instalación efectiva, el preflight de `Learner`, una corrida corta con `RustEngine`, la verificación del checkpoint y el análisis de métricas. La revisión de fuentes no equivale a haber entrenado un modelo.
