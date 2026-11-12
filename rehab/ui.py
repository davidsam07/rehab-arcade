"""Utilidades de dibujo con OpenCV: textos, paneles y botones por "dwell".

Botones por dwell: el usuario pulsa un botón manteniendo el dedo índice
encima durante unos segundos, sin teclado ni ratón. Es una técnica de IPM
típica en interfaces sin contacto y accesibles.
"""
import time
import unicodedata

import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_DUPLEX

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (90, 220, 90)
RED = (70, 70, 230)
YELLOW = (60, 220, 250)
CYAN = (230, 210, 60)
ORANGE = (40, 150, 255)
GREY = (160, 160, 160)


def _ascii(text: str) -> str:
    """cv2.putText no dibuja tildes ni eñes: las quitamos (á -> a, ñ -> n)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def text_size(text: str, scale: float = 1.0, thickness: int = 2):
    (w, h), _ = cv2.getTextSize(_ascii(text), FONT, scale, thickness)
    return w, h


def put_text(img, text, org, scale=1.0, color=WHITE, thickness=2, center=False, shadow=True):
    text = _ascii(text)
    x, y = int(org[0]), int(org[1])
    if center:
        w, _ = text_size(text, scale, thickness)
        x -= w // 2
    if shadow:
        off = 2 if scale >= 0.8 else 1
        cv2.putText(img, text, (x + off, y + off), FONT, scale, BLACK, thickness + 1, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), FONT, scale, color, thickness, cv2.LINE_AA)


def panel(img, x1, y1, x2, y2, color=(30, 30, 30), alpha=0.65):
    """Rectángulo semitransparente para que el texto se lea encima de la cámara."""
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(img.shape[1], int(x2)), min(img.shape[0], int(y2))
    if x2 <= x1 or y2 <= y1:
        return
    roi = img[y1:y2, x1:x2]
    overlay = np.full_like(roi, color)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def progress_ring(img, center, radius, progress, color=GREEN, thickness=6):
    """Arco circular que se va llenando (0 a 1)."""
    c = (int(center[0]), int(center[1]))
    cv2.circle(img, c, radius, GREY, 2, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(img, c, (radius, radius), -90, 0, 360 * min(progress, 1.0), color, thickness, cv2.LINE_AA)


def message_box(img, lines, y_center=None, scale=1.0):
    """Caja centrada con varias líneas de texto (instrucciones, avisos...)."""
    h, w = img.shape[:2]
    line_h = int(48 * scale)
    box_h = line_h * len(lines) + 30
    y1 = (y_center or h // 2) - box_h // 2
    panel(img, w * 0.1, y1, w * 0.9, y1 + box_h)
    for i, line in enumerate(lines):
        put_text(img, line, (w // 2, y1 + 15 + line_h * (i + 1) - 12), scale, WHITE, 2, center=True)


class Button:
    def __init__(self, key, label, rect, color=CYAN, sublabel=""):
        self.key = key
        self.label = label
        self.sublabel = sublabel
        self.rect = rect  # (x1, y1, x2, y2)
        self.color = color

    def contains(self, point) -> bool:
        if point is None:
            return False
        x1, y1, x2, y2 = self.rect
        return x1 <= point[0] <= x2 and y1 <= point[1] <= y2

    def draw(self, img, progress=0.0):
        x1, y1, x2, y2 = map(int, self.rect)
        panel(img, x1, y1, x2, y2, (40, 40, 40), 0.7)
        border = self.color if progress == 0 else GREEN
        cv2.rectangle(img, (x1, y1), (x2, y2), border, 3, cv2.LINE_AA)
        if progress > 0:  # barra de carga en la parte inferior del botón
            fill = int(x1 + (x2 - x1) * min(progress, 1.0))
            cv2.rectangle(img, (x1, y2 - 10), (fill, y2), GREEN, -1)
        cx = (x1 + x2) // 2
        put_text(img, self.label, (cx, (y1 + y2) // 2 + (0 if self.sublabel else 12)), 1.1, WHITE, 2, center=True)
        if self.sublabel:
            put_text(img, self.sublabel, (cx, (y1 + y2) // 2 + 40), 0.6, GREY, 1, center=True)


class DwellSelector:
    """Pulsa un botón cuando el puntero se queda encima `dwell_time` segundos."""

    def __init__(self, dwell_time: float):
        self.dwell_time = dwell_time
        self._current = None
        self._since = 0.0

    def reset(self):
        self._current = None

    def update(self, buttons, pointer, now=None):
        """Devuelve (botón seleccionado o None, {key: progreso})."""
        now = time.monotonic() if now is None else now
        hovered = next((b for b in buttons if b.contains(pointer)), None)
        if hovered is None:
            self._current = None
            return None, {}
        if self._current != hovered.key:
            self._current = hovered.key
            self._since = now
        progress = (now - self._since) / self.dwell_time
        if progress >= 1.0:
            self._current = None
            return hovered, {}
        return None, {hovered.key: progress}


def draw_pointer(img, pointer):
    if pointer is not None:
        p = (int(pointer[0]), int(pointer[1]))
        cv2.circle(img, p, 14, YELLOW, 3, cv2.LINE_AA)
        cv2.circle(img, p, 4, YELLOW, -1, cv2.LINE_AA)
