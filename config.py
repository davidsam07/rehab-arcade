"""Configuración global de Rehab Arcade.

Todos los parámetros ajustables del juego están aquí, para no tener
"números mágicos" repartidos por el código.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")   # imágenes PNG opcionales (ver assets/LEEME.md)
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "informes")

POSE_MODEL = os.path.join(MODELS_DIR, "pose_landmarker_full.task")
HAND_MODEL = os.path.join(MODELS_DIR, "hand_landmarker.task")

WINDOW_NAME = "Rehab Arcade"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# Tiempo que hay que mantener el dedo sobre un botón para pulsarlo (s)
DWELL_TIME = 1.5
# Visibilidad mínima de un landmark de pose para darlo por bueno
MIN_VISIBILITY = 0.5

# Sonido (tecla M para quitar/poner la música durante el juego)
MUSIC_ENABLED = True
MUSIC_VOLUME = 0.08       # música de fondo, flojita para no tapar los aciertos
SFX_VOLUME = 0.30         # sonidos sueltos (calibración del piano)
MELODY_VOLUME = 0.17      # notas de la melodía que le tocan al paciente (un poco más fuertes)
AUTO_NOTE_VOLUME = 0.14   # resto de notas de la melodía
# Retardo extra del audio, además del que informa la tarjeta de sonido. Súbelo (p.ej. 0.15)
# si usas auriculares Bluetooth y notas que la música va por detrás de las notas que caen.
AUDIO_EXTRA_LATENCY = 0.0

# Aspecto
SNOW = True               # copos de nieve en los menús y en las canciones navideñas


class Sleigh:
    """Modo hombro (Trineo volador)."""
    INTRO_TIME = 7.0          # s de instrucciones antes de calibrar
    CALIB_TIME = 6.0          # s para medir el rango máximo
    GAME_TIME = 75.0          # duración del vuelo (s)
    MIN_CALIB_ANGLE = 30.0    # si la calibración sale más baja, usamos esto
    # Altura del trineo: 0 = brazos abajo, 1 = su máximo de la calibración
    TOP_LEVEL = 1.25          # con esta elevación el trineo llega arriba del todo
    LOW_LEVEL = 0.25          # los regalos más bajos (brazos casi relajados)
    FOLLOW = 7.0              # rapidez con la que el trineo sigue a los brazos (1/s)
    CATCH_RADIUS = 80         # px: distancia para coger un regalo
    ITEM_SPACING = 110        # px entre regalos de un mismo grupo
    PATTERN_GAP = 1.1         # s de descanso entre grupos de regalos
    MUSIC_TEMPO = 0.9         # velocidad de la música de fondo (Jingle Bells)
    # Dificultad adaptativa: hasta qué altura salen los regalos y a qué velocidad vuela
    CHALLENGE_START, CHALLENGE_MIN, CHALLENGE_MAX = 0.90, 0.60, 1.15
    CHALLENGE_UP, CHALLENGE_DOWN = 0.03, 0.05
    SPEED_START, SPEED_MIN, SPEED_MAX = 240.0, 170.0, 380.0   # px/s
    ADAPT_WINDOW = 8          # últimos regalos que se miran para adaptar


class Piano:
    """Modo mano (Piano de dedos). Valores pensados para personas mayores."""
    INTRO_TIME = 8.0
    INTRO_TIME_RECALL = 4.0   # intro más corta si ya se midió la mano en esta sesión
    # Calibración guiada, paso a paso
    CALIB_PREP_TIME = 4.0     # s para leer la instrucción y ver qué dedo se ilumina
    CALIB_HOLD_TIME = 3.0     # s que hay que mantener la posición
    CALIB_MAX_WAIT = 12.0     # si no consigue cerrar la pinza, medimos igualmente su mejor intento
    CALIB_ATTEMPT = 0.70      # se considera que lo intenta al cerrar hasta el 70% de la mano abierta
    CALIB_PRAISE_TIME = 2.0   # s de "Muy bien!" entre pasos (le da tiempo a soltar)

    # Pinza. Umbrales relativos a la calibración de cada dedo (0 = pinza máxima, 1 = mano abierta)
    PINCH_ON = 0.35           # por debajo, el dedo cuenta como pinza
    PINCH_OFF = 0.48          # por encima, se suelta seguro
    RELEASE_RISE = 0.20       # también se suelta al abrir un 20% desde su punto más cerrado
    RELEASE_GAP = 0.10        # ...pero siempre un poco por encima de ON (evita dobles pulsaciones)
    SWITCH_RATIO = 0.75       # si otro dedo está mucho más cerrado, cambiamos de dedo sin soltar
    SMOOTHING = 0.6           # filtro de las distancias (1 = sin filtro)
    STUCK_HINT_TIME = 2.0     # s con la pinza cerrada antes de recordar que separe los dedos
    # Valores por defecto si la calibración sale rara (ratio distancia / tamaño de la mano)
    DEFAULT_CLOSED, DEFAULT_OPEN = 0.10, 0.80

    # Ritmo: las notas caen al compás de la canción
    FALL_TIME = 3.0           # s que tarda una nota en cruzar la pantalla (a la velocidad inicial)
    HIT_WINDOW = 0.45         # s de margen antes/después de la línea para acertar
    PERFECT_WINDOW = 0.15     # s de margen para "Perfecto!"
    HINT_TIME = 1.5           # s antes de llegar la nota se ilumina el dedo que toca
    # Notas largas: hay que mantener la pinza hasta que acabe la cola (trabajo isométrico)
    HOLD_MIN_TIME = 1.3       # s: las notas que duran más que esto se vuelven notas largas
    HOLD_MAX_TIME = 3.0       # s: como mucho se pide mantener esto
    HOLD_OK = 0.80            # fracción de la nota que hay que aguantar para que cuente
    AUDIO_LOOKAHEAD = 0.15    # s que se programa el audio por adelantado (para que vaya a tempo)
    INPUT_LATENCY = 0.10      # s que tarda la cámara + MediaPipe en ver la pinza (se descuenta al juzgar)
    GAME_MIN_TIME = 45.0      # si la canción dura menos, se repite (hasta MAX_REPEATS veces)
    MAX_REPEATS = 3

    # Dificultad adaptativa
    TEMPO_START, TEMPO_MIN, TEMPO_MAX = 0.75, 0.50, 1.10   # velocidad de la canción (1 = original)
    TEMPO_UP, TEMPO_DOWN = 1.03, 0.93                      # si acierta / si le cuesta
    GAP_START, GAP_MIN, GAP_MAX = 1.2, 0.6, 2.4            # s mínimos entre dos notas del jugador
    ADAPT_WINDOW = 8          # últimas notas que se miran para adaptar
    REFUERZO = 0.30           # probabilidad de mandar una nota al dedo que más le cuesta
