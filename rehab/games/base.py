"""Clase base común a los dos minijuegos.

Todos los minijuegos pasan por las mismas fases:

    intro -> calibracion -> cuenta atras -> juego -> (terminado)

Cada modo solo implementa lo suyo (calibrar, jugar y resumir resultados);
el flujo de fases, la cuenta atrás y la barra superior son comunes. Así cada
persona del grupo puede trabajar en su archivo sin pisar al otro.
"""
from datetime import datetime

import cv2

from rehab import ui


class Minigame:
    key = ""            # nombre corto: "hombro" / "mano" (también nombre del CSV)
    title = ""          # título que se ve en pantalla
    uses = "pose"       # "pose" o "hand": qué detector de MediaPipe necesita
    intro_time = 5.0
    game_time = 60.0
    countdown_time = 3.0

    def __init__(self, patient: str):
        self.patient = patient
        self.started_at = datetime.now()
        self.phase = "intro"
        self.phase_time = 0.0
        self.time_left = self.game_time
        self.finished = False

    # ------------------------------------------------------------ flujo común
    def _set_phase(self, phase: str):
        self.phase = phase
        self.phase_time = 0.0

    def skip_intro(self):
        """Tecla ENTER: saltar las instrucciones."""
        if self.phase == "intro":
            self.phase_time = self.intro_time

    def update(self, frame, landmarks, dt: float):
        """Se llama una vez por frame desde main.py."""
        self.phase_time += dt
        h, w = frame.shape[:2]

        if self.phase == "intro":
            self.draw_landmarks(frame, landmarks)
            ui.message_box(frame, self.intro_lines(), y_center=int(h * 0.42))
            remaining = max(0.0, self.intro_time - self.phase_time)
            ui.progress_ring(frame, (w // 2, int(h * 0.80)), 38, 1 - remaining / self.intro_time, ui.CYAN,
                             label=str(int(remaining) + 1))
            ui.put_text(frame, "Pulsa ENTER para empezar ya", (w // 2, int(h * 0.80) + 76), 0.6, ui.GREY, 1,
                        center=True)
            if self.phase_time >= self.intro_time:
                self._set_phase("calibracion")
                self.on_calibration_start()

        elif self.phase == "calibracion":
            self.draw_landmarks(frame, landmarks)
            if self.update_calibration(frame, landmarks, dt):
                self._set_phase("cuenta")

        elif self.phase == "cuenta":
            self.draw_landmarks(frame, landmarks)
            remaining = self.countdown_time - self.phase_time
            number = max(1, int(remaining) + 1)
            frac = remaining - int(remaining)          # 1 -> 0 dentro de cada segundo
            radius = int(70 + 25 * frac)
            cv2.circle(frame, (w // 2, h // 2 - 20), radius + 10, ui.DARKER, -1, cv2.LINE_AA)
            cv2.circle(frame, (w // 2, h // 2 - 20), radius, ui.YELLOW, 6, cv2.LINE_AA)
            ui.put_text(frame, str(number), (w // 2, h // 2 + 18), 3.2, ui.YELLOW, 2, center=True, shadow=False)
            ui.put_text(frame, "Prepárate...", (w // 2, h // 2 + 130), 1.2, ui.WHITE, 2, center=True)
            if remaining <= 0:
                self._set_phase("juego")
                self.on_game_start()

        elif self.phase == "juego":
            self.time_left = max(0.0, self.game_time - self.phase_time)
            self.update_game(frame, landmarks, dt)
            self.draw_hud(frame)
            if self.time_left <= 0:
                self.finished = True

    def draw_hud(self, frame):
        """Barra de arriba: título, progreso de la partida y marcador."""
        w = frame.shape[1]
        ui.rounded_rect(frame, (12, 10, w - 12, 70), 20, ui.DARK, 0.85)
        ui.put_text(frame, self.title, (32, 50), 0.8, ui.CYAN, 2, shadow=False)
        progress = self.hud_progress()
        cx = w // 2
        if progress is None:
            ui.put_text(frame, self.hud_center(), (cx, 50), 0.8, ui.WHITE, 2, center=True, shadow=False)
        else:
            ui.put_text(frame, self.hud_center(), (cx, 38), 0.6, ui.WHITE, 2, center=True, shadow=False)
            ui.progress_bar(frame, (cx - 170, 48, cx + 170, 60), progress, ui.CYAN)
        ui.put_text(frame, self.hud_right(), (w - 32, 50), 0.8, ui.YELLOW, 2, shadow=False, align="right")

    @staticmethod
    def warn_not_detected(frame, text, y=None):
        ui.banner(frame, text, ui.RED, y=y)

    def hud_center(self) -> str:
        return f"Tiempo: {self.time_left:.0f} s"

    def hud_progress(self):
        """Fracción de partida jugada (0 a 1) para la barra de arriba, o None para no pintarla."""
        return 1 - self.time_left / self.game_time if self.game_time else None

    # ------------------------------------------------ lo que implementa cada modo
    def intro_lines(self) -> list:
        raise NotImplementedError

    def draw_landmarks(self, frame, landmarks):
        raise NotImplementedError

    def on_calibration_start(self):
        pass

    def update_calibration(self, frame, landmarks, dt) -> bool:
        """Devuelve True cuando la calibración ha terminado."""
        raise NotImplementedError

    def on_game_start(self):
        pass

    def update_game(self, frame, landmarks, dt):
        raise NotImplementedError

    def hud_right(self) -> str:
        return ""

    def results(self) -> tuple:
        """Devuelve (líneas para la pantalla de resultados, fila para el CSV)."""
        raise NotImplementedError
