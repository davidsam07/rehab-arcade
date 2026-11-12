# Rehab Arcade

Juego serio de **rehabilitación del miembro superior** (hombro y mano), pensado para pacientes que han sufrido un ictus. Se juega solo con la **webcam**, sin mandos ni sensores, gracias a **MediaPipe** de Google.

IPM, Práctica 2: IPM mediante visión por computador.

## Modos de juego

### 1. Hombro: Fruit Ninja
- **Calibración:** el paciente sube los brazos por los lados todo lo que puede y se guarda el ángulo máximo de cada hombro (su rango de movimiento).
- **Juego:** aparecen frutas en el límite de ese rango y el paciente las corta con la mano de su lado.
- **Adaptativo:** si acierta, las frutas salen un poco más arriba y duran menos. Si falla, salen más abajo y duran más.
- **Métrica:** ángulo del hombro (MediaPipe Pose, puntos hombro y codo respecto a la vertical).

### 2. Mano: Piano de dedos
- **Calibración guiada (pensada para personas mayores):** paso a paso, sin prisa. En cada paso se iluminan sobre la propia mano los dos dedos que hay que juntar, el juego espera a que el paciente lo intente y le pide mantenerlo 3 segundos. Si no llega a cerrar la pinza, se mide igualmente su mejor intento. Así los umbrales se ajustan a la movilidad de cada dedo.
- **Canciones:** el paciente elige entre *Jingle Bells*, *Noche de paz*, *We Wish You a Merry Christmas*, *Deck the Halls* y el *Himno de la alegría* (todas de dominio público). La medida de la mano se guarda durante la sesión, así que al cambiar de canción no hay que volver a calibrar.
- **Juego a ritmo:** las notas caen al compás de la canción por 4 carriles (índice, corazón, anular y meñique), como en un piano: las notas graves van al índice y las agudas al meñique. Cuando la nota llega a la línea, el paciente junta el pulgar con ese dedo y suena esa nota de la melodía. Las notas que van demasiado seguidas las toca el ordenador, así la canción nunca se corta.
- **Música:** todo se sintetiza con numpy (piano, bajo y acordes), sin archivos de audio. El acompañamiento se programa con unas décimas de antelación para que vaya a tempo aunque la cámara dé algún tirón.
- **Adaptativo:** si acierta, la canción va más rápida y le tocan más notas; si le cuesta, va más lenta y con más espacio entre notas. Además, los dedos que más fallan reciben más notas.
- **Pinza robusta:** solo cuenta un dedo a la vez, con histéresis para que el temblor no dé dobles pulsaciones. La pinza se suelta en cuanto el dedo se separa un poco de su punto más cerrado (no hace falta abrir la mano del todo), y si otro dedo se cierra claramente más, se cambia a ese dedo.
- **Métrica:** distancia pulgar–dedo dividida por el tamaño de la mano (MediaPipe Hands). Así no importa lo cerca que esté la mano de la cámara.

Cada partida se guarda en `data/hombro.csv` o `data/mano.csv`. Al acabar se muestra una gráfica con la evolución del paciente, que también se guarda en `data/informes/`.

## Instalación

Requisito: tener **Conda** instalado ([Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install)).

### Opción A: script automático
Desde **Anaconda Prompt** (Windows) o una terminal (macOS/Linux), dentro de la carpeta del proyecto:

```bash
setup.bat        # Windows
bash setup.sh    # macOS / Linux
```

### Opción B: paso a paso
```bash
conda create -n rehab-arcade python=3.12 -y
conda activate rehab-arcade
pip install -r requirements.txt
python download_models.py
```

> Si conda pide aceptar los Términos de Servicio de sus canales, ejecuta los comandos `conda tos accept ...` que aparecen en el mensaje y repite.

## Ejecución

```bash
conda activate rehab-arcade
python main.py --paciente "Ana"
```

| Opción | Descripción |
|---|---|
| `--paciente` | Nombre del paciente. Su historial se guarda con ese nombre (por defecto `invitado`). |
| `--camara` | Índice de la webcam si tienes varias (por defecto `0`). |

## Controles

El juego se maneja **sin tocar el ordenador**: para pulsar un botón, deja el dedo índice encima durante un segundo y medio.

| Tecla | Acción |
|---|---|
| `1` / `2` | Elegir modo en el menú |
| `1` - `5` | Elegir canción |
| `ENTER` | Saltar instrucciones / volver al menú |
| `M` | Quitar / poner la música |
| `F` | Pantalla completa |
| `ESC` | Volver al menú (o salir desde el menú) |

## Estructura del proyecto

```
rehab-arcade/
├── main.py                  # Bucle principal: cámara, menú, partida y resultados
├── config.py                # Todos los parámetros ajustables
├── download_models.py       # Descarga los modelos de MediaPipe
├── requirements.txt
├── setup.bat / setup.sh     # Instalación automática
└── rehab/
    ├── vision.py            # MediaPipe Pose y Hands (modo VIDEO)
    ├── geometry.py          # Ángulos y distancias
    ├── ui.py                # Textos con tildes (Pillow), tarjetas, botones por "dwell", iconos y nieve
    ├── audio.py             # Piano, acompañamiento y efectos generados con numpy (sin archivos)
    ├── songs.py             # Canciones del piano: melodía y acordes escritos nota a nota
    ├── session.py           # Historial en CSV
    ├── report.py            # Gráficas de evolución (matplotlib)
    └── games/
        ├── base.py          # Fases comunes: intro, calibración, cuenta atrás, juego
        ├── shoulder_ninja.py
        └── finger_piano.py
```

Para añadir un minijuego nuevo basta con heredar de `Minigame` (`games/base.py`) y registrarlo en `games/__init__.py`.

## Autores

- _Nombre Apellido_: modo hombro
- _Nombre Apellido_: modo mano
