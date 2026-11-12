"""Modo hombro: Fruit Ninja de rehabilitación.

Cómo funciona:
1. Calibración: el paciente sube los brazos por los lados todo lo que pueda
   y guardamos el ángulo máximo de cada hombro (su rango de movimiento, ROM).
2. Juego: aparecen frutas en el borde de ese rango, a la distancia del brazo
   estirado. El paciente las corta con la mano del mismo lado.
3. Dificultad adaptativa: si acierta, el "reto" sube y las frutas salen un
   poco más arriba (más allá de su máximo); si falla, baja.

El ángulo del hombro se mide con MediaPipe Pose como el ángulo entre la
vertical y el brazo (hombro -> codo): 0 grados = brazo abajo, 90 = en
horizontal, 180 = brazo arriba.
"""
import random
from dataclasses import dataclass

import cv2

from config import MIN_VISIBILITY
from config import Ninja as C
from rehab import audio, ui
from rehab.games.base import Minigame
from rehab.geometry import angle_deg, distance, point_at_angle
from rehab.vision import draw_pose, to_px

# Índices de MediaPipe Pose de cada brazo: (hombro, codo, muñeca, índice)
CHAINS = [(11, 13, 15, 19), (12, 14, 16, 20)]
SIDE_NAMES = {"izq": "izquierdo", "der": "derecho"}
FRUIT_COLORS = [(40, 40, 220), (40, 160, 255), (60, 200, 60), (0, 215, 255), (180, 60, 200)]
GRAVITY = 900.0  # px/s^2 para los trozos de fruta
SLICE_SOUND = audio.slice_sound()


@dataclass
class Arm:
    shoulder: tuple
    elbow: tuple
    wrist: tuple
    index: tuple
    outward: int        # +1 si el brazo abre hacia la derecha de la pantalla, -1 a la izquierda
    angle: float        # apertura del hombro en grados

    @property
    def length(self) -> float:
        """Longitud del brazo en píxeles en este frame (hombro-codo + codo-muñeca)."""
        return distance(self.shoulder, self.elbow) + distance(self.elbow, self.wrist)


def read_arms(landmarks, width: int, height: int) -> dict:
    """Devuelve {"izq": Arm, "der": Arm} con los brazos bien visibles.

    La imagen está en espejo, así que el brazo que se ve a la derecha de la
    pantalla es el derecho del paciente. Lo decidimos por posición en pantalla
    para no depender de las etiquetas izquierda/derecha de MediaPipe.
    """
    if landmarks is None:
        return {}
    found = []
    for s, e, w, i in CHAINS:
        if min(landmarks[k].visibility for k in (s, e, w)) < MIN_VISIBILITY:
            continue
        shoulder, elbow = to_px(landmarks[s], width, height), to_px(landmarks[e], width, height)
        wrist, index = to_px(landmarks[w], width, height), to_px(landmarks[i], width, height)
        vertical = (shoulder[0], shoulder[1] + 100)  # punto justo debajo del hombro
        found.append((shoulder, elbow, wrist, index, angle_deg(vertical, shoulder, elbow)))

    # El centro del cuerpo: media de los dos hombros (estén visibles o no)
    center_x = (landmarks[11].x + landmarks[12].x) / 2 * width
    arms = {}
    for shoulder, elbow, wrist, index, angle in found:
        side = "der" if shoulder[0] >= center_x else "izq"
        arms[side] = Arm(shoulder, elbow, wrist, index, 1 if side == "der" else -1, angle)
    return arms


@dataclass
class Fruit:
    pos: tuple
    side: str
    angle: float        # ángulo de hombro necesario para alcanzarla
    spawn_time: float
    life: float
    color: tuple


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple


class ShoulderNinja(Minigame):
    key = "hombro"
    title = "Hombro - Fruit Ninja"
    uses = "pose"
    intro_time = C.INTRO_TIME
    game_time = C.GAME_TIME

    def __init__(self, patient: str):
        super().__init__(patient)
        self.calib_elapsed = 0.0
        self.calib = {"izq": 0.0, "der": 0.0}      # ROM máximo en la calibración
        self.rom_max = {"izq": 0.0, "der": 0.0}    # ROM máximo durante el juego
        self.hits = 0
        self.misses = 0
        self.hit_angles = []
        self.reaction_times = []
        self.challenge = C.CHALLENGE_START
        self.life = C.LIFE_START
        self.fruit = None
        self.next_spawn = 0.0
        self.last_side = "der"
        self.particles = []

    # --------------------------------------------------------------- intro
    def intro_lines(self):
        return [
            "MODO HOMBRO - Fruit Ninja",
            "Colocate para que se te vea de cintura para arriba.",
            "Corta cada fruta con la mano de SU lado.",
            "Saldran en el limite de lo que alcanzas: estira un poco mas!",
        ]

    def draw_landmarks(self, frame, landmarks):
        if landmarks is not None:
            draw_pose(frame, landmarks)

    # --------------------------------------------------------- calibración
    def update_calibration(self, frame, landmarks, dt):
        h, w = frame.shape[:2]
        arms = read_arms(landmarks, w, h)
        ui.message_box(frame, ["CALIBRACION", "Sube los dos brazos por los lados", "lo mas alto que puedas"],
                       y_center=int(h * 0.2), scale=0.9)

        if not arms:
            self.warn_not_detected(frame, "No te veo bien: aparta un poco de la camara")
            return False

        self.calib_elapsed += dt  # el tiempo solo corre cuando se te ve
        for side, arm in arms.items():
            self.calib[side] = max(self.calib[side], arm.angle)
            self._draw_arm_angle(frame, arm, best=self.calib[side])

        progress = self.calib_elapsed / C.CALIB_TIME
        ui.progress_ring(frame, (w // 2, int(h * 0.85)), 40, progress)

        if progress >= 1.0:
            for side in self.calib:
                self.calib[side] = max(self.calib[side], C.MIN_CALIB_ANGLE)
            return True
        return False

    def _draw_arm_angle(self, frame, arm: Arm, best: float):
        # Línea gris = mejor marca; texto = ángulo actual
        record_end = point_at_angle(arm.shoulder, arm.length, best, arm.outward)
        cv2.line(frame, tuple(map(int, arm.shoulder)), tuple(map(int, record_end)), ui.GREY, 2, cv2.LINE_AA)
        label_pos = (arm.shoulder[0] + arm.outward * 30 - (90 if arm.outward < 0 else 0), arm.shoulder[1] - 25)
        ui.put_text(frame, f"{arm.angle:.0f} gr", label_pos, 0.8, ui.YELLOW, 2)

    # --------------------------------------------------------------- juego
    def update_game(self, frame, landmarks, dt):
        h, w = frame.shape[:2]
        now = self.phase_time
        arms = read_arms(landmarks, w, h)
        self.draw_landmarks(frame, landmarks)

        if not arms:
            self.warn_not_detected(frame, "No te veo bien: aparta un poco de la camara")
        for side, arm in arms.items():
            self.rom_max[side] = max(self.rom_max[side], arm.angle)
            self._draw_arm_angle(frame, arm, best=self.calib[side])

        if self.fruit is None and now >= self.next_spawn and arms:
            self._spawn_fruit(arms, w, h, now)

        if self.fruit is not None:
            self._update_fruit(frame, arms, now)

        self._update_particles(frame, dt)

    def _spawn_fruit(self, arms, w, h, now):
        # Alternamos de lado; si solo se ve un brazo, usamos ese
        options = [s for s in ("izq", "der") if s in arms]
        side = next((s for s in options if s != self.last_side), options[0])
        self.last_side = side
        arm = arms[side]

        target = min(175.0, max(25.0, self.calib[side] * self.challenge))
        angle = random.uniform(max(15.0, target - C.ANGLE_SPREAD), target)
        x, y = point_at_angle(arm.shoulder, arm.length * 0.95, angle, arm.outward)
        r = C.FRUIT_RADIUS
        x = min(max(x, r + 5), w - r - 5)
        y = min(max(y, 70 + r), h - r - 5)
        self.fruit = Fruit((x, y), side, angle, now, self.life, random.choice(FRUIT_COLORS))

    def _update_fruit(self, frame, arms, now):
        f = self.fruit
        age = now - f.spawn_time
        center = tuple(map(int, f.pos))

        # Dibujo: fruta + anillo que se encoge con el tiempo que le queda
        cv2.circle(frame, center, C.FRUIT_RADIUS, f.color, -1, cv2.LINE_AA)
        cv2.circle(frame, (center[0] - 10, center[1] - 12), 9, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (center[0], center[1] - C.FRUIT_RADIUS), (8, 14), 30, 0, 360, (40, 140, 40), -1)
        remaining = max(0.0, 1 - age / f.life)
        ring = int(C.FRUIT_RADIUS + 10 + 40 * remaining)
        cv2.circle(frame, center, ring, ui.WHITE, 2, cv2.LINE_AA)
        ui.put_text(frame, SIDE_NAMES[f.side][:3].upper(), (center[0], center[1] + C.FRUIT_RADIUS + 30),
                    0.6, ui.WHITE, 1, center=True)

        # ¿La corta la mano de su lado?
        arm = arms.get(f.side)
        if arm is not None:
            reach = C.FRUIT_RADIUS + C.HIT_MARGIN
            if min(distance(arm.wrist, f.pos), distance(arm.index, f.pos)) <= reach:
                self._on_hit(now, arm)
                return
        if age >= f.life:
            self._on_miss(now)

    def on_game_start(self):
        audio.mixer.set_music(audio.background())

    def _on_hit(self, now, arm):
        f = self.fruit
        audio.mixer.play(SLICE_SOUND)
        self.hits += 1
        self.hit_angles.append(arm.angle)
        self.reaction_times.append(now - f.spawn_time)
        self.challenge = min(C.CHALLENGE_MAX, self.challenge + C.CHALLENGE_UP)
        self.life = max(C.LIFE_MIN, self.life - 0.1)
        for _ in range(16):
            self.particles.append(Particle(f.pos[0], f.pos[1], random.uniform(-350, 350),
                                           random.uniform(-450, -50), 0.7, f.color))
        self.fruit = None
        self.next_spawn = now + C.SPAWN_GAP

    def _on_miss(self, now):
        self.misses += 1
        self.challenge = max(C.CHALLENGE_MIN, self.challenge - C.CHALLENGE_DOWN)
        self.life = min(C.LIFE_MAX, self.life + 0.25)
        self.fruit = None
        self.next_spawn = now + C.SPAWN_GAP

    def _update_particles(self, frame, dt):
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vy += GRAVITY * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            cv2.circle(frame, (int(p.x), int(p.y)), max(2, int(10 * p.life)), p.color, -1, cv2.LINE_AA)
            alive.append(p)
        self.particles = alive

    def hud_right(self):
        return f"Frutas: {self.hits}   Reto: {self.challenge * 100:.0f}%"

    # ---------------------------------------------------------- resultados
    def results(self):
        total = self.hits + self.misses
        precision = 100 * self.hits / total if total else 0.0
        reaction = sum(self.reaction_times) / len(self.reaction_times) if self.reaction_times else 0.0

        lines = [
            f"Frutas cortadas: {self.hits} de {total}  ({precision:.0f}%)",
            f"Tiempo medio de reaccion: {reaction:.2f} s",
        ]
        for side in ("izq", "der"):
            gain = self.rom_max[side] - self.calib[side]
            lines.append(f"Hombro {SIDE_NAMES[side]}: calibracion {self.calib[side]:.0f} gr  ->  "
                         f"maximo en juego {self.rom_max[side]:.0f} gr ({gain:+.0f})")
        lines.append(f"Nivel de reto final: {self.challenge * 100:.0f}%")

        row = {
            "fecha": self.started_at.strftime("%Y-%m-%d %H:%M"),
            "paciente": self.patient,
            "aciertos": self.hits,
            "fallos": self.misses,
            "precision": round(precision, 1),
            "rom_calib_izq": round(self.calib["izq"], 1),
            "rom_calib_der": round(self.calib["der"], 1),
            "rom_max_izq": round(self.rom_max["izq"], 1),
            "rom_max_der": round(self.rom_max["der"], 1),
            "reaccion_media_s": round(reaction, 2),
            "reto_final": round(self.challenge, 2),
        }
        return lines, row
