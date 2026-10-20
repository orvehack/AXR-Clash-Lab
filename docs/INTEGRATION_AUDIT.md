# Auditoría de integración de proyectos

Fecha de revisión: 2026-10-20.

Este documento separa lo comprobado de lo pendiente. Todavía no se ha copiado código de los proyectos externos a AXR Clash Lab.

## 1. RoyaleGym

- Repositorio: https://github.com/RoyaleGym/RoyaleGym
- README revisado: https://github.com/RoyaleGym/RoyaleGym/blob/main/README.md
- Licencia: MIT; se encontró el archivo LICENSE.
- Enfoque anunciado: entorno de batallas determinista, API compatible con Gymnasium/PettingZoo y herramientas de entrenamiento en Python.
- Posible uso en AXR: candidato principal para experimentar con políticas y entrenamiento en un entorno simulado, después de verificar requisitos de Python, instalación, API y compatibilidad con nuestro equipo.

La licencia MIT permite reutilizar y modificar código si se conservan el aviso de copyright y el texto de licencia aplicables. Si se incorpora código, habrá que conservar atribuciones y documentar qué archivos provienen del upstream.

## 2. ClashRoyaleBuildABot

- Repositorio: https://github.com/Pbatch/ClashRoyaleBuildABot
- README revisado: https://github.com/Pbatch/ClashRoyaleBuildABot/blob/main/README.md
- El README describe generación de estados y visión por computadora, y limita expresamente el uso a investigación/educación; también advierte que usarlo conectado al juego está prohibido por sus términos y puede ocasionar sanciones.
- Estado de licencia: no se pudo recuperar un archivo raíz llamado LICENSE en esta revisión. El README menciona una licencia aplicable y créditos, pero eso no basta para determinar con seguridad sus permisos exactos.

**Regla:** no copiar ni distribuir código de este repositorio hasta identificar y revisar la licencia aplicable. Podemos estudiar documentación pública y diseñar interfaces compatibles sin copiar su implementación.

## 3. Plan de integración de AXR Clash Lab

1. Mantener el registro de partidas, estadísticas y pruebas como base propia.
2. Evaluar RoyaleGym en una rama/entorno de prueba aislado; medir instalación, ejemplos y API antes de añadir dependencias.
3. Revisar la licencia y arquitectura de ClashRoyaleBuildABot antes de cualquier reutilización. Si no hay permiso claro, mantenerlo como referencia conceptual y escribir una implementación propia.
4. Crear una capa de datos común para observaciones, acciones, recompensas y resultados, sin asumir que ambos proyectos comparten el mismo formato.
5. Entrenar y evaluar políticas en simulación offline, comparar contra baselines sencillos y guardar métricas y semillas para repetir experimentos.
6. Añadir análisis de repeticiones/vídeos offline como fuente de ejemplos etiquetados, respetando derechos de autor y sin automatizar partidas competitivas reales.

## Qué significa “IA avanzada” aquí

No basta con llamar a un modelo “IA”. La progresión verificable sería: baseline de reglas, evaluación reproducible, política entrenable en simulación, aprendizaje a partir de ejemplos etiquetados y comparación cuantitativa. No se afirmará que un modelo está entrenado hasta que existan código, datos, resultados y pruebas reproducibles.

## Límites de esta auditoría

Esta es una revisión inicial de los README y del archivo LICENSE de RoyaleGym. No es una auditoría legal completa ni una inspección exhaustiva de todos los archivos, dependencias o licencias de terceros.
