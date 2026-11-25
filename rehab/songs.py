"""Canciones del piano (todas de dominio público).

Cada canción está escrita como texto, nota a nota:

    "E5:1 E5:1 E5:2 | ..."   ->  nota:duración en pulsos (el "|" separa compases, es solo para leerlo mejor)

Los acordes van igual ("C:4 F:2 G7:2 ...") y con ellos se genera el bajo y
los acordes del acompañamiento.

Para añadir una canción: escribir su melodía y sus acordes abajo y meterla
en SONGS. Tienen que durar lo mismo; si no, salta un error al arrancar.
"""
from dataclasses import dataclass

SOLFEGE = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
_SEMITONE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
             "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def midi(pitch: str) -> int:
    """'C4' -> 60, 'A4' -> 69 (para ordenar notas de grave a agudo)."""
    return _SEMITONE[pitch[:-1]] + 12 * (int(pitch[-1]) + 1)


def solfege(pitch: str) -> str:
    """'E5' -> 'Mi', 'F#4' -> 'Fa#'."""
    return SOLFEGE[pitch[0]] + ("#" if "#" in pitch else "")


def _parse(text: str):
    """Convierte 'E5:1 D5:0.5 ...' en [(pulso, nota, duración), ...] y su duración total."""
    events, beat = [], 0.0
    for token in text.replace("|", " ").split():
        name, dur = token.split(":")
        dur = float(dur)
        if name != "R":  # R = silencio
            events.append((beat, name, dur))
        beat += dur
    return tuple(events), beat


@dataclass(frozen=True)
class Song:
    key: str
    title: str
    subtitle: str
    bpm: float              # tempo original (pulsos por minuto)
    beats_per_bar: int      # 4 = compás de 4/4, 3 = vals (3/4)
    pickup: float           # pulsos de anacrusa (notas antes del primer compás)
    melody: tuple           # ((pulso, nota, duración), ...)
    chords: tuple           # ((pulso, acorde, duración), ...)
    length: float           # duración total en pulsos
    christmas: bool = True

    @property
    def mood(self) -> str:
        if self.bpm < 95:
            return "Tranquila"
        return "Alegre" if self.bpm >= 115 else "Animada"


def _song(key, title, subtitle, bpm, beats_per_bar, melody, chords, pickup=0.0, christmas=True):
    mel, mel_len = _parse(melody)
    cho, cho_len = _parse(chords)
    if abs(mel_len - cho_len) > 1e-6:
        raise ValueError(f"{key}: la melodía dura {mel_len} pulsos y los acordes {cho_len}")
    return Song(key, title, subtitle, bpm, beats_per_bar, pickup, mel, cho, mel_len, christmas)


# ----------------------------------------------------------------- canciones

# James Lord Pierpont, 1857
JINGLE_BELLS = _song(
    "jingle", "Jingle Bells", "Navidad - campanas", 120, 4,
    """E5:1 E5:1 E5:2 | E5:1 E5:1 E5:2 | E5:1 G5:1 C5:1.5 D5:0.5 | E5:4 |
       F5:1 F5:1 F5:1.5 F5:0.5 | F5:1 E5:1 E5:1 E5:0.5 E5:0.5 | E5:1 D5:1 D5:1 E5:1 | D5:2 G5:2 |
       E5:1 E5:1 E5:2 | E5:1 E5:1 E5:2 | E5:1 G5:1 C5:1.5 D5:0.5 | E5:4 |
       F5:1 F5:1 F5:1.5 F5:0.5 | F5:1 E5:1 E5:1 E5:0.5 E5:0.5 | G5:1 G5:1 F5:1 D5:1 | C5:4""",
    "C:4 C:4 C:4 C:4 F:4 C:4 D7:4 G7:4 C:4 C:4 C:4 C:4 F:4 C:4 G7:4 C:4")

# Franz Xaver Gruber, 1818 (vals lento)
NOCHE_DE_PAZ = _song(
    "nochedepaz", "Noche de paz", "Navidad - vals lento", 84, 3,
    """G4:1.5 A4:0.5 G4:1 | E4:3 | G4:1.5 A4:0.5 G4:1 | E4:3 | D5:2 D5:1 | B4:3 | C5:2 C5:1 | G4:3 |
       A4:2 A4:1 | C5:1.5 B4:0.5 A4:1 | G4:1.5 A4:0.5 G4:1 | E4:3 |
       A4:2 A4:1 | C5:1.5 B4:0.5 A4:1 | G4:1.5 A4:0.5 G4:1 | E4:3 |
       D5:2 D5:1 | F5:1.5 D5:0.5 B4:1 | C5:3 | E5:3 | C5:1 G4:1 E4:1 | G4:1.5 F4:0.5 D4:1 | C4:6""",
    "C:3 C:3 C:3 C:3 G:3 G:3 C:3 C:3 F:3 F:3 C:3 C:3 F:3 F:3 C:3 C:3 G:3 G7:3 C:3 C:3 C:3 G7:3 C:6")

# Villancico tradicional inglés (vals). Empieza con una nota de anacrusa.
WE_WISH = _song(
    "wewish", "We Wish You a Merry Christmas", "Navidad - villancico", 120, 3,
    """G4:1 | C5:1 C5:0.5 D5:0.5 C5:0.5 B4:0.5 | A4:1 A4:1 A4:1 | D5:1 D5:0.5 E5:0.5 D5:0.5 C5:0.5 |
       B4:1 G4:1 G4:1 | E5:1 E5:0.5 F5:0.5 E5:0.5 D5:0.5 | C5:1 A4:1 G4:0.5 G4:0.5 | A4:1 D5:1 B4:1 | C5:2""",
    "G7:1 C:3 F:3 D7:3 G:3 E7:3 Am:3 F:1 G7:2 C:2",
    pickup=1)

# Villancico tradicional galés
DECK_THE_HALLS = _song(
    "deck", "Deck the Halls", "Navidad - fa la la la", 112, 4,
    """G5:1.5 F5:0.5 E5:1 D5:1 | C5:1 D5:1 E5:1 C5:1 | D5:0.5 E5:0.5 F5:0.5 D5:0.5 E5:1.5 D5:0.5 | C5:1 B4:1 C5:2 |
       G5:1.5 F5:0.5 E5:1 D5:1 | C5:1 D5:1 E5:1 C5:1 | D5:0.5 E5:0.5 F5:0.5 D5:0.5 E5:1.5 D5:0.5 | C5:1 B4:1 C5:2 |
       D5:1.5 E5:0.5 F5:1 D5:1 | E5:1.5 F5:0.5 G5:1 D5:1 | E5:0.5 F5:0.5 G5:1 A5:0.5 B5:0.5 C6:1 | B5:1 A5:1 G5:2 |
       G5:1.5 F5:0.5 E5:1 D5:1 | C5:1 D5:1 E5:1 C5:1 | A5:0.5 A5:0.5 A5:0.5 A5:0.5 G5:1.5 F5:0.5 | E5:1 D5:1 C5:2""",
    """C:4 C:4 G7:4 G7:2 C:2 | C:4 C:4 G7:4 G7:2 C:2 | G7:4 C:4 C:4 G:4 | C:4 C:4 F:4 G7:2 C:2""")

# Ludwig van Beethoven, 1824
HIMNO = _song(
    "himno", "Himno de la alegría", "Beethoven - clásica", 110, 4,
    """E5:1 E5:1 F5:1 G5:1 | G5:1 F5:1 E5:1 D5:1 | C5:1 C5:1 D5:1 E5:1 | E5:1.5 D5:0.5 D5:2 |
       E5:1 E5:1 F5:1 G5:1 | G5:1 F5:1 E5:1 D5:1 | C5:1 C5:1 D5:1 E5:1 | D5:1.5 C5:0.5 C5:2 |
       D5:1 D5:1 E5:1 C5:1 | D5:1 E5:0.5 F5:0.5 E5:1 C5:1 | D5:1 E5:0.5 F5:0.5 E5:1 D5:1 | C5:1 D5:1 G4:2 |
       E5:1 E5:1 F5:1 G5:1 | G5:1 F5:1 E5:1 D5:1 | C5:1 C5:1 D5:1 E5:1 | D5:1.5 C5:0.5 C5:2""",
    """C:4 G:4 C:4 G:4 | C:4 G:4 C:4 G:2 C:2 | G:2 C:2 G:2 C:2 G:2 C:2 C:2 G:2 | C:4 G:4 C:4 G:2 C:2""",
    christmas=False)

SONGS = {s.key: s for s in (JINGLE_BELLS, NOCHE_DE_PAZ, WE_WISH, DECK_THE_HALLS, HIMNO)}
