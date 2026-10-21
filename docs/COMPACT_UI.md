# AXR Compact UI

La interfaz compacta se inicia en Windows con doble clic en `INICIAR_AXR_COMPACTO.bat`, o desde la raíz del repositorio con:

```powershell
.\.venv\Scripts\python.exe -m src.axr_compact_ui
```

Incluye pestañas de panel, configuración PPO, partidas CSV y manifiestos de experimentos. El botón de plan ejecuta `src.train_agent --plan-only`; el botón de entrenamiento intenta ejecutar el entrenamiento real y pide confirmación primero. Si RoyaleGym/RoyaleLearn no están instalados o su API no coincide, el proceso reportará el error: la interfaz no simula resultados ni afirma que el modelo haya aprendido.

## Relación con py-clash-bot

La interfaz de AXR es una implementación propia inspirada en el patrón general de ventana compacta con pestañas y ajustes. No incorpora código fuente ni recursos de py-clash-bot. Su código fuente tiene licencia NC-CL-1.0, que impone condiciones no comerciales y copyleft para redistribuciones/obras derivadas. Antes de integrar cualquier implementación de terceros se debe comprobar su licencia y conservar atribución y avisos cuando corresponda.

AXR sigue orientado a análisis local y simulación; esta interfaz no controla el cliente oficial ni automatiza partidas competitivas.
