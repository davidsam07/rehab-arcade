"""Modo hombro: Trineo volador.

La idea: un trineo vuela y su altura depende de cuánto subes los brazos por
los lados (abducción de hombro). Para coger los regalos hay que subir y bajar
los brazos todo el rato, que es justo el ejercicio. Al principio este modo era
un Fruit Ninja, pero el trineo engancha más y el movimiento es más continuo.

1. Calibración: se suben los brazos todo lo posible y guardo el ángulo
   máximo de cada hombro (su rango de movimiento).
2. Juego: los regalos salen a distintas alturas dentro de ese rango, y las
   estrellas arriba del todo para que estire un poco más.
3. Dificultad adaptativa: si coge casi todo, los regalos salen más altos
   (hasta un poco por encima de su máximo) y el trineo va más rápido; si le
   cuesta, más bajos y más despacio.

La elevación es el ángulo entre la vertical y el brazo (hombro -> codo) que
saca MediaPipe Pose, dividido por el máximo de la calibración de cada lado.
Uso la media de los dos brazos (o el que se vea).
"""
import math
import random
from collections import deque
from dataclasses import dataclass, field

import cv2
import numpy as np

from config import MIN_VISIBILITY
from config import Sleigh as C
from rehab import assets, audio, ui
from rehab.games.base import Minigame
from rehab.geometry import angle_deg, distance, point_at_angle
from rehab.scene import WinterScene
from rehab.songs import SONGS
from rehab.vision import draw_pose, to_px

# Índices de MediaPipe Pose de cada brazo: (hombro, codo, muñeca, índice)
CHAINS = [(11, 13, 15, 19), (12, 14, 16, 20)]
SIDE_NAMES = {"izq": "izquierdo", "der": "derecho"}
GIFTS = ["regalo_1", "regalo_2", "regalo_3"]


@dataclass
class Arm:
    shoulder: tuple
    elbow: tuple
    wrist: tuple
    outward: int        # +1 si el brazo abre hacia la derecha de la pantalla, -1 a la izquierda
    angle: float        # apertura del hombro en grados

    @property
    def length(self) -> float:
        """Longitud del brazo en píxeles en este frame (hombro-codo + codo-muñeca)."""
        return distance(self.shoulder, self.elbow) + distance(self.elbow, self.wrist)


def read_arms(landmarks, width: int, height: int) -> dict:
    """Devuelve {"izq": Arm, "der": Arm} con los brazos que se ven bien.

    La imagen va en espejo, así que el brazo que sale a la derecha de la
    pantalla es el derecho. Lo decido por la posición en pantalla para no
    liarme con las etiquetas izquierda/derecha de MediaPipe.
    """
    if landmarks is None:
        return {}
    found = []
    for s, e, w, _ in CHAINS:
        if min(landmarks[k].visibility for k in (s, e, w)) < MIN_VISIBILITY:
            continue
        shoulder, elbow = to_px(landmarks[s], width, height), to_px(landmarks[e], width, height)
        wrist = to_px(landmarks[w], width, height)
        vertical = (shoulder[0], shoulder[1] + 100)  # punto justo debajo del hombro
        found.append((shoulder, elbow, wrist, angle_deg(vertical, shoulder, elbow)))

    center_x = (landmarks[11].x + landmarks[12].x) / 2 * width  # centro del cuerpo
    arms = {}
    for shoulder, elbow, wrist, angle in found:
        side = "der" if shoulder[0] >= center_x else "izq"
        arms[side] = Arm(shoulder, elbow, wrist, 1 if side == "der" else -1, angle)
    return arms


@dataclass
class Item:
    kind: str           # "regalo" o "estrella"
    sprite: str
    x: float
    level: float        # altura en "nivel de brazos" (1 = su máximo de la calibración)
    phase: float = field(default_factory=lambda: random.uniform(0, 6.28))


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple
    size: int = 4


class SleighFlight(Minigame):
    key = "hombro"
    title = "Trineo volador"
    uses = "pose"
    intro_time = C.INTRO_TIME
    game_time = C.GAME_TIME

    def __init__(self, patient: str):
        super().__init__(patient)
        self.calib_elapsed = 0.0
        self.calib = {"izq": 0.0, "der": 0.0}      # ROM máximo en la calibración
        self.rom_max = {"izq": 0.0, "der": 0.0}    # ROM máximo durante el juego
        self.level = 0.0                           # nivel de brazos actual (suavizado)
        self.level_max = 0.0
        self.sleigh_y = None
        self.tilt = 0.0
        self.items = []
        self.next_pattern = 1.5                    # s hasta el siguiente grupo de regalos
        self.challenge = C.CHALLENGE_START
        self.speed = C.SPEED_START
        self.recent = deque(maxlen=C.ADAPT_WINDOW)
        self.hits = self.misses = 0
        self.stars_hit = self.stars_total = 0
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.particles = []
        self.texts = []                            # [x, y, texto, color, vida]
        self.scene = None
        self.seen = False
        self.h = 720
        self.rng = random.Random()

    # --------------------------------------------------------------- intro
    def intro_lines(self):
        return [
            "Hombro - Trineo volador",
            "Colócate para que se te vea de cintura para arriba.",
            "Sube los brazos por los lados y el trineo sube;",
            "bájalos y el trineo baja.",
            "¡Recoge todos los regalos y estrellas que puedas!",
        ]

    def draw_landmarks(self, frame, landmarks):
        if landmarks is not None:
            draw_pose(frame, landmarks)

    # --------------------------------------------------------- calibración
    def update_calibration(self, frame, landmarks, dt):
        h, w = frame.shape[:2]
        arms = read_arms(landmarks, w, h)
        lines = ["Sube los dos brazos por los lados", "lo más alto que puedas"]
        if not arms:
            top = ui.instruction_card(frame, "Calibración", lines, accent=ui.CYAN)
            self.warn_not_detected(frame, "No te veo bien: apártate un poco de la cámara", y=top - 30)
            return False

        self.calib_elapsed += dt  # el tiempo solo corre cuando se te ve
        for side, arm in arms.items():
            self.calib[side] = max(self.calib[side], arm.angle)
            self._draw_arm_angle(frame, arm, best=self.calib[side])

        progress = self.calib_elapsed / C.CALIB_TIME
        ui.instruction_card(frame, "Calibración", lines, progress, accent=ui.CYAN)
        if progress >= 1.0:
            for side in self.calib:
                self.calib[side] = max(self.calib[side], C.MIN_CALIB_ANGLE)
            return True
        return False

    def _draw_arm_angle(self, frame, arm: Arm, best: float):
        # Línea amarilla = mejor marca; texto = ángulo actual
        end = point_at_angle(arm.shoulder, arm.length, best, arm.outward)
        cv2.line(frame, tuple(map(int, arm.shoulder)), tuple(map(int, end)), ui.YELLOW, 3, cv2.LINE_AA)
        label = (arm.shoulder[0] + arm.outward * 40, arm.shoulder[1] - 30)
        ui.put_text(frame, f"{arm.angle:.0f}°", label, 0.9, ui.YELLOW, 2, align="left" if arm.outward > 0 else "right")

    # --------------------------------------------------------------- juego
    def on_game_start(self):
        audio.mixer.stop_all()
        audio.mixer.set_music(audio.render_song(SONGS["jingle"], C.MUSIC_TEMPO))

    def _geometry(self, w, h):
        """x del trineo, y más baja y más alta a la que puede volar."""
        return int(w * 0.27), int(h * 0.80), int(h * 0.16)

    def _level_to_y(self, level, h):
        _, low, high = self._geometry(0, h)
        return low - min(1.0, max(0.0, level / C.TOP_LEVEL)) * (low - high)

    def update_game(self, frame, landmarks, dt):
        h, w = frame.shape[:2]
        self.h = h
        arms = read_arms(landmarks, w, h)

        # 1) Lectura de los brazos -> nivel de elevación (1 = su máximo calibrado)
        levels = []
        for side, arm in arms.items():
            self.rom_max[side] = max(self.rom_max[side], arm.angle)
            levels.append(arm.angle / max(self.calib[side], C.MIN_CALIB_ANGLE))
        self.seen = bool(levels)
        if levels:
            target = sum(levels) / len(levels)
            self.level += (target - self.level) * (1 - math.exp(-C.FOLLOW * dt))
            self.level_max = max(self.level_max, self.level)

        # 2) Miniatura de la cámara (con el esqueleto) antes de pintar el paisaje encima
        self.draw_landmarks(frame, landmarks)
        for arm in arms.values():
            self._draw_arm_angle(frame, arm, self.calib["izq" if arm.outward < 0 else "der"])
        cam = cv2.resize(frame, (w // 4, h // 4), interpolation=cv2.INTER_AREA)

        # 3) Paisaje (se para si no se ve al paciente: así no pierde regalos)
        if self.scene is None:
            self.scene = WinterScene(w, h)
        move = dt if self.seen else 0.0
        self.scene.draw(frame, dt, speed=self.speed if self.seen else 0.0)

        # 4) Trineo
        sx, _, _ = self._geometry(w, h)
        target_y = self._level_to_y(self.level, h)
        prev_y = self.sleigh_y if self.sleigh_y is not None else target_y
        self.sleigh_y = target_y
        vy = (target_y - prev_y) / max(dt, 1e-3)
        self.tilt += (max(-18.0, min(18.0, vy * 0.04)) - self.tilt) * min(1.0, dt * 8)

        # 5) Regalos
        self.next_pattern -= move
        if self.next_pattern <= 0:
            self._spawn_pattern(w)
        for item in self.items:
            item.x -= self.speed * move
        self._collect(sx, self.sleigh_y, h)
        alive = []
        for item in self.items:
            if item.x < -60:
                self._register(False, item)
            else:
                alive.append(item)
        self.items = alive

        self._draw_world(frame, dt, sx, h)
        self._draw_gauge(frame, h)
        self._draw_hint(frame, sx, h)
        self._draw_camera(frame, cam)
        if not self.seen:
            self.warn_not_detected(frame, "No te veo bien: ponte delante de la cámara", y=h - 230)

    def _spawn_pattern(self, w):
        """Un grupo de regalos: en línea, en rampa (subir o bajar) o una estrella arriba del todo."""
        c, low = self.challenge, C.LOW_LEVEL
        kind = self.rng.choices(["linea", "rampa", "estrella"], weights=[3, 4, 2])[0]
        x0 = w + 60
        if kind == "linea":
            level = self.rng.uniform(low + 0.15, c)
            levels = [level] * 3
        elif kind == "rampa":
            a, b = self.rng.uniform(low, c * 0.55), self.rng.uniform(c * 0.75, c)
            if self.rng.random() < 0.5:
                a, b = b, a
            levels = list(np.linspace(a, b, 5))
        else:  # estrella: dos regalos que suben hasta una estrella en lo más alto del reto
            levels = [c * 0.6, c * 0.8, c]
        for i, level in enumerate(levels):
            star = kind == "estrella" and i == len(levels) - 1
            self.items.append(Item("estrella" if star else "regalo", "estrella" if star else self.rng.choice(GIFTS),
                                   x0 + i * C.ITEM_SPACING, float(level)))
        self.next_pattern = (len(levels) * C.ITEM_SPACING) / self.speed + C.PATTERN_GAP

    def _collect(self, sx, sy, h):
        remaining = []
        for item in self.items:
            iy = self._level_to_y(item.level, h)
            if self.seen and distance((sx + 30, sy), (item.x, iy)) <= C.CATCH_RADIUS:
                self._register(True, item)
                self._burst(item.x, iy, ui.GOLD if item.kind == "estrella" else ui.WHITE)
            else:
                remaining.append(item)
        self.items = remaining

    def _register(self, hit, item):
        star = item.kind == "estrella"
        self.stars_total += star
        if hit:
            self.hits += 1
            self.stars_hit += star
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            points = (30 if star else 10) * (1 + self.combo // 5)
            self.score += points
            self.texts.append([item.x, self._level_to_y(item.level, self.h) - 30, f"+{points}",
                               ui.GOLD if star else ui.WHITE, 0.9])
        else:
            self.misses += 1
            self.combo = 0
        # Dificultad adaptativa según los últimos regalos
        self.recent.append(hit)
        if len(self.recent) >= 4:
            rate = sum(self.recent) / len(self.recent)
            if rate > 0.8:
                self.challenge = min(C.CHALLENGE_MAX, self.challenge + C.CHALLENGE_UP / 3)
                self.speed = min(C.SPEED_MAX, self.speed * 1.01)
            elif rate < 0.5:
                self.challenge = max(C.CHALLENGE_MIN, self.challenge - C.CHALLENGE_DOWN / 3)
                self.speed = max(C.SPEED_MIN, self.speed * 0.97)

    def _burst(self, x, y, color):
        for _ in range(18):
            a = self.rng.uniform(0, 6.28)
            v = self.rng.uniform(120, 380)
            self.particles.append(Particle(x, y, v * math.cos(a), v * math.sin(a) - 80, 0.7,
                                           self.rng.choice([color, ui.GOLD, (255, 220, 200)]),
                                           self.rng.choice((3, 4, 5))))

    # -------------------------------------------------------------- dibujo
    def _draw_world(self, frame, dt, sx, h):
        t = self.scene.t
        for item in self.items:  # regalos que flotan un poco
            iy = self._level_to_y(item.level, h) + 6 * math.sin(t * 3 + item.phase)
            size = 86 if item.kind == "estrella" else 72
            if item.kind == "estrella":
                size = int(size * (1 + 0.08 * math.sin(t * 6)))
            assets.draw(frame, item.sprite, (item.x, iy), size, size)

        # Estela brillante detrás del trineo
        if self.seen and self.rng.random() < 0.8:
            self.particles.append(Particle(sx - 70, self.sleigh_y + 20 + self.rng.uniform(-8, 8),
                                           -self.speed * 0.6, self.rng.uniform(-20, 20), 0.6,
                                           self.rng.choice([ui.GOLD, (255, 240, 220), (240, 200, 120)]), 3))
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vy += 300 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            cv2.circle(frame, (int(p.x), int(p.y)), max(1, int(p.size * min(1.0, p.life * 2))), p.color, -1,
                       cv2.LINE_AA)
            alive.append(p)
        self.particles = alive

        bob = 4 * math.sin(t * 4)
        assets.draw(frame, "trineo", (sx, self.sleigh_y + bob), 230, 120, angle=-self.tilt)

        alive = []
        for tx in self.texts:
            tx[4] -= dt
            if tx[4] <= 0:
                continue
            tx[1] -= 60 * dt
            ui.put_text(frame, tx[2], (tx[0], tx[1]), 0.9, tx[3], 2, center=True)
            alive.append(tx)
        self.texts = alive
        if self.combo >= 5:
            ui.put_text(frame, f"¡{self.combo} seguidos!", (frame.shape[1] // 2, 120), 1.0, ui.GOLD, 2, center=True)

    def _draw_gauge(self, frame, h):
        """Barra de la izquierda: altura de los brazos respecto a su máximo de la calibración."""
        x1, x2 = 26, 50
        _, low, high = self._geometry(0, h)
        ui.rounded_rect(frame, (x1 - 8, high - 40, x2 + 8, low + 20), 18, ui.DARK, 0.75)
        ui.rounded_rect(frame, (x1, high, x2, low), 12, (90, 80, 75), 0.9)
        y_now = int(self._level_to_y(self.level, h))
        ui.rounded_rect(frame, (x1, y_now, x2, low), 12, ui.GREEN, 1.0)
        y_max = int(self._level_to_y(1.0, h))          # su máximo de la calibración
        cv2.line(frame, (x1 - 6, y_max), (x2 + 6, y_max), ui.YELLOW, 3, cv2.LINE_AA)
        ui.put_text(frame, "Tu máx.", (x2 + 14, y_max + 8), 0.55, ui.YELLOW, 2)
        ui.put_text(frame, f"{self.level * 100:.0f}%", ((x1 + x2) // 2, high - 14), 0.55, ui.WHITE, 2, center=True)

    def _draw_hint(self, frame, sx, h):
        """Flecha junto al trineo que indica si tiene que subir o bajar los brazos para el próximo regalo."""
        ahead = [it for it in self.items if it.x > sx]
        if not ahead or not self.seen:
            return
        nxt = min(ahead, key=lambda it: it.x)
        if nxt.x - sx > 520:
            return
        diff = nxt.level - self.level
        if abs(diff) < 0.12:
            return
        up = diff > 0
        y0 = int(self.sleigh_y + (-75 if up else 75))
        y1 = y0 + (-45 if up else 45)
        pulse = int(6 * math.sin(self.scene.t * 8))
        cv2.arrowedLine(frame, (sx, y0 - (pulse if up else -pulse)), (sx, y1 - (pulse if up else -pulse)),
                        ui.YELLOW, 8, cv2.LINE_AA, tipLength=0.5)
        ui.put_text(frame, "¡Sube los brazos!" if up else "Baja los brazos", (sx + 40, (y0 + y1) // 2 + 10),
                    0.75, ui.YELLOW, 2)

    def _draw_camera(self, frame, cam):
        """La imagen de la cámara en pequeño, abajo a la derecha, para que se vea a sí mismo."""
        h, w = frame.shape[:2]
        ch, cw = cam.shape[:2]
        x, y = w - cw - 20, h - ch - 20
        ui.rounded_rect(frame, (x - 6, y - 6, x + cw + 6, y + ch + 6), 14, ui.DARK, 0.9, border=ui.WHITE)
        frame[y:y + ch, x:x + cw] = cam
        ui.put_text(frame, "Tú", (x + 12, y + 30), 0.7, ui.WHITE, 2)

    def hud_right(self):
        return f"Regalos: {self.hits}   Puntos: {self.score}"

    # ---------------------------------------------------------- resultados
    def results(self):
        total = self.hits + self.misses
        precision = 100 * self.hits / total if total else 0.0
        lines = [
            f"Regalos recogidos: {self.hits} de {total}  ({precision:.0f}%)   ·   Puntos: {self.score}",
            f"Estrellas: {self.stars_hit} de {self.stars_total}   ·   Mejor racha: {self.best_combo}",
            f"Altura máxima de los brazos: {self.level_max * 100:.0f}% de tu calibración",
        ]
        for side in ("izq", "der"):
            gain = self.rom_max[side] - self.calib[side]
            lines.append(f"Hombro {SIDE_NAMES[side]}: calibración {self.calib[side]:.0f}°  ->  "
                         f"máximo en juego {self.rom_max[side]:.0f}° ({gain:+.0f})")
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
            "reto_final": round(self.challenge, 2),
            "juego": "trineo",
            "puntos": self.score,
            "estrellas": self.stars_hit,
            "altura_max_pct": round(self.level_max * 100),
        }
        return lines, row
