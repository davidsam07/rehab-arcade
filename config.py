"""Configuración global de Rehab Arcade.

Todos los parámetros ajustables del juego están aquí, para no tener
"números mágicos" repartidos por el código.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
SFX_VOLUME = 0.30         # notas del piano y sonido al cortar fruta


class Ninja:
    """Modo hombro (Fruit Ninja)."""
    INTRO_TIME = 5.0          # s de instrucciones antes de calibrar
    CALIB_TIME = 6.0          # s para medir el rango máximo
    GAME_TIME = 60.0          # duración de la partida (s)
    MIN_CALIB_ANGLE = 30.0    # si la calibración sale más baja, usamos esto
    FRUIT_RADIUS = 38         # px
    HIT_MARGIN = 20           # px extra alrededor de la fruta para contar el corte
    SPAWN_GAP = 0.4           # s entre una fruta y la siguiente
    # Dificultad adaptativa
    LIFE_START, LIFE_MIN, LIFE_MAX = 3.0, 1.8, 5.0      # s que dura cada fruta
    CHALLENGE_START, CHALLENGE_MIN, CHALLENGE_MAX = 0.95, 0.70, 1.25
    CHALLENGE_UP, CHALLENGE_DOWN = 0.03, 0.05           # cuánto sube/baja el reto
    ANGLE_SPREAD = 35.0       # grados por debajo del objetivo donde puede salir fruta


class Piano:
    """Modo mano (Piano de dedos). Valores pensados para personas mayores."""
    INTRO_TIME = 8.0
    # Calibración guiada, paso a paso
    CALIB_PREP_TIME = 4.0     # s para leer la instrucción y ver qué dedo se ilumina
    CALIB_HOLD_TIME = 3.0     # s que hay que mantener la posición
    CALIB_MAX_WAIT = 12.0     # si no consigue cerrar la pinza, medimos igualmente su mejor intento
    CALIB_ATTEMPT = 0.70      # se considera que lo intenta al cerrar hasta el 70% de la mano abierta
    CALIB_PRAISE_TIME = 2.0   # s de "Muy bien!" entre pasos (le da tiempo a soltar)
    GAME_TIME = 60.0
    HIT_WINDOW = 0.45         # s de margen antes/después de la línea para acertar
    HINT_TIME = 1.2           # s antes de llegar la nota se ilumina el dedo que toca
    # Umbrales de pinza relativos a la calibración (0 = pinza máxima, 1 = mano abierta)
    PINCH_ON = 0.35
    PINCH_OFF = 0.60
    # Valores por defecto si la calibración sale rara (ratio distancia/tamaño mano)
    DEFAULT_ON, DEFAULT_OFF = 0.35, 0.50
    # Dificultad adaptativa
    FALL_START, FALL_MIN, FALL_MAX = 3.5, 1.6, 5.0          # s que tarda una nota en caer
    INTERVAL_START, INTERVAL_MIN, INTERVAL_MAX = 2.2, 0.8, 3.2  # s entre notas
    ADAPT_WINDOW = 8          # últimas notas que se miran para adaptar
