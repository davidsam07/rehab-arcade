# Rehab Arcade

Práctica 2 de **Interacción Persona-Máquina** (IPM mediante visión por computador).

**Autor:** José David Samaniego Guerrero

Rehab Arcade es un juego serio para la **rehabilitación del brazo y la mano** pensado para personas que han tenido un ictus. La idea es que los ejercicios de casa, que suelen ser repetitivos y aburridos, se hagan jugando, y que además quede guardado cómo va mejorando el paciente.

Se juega **solo con la webcam**, sin mandos ni sensores: el cuerpo y la mano se detectan con **MediaPipe** (Google) y todo lo demás está hecho en Python con OpenCV.

## Los dos juegos

### 1. Hombro: Trineo volador

Un trineo de Papá Noel vuela sobre un pueblo nevado y **su altura depende de cuánto subes los brazos por los lados**. Hay que recoger los regalos y las estrellas que van llegando, así que se trabaja la abducción del hombro (subir y bajar los brazos) sin parar.

- **Calibración:** al empezar se suben los brazos todo lo posible y se guarda el ángulo máximo de cada hombro. A partir de ahí, "100 %" es *tu* máximo.
- **Ayudas:** a la izquierda hay una barra con la altura de los brazos, una flecha te dice si tienes que subir o bajar y abajo a la derecha te ves en pequeño. Si la cámara deja de verte, el juego se para.
- **Dificultad:** si recoges casi todo, los regalos salen más arriba (hasta un poco por encima de tu máximo, para que estires) y el trineo va más rápido. Si te cuesta, al revés.
- **Qué se mide:** el ángulo entre la vertical y el brazo (hombro → codo), con MediaPipe Pose.

### 2. Mano: Piano de dedos

Caen notas como en un piano y, cuando llegan a la línea, hay que **juntar el pulgar con el dedo que toca** (la pinza). Hay 4 carriles: índice, corazón, anular y meñique.

- **Canciones:** *Jingle Bells*, *Noche de paz*, *We Wish You a Merry Christmas*, *Deck the Halls* y el *Himno de la alegría* (todas de dominio público). Las notas caen al ritmo de la música, con las graves en el índice y las agudas en el meñique.
- **Calibración:** primero mano abierta y luego la pinza con cada dedo. Va despacio y paso a paso, porque la primera versión iba demasiado rápida para una persona mayor. Si no llegas a cerrar la pinza, se coge tu mejor intento.
- **Notas largas:** algunas tienen cola y hay que **mantener** la pinza hasta que acabe.
- **Mano guía:** a la izquierda se ve tu mano en grande con el dedo que toca iluminado.
- **Dificultad:** si aciertas, la canción va más rápida y caen más notas; si fallas, más lenta. Los dedos que más fallan reciben más notas.
- **Qué se mide:** la distancia de la punta del pulgar a la punta de cada dedo, dividida por el tamaño de la mano (así da igual lo cerca que estés de la cámara).

Cada partida se guarda en `data/hombro.csv` o `data/mano.csv`, y al terminar sale una gráfica con la evolución del paciente (también se guarda en `data/informes/`).

## Instalación

Hace falta tener **Conda** ([Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) vale).

**Opción rápida:** abrir **Anaconda Prompt** (en Windows) o una terminal (macOS/Linux), ir a la carpeta del proyecto y ejecutar:

```bash
setup.bat        # Windows
bash setup.sh    # macOS / Linux
```

**Paso a paso** (es lo mismo que hace el script):

```bash
conda create -n rehab-arcade python=3.12 -y
conda activate rehab-arcade
pip install -r requirements.txt
python download_models.py
```

> Ojo: tiene que ser **Python 3.12**. Con versiones más nuevas `mediapipe==0.10.21` no se instala.
> Si conda pide aceptar los Términos de Servicio de los canales, ejecuta los `conda tos accept ...` que salen en el mensaje y vuelve a lanzarlo.

## Cómo se juega

```bash
conda activate rehab-arcade
python main.py --paciente "Ana"
```

- `--paciente`: nombre del paciente; su historial se guarda con ese nombre (si no se pone, `invitado`).
- `--camara`: número de la webcam si tienes varias (por defecto `0`).

Los botones se pulsan **dejando el dedo índice quieto encima un segundo y medio**, sin tocar el ordenador. Para ir más rápido también hay teclas:

| Tecla | Qué hace |
|---|---|
| `1` / `2` | Elegir hombro o mano en el menú |
| `1` - `5` | Elegir canción |
| `ENTER` | Saltar las instrucciones / volver al menú |
| `M` | Quitar o poner la música |
| `F` | Pantalla completa |
| `ESC` | Volver al menú (o salir si ya estás en él) |

**Consejos para que detecte bien:** buena luz de frente (no con una ventana detrás) y, para el trineo, ponerse a 1,5–2 m de la cámara de forma que se vean los codos. Si con auriculares Bluetooth notas la música retrasada, sube `AUDIO_EXTRA_LATENCY` en `config.py`.

## Cómo está organizado

```
rehab-arcade/
├── main.py              # bucle principal: cámara, menús, partida y resultados
├── config.py            # todos los parámetros que se pueden ajustar
├── download_models.py   # descarga los modelos de MediaPipe
├── setup.bat / setup.sh # instalación automática
├── assets/              # imágenes del juego (ver assets/LEEME.md)
└── rehab/
    ├── vision.py        # MediaPipe Pose y Hands
    ├── geometry.py      # ángulos y distancias
    ├── ui.py            # textos, botones por dwell, tarjetas e iconos
    ├── audio.py         # música y piano generados con numpy
    ├── songs.py         # las canciones escritas nota a nota
    ├── scene.py         # el paisaje nevado de fondo
    ├── assets.py        # carga de las imágenes de assets/
    ├── session.py       # guardar partidas en CSV
    ├── report.py        # gráficas de evolución
    └── games/
        ├── base.py          # fases comunes: intro, calibración, cuenta atrás y juego
        ├── sleigh_flight.py # trineo volador (hombro)
        └── finger_piano.py  # piano de dedos (mano)
```

Las imágenes las generé con IA a partir de los prompts de [assets/PROMPTS.md](assets/PROMPTS.md). La música no usa archivos: se sintetiza en el propio juego.

## Cosas que me costaron (y cómo las resolví)

- **El pulgar se quedaba "enganchado"** en el piano: para soltar la pinza había que abrir la mano del todo. Ahora se suelta en cuanto el dedo se separa un poco de su punto más cerrado.
- **La música iba desacompasada:** el audio de Windows salía con unos 200 ms de retraso y la cámara tarda unas décimas en ver la pinza. El juego usa el reloj del audio y descuenta los dos retrasos.
- **Iba lento al dibujar la interfaz** (unos 35 ms por frame). Cambiando las mezclas con transparencia de numpy a OpenCV bajó a unos 4 ms.
- **`cv2.putText` no pinta tildes**, así que los textos se dibujan con Pillow.
