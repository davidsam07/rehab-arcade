"""Modo mano: Piano de dedos.

Cómo funciona:
1. Calibración: el paciente abre la mano y luego hace la pinza pulgar con
   cada dedo. Así sabemos cuánto puede cerrar y abrir CADA dedo, y ajustamos
   los umbrales a su mano (un dedo con poca movilidad tiene un umbral más fácil).
2. Juego: caen notas por 4 carriles (índice, corazón, anular, meñique).
   Cuando una nota llega a la línea, el paciente junta el pulgar con ese dedo.
3. Dificultad adaptativa: la velocidad de las notas se ajusta a su precisión
   reciente, y los dedos que más fallan reciben más notas para entrenarlos.

La pinza se mide con MediaPipe Hands: distancia entre la punta del pulgar (4)
y la punta de cada dedo, dividida por el tamaño de la mano (muñeca 0 ->
nudillo del corazón 9). Al dividir, da igual lo cerca que esté la mano de la cámara.
"""
import random
from collections import deque
from dataclasses import dataclass

import math

import cv2
import numpy as np

import config
from config import Piano as C
from rehab import audio, ui
from rehab.games.base import Minigame
from rehab.geometry import distance
from rehab.vision import draw_hand, to_px

FINGERS = ["Indice", "Corazon", "Anular", "Menique"]
FINGER_KEYS = ["indice", "corazon", "anular", "menique"]
TIPS = [8, 12, 16, 20]          # puntas de los dedos en MediaPipe Hands
THUMB_TIP, WRIST, MIDDLE_MCP = 4, 0, 9
LANE_COLORS = [(80, 80, 240), (60, 200, 250), (90, 220, 90), (240, 160, 60)]

# Las notas de la melodía se generan una vez al cargar el módulo
MELODY = [audio.pluck(n, 0.7, config.SFX_VOLUME, decay=4) for n in audio.ODE_TO_JOY]
PRAISE = ["Muy bien!", "Perfecto!", "Genial!", "Estupendo!"]


def pinch_ratios(landmarks, width, height):
    """Distancia pulgar-dedo / tamaño de la mano, para los 4 dedos."""
    pts = [to_px(lm, width, height) for lm in landmarks]
    size = distance(pts[WRIST], pts[MIDDLE_MCP]) or 1.0
    return [distance(pts[THUMB_TIP], pts[tip]) / size for tip in TIPS], pts


@dataclass
class Note:
    lane: int
    spawn_time: float
    fall_time: float
    done: bool = False

    @property
    def hit_time(self):
        return self.spawn_time + self.fall_time


class FingerPiano(Minigame):
    key = "mano"
    title = "Mano - Piano de dedos"
    uses = "hand"
    intro_time = C.INTRO_TIME
    game_time = C.GAME_TIME

    # Pasos de calibración: None = mano abierta, 0..3 = pinza con ese dedo
    CALIB_STEPS = [None, 0, 1, 2, 3]

    def __init__(self, patient: str):
        super().__init__(patient)
        self.calib_step = 0
        self.calib_stage = "preparar"   # preparar -> medir -> bien
        self.stage_time = 0.0
        self.hold_time = 0.0
        self.open_samples = [[] for _ in FINGERS]
        self.pinch_samples = [[] for _ in FINGERS]
        self.on_thr = [C.DEFAULT_ON] * 4
        self.off_thr = [C.DEFAULT_OFF] * 4
        self.pinched = [False] * 4

        self.notes = []
        self.next_note = 0.0
        self.fall_time = C.FALL_START
        self.interval = C.INTERVAL_START
        self.recent = deque(maxlen=C.ADAPT_WINDOW)
        self.last_lanes = deque(maxlen=2)

        self.hits = [0] * 4
        self.misses = [0] * 4
        self.wrong = [0] * 4       # pinzas sin nota en ese carril
        self.offsets = []          # error de tiempo de cada acierto (s)
        self.feedback = []         # [carril, texto, color, tiempo restante]
        self.melody_pos = 0        # siguiente nota del Himno de la alegría

    # --------------------------------------------------------------- intro
    def intro_lines(self):
        return [
            "MODO MANO - Piano de dedos",
            "Pon una mano delante de la camara, con la palma hacia ti.",
            "Primero mediremos tus dedos, sin prisa.",
            "Despues, cuando una nota llegue a la linea,",
            "junta el pulgar con el dedo que se ilumine.",
        ]

    def draw_landmarks(self, frame, landmarks):
        if landmarks is not None:
            draw_hand(frame, landmarks)

    # --------------------------------------------------------- calibración
    def update_calibration(self, frame, landmarks, dt):
        """Calibración guiada pensada para personas mayores.

        Cada paso tiene tres momentos:
          1. preparar: se explica qué hacer y se iluminan los dedos sobre su mano.
          2. medir: esperamos a que lo intente y que lo mantenga unos segundos.
             Si su movilidad no le deja cerrar la pinza, tras un rato medimos
             igualmente su mejor intento (no queremos que se quede atascado).
          3. bien: mensaje de ánimo y tiempo para soltar la mano.
        El tiempo solo avanza mientras se ve la mano.
        """
        h, w = frame.shape[:2]
        step = self.CALIB_STEPS[self.calib_step]
        total = len(self.CALIB_STEPS)

        if landmarks is None:
            self._calib_box(frame, step, total, ["Pon la mano delante de la camara", "con la palma mirando hacia ti"])
            self.warn_not_detected(frame, "No veo tu mano")
            return False

        ratios, pts = pinch_ratios(landmarks, w, h)
        self.stage_time += dt
        self._highlight_fingers(frame, pts, step)

        if self.calib_stage == "preparar":
            if step is None:
                lines = ["Abre bien la mano", "y separa los dedos"]
            else:
                lines = ["Junta la punta del PULGAR", f"con la punta del dedo {FINGERS[step].upper()}"]
            self._calib_box(frame, step, total, lines + ["(mira los circulos en tu mano)"])
            ui.progress_ring(frame, (w // 2, int(h * 0.85)), 34, self.stage_time / C.CALIB_PREP_TIME, ui.GREY)
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
                lines = ["Muy bien, mantenlo asi...", "sin moverte"]
            elif step is not None and self.stage_time >= C.CALIB_MAX_WAIT / 2:
                lines = ["Hazlo lo mejor que puedas,", "no pasa nada si no llegan a tocarse"]
            else:
                lines = ["Junta la punta del PULGAR", f"con la punta del dedo {FINGERS[step].upper()}"]
            self._calib_box(frame, step, total, lines)
            ui.progress_ring(frame, (w // 2, int(h * 0.85)), 40, self.hold_time / C.CALIB_HOLD_TIME, ui.GREEN, 10)
            if self.hold_time >= C.CALIB_HOLD_TIME:
                self._next_stage("bien")
                audio.mixer.play(MELODY[self.calib_step % len(MELODY)])

        elif self.calib_stage == "bien":
            text = PRAISE[self.calib_step % len(PRAISE)]
            ui.put_text(frame, text, (w // 2, h // 2), 2.2, ui.GREEN, 5, center=True)
            ui.put_text(frame, "Ya puedes soltar la mano", (w // 2, h // 2 + 60), 1.0, ui.WHITE, 2, center=True)
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

    def _calib_box(self, frame, step, total, lines):
        h = frame.shape[0]
        ui.message_box(frame, [f"MIDIENDO TUS DEDOS - paso {self.calib_step + 1} de {total}"] + lines,
                       y_center=int(h * 0.2), scale=1.0)

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
        ui.put_text(frame, "Pulgar", (thumb[0] - 110, thumb[1] + 8), 0.8, ui.WHITE, 2)
        ui.put_text(frame, FINGERS[step], (tip[0] + 25, tip[1] - 10), 0.8, LANE_COLORS[step], 2)

    def _compute_thresholds(self):
        for i in range(4):
            if not self.open_samples[i] or not self.pinch_samples[i]:
                continue
            # Percentiles en vez de max/min para que un frame raro no estropee la calibración
            opened = float(np.percentile(self.open_samples[i], 90))
            closed = float(np.percentile(self.pinch_samples[i], 10))
            if opened - closed < 0.08:  # casi no hay movimiento medible: valores por defecto
                continue
            self.on_thr[i] = closed + C.PINCH_ON * (opened - closed)
            self.off_thr[i] = closed + C.PINCH_OFF * (opened - closed)

    # --------------------------------------------------------------- juego
    def on_game_start(self):
        self.melody_pos = 0
        audio.mixer.set_music(audio.background())

    def _lanes_geometry(self, w, h):
        x1, x2 = int(w * 0.52), int(w * 0.96)
        lane_w = (x2 - x1) // 4
        return x1, lane_w, 75, int(h * 0.80), int(h * 0.95)  # x1, ancho, arriba, línea, abajo

    def update_game(self, frame, landmarks, dt):
        h, w = frame.shape[:2]
        now = self.phase_time
        self.draw_landmarks(frame, landmarks)

        onsets = []
        if landmarks is None:
            self.warn_not_detected(frame, "No veo tu mano: ponla delante de la camara")
        else:
            ratios, pts = pinch_ratios(landmarks, w, h)
            onset = self._update_pinch(ratios)
            if onset is not None:
                onsets.append(onset)
            for i in range(4):
                color = LANE_COLORS[i] if self.pinched[i] else ui.GREY
                cv2.line(frame, tuple(map(int, pts[THUMB_TIP])), tuple(map(int, pts[TIPS[i]])),
                         color, 4 if self.pinched[i] else 1, cv2.LINE_AA)
            # Pista: se ilumina en la mano el dedo de la próxima nota
            upcoming = [n for n in self.notes if not n.done and -C.HIT_WINDOW <= n.hit_time - now <= C.HINT_TIME]
            if upcoming:
                lane = min(upcoming, key=lambda n: n.hit_time).lane
                radius = int(16 + 6 * math.sin(now * 8))
                cv2.circle(frame, tuple(map(int, pts[TIPS[lane]])), radius, LANE_COLORS[lane], 4, cv2.LINE_AA)
                cv2.circle(frame, tuple(map(int, pts[THUMB_TIP])), radius, ui.WHITE, 3, cv2.LINE_AA)

        if now >= self.next_note:
            self._spawn_note(now)
        for lane in onsets:
            self._on_pinch(lane, now)
        for note in self.notes:
            if not note.done and now > note.hit_time + C.HIT_WINDOW:
                note.done = True
                self.misses[note.lane] += 1
                self._register(False, note.lane, "FALLO", ui.RED)
        self.notes = [n for n in self.notes if not n.done]

        self._draw_piano(frame, now, dt)

    def _update_pinch(self, ratios):
        """Decide qué dedo está haciendo la pinza. Devuelve el dedo si acaba de empezar.

        Solo puede haber UN dedo activo: al juntar el pulgar con el meñique, el
        pulgar pasa cerca del anular, y no queremos que eso cuente como pinza.
        Usamos histéresis: se activa por debajo de ON y se suelta por encima de OFF,
        para que el temblor de la mano no genere pulsaciones dobles.
        """
        active = self.pinched.index(True) if True in self.pinched else None
        if active is not None and ratios[active] > self.off_thr[active]:
            self.pinched[active] = False
            active = None
        if active is None:
            below = [i for i in range(4) if ratios[i] < self.on_thr[i]]
            if below:
                # El dedo más "cerrado" respecto a su propio umbral
                finger = min(below, key=lambda i: ratios[i] / self.on_thr[i])
                self.pinched[finger] = True
                return finger
        return None

    def _spawn_note(self, now):
        # Los dedos que más fallan tienen más probabilidad de recibir nota
        weights = []
        for i in range(4):
            weak = (self.misses[i] + 0.5 * self.wrong[i] + 1) / (self.hits[i] + self.misses[i] + 2)
            repeated = len(self.last_lanes) == 2 and all(l == i for l in self.last_lanes)
            weights.append(0.0 if repeated else weak)
        lane = random.choices(range(4), weights=weights)[0]
        self.last_lanes.append(lane)
        self.notes.append(Note(lane, now, self.fall_time))
        self.next_note = now + self.interval

    def _on_pinch(self, lane, now):
        candidates = [n for n in self.notes if n.lane == lane and not n.done
                      and abs(now - n.hit_time) <= C.HIT_WINDOW]
        if not candidates:
            self.wrong[lane] += 1
            self._add_feedback(lane, "x", ui.ORANGE)
            return
        note = min(candidates, key=lambda n: abs(now - n.hit_time))
        note.done = True
        self.hits[lane] += 1
        self.offsets.append(now - note.hit_time)
        # Cada acierto toca la siguiente nota de la canción
        audio.mixer.play(MELODY[self.melody_pos])
        self.melody_pos = (self.melody_pos + 1) % len(MELODY)
        self._register(True, lane, "BIEN!", ui.GREEN)

    def _register(self, hit, lane, text, color):
        """Guarda el resultado y adapta la velocidad a la precisión reciente."""
        self.recent.append(hit)
        self._add_feedback(lane, text, color)
        if len(self.recent) < 4:
            return
        accuracy = sum(self.recent) / len(self.recent)
        if accuracy > 0.8:
            factor = 0.95   # va bien: más rápido
        elif accuracy < 0.5:
            factor = 1.08   # le cuesta: más lento
        else:
            return
        self.fall_time = min(C.FALL_MAX, max(C.FALL_MIN, self.fall_time * factor))
        self.interval = min(C.INTERVAL_MAX, max(C.INTERVAL_MIN, self.interval * factor))

    def _add_feedback(self, lane, text, color):
        self.feedback.append([lane, text, color, 0.6])

    def _draw_piano(self, frame, now, dt):
        h, w = frame.shape[:2]
        x1, lane_w, top, line_y, bottom = self._lanes_geometry(w, h)
        ui.panel(frame, x1, top, x1 + 4 * lane_w, bottom, alpha=0.45)

        for i in range(4):
            lx = x1 + i * lane_w
            cv2.line(frame, (lx, top), (lx, bottom), (90, 90, 90), 1)
            # Tecla: se ilumina mientras la pinza de ese dedo está hecha
            key_color = LANE_COLORS[i] if self.pinched[i] else (70, 70, 70)
            cv2.rectangle(frame, (lx + 4, line_y + 6), (lx + lane_w - 4, bottom - 4), key_color, -1)
            ui.put_text(frame, FINGERS[i], (lx + lane_w // 2, bottom - 18), 0.55, ui.WHITE, 1, center=True)
        cv2.line(frame, (x1, line_y), (x1 + 4 * lane_w, line_y), ui.WHITE, 3)

        for note in self.notes:
            progress = (now - note.spawn_time) / note.fall_time
            y = min(int(top + progress * (line_y - top)), line_y)  # espera sobre la línea
            if y > bottom:
                continue
            lx = x1 + note.lane * lane_w
            cv2.rectangle(frame, (lx + 10, y - 14), (lx + lane_w - 10, y + 14), LANE_COLORS[note.lane], -1)
            cv2.rectangle(frame, (lx + 10, y - 14), (lx + lane_w - 10, y + 14), ui.WHITE, 2)

        alive = []
        for fb in self.feedback:
            lane, text, color, t = fb
            fb[3] -= dt
            if fb[3] <= 0:
                continue
            y = int(line_y - 40 - (0.6 - t) * 80)
            ui.put_text(frame, text, (x1 + lane * lane_w + lane_w // 2, y), 0.8, color, 2, center=True)
            alive.append(fb)
        self.feedback = alive

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
            f"Notas acertadas: {total_hits} de {total}  ({precision:.0f}%)",
            "  ".join(f"{FINGERS[i]}: {per_finger[i]:.0f}%" for i in range(4)),
            f"Pinzas sin nota (errores): {total_wrong}",
            f"Desfase medio con el ritmo: {offset_ms:.0f} ms",
        ]
        if worst is not None:
            lines.append(f"Dedo a trabajar mas: {FINGERS[worst]}")

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
        row["caida_final_s"] = round(self.fall_time, 2)
        return lines, row
