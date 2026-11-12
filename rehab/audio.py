"""Música y efectos de sonido, generados con numpy (sin archivos de audio).

- Música de fondo: un bucle suave de acordes (Do - La menor - Fa - Sol) con
  un arpegio por encima. La compone el propio programa, así no hay
  problemas de derechos de autor.
- Piano: cada acierto toca la siguiente nota del "Himno de la alegría"
  (Beethoven, dominio público). Si el paciente acierta seguido, oye la
  canción entera: es una recompensa que motiva a seguir.

Un mezclador (Mixer) suma la música y los efectos en tiempo real con
sounddevice. Si el ordenador no tiene audio, el juego sigue sin sonido.
"""
import threading

import numpy as np

import config

SR = 44100  # muestras por segundo

try:
    import sounddevice as sd
except Exception:  # noqa: BLE001
    sd = None

NOTE_INDEX = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
              "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def freq(note: str) -> float:
    """'A4' -> 440 Hz, 'C5' -> 523 Hz..."""
    name, octave = note[:-1], int(note[-1])
    semitones = NOTE_INDEX[name] + 12 * (octave - 4)
    return 440.0 * 2 ** (semitones / 12)


def _t(duration):
    return np.arange(int(SR * duration)) / SR


def pluck(note_or_freq, duration=0.6, volume=1.0, decay=5.0):
    """Nota tipo piano: fundamental + armónicos, ataque rápido y caída exponencial."""
    f = freq(note_or_freq) if isinstance(note_or_freq, str) else note_or_freq
    t = _t(duration)
    wave = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)
    env = np.exp(-decay * t) * np.minimum(1.0, t / 0.005)
    return (volume * wave * env / 1.55).astype(np.float32)


def pad(notes, duration, volume=1.0):
    """Acorde sostenido y suave (entra y sale despacio)."""
    t = _t(duration)
    wave = sum(np.sin(2 * np.pi * freq(n) * t) for n in notes) / len(notes)
    fade = 0.3
    env = np.minimum(1.0, np.minimum(t / fade, (duration - t) / fade))
    return (volume * wave * env).astype(np.float32)


def background_loop():
    """Bucle de 8 s: 4 acordes de 2 s con un arpegio de corcheas encima."""
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


# Himno de la alegría (Beethoven, 1824 - dominio público)
ODE_TO_JOY = ("E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 E5 D5 D5 "
              "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5 "
              "D5 D5 E5 C5 D5 E5 F5 E5 C5 D5 E5 F5 E5 D5 C5 D5 G4 "
              "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5").split()


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
    """Suma en tiempo real la música de fondo y los efectos que estén sonando."""

    def __init__(self):
        self._lock = threading.Lock()
        self._voices = []           # [muestras, posición]
        self._music = None
        self._music_pos = 0
        self._stream = None
        self.music_on = config.MUSIC_ENABLED
        self.available = False

    def start(self):
        if sd is None:
            print("Aviso: sounddevice no disponible, el juego irá sin sonido.")
            return
        try:
            self._stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                           blocksize=1024, callback=self._callback)
            self._stream.start()
            self.available = True
        except Exception as exc:  # noqa: BLE001
            print(f"Aviso: no se pudo abrir el audio ({exc}). El juego irá sin sonido.")

    def _callback(self, outdata, frames, _time, _status):
        buf = np.zeros(frames, dtype=np.float32)
        with self._lock:
            if self._music is not None and self.music_on:
                idx = (np.arange(frames) + self._music_pos) % len(self._music)
                buf += self._music[idx]
                self._music_pos = (self._music_pos + frames) % len(self._music)
            alive = []
            for voice in self._voices:
                data, pos = voice
                chunk = data[pos:pos + frames]
                buf[:len(chunk)] += chunk
                voice[1] = pos + frames
                if voice[1] < len(data):
                    alive.append(voice)
            self._voices = alive
        np.clip(buf, -1.0, 1.0, out=buf)
        outdata[:, 0] = buf

    def play(self, samples):
        if self.available:
            with self._lock:
                self._voices.append([samples, 0])

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
