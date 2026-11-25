"""Música y sonidos, todo generado con numpy (no hay archivos de audio).

- Piano: cada nota es una suma de armónicos que se van apagando, más un
  pequeño "golpe" al principio. No es un piano de verdad, pero da bastante
  más el pego que una onda senoidal.
- Acompañamiento: bajo y acordes de la canción al mismo tempo que la melodía.
- Trineo: la canción entera se renderiza en un bucle que suena de fondo.

El Mixer va sumando todo en tiempo real con sounddevice. Si el ordenador no
tiene audio, el juego sigue funcionando, solo que sin sonido.
"""
import math
import threading
import time
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
    "D7": ("D3", ["C4", "F#4", "A4"]),
    "E7": ("E3", ["D4", "G#4", "B4"]),
    "Am": ("A2", ["E4", "A4", "C5"]),
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
    return piano(note, 1.6, volume, brightness=0.8)  # algo más cálida, para que empaste con la base


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


def accomp_hits(chord: str, pos_in_bar: int, beats_per_bar: int):
    """Sonidos del acompañamiento "pum-pa" en un pulso: bajo en el 1, acordes en los demás."""
    vol = config.MUSIC_VOLUME
    if pos_in_bar == 0:
        return [bass_sound(chord, round(vol * 1.6, 3)), chord_sound(chord, round(vol * 1.0, 3))]
    if beats_per_bar == 4 and pos_in_bar == 2:
        return [bass_sound(chord, round(vol * 1.3, 3), fifth=True), chord_sound(chord, round(vol * 0.8, 3))]
    return [chord_sound(chord, round(vol * 0.65, 3))]


def render_song(song, tempo=1.0):
    """Toda la canción (melodía + acompañamiento) en un bucle de audio, para música de fondo."""
    import bisect
    spb = 60 / (song.bpm * tempo)
    n = int(round(song.length * spb * SR))
    out = np.zeros(n, dtype=np.float32)

    def add(sound, t):  # lo que sobresale por el final vuelve al principio: el bucle no se corta
        i = int(t * SR) % n
        end = min(n, i + len(sound))
        out[i:end] += sound[:end - i]
        if i + len(sound) > n:
            rest = sound[end - i:][:n]
            out[:len(rest)] += rest

    for beat, pitch, _ in song.melody:
        add(piano_note(pitch, config.AUTO_NOTE_VOLUME), beat * spb)
    starts = [b for b, _, _ in song.chords]
    for beat in range(int(math.ceil(song.length))):
        chord = song.chords[max(0, bisect.bisect_right(starts, beat + 1e-6) - 1)][1]
        for sound in accomp_hits(chord, int((beat - song.pickup) % song.beats_per_bar), song.beats_per_bar):
            add(sound, beat * spb)
    np.clip(out, -1.0, 1.0, out=out)
    return out


class Mixer:
    """Suma en tiempo real la música de fondo y los sonidos que estén sonando.

    Cada sonido guarda en qué muestra tiene que empezar, así puedo programar
    sonidos para dentro de unos milisegundos y que el acompañamiento vaya a tempo.

    También lo uso como reloj del piano (now()). Probándolo me di cuenta de que
    el audio de Windows sale con unos 200 ms de retraso y las notas no cuadraban
    con la música, así que ahora el juego sabe ese retraso (latency) y lo descuenta.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._voices = []           # [muestras, muestra de inicio, es_musica]
        self._music = None
        self._music_pos = 0
        self._clock = 0             # muestras ya enviadas a la tarjeta de sonido
        self._block_start = 0       # primera muestra del último bloque enviado
        self._wall = None           # momento (perf_counter) en que se envió ese bloque
        self._stream = None
        self.music_on = config.MUSIC_ENABLED
        self.available = False
        self.latency = 0.0          # s desde que se programa un sonido hasta que se oye

    def start(self):
        if sd is None:
            print("Aviso: sounddevice no disponible, el juego irá sin sonido.")
            return
        try:
            # latency="low": en Windows (MME) baja el retardo de ~210 ms a ~90 ms sin cortes
            self._stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                           blocksize=512, latency="low", callback=self._callback)
            self._stream.start()
            self.latency = float(self._stream.latency) + config.AUDIO_EXTRA_LATENCY
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
            self._block_start, self._clock = start, end
            self._wall = time.perf_counter()
        np.clip(buf, -1.0, 1.0, out=buf)
        outdata[:, 0] = buf

    def now(self) -> float:
        """Reloj del audio en segundos (continuo: se interpola entre bloque y bloque)."""
        with self._lock:
            base, wall, ahead = self._block_start / SR, self._wall, (self._clock - self._block_start) / SR
        if wall is None:
            return 0.0
        return base + min(time.perf_counter() - wall, 2 * ahead)

    def play_at(self, samples, when: float, music=False):
        """Programa un sonido en el instante `when` del reloj now() (si ya pasó, suena enseguida)."""
        if self.available:
            with self._lock:
                self._voices.append([samples, max(self._clock, int(when * SR)), music])

    def play(self, samples, music=False):
        """Suena ya (en el siguiente bloque de audio)."""
        self.play_at(samples, 0.0, music)

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
