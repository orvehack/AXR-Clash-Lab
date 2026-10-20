# Auditoría de py-clash-bot y estrategia de AXR

Fecha de revisión: 2026-10-20.

## Fuentes inspeccionadas

- [py-clash-bot README](https://github.com/pyclashbot/py-clash-bot/blob/master/README.md)
- [py-clash-bot pyproject.toml](https://github.com/pyclashbot/py-clash-bot/blob/master/pyproject.toml)
- [Licencia del código y assets](https://github.com/pyclashbot/py-clash-bot/blob/master/LICENSE)
- [pymemuc](https://github.com/pyclashbot/pymemuc)
- [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym)

## Cómo funciona py-clash-bot, a alto nivel

El README describe una aplicación de escritorio para Windows/macOS con pestañas de emulador y trabajos. Sus dependencias declaradas incluyen OpenCV, NumPy, pymemuc, psutil, Pillow, pypresence y ttkbootstrap. La arquitectura pública anuncia reconocimiento de imágenes, gestión del emulador Android y tareas configurables. El flujo documentado es seleccionar un emulador, iniciar o crear una instancia, preparar manualmente el juego y seleccionar trabajos.

Esto es una lectura de README y metadatos del paquete; no significa que se haya inspeccionado exhaustivamente cada módulo interno ni que AXR haya incorporado esos módulos.

## Hallazgo de licencia

El código fuente de py-clash-bot declara NC-CL-1.0, una licencia no comercial con obligación de compartir bajo la misma licencia las obras derivadas distribuidas. Los assets/documentación tienen CC BY-NC-SA 4.0. Por eso AXR no copia sus archivos fuente, UI, imágenes ni rutinas internas. Se toma inspiración funcional y se desarrolla una implementación independiente. Si en el futuro se desea reutilizar código concreto, hay que revisar el archivo, avisos y obligaciones antes de copiarlo.

El repositorio separado pymemuc tiene su propio README y licencia; no se presume que las condiciones de un proyecto se apliquen automáticamente al otro. Su README documenta la API de Python para iniciar/detener VMs MEmu y consultar información del emulador.

## Qué añadimos a AXR

`src/emulator_manager.py` es una implementación propia y acotada para:
- detectar instalaciones habituales de MEmu y BlueStacks 5;
- mostrar diagnósticos locales;
- lanzar el proceso GUI del emulador sin shell;
- consultar estado aproximado del proceso;
- no guardar credenciales ni recopilar datos de cuenta.

El módulo no instala software, no inicia sesión, no manipula la pantalla del juego y no automatiza partidas. El usuario debe instalar y configurar el emulador y abrir Clash Royale manualmente.

## Por qué no copiamos el bot de partidas

La prioridad de AXR es la investigación offline: simulación RoyaleGym/RoyaleSim, análisis de replays, conjuntos de decisiones, entrenamiento y evaluación reproducible. No implementamos evasión de detección ni automatización de partidas competitivas en el cliente oficial. El lanzamiento del emulador es una función de comodidad, separada del motor de IA.

## Verificación pendiente

- Ejecutar pruebas en Windows 11 con MEmu instalado.
- Verificar rutas personalizadas y múltiples instancias.
- Confirmar versiones reales de RoyaleGym/RoyaleLearn y sus APIs antes de entrenar.
- Ejecutar CI y corregir cualquier fallo.
