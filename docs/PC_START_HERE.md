# AXR Clash Lab — empieza aquí en tu PC (Windows 11)

Esta guía está pensada para la primera ejecución. No necesitas editar código para comenzar.

## 1. Descargar el proyecto

1. Abre el repositorio: https://github.com/orvehack/AXR-Clash-Lab
2. Pulsa **Code → Download ZIP**.
3. En Descargas, extrae el ZIP completo. No ejecutes el proyecto dentro del ZIP.
4. Entra a la carpeta extraída y confirma que ves `README.md`, `src`, `tests` y `scripts`.

## 2. Instalar Python 3.12

El iniciador actual requiere Python 3.12 y el lanzador de Windows `py`.

1. Descarga Python 3.12 desde https://www.python.org/downloads/
2. Durante la instalación, marca **Add python.exe to PATH** y asegúrate de instalar el Python Launcher.
3. Abre una ventana nueva de PowerShell y ejecuta:

```powershell
py -3.12 --version
```

Debe mostrar `Python 3.12.x`. Si no, no sigas aún: envíame el texto exacto del error.

## 3. Ejecutar la primera comprobación

Dentro de la carpeta extraída del proyecto, haz doble clic en `INICIAR_AXR_WINDOWS.bat`.

El iniciador:
- crea el entorno aislado `.venv` si hace falta;
- ejecuta el diagnóstico local y las pruebas unitarias;
- valida los planes de entrenamiento e imitación en modo `--plan-only`;
- te pregunta si quieres abrir la interfaz.

No instala PyTorch/RoyaleGym, no descarga replays, no entrena una IA y no inicia ni controla partidas reales. Si una comprobación falla, copia el mensaje completo y compártelo; no borres archivos ni reinstales todo por tu cuenta.

### Alternativa desde PowerShell

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\first_run_windows.ps1
```

## 4. Qué haremos después

Cuando la comprobación termine, comparte el resultado y avanzaremos según lo que diga:

1. **Interfaz:** comprobar que la ventana AXR se abre correctamente.
2. **Emulador:** detectar MEmu o BlueStacks sin automatizar el juego.
3. **Simulación offline:** instalar y comprobar las dependencias compatibles de RoyaleGym/RoyaleLearn.
4. **Entrenamiento pequeño:** ejecutar una prueba reproducible, revisar métricas y guardar el artefacto.
5. **Imitación de replays:** solo después de verificar compatibilidad y disponibilidad de datos.

## Importante: estado real

El repositorio contiene código inicial, pruebas y planes de integración; todavía no está demostrado que toda la pila de IA funcione de extremo a extremo en tu equipo. Las pruebas del script son la primera validación local, no una garantía de que RoyaleGym o el entrenamiento estén funcionando. Los datos de ejemplo de `data/matches.csv` son ficticios.
