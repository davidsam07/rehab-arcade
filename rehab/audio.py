"""Música y efectos de sonido, generados con numpy (sin archivos de audio).

- Piano: cada nota se sintetiza sumando armónicos que se apagan a distinta
  velocidad (los agudos antes), más un pequeño "golpe" de martillo al
  principio. Suena bastante más a piano que una onda senoidal pura.
- Acompañamiento: bajo y acordes de la canción, tocados al mismo tempo que la
  melodía. El juego los programa con unas décimas de antelación
  (Mixer.play_in) para que vayan a ritmo aunque la cámara dé algún tirón.
- Modo hombro: un bucle suave de acordes (Do - La menor - Fa - Sol).

Un mezclador (Mixer) suma todo en tiempo real con sounddevice. Si el
ordenador no tiene audio, el juego sigue sin sonido.
"""
import threading
from functools import lru_cache

import numpy as np

import config

SR = 44100  # muestras por segundo

try:
    import sounddevice as sd
except Exception:  # noqa: BLE001
    sd = None

NOTE_INDEX = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
              "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}

# Acordes: (bajo, notas del acorde). Las notas van en una octava media para no tapar la melodía.
CHORDS = {
    "C": ("C3", ["E4", "G4", "C5"]),
    "F": ("F2", ["F4", "A4", "C5"]),
    "G": ("G2", ["D4", "G4", "B4"]),
    "G7": ("G2", ["D4", "F4", "B4"]),
    "D": ("D3", ["D4", "F#4", "A4"]),
    "D7": ("D3", ["C4", "F#4", "A4"]),
    "E7": ("E3", ["D4", "G#4", "B4"]),
    "Am": ("A2", ["E4", "A4", "C5"]),
    "Dm": ("D3", ["D4", "F4", "A4"]),
    "Em": ("E3", ["E4", "G4", "B4"]),
    "A7": ("A2", ["E4", "G4", "C#5"]),
}


def freq(note: str) -> float:
    """'A4' -> 440 Hz, 'C5' -> 523 Hz..."""
    name, octave = note[:-1], int(note[-1])
    semitones = NOTE_INDEX[name] + 12 * (octave - 4)
    return 440.0 * 2 ** (semitones / 12)


def _t(duration):
    return np.arange(int(SR * duration)) / SR


def _normalize(wave, volume):
    peak = np.max(np.abs(wave)) or 1.0
    return (volume * wave / peak).astype(np.float32)


def pluck(note_or_freq, duration=0.6, volume=1.0, decay=5.0):
    """Nota corta tipo pizzicato: fundamental + armónicos y caída exponencial."""
    f = freq(note_or_freq) if isinstance(note_or_freq, str) else note_or_freq
    t = _t(duration)
    wave = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)
    env = np.exp(-decay * t) * np.minimum(1.0, t / 0.005)
    return (volume * wave * env / 1.55).astype(np.float32)


def piano(note_or_freq, duration=1.6, volume=1.0, brightness=1.0):
    """Nota de piano sintetizada (aditiva)."""
    f = freq(note_or_freq) if isinstance(note_or_freq, str) else note_or_freq
    t = _t(duration)
    wave = np.zeros_like(t)
    for k, amp in enumerate([1.0, 0.55, 0.30, 0.16, 0.09, 0.05], start=1):
        if k * f > SR / 2.2:
            break
        # Cada armónico se apaga antes que el anterior; un pelín desafinado para que suene "vivo"
        wave += (amp * brightness ** (k - 1)) * np.sin(2 * np.pi * k * f * 1.0007 ** (k - 1) * t) \
            * np.exp(-(1.6 + 1.1 * k) * t)
    hammer = np.random.default_rng(int(f)).uniform(-1, 1, len(t)) * np.exp(-90 * t) * 0.12
    attack = np.minimum(1.0, t / 0.004)
    release = np.minimum(1.0, (duration - t) / 0.05)  # sin chasquido al final
    return _normalize((wave + hammer) * attack * release, volume)


@lru_cache(maxsize=256)
def piano_note(note: str, volume: float) -> np.ndarray:
    """Nota de piano cacheada (se genera una vez y se reutiliza)."""
    return piano(note, 1.6, volume)


@lru_cache(maxsize=64)
def chord_sound(name: str, volume: float) -> np.ndarray:
    """Acorde corto y suave (las tres notas casi a la vez, como una mano en el piano)."""
    _, notes = CHORDS[name]
    out = np.zeros(int(SR * 0.9), dtype=np.float32)
    for i, n in enumerate(notes):
        s = piano(n, 0.9 - 0.012 * i, 1.0, brightness=0.6)
        start = int(0.012 * i * SR)  # ligerísimo arpegio
        out[start:start + len(s)] += s
    return _normalize(out, volume)


@lru_cache(maxsize=64)
def bass_sound(name: str, volume: float, fifth: bool = False) -> np.ndarray:
    """Nota grave del acorde (la fundamental, o la quinta para alternar)."""
    root = freq(CHORDS[name][0]) * (1.5 if fifth else 1.0)
    return piano(root, 1.0, volume, brightness=0.5)


def chime(step: int) -> np.ndarray:
    """Sonido de "bien hecho" en la calibración: sube una nota por paso."""
    return piano_note(["C5", "D5", "E5", "F5", "G5", "A5"][step % 6], config.SFX_VOLUME)


def pad(notes, duration, volume=1.0):
    """Acorde sostenido y suave (entra y sale despacio)."""
    t = _t(duration)
    wave = sum(np.sin(2 * np.pi * freq(n) * t) for n in notes) / len(notes)
    fade = 0.3
    env = np.minimum(1.0, np.minimum(t / fade, (duration - t) / fade))
    return (volume * wave * env).astype(np.float32)


def background_loop():
    """Bucle de 8 s para el modo hombro: 4 acordes de 2 s con un arpegio encima."""
    chords = [
        ("C3", ["C4", "E4", "G4"]),
        ("A2", ["A3", "C4", "E4"]),
        ("F2", ["F3", "A3", "C4"]),
        ("G2", ["G3", "B3", "D4"]),
    ]
    chord_len, step = 2.0, 0.25
    loop = np.zeros(int(SR * chord_len * len(chords)), dtype=np.float32)
    for c, (bass, notes) in enumerate(chords):
        start = int(c * chord_len * SR)
        block = pad(notes, chord_len, 0.5)
        block += pluck(bass, chord_len, 0.6, decay=1.5)[:len(block)]
        pattern = [notes[0], notes[1], notes[2], notes[1]] * 2
        for i, n in enumerate(pattern):
            s = int(i * step * SR)
            f = freq(n) * (2 if i % 4 == 2 else 1)  # la tercera nota, una octava más alta
            note = pluck(f, 0.5, 0.35, decay=6)
            end = min(len(block), s + len(note))
            block[s:end] += note[:end - s]
        loop[start:start + len(block)] += block
    loop /= np.max(np.abs(loop)) or 1.0
    return loop * config.MUSIC_VOLUME


def slice_sound():
    """'Fiuu-pop' al cortar una fruta: barrido de frecuencia + un poco de ruido."""
    t = _t(0.18)
    f = np.linspace(1400, 350, len(t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    rng = np.random.default_rng(0)
    wave = 0.7 * np.sin(phase) + 0.3 * rng.uniform(-1, 1, len(t))
    env = np.exp(-18 * t)
    return (config.SFX_VOLUME * wave * env).astype(np.float32)


class Mixer:
    """Suma en tiempo real la música de fondo y los sonidos que estén sonando.

    Cada sonido ("voz") guarda en qué muestra tiene que empezar. Así se pueden
    programar sonidos para dentro de unos milisegundos con precisión de muestra,
    que es lo que hace falta para que el acompañamiento vaya a tempo.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._voices = []           # [muestras, muestra de inicio, es_musica]
        self._music = None
        self._music_pos = 0
        self._clock = 0             # muestras ya enviadas a la tarjeta de sonido
        self._stream = None
        self.music_on = config.MUSIC_ENABLED
        self.available = False

    def start(self):
        if sd is None:
            print("Aviso: sounddevice no disponible, el juego irá sin sonido.")
            return
        try:
            self._stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                           blocksize=512, callback=self._callback)
            self._stream.start()
            self.available = True
        except Exception as exc:  # noqa: BLE001
            print(f"Aviso: no se pudo abrir el audio ({exc}). El juego irá sin sonido.")

    def _callback(self, outdata, frames, _time, _status):
        buf = np.zeros(frames, dtype=np.float32)
        with self._lock:
            start, end = self._clock, self._clock + frames
            if self._music is not None and self.music_on:
                idx = (np.arange(frames) + self._music_pos) % len(self._music)
                buf += self._music[idx]
                self._music_pos = (self._music_pos + frames) % len(self._music)
            alive = []
            for voice in self._voices:
                data, begin, is_music = voice
                if begin >= end:            # todavía no le toca
                    alive.append(voice)
                    continue
                src = max(0, start - begin)
                dst = max(0, begin - start)
                n = min(frames - dst, len(data) - src)
                if n > 0 and (self.music_on or not is_music):
                    buf[dst:dst + n] += data[src:src + n]
                if begin + len(data) > end:
                    alive.append(voice)
            self._voices = alive
            self._clock = end
        np.clip(buf, -1.0, 1.0, out=buf)
        outdata[:, 0] = buf

    def play(self, samples, music=False):
        """Suena ya (en el siguiente bloque de audio)."""
        self.play_in(samples, 0.0, music)

    def play_in(self, samples, delay: float, music=False):
        """Suena dentro de `delay` segundos. music=True: se calla con la tecla M."""
        if self.available:
            with self._lock:
                self._voices.append([samples, self._clock + int(max(0.0, delay) * SR), music])

    def stop_all(self):
        """Corta la música y los sonidos pendientes (al salir de una partida)."""
        with self._lock:
            self._voices = []
            self._music = None

    def set_music(self, loop):
        """Pone un bucle de música de fondo (o None para quitarla)."""
        with self._lock:
            self._music = loop
            self._music_pos = 0

    def toggle_music(self):
        self.music_on = not self.music_on
        return self.music_on

    def close(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()


mixer = Mixer()
_background = None


def background():
    """El bucle de fondo se genera una sola vez y se reutiliza."""
    global _background
    if _background is None:
        _background = background_loop()
    return _background
