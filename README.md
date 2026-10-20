# Cube Simulator

Aplicacion de escritorio en Python para convertir videos ecograficos en salidas orientadas a simulacion educativa.

Actualmente el proyecto soporta tres flujos principales:

- `AVI anonimizado`: aplica ROI y máscaras a la secuencia completa y guarda un `.avi` en MJPG, conservando la frecuencia de cuadros de origen. Esta salida se encuentra pendiente de validación en OPUS.
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
- Exportacion AVI anonimizado (MJPG), con FPS de origen. Debe inspeccionarse el video completo para verificar que no haya identificadores.
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

## Exportación AVI (prueba experimental)

Selecciona `AVI anonimizado`, carga AVI / MP4 / DICOM, define el ROI y las máscaras, y exporta desde el botón 5. El archivo termina en `_anonimizado_MJPG.avi` dentro de `output_volumes/`.

La salida conserva todos los fotogramas procesados y los FPS originales de videos AVI/MP4. En DICOM, el valor FPS se estima si no hay información temporal disponible. La compresión MJPG no es sin pérdida. La compatibilidad de este AVI con reproducción temporal en OPUS **no está comprobada**; importar AVI como volumen no garantiza reproducción automática de un cine loop.

**Privacidad:** la anonimización es manual mediante ROI/máscaras; revisar todos los fotogramas del resultado antes de divulgar. No subir videos o estudios con datos del paciente a GitHub.

## Preparar OPUS 4D (prueba experimental)

Modo `OPUS 4D (test)`: carga el AVI original o anonimizado, conserva ROI/mascaras elegidos y crea una carpeta `*_opus4d_test` con ocho archivos `Intervalo_01.avi` a `Intervalo_08.avi` y un `OPUS_Create_4D.txt` con sus nombres. Importa el TXT mediante `Info > Academic > Course Creator > Create 4D Volume` de OPUS. Se produce un STY de varios intervalos.

Cada archivo tiene el mismo numero de fotogramas y desplazamiento circular de 1 fotograma respecto al anterior. El material **no** representa volumenes 3D reales de un mismo instante y no esta validado para simulacion anatomica o diagnostico. Se debe observar si el cambio de intervalo muestra movimiento mas continuo que el experimento de brillo y detectar discontinuidades. Si los datos deben anonimizarse, revisar todos los fotogramas de salida antes de compartirlos.

La pantalla de previsualizacion OpenCV aun puede bloquearse si se cierra con X; evitar usarla en esta prueba.

## Prueba de 32 fases (octubre 2026)
En `OPUS 4D (test)`, configurar **Intervalos=32**, **Inicio=0%**, **Fin=100%**; cargar el AVI anonimizado y generar. Se escriben 32 AVI del mismo tamaño y el TXT válido con una ruta relativa por línea, en la carpeta `*_opus4d_nuevo`. OPUS: `Info > Academic > Course Creator > Create 4D Volume`.

Con un AVI de 225 cuadros a 35 FPS, cada fase contiene 225 cuadros con desplazamiento circular de un cuadro respecto a la anterior; con sonda fija se recorren 32 instantes vecinos, no todo el AVI. Para 32 fases a una cadencia teórica de 35 intervalos/segundo, el valor equivalente es 65,625 BPM (una vuelta de 32 fases cada 0,914 segundos), **sujeto a verificación en OPUS**. BPM representa ciclos/minuto, no FPS. Para cubrir 225 instantes con sonda fija harían falta 225 intervalos, mucho más costosos en almacenamiento y potencialmente no admitidos por OPUS.

**Limitación:** Esta estrategia reutiliza vídeo temporal como si fueran cortes espaciales; su validez es exclusivamente experimental y pedagógica, no anatómica o diagnóstica. Están pendientes pruebas integrales de interfaz en Windows y límites de OPUS. Se mantiene el aviso sobre previsualización.

## Prueba V5: 225 intervalos

El modo `OPUS 4D (test)` ahora acepta de 2 a **225** intervalos. Para usar el AVI completo de 225 fotogramas, configurar `Intervalos=225`, `Inicio=0`, `Fin=100`. Los parámetros guardados de una ejecución anterior (por ejemplo, 32) pueden seguir apareciendo: cambiarlos manualmente. La salida se genera en `*_opus4d_225_intervalos` para no sobrescribir pruebas previas.

Se generan **225 videos de 225 cuadros** (50.625 cuadros codificados en total) y un archivo TXT. Pueden consumir mucho espacio y tiempo. A 8 segundos por intervalo dentro de OPUS, la construcción del STY tomaría **aproximadamente 30 minutos**, sin contar la exportación de Cube Simulator. La velocidad de reproducción de todos los 225 cuadros a 35 cuadros/s correspondería teóricamente a unos **9,33 BPM** (una vuelta cada 6,43 s), pero OPUS podría limitar el rango, truncar intervalos o interpretar BPM de modo distinto: validarlo.

El último intervalo vuelve al primero abruptamente si el AVI original no termina con un estado que conecte bien con el inicial; 225 fases **no eliminan por sí mismas** ese salto. No se crean datos 4D espaciales reales.

## Prueba de 256 x 256 — video completo conservado
En modo `OPUS 4D (test)`: `Intervalos=38`, `Inicio=0`, `Fin=100`, `Salida cuadrada=256`. Cargar el **AVI original o AVI anonimizado**; definir y verificar ROI y máscaras antes de exportar. El recorte se escala preservando su proporción y centrado en canvas negro 256x256. Se mantienen TODOS los 225 fotogramas del tramo completo en cada intervalo, sin pérdida temporal, pero con reducción de resolución espacial. El TXT lista 38 AVI, uno por línea, para `Create 4D Volume` de OPUS. Los AVI se colocan en carpeta `*_opus4d_038_256px`. En MJPG/OpenCV el tamaño impar 255x255 puede truncarse a 254x254, por lo que se usa 256x256 deliberadamente.

**Importante:** los 38 intervalos solo exponen 38 fases en un punto fijo del volumen, aunque cada AVI contenga los 225 fotogramas: es una prueba de consumo de memoria, no de reproducción de las 225 fases completas. Probar primero con 38 intervalos; confirmar cuántos frames tiene cada AVI antes de la conversión. OPUS puede requerir RAM adicional o tener límites internos. No es reconstrucción espacial 4D real.

## Experimento 255 x 255 exacto (hipotesis de matrices OPUS)
Se habilito la entrada manual del lado cuadrado en `OPUS 4D (test)`; valor inicial `255` (rango 32-1024). Se mantiene proporcion del ROI y relleno negro. Para dimensiones impares como 255x255 se emplea **ffmpeg instalado en PATH** para generar AVI MJPEG `yuvj444p` y se verifica con OpenCV que la resolucion sea exacta. El codec y formato de pixel deben probarse en OPUS: la compatibilidad de MJPG 256x256 ya verificada no demuestra compatibilidad de MJPG 255x255 yuvj444p. Para tamanos pares se conserva el procedimiento OpenCV habitual. La propuesta de 255 surge de una hipotesis no verificada de que OPUS podria subir 256 a 512 internamente; aun no tenemos evidencia de esa conducta. Para la prueba completa: 225 intervalos, 0-100%, lado 255. Genera 225 AVI x 225 cuadros (procesamiento intensivo). No empezar importacion masiva en OPUS sin verificar que al menos un AVI 255x255 abre correctamente.
