"""Modo mano: Piano de dedos.

La idea: caen notas como en un piano y hay que juntar el pulgar con el dedo
que toca (la pinza), que es un ejercicio típico de motricidad fina.

1. Calibración: primero se abre la mano y luego se hace la pinza con cada
   dedo. Así sé cuánto puede cerrar cada dedo y los umbrales se adaptan a su
   mano (si un dedo se mueve poco, su umbral es más fácil). Si ya se midió en
   la sesión, se reutiliza.
2. Juego: las notas caen al ritmo de la canción por 4 carriles (índice,
   corazón, anular y meñique), las graves al índice y las agudas al meñique.
   Las que van demasiado seguidas no caen, solo suenan. Las notas largas hay
   que mantenerlas (así también se trabaja la fuerza de la pinza).
3. Dificultad adaptativa: si acierta, la canción va más rápida y caen más
   notas; si falla, más lenta. Los dedos que más fallan reciben más notas.

La pinza se mide con MediaPipe Hands: distancia de la punta del pulgar (4) a
la punta de cada dedo, dividida por el tamaño de la mano (muñeca 0 -> nudillo
del corazón 9), para que dé igual lo cerca que esté la mano de la cámara.

Cosas que fui cambiando al probarlo:
- Al principio cada acierto tocaba su nota, pero la cámara tarda unas décimas
  en ver la pinza y siempre sonaba tarde. Ahora la melodía la toca siempre la
  música a su tiempo y el acierto solo se ve.
- El tiempo va en PULSOS de la canción y sale del reloj del audio (no de los
  frames), descontando el retraso de los altavoces. Si no, las notas no
  cuadraban con la música.
"""
import bisect
import math
import random
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

import config
from config import Piano as C
from rehab import assets, audio, ui
from rehab.games.base import Minigame
from rehab.geometry import distance
from rehab.scene import WinterScene
from rehab.songs import SONGS, midi, solfege
from rehab.vision import HAND_CONNECTIONS, draw_hand, to_px

FINGERS = ["Índice", "Corazón", "Anular", "Meñique"]
FINGER_KEYS = ["indice", "corazon", "anular", "menique"]
TIPS = [8, 12, 16, 20]          # puntas de los dedos en MediaPipe Hands
THUMB_TIP, WRIST, MIDDLE_MCP = 4, 0, 9
LANE_COLORS = [(90, 90, 240), (60, 200, 250), (100, 215, 90), (240, 160, 70)]
PRAISE = ["¡Muy bien!", "¡Perfecto!", "¡Genial!", "¡Estupendo!", "¡Así se hace!"]


def pinch_ratios(landmarks, width, height):
    """Distancia pulgar-dedo / tamaño de la mano, para los 4 dedos."""
    pts = [to_px(lm, width, height) for lm in landmarks]
    size = distance(pts[WRIST], pts[MIDDLE_MCP]) or 1.0
    return [distance(pts[THUMB_TIP], pts[tip]) / size for tip in TIPS], pts


@dataclass
class Note:
    lane: int
    beat: float         # pulso en el que hay que tocarla
    dur: float          # duración en pulsos (para dibujarla más o menos larga)
    pitch: str
    playable: bool      # True = la toca el paciente; False = la toca el ordenador
    done: bool = False
    hold_end: float = 0.0   # nota larga: pulso hasta el que hay que mantener la pinza (0 = nota normal)
    holding: bool = False   # el paciente la está manteniendo ahora mismo
    sounded: bool = False   # su sonido ya está programado


class FingerPiano(Minigame):
    key = "mano"
    title = "Piano de dedos"
    uses = "hand"
    intro_time = C.INTRO_TIME
    game_time = float("inf")   # la partida dura lo que dure la canción

    # Pasos de calibración: None = mano abierta, 0..3 = pinza con ese dedo
    CALIB_STEPS = [None, 0, 1, 2, 3]

    def __init__(self, patient: str, song_key: str = None, calibration: dict = None):
        super().__init__(patient)
        self.song = SONGS.get(song_key) or next(iter(SONGS.values()))
        self.title = self.song.title

        # Calibración
        self.calib_step = 0
        self.calib_stage = "preparar"   # preparar -> medir -> bien
        self.stage_time = 0.0
        self.hold_time = 0.0
        self.open_samples = [[] for _ in FINGERS]
        self.pinch_samples = [[] for _ in FINGERS]
        self.open_val = [C.DEFAULT_OPEN] * 4
        self.closed_val = [C.DEFAULT_CLOSED] * 4
        self.calibrated = False
        if calibration:
            self.open_val, self.closed_val = list(calibration["open"]), list(calibration["closed"])
            self.calibrated = True
            self.intro_time = C.INTRO_TIME_RECALL
        self._apply_thresholds()

        # Pinza
        self.pinched = [False] * 4
        self.pinch_min = 0.0         # punto más cerrado de la pinza actual
        self.pinch_time = 0.0        # cuánto lleva cerrada la pinza actual
        self.smooth = None           # distancias filtradas

        # Ritmo y dificultad
        self.tempo = self.tempo_target = C.TEMPO_START
        self.min_gap = C.GAP_START
        self.beat = 0.0
        self.recent = deque(maxlen=C.ADAPT_WINDOW)
        self.rng = random.Random()
        self._audio_t = None
        self.notes = []
        self._build_timeline()

        # Estadísticas
        self.hits = [0] * 4
        self.misses = [0] * 4
        self.wrong = [0] * 4         # pinzas sin nota en ese carril
        self.used = [0] * 4          # notas que ha recibido cada dedo
        self.offsets = []            # error de tiempo de cada acierto (s)
        self.combo = 0
        self.best_combo = 0
        self.holding_note = None     # nota larga que se está manteniendo
        self.holds_ok = 0
        self.holds_total = 0
        self.effects = []            # animaciones de acierto / fallo
        self.scene = None            # paisaje nevado de fondo (como en el trineo)

    # ------------------------------------------------------------- canción
    def _build_timeline(self):
        """Prepara la melodía y el acompañamiento, en pulsos desde el inicio de la partida."""
        s = self.song
        bpm0 = s.bpm * C.TEMPO_START
        # Pulsos que se ven en pantalla: una nota tarda FALL_TIME segundos en caer al tempo inicial
        self.lookahead = C.FALL_TIME * bpm0 / 60
        # Antes de la primera nota hay unos compases de introducción (solo acompañamiento),
        # los justos para que la primera nota caiga desde arriba
        lead_bars = math.ceil((self.lookahead + s.pickup) / s.beats_per_bar)
        self.lead = lead_bars * s.beats_per_bar - s.pickup
        seconds = s.length * 60 / bpm0
        self.repeats = max(1, min(C.MAX_REPEATS, math.ceil(C.GAME_MIN_TIME / seconds)))
        self.end_beat = self.lead + self.repeats * s.length

        self.melody = [(self.lead + r * s.length + b, p, d) for r in range(self.repeats) for b, p, d in s.melody]
        self.mel_i = 0
        self.last_play_beat = -1e9

        # Notas graves al índice, agudas al meñique (como las teclas de un piano)
        pitches = sorted({p for _, p, _ in s.melody}, key=midi)
        self.pitch_lane = {p: min(3, i * 4 // len(pitches)) for i, p in enumerate(pitches)}

        # Acompañamiento "pum-pa": bajo en el primer pulso del compás y acordes en los demás
        chord_starts = [(0.0, s.chords[0][1])]  # la introducción usa el primer acorde
        for r in range(self.repeats):
            chord_starts += [(self.lead + r * s.length + b, name) for b, name, _ in s.chords]
        starts = [b for b, _ in chord_starts]
        self.accomp = []
        for beat in range(int(math.ceil(self.end_beat))):
            name = chord_starts[bisect.bisect_right(starts, beat + 1e-6) - 1][1]
            for sound in audio.accomp_hits(name, beat % s.beats_per_bar, s.beats_per_bar):
                self.accomp.append((beat, sound))
        # Acorde final
        for sound in audio.accomp_hits(s.chords[-1][1], 0, s.beats_per_bar):
            self.accomp.append((self.end_beat, sound))
        self.acc_i = 0

    @property
    def bpm(self):
        return self.song.bpm * self.tempo

    # --------------------------------------------------------------- intro
    def intro_lines(self):
        if self.calibrated:
            return [
                f"Piano de dedos - {self.song.title}",
                "Usamos la medida de tu mano de antes.",
                "Cuando una nota llegue a la línea,",
                "junta el pulgar con el dedo que se ilumine.",
            ]
        return [
            f"Piano de dedos - {self.song.title}",
            "Pon una mano delante de la cámara, con la palma hacia ti.",
            "Primero mediremos tus dedos, sin prisa.",
            "Después, cuando una nota llegue a la línea,",
            "junta el pulgar con el dedo que se ilumine.",
        ]

    def draw_landmarks(self, frame, landmarks):
        if landmarks is not None:
            draw_hand(frame, landmarks)

    def calibration_data(self):
        """Medida de la mano, para reutilizarla en la siguiente canción."""
        if not self.calibrated:
            return None
        return {"open": list(self.open_val), "closed": list(self.closed_val)}

    # --------------------------------------------------------- calibración
    def update_calibration(self, frame, landmarks, dt):
        """Calibración paso a paso y sin prisa (la primera versión iba demasiado rápida).

        Cada paso tiene tres momentos:
          1. preparar: se explica qué hacer y se marcan los dedos sobre la mano.
          2. medir: espera a que lo intente y lo mantenga unos segundos. Si no
             consigue cerrar la pinza, al rato se mide su mejor intento para
             que no se quede atascado.
          3. bien: mensaje de ánimo y tiempo para soltar la mano.
        El tiempo solo cuenta mientras se ve la mano.
        """
        if self.calibrated:
            return True
        h, w = frame.shape[:2]
        step = self.CALIB_STEPS[self.calib_step]
        total = len(self.CALIB_STEPS)

        if landmarks is None:
            top = self._calib_box(frame, total, ["Pon la mano delante de la cámara", "con la palma mirando hacia ti"])
            self.warn_not_detected(frame, "No veo tu mano", y=top - 70)
            return False

        ratios, pts = pinch_ratios(landmarks, w, h)
        self.stage_time += dt
        self._highlight_fingers(frame, pts, step)

        if self.calib_stage == "preparar":
            if step is None:
                lines = ["Abre bien la mano", "y separa los dedos"]
            else:
                lines = ["Junta la punta del PULGAR", f"con la punta del dedo {FINGERS[step].upper()}"]
            self._calib_box(frame, total, lines + ["(mira los círculos en tu mano)"],
                            self.stage_time / C.CALIB_PREP_TIME, ui.GREY)
            if self.stage_time >= C.CALIB_PREP_TIME:
                self._next_stage("medir")

        elif self.calib_stage == "medir":
            if step is None:
                trying = True
                for i, r in enumerate(ratios):
                    self.open_samples[i].append(r)
            else:
                self.pinch_samples[step].append(ratios[step])
                opened = float(np.percentile(self.open_samples[step], 90)) if self.open_samples[step] else 1.0
                trying = ratios[step] < C.CALIB_ATTEMPT * opened or self.stage_time >= C.CALIB_MAX_WAIT

            if trying:
                self.hold_time += dt
                lines = ["Muy bien, mantenlo así...", "sin moverte"]
            elif step is not None and self.stage_time >= C.CALIB_MAX_WAIT / 2:
                lines = ["Hazlo lo mejor que puedas,", "no pasa nada si no llegan a tocarse"]
            else:
                lines = ["Junta la punta del PULGAR", f"con la punta del dedo {FINGERS[step].upper()}"]
            self._calib_box(frame, total, lines, self.hold_time / C.CALIB_HOLD_TIME, ui.GREEN)
            if self.hold_time >= C.CALIB_HOLD_TIME:
                self._next_stage("bien")
                audio.mixer.play(audio.chime(self.calib_step))

        elif self.calib_stage == "bien":
            text = PRAISE[self.calib_step % len(PRAISE)]
            ui.rounded_rect(frame, (w // 2 - 330, h // 2 - 95, w // 2 + 330, h // 2 + 85), 30, ui.DARK, 0.85,
                            border=ui.GREEN)
            ui.put_text(frame, text, (w // 2, h // 2 - 5), 2.0, ui.GREEN, 2, center=True, shadow=False)
            ui.put_text(frame, "Ya puedes soltar la mano", (w // 2, h // 2 + 55), 0.9, ui.WHITE, 2, center=True,
                        shadow=False)
            if self.stage_time >= C.CALIB_PRAISE_TIME:
                self.calib_step += 1
                self._next_stage("preparar")
                if self.calib_step >= total:
                    self._compute_thresholds()
                    return True
        return False

    def _next_stage(self, stage):
        self.calib_stage = stage
        self.stage_time = 0.0
        self.hold_time = 0.0

    def _calib_box(self, frame, total, lines, progress=None, ring_color=ui.GREEN):
        """Instrucciones abajo (para no tapar la mano), con el anillo de progreso y los pasos."""
        return ui.instruction_card(frame, f"Midiendo tus dedos - paso {self.calib_step + 1} de {total}", lines,
                                   progress, ring_color, ui.YELLOW, steps=(self.calib_step, total))

    def _highlight_fingers(self, frame, pts, step):
        """Círculos que laten sobre los dedos que hay que juntar."""
        pulse = 0.5 + 0.5 * math.sin(self.stage_time * 6)
        radius = int(14 + 8 * pulse)
        if step is None:  # mano abierta: todas las puntas
            for tip in [THUMB_TIP] + TIPS:
                cv2.circle(frame, tuple(map(int, pts[tip])), radius, ui.YELLOW, 3, cv2.LINE_AA)
            return
        thumb, tip = tuple(map(int, pts[THUMB_TIP])), tuple(map(int, pts[TIPS[step]]))
        cv2.line(frame, thumb, tip, LANE_COLORS[step], 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, radius, ui.WHITE, 4, cv2.LINE_AA)
        cv2.circle(frame, tip, radius, LANE_COLORS[step], 4, cv2.LINE_AA)
        ui.put_text(frame, "Pulgar", (thumb[0] - 40, thumb[1] + 8), 0.8, ui.WHITE, 2, align="right")
        ui.put_text(frame, FINGERS[step], (tip[0] + 30, tip[1] - 10), 0.8, LANE_COLORS[step], 2)

    def _compute_thresholds(self):
        for i in range(4):
            if not self.open_samples[i] or not self.pinch_samples[i]:
                continue
            # Percentiles en vez de max/min para que un frame raro no estropee la calibración
            opened = float(np.percentile(self.open_samples[i], 90))
            closed = float(np.percentile(self.pinch_samples[i], 10))
            if opened - closed < 0.08:  # casi no hay movimiento medible: valores por defecto
                continue
            self.open_val[i], self.closed_val[i] = opened, closed
        self.calibrated = True
        self._apply_thresholds()

    def _apply_thresholds(self):
        self.range = [max(0.08, o - c) for o, c in zip(self.open_val, self.closed_val)]
        self.on_thr = [c + C.PINCH_ON * r for c, r in zip(self.closed_val, self.range)]
        self.off_thr = [c + C.PINCH_OFF * r for c, r in zip(self.closed_val, self.range)]

    # --------------------------------------------------------------- pinza
    def _update_pinch(self, raw, dt):
        """Decide qué dedo está haciendo la pinza. Devuelve el dedo si acaba de empezar.

        Solo dejo UN dedo activo a la vez, porque al juntar el pulgar con el
        meñique pasa cerca del anular y contaba los dos.
        La pinza se suelta cuando:
          - el dedo se abre por encima del umbral OFF,
          - o se separa bastante de su punto más cerrado (antes había que abrir
            la mano entera y el pulgar se quedaba "enganchado"),
          - o otro dedo está claramente más cerrado (entonces cambia a ese).
        """
        if self.smooth is None:
            self.smooth = list(raw)
        a = C.SMOOTHING
        self.smooth = [a * r + (1 - a) * s for r, s in zip(raw, self.smooth)]
        ratios = self.smooth
        closeness = [ratios[i] / self.on_thr[i] for i in range(4)]  # < 1 = pinza

        active = self.pinched.index(True) if True in self.pinched else None
        if active is not None:
            self.pinch_time += dt
            self.pinch_min = min(self.pinch_min, ratios[active])
            rng = self.range[active]
            release_at = min(self.off_thr[active],
                             max(self.on_thr[active] + C.RELEASE_GAP * rng, self.pinch_min + C.RELEASE_RISE * rng))
            others = [i for i in range(4) if i != active and closeness[i] < 1.0]
            better = min(others, key=lambda i: closeness[i]) if others else None
            if better is not None and closeness[better] < C.SWITCH_RATIO * closeness[active]:
                self.pinched[active] = False
                return self._press(better, ratios)
            if ratios[active] > release_at:
                self.pinched[active] = False
            return None

        below = [i for i in range(4) if closeness[i] < 1.0]
        if below:
            # El dedo más "cerrado" respecto a su propio umbral
            return self._press(min(below, key=lambda i: closeness[i]), ratios)
        return None

    def _press(self, finger, ratios):
        self.pinched[finger] = True
        self.pinch_min = ratios[finger]
        self.pinch_time = 0.0
        return finger

    # --------------------------------------------------------------- juego
    def on_game_start(self):
        audio.mixer.stop_all()
        self.beat = 0.0
        self._audio_t = None

    def _geometry(self, w, h):
        x1, x2 = int(w * 0.45), int(w * 0.975)
        lane_w = (x2 - x1) // 4
        return x1, lane_w, 92, int(h * 0.75), int(h * 0.955)  # x1, ancho, arriba, línea, abajo

    def update_game(self, frame, landmarks, dt):
        h, w = frame.shape[:2]

        # Reloj de la canción (en pulsos). El tempo cambia suave, sin saltos.
        self.tempo += (self.tempo_target - self.tempo) * min(1.0, dt * 0.8)
        step = dt
        if audio.mixer.available:  # reloj del audio: más estable que el de los frames
            t = audio.mixer.now()
            step = 0.0 if self._audio_t is None else min(0.25, max(0.0, t - self._audio_t))
            self._audio_t = t
        self.beat += step * self.bpm / 60
        self._spawn_notes()
        self._schedule_audio()

        self.draw_landmarks(frame, landmarks)
        onset, pts = None, None
        if landmarks is None:
            self.smooth = None
            self.pinched = [False] * 4   # si se pierde la mano, la pinza se suelta
        else:
            ratios, pts = pinch_ratios(landmarks, w, h)
            onset = self._update_pinch(ratios, dt)
            self._draw_hand_overlay(frame, pts)
        # La cámara se queda en pequeño en una esquina; el resto de la pantalla es el juego
        cam = cv2.resize(frame, (int(w * 0.225), int(h * 0.225)), interpolation=cv2.INTER_AREA)
        if self.scene is None:
            self.scene = WinterScene(w, h)
        self.scene.draw(frame, dt, speed=12.0, snow=self.song.christmas)

        if onset is not None:
            self._on_pinch(onset)
        self._update_hold()
        window = C.HIT_WINDOW * self.bpm / 60
        seen_beat = self.beat - C.INPUT_LATENCY * self.bpm / 60
        for note in self.notes:
            if note.playable and not note.done and not note.holding and seen_beat > note.beat + window:
                note.done = True
                self.misses[note.lane] += 1
                self.combo = 0
                self._register(False)
                self.effects.append({"lane": note.lane, "text": "Fallo", "color": ui.GREY, "t": 0.0, "ring": False})
        self.notes = [n for n in self.notes if not n.done]

        self._draw_piano(frame, dt)
        self._draw_hand_view(frame, pts, (24, 180, int(w * 0.42), int(h * 0.72)))
        self._draw_camera(frame, cam, (24, int(h * 0.74)))
        self._draw_next_finger(frame)
        if self.beat >= self.end_beat + 1:
            self.finished = True

    def _spawn_notes(self):
        """Saca las notas que van a entrar en pantalla y decide cuáles toca el paciente."""
        while self.mel_i < len(self.melody) and self.melody[self.mel_i][0] <= self.beat + self.lookahead:
            beat, pitch, dur = self.melody[self.mel_i]
            self.mel_i += 1
            gap = (beat - self.last_play_beat) * 60 / self.bpm
            on_beat = abs(beat - round(beat)) < 1e-6
            # Para el paciente: notas separadas al menos min_gap, preferiblemente en un pulso fuerte
            playable = gap >= self.min_gap and (on_beat or gap >= 1.8 * self.min_gap)
            lane = self.pitch_lane[pitch]
            hold_end = 0.0
            if playable:
                lane = self._reinforce(lane)
                self.used[lane] += 1
                self.last_play_beat = beat
                if dur * 60 / self.bpm >= C.HOLD_MIN_TIME:
                    # Nota larga: se mantiene casi toda su duración (y la siguiente nota espera a que acabe)
                    hold_end = beat + min(dur - 0.25, C.HOLD_MAX_TIME * self.bpm / 60)
                    self.last_play_beat = hold_end
            self.notes.append(Note(lane, beat, dur, pitch, playable, hold_end=hold_end))

    def _reinforce(self, lane):
        """A veces manda la nota al dedo que más le cuesta (o al que menos ha trabajado)."""
        if self.rng.random() >= C.REFUERZO:
            return lane
        total = sum(self.used) + 1

        def need(i):
            weak = (self.misses[i] + 0.5 * self.wrong[i] + 1) / (self.hits[i] + self.misses[i] + 2)
            return weak + max(0.0, 0.2 - self.used[i] / total)

        best = max(range(4), key=need)
        return best if need(best) > need(lane) + 0.1 else lane

    def _schedule_audio(self):
        """Programa con antelación el acompañamiento y la melodía.

        Cada sonido se programa "latency" segundos antes de su pulso (lo que
        tarda en salir por los altavoces), así se oye justo cuando la nota
        llega a la línea.
        """
        spb = 60 / self.bpm
        lat = audio.mixer.latency
        now = audio.mixer.now()
        horizon = self.beat + (C.AUDIO_LOOKAHEAD + lat) / spb

        def when(beat):
            return now + (beat - self.beat) * spb - lat

        while self.acc_i < len(self.accomp) and self.accomp[self.acc_i][0] <= horizon:
            beat, sound = self.accomp[self.acc_i]
            audio.mixer.play_at(sound, when(beat), music=True)
            self.acc_i += 1
        for note in self.notes:
            if not note.sounded and note.beat <= horizon:
                volume = config.MELODY_VOLUME if note.playable else config.AUTO_NOTE_VOLUME
                audio.mixer.play_at(audio.piano_note(note.pitch, volume), when(note.beat), music=True)
                note.sounded = True
                if not note.playable:
                    note.done = True

    def _on_pinch(self, lane):
        window = C.HIT_WINDOW * self.bpm / 60
        # La pinza ocurrió un poco antes de que la cámara la viera: descontamos ese retardo
        seen_beat = self.beat - C.INPUT_LATENCY * self.bpm / 60
        candidates = [n for n in self.notes if n.playable and n.lane == lane and not n.done and not n.holding
                      and abs(seen_beat - n.beat) <= window]
        if not candidates:
            self.wrong[lane] += 1
            return
        note = min(candidates, key=lambda n: abs(seen_beat - n.beat))
        if note.hold_end:
            note.holding = True      # nota larga: ahora hay que mantenerla
            self.holding_note = note
        else:
            note.done = True
        offset = (seen_beat - note.beat) * 60 / self.bpm
        self.hits[lane] += 1
        self.offsets.append(offset)
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        perfect = abs(offset) <= C.PERFECT_WINDOW
        if note.hold_end:
            self.effects.append({"lane": lane, "text": "¡Mantén!", "color": ui.CYAN, "t": 0.0, "ring": True,
                                 "name": solfege(note.pitch)})
            self._register(True)
            return
        self.effects.append({"lane": lane, "text": "¡Perfecto!" if perfect else "¡Bien!",
                             "color": ui.YELLOW if perfect else ui.GREEN, "t": 0.0, "ring": True,
                             "name": solfege(note.pitch)})
        self._register(True)

    def _update_hold(self):
        """Nota larga: termina bien si aguanta la pinza hasta el final (o casi)."""
        note = self.holding_note
        if note is None:
            return
        if self.pinched[note.lane] and self.beat < note.hold_end:
            return  # sigue manteniéndola
        held = (min(self.beat, note.hold_end) - note.beat) / (note.hold_end - note.beat)
        ok = held >= C.HOLD_OK
        self.holds_total += 1
        self.holds_ok += ok
        if ok:
            self.effects.append({"lane": note.lane, "text": "¡Aguantado!", "color": ui.YELLOW, "t": 0.0,
                                 "ring": True})
        else:
            self.effects.append({"lane": note.lane, "text": "Casi...", "color": ui.ORANGE, "t": 0.0,
                                 "ring": False})
        note.holding = False
        note.done = True
        self.holding_note = None

    def _register(self, hit):
        """Adapta la velocidad de la canción y la cantidad de notas a la precisión reciente."""
        self.recent.append(hit)
        if len(self.recent) < 4:
            return
        accuracy = sum(self.recent) / len(self.recent)
        if accuracy > 0.8:      # va bien: más rápido y más notas
            self.tempo_target = min(C.TEMPO_MAX, self.tempo_target * C.TEMPO_UP)
            self.min_gap = max(C.GAP_MIN, self.min_gap * 0.96)
        elif accuracy < 0.5:    # le cuesta: más lento y más espacio entre notas
            self.tempo_target = max(C.TEMPO_MIN, self.tempo_target * C.TEMPO_DOWN)
            self.min_gap = min(C.GAP_MAX, self.min_gap * 1.08)

    # -------------------------------------------------------------- dibujo
    def _next_note(self):
        """La siguiente nota del paciente, si está a punto de llegar."""
        window = C.HIT_WINDOW * self.bpm / 60
        hint = C.HINT_TIME * self.bpm / 60
        upcoming = [n for n in self.notes if n.playable and not n.done and not n.holding
                    and -window <= n.beat - self.beat <= hint]
        return min(upcoming, key=lambda n: n.beat) if upcoming else None

    def _draw_hand_overlay(self, frame, pts):
        thumb = tuple(map(int, pts[THUMB_TIP]))
        for i in range(4):
            tip = tuple(map(int, pts[TIPS[i]]))
            if self.pinched[i]:
                cv2.line(frame, thumb, tip, LANE_COLORS[i], 6, cv2.LINE_AA)
                cv2.circle(frame, tip, 12, LANE_COLORS[i], -1, cv2.LINE_AA)
            else:
                cv2.circle(frame, tip, 7, LANE_COLORS[i], -1, cv2.LINE_AA)
        # Pista: se ilumina en la mano el dedo de la próxima nota
        nxt = self._next_note()
        if nxt is not None:
            radius = int(20 + 6 * math.sin(self.beat * math.pi * 2))
            cv2.circle(frame, tuple(map(int, pts[TIPS[nxt.lane]])), radius, LANE_COLORS[nxt.lane], 5, cv2.LINE_AA)
            cv2.circle(frame, thumb, radius, ui.WHITE, 4, cv2.LINE_AA)

    def _draw_hand_view(self, frame, pts, rect):
        """Mano guía: la mano del paciente dibujada en grande, con el dedo que toca iluminado.

        Como la cámara va en pequeño, así se ve bien qué dedo hay que mover.
        Está centrada en la palma y escalada con el tamaño de la mano, así sale
        igual de grande aunque la mano esté lejos de la cámara.
        """
        x1, y1, x2, y2 = rect
        ui.rounded_rect(frame, rect, 26, ui.DARK, 0.9, border=ui.RED if pts is None else None)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if pts is None:
            assets.draw(frame, "icono_mano", (cx, cy - 40), 150, 150)
            ui.put_text(frame, "No veo tu mano", (cx, cy + 62), 0.9, ui.RED, 2, center=True, shadow=False)
            ui.put_text(frame, "Ponla delante", (cx, cy + 100), 0.75, ui.WHITE, 2, center=True, shadow=False)
            ui.put_text(frame, "de la cámara", (cx, cy + 134), 0.75, ui.WHITE, 2, center=True, shadow=False)
            return
        size = distance(pts[WRIST], pts[MIDDLE_MCP]) or 1.0
        scale = (y2 - y1) * 0.36 / size
        palm = np.mean([pts[i] for i in (0, 5, 9, 13, 17)], axis=0)
        ox, oy = cx, int(y1 + (y2 - y1) * 0.70)

        def P(i):
            return int(ox + (pts[i][0] - palm[0]) * scale), int(oy + (pts[i][1] - palm[1]) * scale)

        # Palma rellena y dedos gruesos (como un guante)
        palm_poly = np.array([P(i) for i in (0, 1, 5, 9, 13, 17)], np.int32)
        cv2.fillPoly(frame, [palm_poly], (95, 80, 72), cv2.LINE_AA)
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, P(a), P(b), (205, 195, 190), 16, cv2.LINE_AA)
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, P(a), P(b), (150, 140, 135), 2, cv2.LINE_AA)

        nxt = self._next_note()
        hold = self.holding_note
        target = hold.lane if hold is not None else (nxt.lane if nxt is not None else None)
        thumb = P(THUMB_TIP)
        for i in range(4):
            tip = P(TIPS[i])
            if self.pinched[i]:
                cv2.line(frame, thumb, tip, LANE_COLORS[i], 10, cv2.LINE_AA)
            cv2.circle(frame, tip, 17 if self.pinched[i] else 13, LANE_COLORS[i], -1, cv2.LINE_AA)
            cv2.circle(frame, tip, 17 if self.pinched[i] else 13, ui.WHITE, 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, 14, ui.WHITE, -1, cv2.LINE_AA)
        if target is not None:  # el dedo que toca: anillos que laten y su nombre al lado
            tip = P(TIPS[target])
            r = int(26 + 7 * math.sin(self.beat * math.pi * 2))
            cv2.circle(frame, tip, r, LANE_COLORS[target], 5, cv2.LINE_AA)
            cv2.circle(frame, thumb, r, ui.WHITE, 4, cv2.LINE_AA)
            if hold is None:
                cv2.line(frame, thumb, tip, LANE_COLORS[target], 2, cv2.LINE_AA)
            right = tip[0] < cx
            ui.put_text(frame, FINGERS[target], (tip[0] + (34 if right else -34), tip[1] + 10), 0.8,
                        LANE_COLORS[target], 2, align="left" if right else "right")

    def _draw_camera(self, frame, cam, pos):
        """La imagen de la cámara en pequeño, para que el paciente se vea."""
        x, y = pos
        ch, cw = cam.shape[:2]
        ui.rounded_rect(frame, (x - 5, y - 5, x + cw + 5, y + ch + 5), 14, ui.DARK, 0.9, border=ui.WHITE)
        frame[y:y + ch, x:x + cw] = cam
        ui.put_text(frame, "Tú", (x + 12, y + 30), 0.7, ui.WHITE, 2)

    def _draw_next_finger(self, frame):
        """Tarjeta arriba a la izquierda: qué dedo toca ahora (o un aviso si la pinza sigue cerrada)."""
        nxt = self._next_note()
        active = self.pinched.index(True) if True in self.pinched else None
        x1, y1 = 24, 88
        hold = self.holding_note
        if hold is not None:
            color = LANE_COLORS[hold.lane]
            progress = (self.beat - hold.beat) / (hold.hold_end - hold.beat)
            ui.rounded_rect(frame, (x1, y1, x1 + 460, y1 + 96), 22, ui.DARK, 0.9, border=color)
            ui.put_text(frame, "Mantén:", (x1 + 24, y1 + 44), 0.75, ui.WHITE, 2, shadow=False)
            ui.put_text(frame, FINGERS[hold.lane], (x1 + 150, y1 + 46), 1.05, color, 2, shadow=False)
            ui.progress_bar(frame, (x1 + 24, y1 + 64, x1 + 436, y1 + 80), progress, color)
        elif active is not None and self.pinch_time > C.STUCK_HINT_TIME and (nxt is None or nxt.lane != active):
            ui.rounded_rect(frame, (x1, y1, x1 + 470, y1 + 76), 22, ui.DARK, 0.88, border=ui.ORANGE)
            ui.put_text(frame, "Separa un poco el pulgar", (x1 + 24, y1 + 34), 0.75, ui.ORANGE, 2, shadow=False)
            ui.put_text(frame, f"para soltar el {FINGERS[active].lower()}", (x1 + 24, y1 + 64), 0.6, ui.WHITE, 2,
                        shadow=False)
        elif nxt is not None:
            color = LANE_COLORS[nxt.lane]
            ui.rounded_rect(frame, (x1, y1, x1 + 400, y1 + 76), 22, ui.DARK, 0.88, border=color)
            cv2.circle(frame, (x1 + 44, y1 + 38), 20, color, -1, cv2.LINE_AA)
            ui.put_text(frame, "Ahora:", (x1 + 80, y1 + 48), 0.75, ui.WHITE, 2, shadow=False)
            ui.put_text(frame, FINGERS[nxt.lane], (x1 + 190, y1 + 50), 1.05, color, 2, shadow=False)

    def _draw_piano(self, frame, dt):
        h, w = frame.shape[:2]
        x1, lane_w, top, line_y, bottom = self._geometry(w, h)
        x2 = x1 + 4 * lane_w
        ppb = (line_y - top) / self.lookahead      # píxeles por pulso
        bpb = self.song.beats_per_bar
        nxt = self._next_note()

        if not assets.draw_rect(frame, "fondo_piano", (x1 - 10, top - 10, x2 + 10, bottom + 10)):
            ui.rounded_rect(frame, (x1 - 10, top - 10, x2 + 10, bottom + 10), 24, ui.DARKER, 1.0)
        for i in range(4):  # carriles con un tinte muy suave de su color
            lx = x1 + i * lane_w
            ui.rounded_rect(frame, (lx + 4, top, lx + lane_w - 4, line_y), 14, LANE_COLORS[i],
                            0.16 if nxt is not None and nxt.lane == i else 0.07)

        # Líneas de pulso (finas) y de compás (más marcadas): se ve el ritmo bajar
        for b in range(math.ceil(self.beat), int(self.beat + self.lookahead) + 1):
            y = int(line_y - (b - self.beat) * ppb)
            if top <= y < line_y:
                bar = b % bpb == 0
                cv2.line(frame, (x1 + 6, y), (x2 - 6, y), (120, 110, 105) if bar else (75, 68, 62),
                         2 if bar else 1, cv2.LINE_AA)

        # Notas del paciente: la cabeza llega a la línea en su pulso; la cola indica cuánto dura
        for note in self.notes:
            if not note.playable or note.done:
                continue
            if note.hold_end:
                self._draw_long_note(frame, note, x1, lane_w, top, line_y, ppb, note is nxt)
                continue
            y_head = int(line_y - (note.beat - self.beat) * ppb)
            y_head = min(y_head, line_y + 8)     # si llega antes que el paciente, espera en la línea
            length = int(min(160, max(40, note.dur * ppb - 10)))
            y_top = max(top, y_head - length)
            if y_head <= top + 4:
                continue
            lx = x1 + note.lane * lane_w
            color = LANE_COLORS[note.lane]
            if note is nxt:  # brillo alrededor de la siguiente nota
                ui.rounded_rect(frame, (lx + 3, y_top - 6, lx + lane_w - 3, y_head + 6), 18, color, 0.35)
            self._draw_note_box(frame, (lx + 10, y_top, lx + lane_w - 10, y_head), color)
            if y_head - y_top > 30:
                ui.put_text(frame, solfege(note.pitch), (lx + lane_w // 2, y_head - 12), 0.55, ui.DARKER, 2,
                            center=True, shadow=False)

        # Línea de golpeo
        ui.rounded_rect(frame, (x1, line_y - 7, x2, line_y + 7), 7, ui.WHITE, 0.25)
        cv2.line(frame, (x1, line_y), (x2, line_y), ui.WHITE, 3, cv2.LINE_AA)

        # Teclas de piano: marfil, y del color del dedo mientras la pinza está hecha
        for i in range(4):
            lx = x1 + i * lane_w
            pressed = self.pinched[i]
            dy = 5 if pressed else 0
            rect = (lx + 5, line_y + 12 + dy, lx + lane_w - 5, bottom + dy)
            if not assets.draw_rect(frame, "tecla", rect, tint=LANE_COLORS[i] if pressed else None):
                ui.rounded_rect(frame, rect, 14, LANE_COLORS[i] if pressed else ui.IVORY, 1.0)
            if nxt is not None and nxt.lane == i:
                ui.rounded_rect(frame, rect, 14, ui.WHITE, 0.0, border=LANE_COLORS[i], border_th=5)
            ui.rounded_rect(frame, (rect[0], rect[1], rect[2], rect[1] + 14), 7, LANE_COLORS[i], 1.0)
            ui.put_text(frame, FINGERS[i], (lx + lane_w // 2, bottom - 22 + dy), 0.62,
                        ui.WHITE if pressed else ui.INK, 2, center=True, shadow=pressed)

        # Efectos: anillo que se expande y texto que sube
        alive = []
        for fx in self.effects:
            fx["t"] += dt
            t = fx["t"]
            if t > 0.8:
                continue
            cx = x1 + fx["lane"] * lane_w + lane_w // 2
            if fx["ring"] and t < 0.4:
                cv2.circle(frame, (cx, line_y), int(20 + 140 * t), fx["color"], max(1, int(8 - 18 * t)), cv2.LINE_AA)
            y = int(line_y - 50 - 90 * t)
            ui.put_text(frame, fx["text"], (cx, y), 0.75, fx["color"], 2, center=True)
            if fx.get("name") and t < 0.6:
                ui.put_text(frame, fx["name"], (cx, y - 34), 0.6, ui.WHITE, 2, center=True)
            alive.append(fx)
        self.effects = alive

        if self.combo >= 3:
            ui.put_text(frame, f"¡{self.combo} seguidas!", ((x1 + x2) // 2, top + 44), 1.0, ui.YELLOW, 2, center=True)

    @staticmethod
    def _draw_note_box(frame, rect, color):
        """Una nota: imagen assets/nota.png (o un degradado) teñida con el color del dedo y borde blanco."""
        if not assets.draw_rect(frame, "nota", rect, tint=color):
            ui.rounded_rect(frame, rect, 14, color, 0.95)
        ui.rounded_rect(frame, rect, 14, color, 0.0, border=ui.WHITE, border_th=2)

    def _draw_long_note(self, frame, note, x1, lane_w, top, line_y, ppb, is_next):
        """Nota larga: cabeza como una nota normal y una cola que hay que "consumir" manteniendo la pinza."""
        lx = x1 + note.lane * lane_w
        color = LANE_COLORS[note.lane]
        if note.holding:
            y_head = line_y
        else:
            y_head = min(int(line_y - (note.beat - self.beat) * ppb), line_y + 8)
        y_end = max(top, int(line_y - (note.hold_end - self.beat) * ppb))
        if y_head <= top + 4:
            return
        if y_head - y_end > 8:  # cola
            ui.rounded_rect(frame, (lx + 26, y_end, lx + lane_w - 26, y_head), 14, color,
                            0.9 if note.holding else 0.55, border=ui.WHITE if note.holding else color, border_th=2)
            if y_head - y_end > 120:
                ui.put_text(frame, "MANTÉN", (lx + lane_w // 2, (y_end + y_head) // 2 + 8), 0.5, ui.WHITE, 2,
                            center=True)
        if note.holding:  # brillo sobre la línea mientras la mantiene
            pulse = 0.35 + 0.25 * math.sin(self.beat * math.pi * 4)
            ui.rounded_rect(frame, (lx + 4, line_y - 26, lx + lane_w - 4, line_y + 10), 14, color, pulse)
            return
        if is_next:
            ui.rounded_rect(frame, (lx + 3, y_head - 56, lx + lane_w - 3, y_head + 6), 18, color, 0.35)
        self._draw_note_box(frame, (lx + 10, y_head - 50, lx + lane_w - 10, y_head), color)
        ui.put_text(frame, solfege(note.pitch), (lx + lane_w // 2, y_head - 14), 0.55, ui.DARKER, 2,
                    center=True, shadow=False)

    def hud_center(self):
        lap = min(self.repeats, int(max(0.0, self.beat - self.lead) // self.song.length) + 1)
        text = f"Canción  {lap}/{self.repeats}" if self.repeats > 1 else "Canción"
        return text + f"   ·   velocidad {self.tempo * 100:.0f}%"

    def hud_progress(self):
        return min(1.0, max(0.0, (self.beat - self.lead) / (self.end_beat - self.lead)))

    def hud_right(self):
        total = sum(self.hits) + sum(self.misses)
        return f"Notas: {sum(self.hits)}/{total}"

    # ---------------------------------------------------------- resultados
    def results(self):
        total_hits, total_miss, total_wrong = sum(self.hits), sum(self.misses), sum(self.wrong)
        total = total_hits + total_miss
        precision = 100 * total_hits / total if total else 0.0
        per_finger = []
        for i in range(4):
            n = self.hits[i] + self.misses[i]
            per_finger.append(100 * self.hits[i] / n if n else 0.0)
        offset_ms = 1000 * float(np.mean(np.abs(self.offsets))) if self.offsets else 0.0

        # Dedo a reforzar: el de peor precisión, solo si hay diferencia entre dedos
        worst = int(np.argmin(per_finger)) if total and min(per_finger) < max(per_finger) else None
        lines = [
            f"Canción: {self.song.title}",
            f"Notas acertadas: {total_hits} de {total}  ({precision:.0f}%)",
            "   ".join(f"{FINGERS[i]}: {per_finger[i]:.0f}%" for i in range(4)),
            f"Mejor racha: {self.best_combo} seguidas   ·   Pinzas sin nota: {total_wrong}",
            f"Desfase medio con el ritmo: {offset_ms:.0f} ms   ·   Velocidad final: {self.tempo * 100:.0f}%",
        ]
        if self.holds_total:
            lines.append(f"Notas largas aguantadas: {self.holds_ok} de {self.holds_total}")
        if worst is not None:
            lines.append(f"Dedo a trabajar más: {FINGERS[worst]}")

        row = {
            "fecha": self.started_at.strftime("%Y-%m-%d %H:%M"),
            "paciente": self.patient,
            "aciertos": total_hits,
            "fallos": total_miss,
            "errores": total_wrong,
            "precision": round(precision, 1),
        }
        for i, key in enumerate(FINGER_KEYS):
            row[f"prec_{key}"] = round(per_finger[i], 1)
        row["desfase_medio_ms"] = round(offset_ms)
        row["cancion"] = self.song.key
        row["tempo_final_pct"] = round(self.tempo * 100)
        row["mejor_racha"] = self.best_combo
        row["largas_ok"] = self.holds_ok
        row["largas_total"] = self.holds_total
        return lines, row
