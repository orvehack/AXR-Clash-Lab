# Arquitectura prevista de IA — AXR Clash Lab

## Objetivo

Construir una plataforma experimental para analizar partidas y entrenar/evaluar estrategias en un entorno offline. No asumir que el proyecto ya tiene una IA entrenada: cada fase debe producir resultados verificables.

## Componentes

1. **Datos y etiquetas**
   - Registro de resultados y mazos.
   - Anotaciones de decisiones desde repeticiones o vídeos que el usuario tenga derecho a analizar.
   - Separación entre datos reales, sintéticos y de ejemplo.
2. **Analítica y baselines**
   - Estadísticas de resultados y rivales.
   - Políticas de referencia sencillas y deterministas para medir progreso.
3. **Adaptador de simulador**
   - Interfaz interna estable para resetear episodios, leer observaciones, ejecutar acciones y recoger recompensas/resultados.
   - Adaptador candidato para RoyaleGym, sujeto a pruebas de instalación y compatibilidad.
4. **Política entrenable**
   - Empezar con un baseline, luego probar aprendizaje por imitación con ejemplos etiquetados y/o aprendizaje por refuerzo en simulación.
   - Separar entrenamiento, validación y evaluación para evitar medir el modelo con los mismos episodios usados para entrenarlo.
5. **Evaluación reproducible**
   - Guardar configuración, semillas, versiones, resultados, duración y tasa de victorias simuladas.
   - Comparar contra baselines y repetir los experimentos.
6. **Análisis visual offline**
   - A futuro, detectar eventos de vídeo y ayudar a etiquetar decisiones. No controlar el juego en vivo ni automatizar partidas competitivas.

## Interfaz de datos inicial

El archivo data/decisions_template.csv define las columnas para anotar decisiones. Los campos de elixir y tiempo deben ser numéricos cuando estén disponibles. Usa decision_label para etiquetar la calidad de la decisión con una escala documentada por el equipo, y outcome_label para el resultado posterior; no confundas una decisión razonable con un resultado favorable por pura suerte.

## Hitos de implementación

- [x] Registro básico de partidas y estadísticas iniciales.
- [x] Pruebas unitarias iniciales del resumen de partidas.
- [x] Plantilla CSV de anotaciones de decisiones.
- [ ] Definir validación estricta del esquema de anotaciones.
- [ ] Evaluar RoyaleGym en un entorno aislado.
- [ ] Confirmar licencia y componentes reutilizables de ClashRoyaleBuildABot.
- [ ] Implementar un baseline de política en simulación.
- [ ] Implementar el primer experimento de entrenamiento y guardar métricas.
- [ ] Comparar el modelo entrenado contra los baselines.
