"""Clase base común a los dos minijuegos.

Todos los minijuegos pasan por las mismas fases:

    intro -> calibracion -> cuenta atras -> juego -> (terminado)

Cada modo solo implementa lo suyo (calibrar, jugar y resumir resultados);
el flujo de fases, la cuenta atrás y la barra superior son comunes. Así cada
persona del grupo puede trabajar en su archivo sin pisar al otro.
"""
from datetime import datetime

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

        if self.phase == "intro":
            self.draw_landmarks(frame, landmarks)
            ui.message_box(frame, self.intro_lines() + ["", "(ENTER para empezar ya)"])
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
            h, w = frame.shape[:2]
            ui.put_text(frame, str(max(1, int(remaining) + 1)), (w // 2, h // 2), 4, ui.YELLOW, 6, center=True)
            ui.put_text(frame, "Preparado...", (w // 2, h // 2 + 70), 1.2, ui.WHITE, 2, center=True)
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
        w = frame.shape[1]
        ui.panel(frame, 0, 0, w, 60, alpha=0.55)
        ui.put_text(frame, self.title, (20, 40), 1.0, ui.CYAN, 2)
        ui.put_text(frame, f"Tiempo: {self.time_left:4.0f}s", (w // 2, 40), 1.0, ui.WHITE, 2, center=True)
        ui.put_text(frame, self.hud_right(), (w - 20 - ui.text_size(self.hud_right(), 1.0)[0], 40), 1.0, ui.YELLOW, 2)

    @staticmethod
    def warn_not_detected(frame, text):
        h, w = frame.shape[:2]
        ui.panel(frame, 0, h - 70, w, h, (0, 0, 120), 0.6)
        ui.put_text(frame, text, (w // 2, h - 25), 0.9, ui.WHITE, 2, center=True)

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
