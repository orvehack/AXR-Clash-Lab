# Hoja de ruta de AXR Clash Lab

Estado actualizado: 2026-10-20. Las casillas distinguen código escrito de código ejecutado. Una implementación no se considera validada hasta que las pruebas se ejecuten y se revise el resultado.

## Fase 0 — estructura y diagnóstico local
- [x] Documentar el objetivo y el alcance inicial.
- [x] Separar interfaz, datos, evaluación, entrenamiento y gestión del emulador.
- [x] Añadir diagnóstico sin instalación: `src/doctor.py`.
- [x] Añadir primera ejecución guiada de Windows: `scripts/first_run_windows.ps1`.
- [ ] Ejecutar el flujo completo en un PC Windows y revisar sus resultados.

## Fase 1 — datos y análisis offline
- [x] Esquema CSV para partidas, mazos, resultado y notas.
- [x] Estadísticas de victorias, derrotas y cambios de trofeos.
- [x] Plantilla de decisiones y validación/auditoría del dataset.
- [x] Pruebas unitarias escritas para utilidades de datos.
- [ ] Ejecutar la suite y corregir cualquier fallo encontrado.
- [ ] Importar partidas reales del usuario, manteniendo separados datos reales y ejemplos ficticios.

## Fase 2 — evaluador y métricas de simulación
- [x] Agentes de referencia heurístico y aleatorio.
- [x] Evaluación con semillas reproducibles y límites por episodio.
- [x] Informes JSON/CSV/Markdown y métricas básicas de incertidumbre.
- [x] Clasificar como `unknown` los episodios sin resultado terminal verificable.
- [x] Puente de informes al registro de modelos, con comprobación opcional del agente fuente.
- [ ] Ejecutar contrato de RoyaleGym con `MockEngine`.
- [ ] Ejecutar pruebas reales con la versión instalada de RoyaleGym/RustEngine.
- [ ] Confirmar que las claves de coronas del entorno son realmente terminales.

## Fase 3 — entrenamiento PPO reproducible
- [x] Entrada de entrenamiento con plan, manifiesto, estimación de recursos y preflight.
- [x] Registro de eventos estructurados y tarjeta de experimento.
- [x] Warm-start opcional desde un artefacto de imitación.
- [ ] Confirmar compatibilidad de versiones RoyaleGym/RoyaleLearn/RoyaleImitate.
- [ ] Ejecutar un entrenamiento corto con el motor Rust.
- [ ] Guardar, cargar y evaluar un checkpoint de principio a fin.
- [ ] Registrar versión de paquetes, revisión del código y huella del artefacto.

## Fase 4 — imitación y cooperación de modelos
- [x] Entrada inicial para reconstruir demostraciones y entrenar un actor de imitación.
- [x] Definir arquitectura por etapas: imitación → PPO → evaluación pareada.
- [ ] Confirmar que los datos/replays descargados tienen el formato y licencia adecuados.
- [ ] Probar una pequeña muestra de replays y revisar calidad de observaciones/acciones.
- [ ] Medir el actor de imitación antes de usarlo como warm-start.
- [ ] Añadir self-play o liga de oponentes después de validar el ciclo básico.

## Fase 5 — registro y promoción de versiones
- [x] Registro JSONL con validación de resultados.
- [x] Manifiestos de artefactos con SHA-256.
- [x] Comparación por semillas comunes y barrera bootstrap pareada conservadora.
- [x] Pruebas escritas para puertas de promoción e importación.
- [ ] Ejecutar las pruebas y verificar el comportamiento estadístico con datos reales.
- [ ] Conectar el registro con resultados de checkpoints de RoyaleLearn, no sólo los agentes de referencia.

## Fase 6 — interfaz y flujo de trabajo
- [x] Interfaz de escritorio inicial con paneles locales.
- [x] Lanzador/diagnóstico de MEmu y BlueStacks.
- [ ] Probar la interfaz en Windows y corregir fallos de Tkinter/rutas.
- [ ] Mostrar progreso de entrenamiento sin bloquear la interfaz.
- [ ] Mostrar historial de ejecuciones, comparación de modelos y gráficos.
- [ ] Mejorar selección de instancia de emulador y manejo de rutas no estándar.

## Fase 7 — análisis de vídeo/repeticiones
- [x] Definir una plantilla de decisiones etiquetadas y un flujo de auditoría de datos.
- [ ] Crear importador de vídeo/repetición con marcas de tiempo.
- [ ] Probar detección de cartas, elixir, torres y eventos contra anotaciones humanas.
- [ ] Registrar confianza y errores de percepción.
- [ ] Convertir observaciones verificadas en datos de imitación sin fuga entre entrenamiento y validación.

## Próximo orden recomendado
1. Ejecutar `scripts/first_run_windows.ps1` en Windows y guardar la salida.
2. Corregir errores de pruebas antes de instalar el stack de ML.
3. Instalar RoyaleGym/RustEngine en un entorno virtual separado y validar el contrato.
4. Hacer una evaluación corta con agentes de referencia.
5. Entrenar un PPO pequeño, guardar/cargar el actor y medirlo contra el baseline con las mismas semillas.
6. Conectar checkpoints al registro y sólo después ampliar a self-play, vídeo y visualizaciones.

## Criterios para declarar una fase terminada
- Hay código revisable y pruebas relevantes.
- Las pruebas se ejecutaron y su salida quedó registrada.
- Se distinguen datos ficticios, humanos y simulados.
- No se declara que una IA mejoró sin evaluación comparable.
- El proyecto se mantiene centrado en simulación offline y análisis autorizado; no automatiza partidas competitivas en el cliente oficial ni evade antitrampas.
