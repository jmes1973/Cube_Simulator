# Cube Simulator

Aplicacion de escritorio en Python para convertir videos ecograficos en salidas orientadas a simulacion educativa.

Actualmente el proyecto soporta dos flujos principales:

- `Pseudo 3D`: convierte una secuencia `AVI` / `MP4` / `DICOM` en un volumen `.nrrd` navegable y aplica compatibilidad automatica para OPUS cuando el caso es demasiado grande.
- `Pseudo 4D`: genera un dataset de micro clips por posicion `Z` a partir del video base, pensado para simulacion dinamica en un simulador externo.

## Objetivo

Este proyecto esta orientado a entrenamiento en simulacion ecografica, sin exponer informacion del paciente y sin depender de practica inicial sobre pacientes reales.

Casos de uso esperados:

- entrenamiento de navegacion con sonda
- memoria de muneca del ecografista
- simulacion de barrido en contextos como UCI o Emergencia
- generacion de material pseudo 3D / pseudo 4D para docencia

## Funcionalidades actuales

- Carga de archivos `AVI`, `MP4` y `DICOM`
- Definicion manual de ROI
- Definicion manual de mascaras para anonimizar overlays o texto
- Exportacion `Pseudo 3D` a `.nrrd`
- Reduccion automatica de volumen para mejorar compatibilidad con OPUS
- Exportacion `Pseudo 4D` a carpeta con:
  - `manifest.json`
  - micro clips por posicion `Z`

## Estructura del proyecto

- `main.py`: interfaz de escritorio con `customtkinter`
- `cube_processing.py`: pipeline de procesamiento, anonimizaci?n y exportaci?n
- `Cube_Simulator.spec`: configuracion de PyInstaller
- `assets/`: iconos y recursos visuales

## Requisitos

Entorno usado por el proyecto:

- Python 3.12
- `customtkinter`
- `opencv-python`
- `numpy`
- `pynrrd`
- `pydicom`
- `pyinstaller`

## Ejecucion local

1. Crear y activar entorno virtual.
2. Instalar dependencias.
3. Ejecutar la app:

```powershell
python main.py
```

## Compilacion

Para generar el ejecutable de escritorio con PyInstaller:

```powershell
python -m PyInstaller Cube_Simulator.spec
```

La salida compilada queda en `dist/`.

## Salidas generadas

### Pseudo 3D

Genera un archivo `.nrrd` en la carpeta de salida del workspace configurado por la aplicacion.

### Pseudo 4D

Genera una carpeta de dataset con una estructura similar a esta:

```text
caso_pseudo4d/
  manifest.json
  clips/
    z_000.avi
    z_001.avi
    z_002.avi
```

## Notas importantes

- `Pseudo 3D` esta pensado para OPUS y navegacion volumetrica.
- `Pseudo 4D` no se exporta como un unico `.nrrd`; se exporta como clips por posicion `Z` para integracion con un simulador.
- El proyecto esta orientado a simulacion y educacion, no a diagnostico clinico.

## Estado del repositorio

Antes de subir a GitHub conviene versionar solo codigo y configuracion, no:

- entorno virtual
- builds compilados
- datasets de entrada
- salidas generadas
- archivos temporales o caches
