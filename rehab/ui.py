"""Utilidades de dibujo: textos, tarjetas, botones por "dwell", iconos y nieve.

- Textos: cv2.putText no sabe dibujar tildes ni eñes y su letra es poco
  legible, así que los textos se dibujan con Pillow usando una fuente de
  verdad (Segoe UI en Windows, DejaVu de matplotlib en el resto). Cada texto
  se renderiza una sola vez y se guarda en caché, así no se nota en los FPS.
  Llevan un borde oscuro para que se lean encima de la imagen de la cámara.
- Botones por dwell: el usuario pulsa un botón manteniendo el dedo índice
  encima un segundo y medio, sin teclado ni ratón. Es una técnica de IPM
  típica en interfaces sin contacto y accesibles.
"""
import math
import os
import random
import time
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Colores en BGR (como los usa OpenCV)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (110, 215, 90)
RED = (80, 80, 235)
YELLOW = (70, 215, 255)
CYAN = (235, 200, 70)
ORANGE = (50, 150, 255)
GREY = (175, 175, 175)
DARK = (48, 34, 26)          # fondo de las tarjetas (azul noche)
DARKER = (32, 22, 16)
IVORY = (235, 244, 248)      # teclas del piano
INK = (60, 45, 40)           # texto oscuro sobre fondo claro
GOLD = (60, 200, 245)
XMAS_RED = (60, 55, 205)
XMAS_GREEN = (80, 165, 45)

SIZE_PER_SCALE = 32          # scale=1.0 equivale a una letra de 32 px


# --------------------------------------------------------------------- fuentes
def _find_font(bold: bool):
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["seguisb.ttf", "segoeui.ttf", "arial.ttf"]
    candidates = [os.path.join(win, n) for n in names]
    candidates += ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
                   else "/System/Library/Fonts/Supplemental/Arial.ttf"]
    try:
        import matplotlib
        mpl = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        candidates.append(os.path.join(mpl, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"))
    except Exception:  # noqa: BLE001
        pass
    return next((p for p in candidates if os.path.exists(p)), None)


_FONT_PATHS = {True: _find_font(True), False: _find_font(False)}


@lru_cache(maxsize=64)
def _font(size: int, bold: bool):
    path = _FONT_PATHS[bold]
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)


@lru_cache(maxsize=2048)
def _sprite(text: str, size: int, color: tuple, bold: bool, stroke: int):
    """Renderiza un texto una vez. Devuelve (255 - alfa, color * alfa, desplazamiento x, desplazamiento y)."""
    font = _font(size, bold)
    left, top, right, bottom = font.getbbox(text, anchor="ls", stroke_width=stroke)
    w, h = max(1, right - left), max(1, bottom - top)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Pillow dibuja "RGB", pero le pasamos el color en BGR: los canales quedan en el orden de OpenCV
    ImageDraw.Draw(img).text((-left, -top), text, font=font, fill=tuple(color) + (255,), anchor="ls",
                             stroke_width=stroke, stroke_fill=(25, 18, 15, 235))
    arr = np.asarray(img)
    alpha = np.ascontiguousarray(np.repeat(arr[..., 3:], 3, axis=2))
    pre = cv2.multiply(np.ascontiguousarray(arr[..., :3]), alpha, scale=1 / 255)
    return 255 - alpha, pre, left, top


def _premultiply(mask, alpha, color):
    """De una máscara 0-255 (HxW) saca lo que necesita _blend: (255 - alfa, color * alfa)."""
    a = cv2.merge([cv2.convertScaleAbs(mask, alpha=alpha)] * 3)
    pre = cv2.multiply(np.full_like(a, 0) + np.array(color, np.uint8), a, scale=1 / 255)
    return 255 - a, pre


def _blend(img, inv, pre, x, y):
    """Mezcla en (x, y) una imagen premultiplicada: img = img * (1 - alfa) + color * alfa.

    Se hace con OpenCV en enteros de 8 bits: unas 15 veces más rápido que con numpy en decimales.
    """
    h, w = inv.shape[:2]
    H, W = img.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sy, sx = slice(y0 - y, y1 - y), slice(x0 - x, x1 - x)
    roi = img[y0:y1, x0:x1]
    roi[:] = cv2.add(cv2.multiply(roi, inv[sy, sx], scale=1 / 255), pre[sy, sx])


def _size_of(scale):
    return max(8, int(round(SIZE_PER_SCALE * scale)))


def text_size(text: str, scale: float = 1.0, thickness: int = 2):
    inv, _, _, _ = _sprite(str(text), _size_of(scale), WHITE, thickness >= 2, 0)
    return inv.shape[1], inv.shape[0]


def put_text(img, text, org, scale=1.0, color=WHITE, thickness=2, center=False, shadow=True, align="left"):
    """Escribe texto con tildes. `org` es la línea base (como en cv2.putText).

    thickness >= 2 usa letra negrita. shadow=True le pone un borde oscuro
    para que se lea sobre la cámara. center=True (o align="center"/"right").
    """
    text = str(text)
    size = _size_of(scale)
    stroke = max(2, size // 11) if shadow else 0
    inv, pre, left, top = _sprite(text, size, tuple(int(c) for c in color), thickness >= 2, stroke)
    x, y = int(org[0]) + left, int(org[1]) + top
    if center or align == "center":
        x = int(org[0]) - inv.shape[1] // 2
    elif align == "right":
        x = int(org[0]) - inv.shape[1]
    _blend(img, inv, pre, x, y)
    return inv.shape[1]


# -------------------------------------------------------------------- formas
@lru_cache(maxsize=512)
def _round_mask(w: int, h: int, r: int):
    """Máscara 0-255 de un rectángulo redondeado (con antialiasing en las esquinas)."""
    mask = np.zeros((h, w), np.uint8)
    r = max(0, min(r, w // 2, h // 2))
    if r == 0:
        mask[:] = 255
    else:
        cv2.rectangle(mask, (r, 0), (w - 1 - r, h - 1), 255, -1)
        cv2.rectangle(mask, (0, r), (w - 1, h - 1 - r), 255, -1)
        for cx, cy in ((r, r), (w - 1 - r, r), (r, h - 1 - r), (w - 1 - r, h - 1 - r)):
            cv2.circle(mask, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return mask


@lru_cache(maxsize=512)
def _ring_mask(w: int, h: int, r: int, th: int):
    outer = _round_mask(w, h, r).copy()
    if w > 2 * th and h > 2 * th:
        inner = outer[th:h - th, th:w - th]
        cv2.subtract(inner, _round_mask(w - 2 * th, h - 2 * th, max(0, r - th)), dst=inner)
    return outer


@lru_cache(maxsize=2048)
def _shape(w, h, r, alpha_pct, color, ring_th):
    mask = _ring_mask(w, h, r, ring_th) if ring_th else _round_mask(w, h, r)
    return _premultiply(mask, alpha_pct / 100, color)


def rounded_rect(img, rect, radius=18, color=DARK, alpha=0.85, border=None, border_th=3):
    """Tarjeta con esquinas redondeadas, semitransparente y con borde opcional."""
    x1, y1, x2, y2 = (int(round(v)) for v in rect)
    w, h = x2 - x1, y2 - y1
    if w <= 1 or h <= 1:
        return
    r = int(min(radius, w // 2, h // 2))
    if alpha > 0:
        _blend(img, *_shape(w, h, r, int(round(alpha * 100)), tuple(color), 0), x1, y1)
    if border is not None:
        _blend(img, *_shape(w, h, r, 100, tuple(border), border_th), x1, y1)


def panel(img, x1, y1, x2, y2, color=(30, 30, 30), alpha=0.65, radius=0):
    """Rectángulo semitransparente para que el texto se lea encima de la cámara."""
    if radius:
        rounded_rect(img, (x1, y1, x2, y2), radius, color, alpha)
        return
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(img.shape[1], int(x2)), min(img.shape[0], int(y2))
    if x2 <= x1 or y2 <= y1:
        return
    roi = img[y1:y2, x1:x2]
    overlay = np.full_like(roi, color)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def dim(img, alpha=0.5, color=DARKER):
    """Oscurece toda la imagen (fondo de los menús), tiñéndola un poco de azul."""
    cv2.addWeighted(img, 1 - alpha, np.full_like(img, color), alpha, 0, img)


def progress_ring(img, center, radius, progress, color=GREEN, thickness=8, label=None):
    """Arco circular que se va llenando (0 a 1), con un número dentro si se quiere."""
    c = (int(center[0]), int(center[1]))
    cv2.circle(img, c, radius, (70, 60, 55), thickness, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(img, c, (radius, radius), -90, 0, 360 * min(progress, 1.0), color, thickness, cv2.LINE_AA)
    if label is not None:
        put_text(img, label, (c[0], c[1] + int(radius * 0.35)), radius / 36, WHITE, 2, center=True)


def progress_bar(img, rect, progress, color=GREEN, back=(80, 70, 65)):
    x1, y1, x2, y2 = rect
    rounded_rect(img, rect, (y2 - y1) // 2, back, 0.9)
    if progress > 0:
        rounded_rect(img, (x1, y1, x1 + max(y2 - y1, (x2 - x1) * min(progress, 1.0)), y2),
                     (y2 - y1) // 2, color, 1.0)


def message_box(img, lines, y_center=None, scale=1.0, width=0.8, accent=CYAN):
    """Tarjeta centrada. La primera línea es el título (en color y más grande)."""
    h, w = img.shape[:2]
    if not lines:
        return
    title, body = lines[0], list(lines[1:])
    title_h, line_h = int(56 * scale), int(46 * scale)
    box_h = title_h + line_h * len(body) + int(38 * scale)
    yc = y_center or h // 2
    y1 = yc - box_h // 2
    x1, x2 = int(w * (1 - width) / 2), int(w * (1 + width) / 2)
    rounded_rect(img, (x1, y1, x2, y1 + box_h), 26, DARK, 0.86, border=accent, border_th=3)
    put_text(img, title, (w // 2, y1 + int(46 * scale)), 1.1 * scale, accent, 2, center=True, shadow=False)
    for i, line in enumerate(body):
        put_text(img, line, (w // 2, y1 + title_h + int(34 * scale) + i * line_h), 0.95 * scale,
                 WHITE, 2, center=True, shadow=False)


def instruction_card(img, title, lines, progress=None, ring_color=GREEN, accent=YELLOW, steps=None):
    """Instrucciones en la parte de abajo, para no tapar la mano ni los brazos.

    progress: anillo de progreso a la derecha (0-1). steps: (paso actual, total) en puntitos.
    Devuelve la coordenada y de arriba de la tarjeta.
    """
    h, w = img.shape[:2]
    line_h = 42
    x1, x2 = int(w * 0.08), int(w * 0.92)
    y2 = h - 16
    y1 = y2 - (64 + line_h * len(lines))
    rounded_rect(img, (x1, y1, x2, y2), 26, DARK, 0.88, border=accent)
    cx = (x1 + x2 - (150 if progress is not None else 0)) // 2
    put_text(img, title, (cx, y1 + 46), 0.95, accent, 2, center=True, shadow=False)
    for i, line in enumerate(lines):
        put_text(img, line, (cx, y1 + 46 + line_h * (i + 1)), 0.85, WHITE, 2, center=True, shadow=False)
    if progress is not None:
        progress_ring(img, (x2 - 90, (y1 + y2) // 2), 44, progress, ring_color, 10)
    if steps:
        current, total = steps
        for i in range(total):
            x = int(w // 2 + (i - (total - 1) / 2) * 36)
            done = i < current
            cv2.circle(img, (x, y1 - 24), 11, DARKER, -1, cv2.LINE_AA)
            cv2.circle(img, (x, y1 - 24), 9, GREEN if done else (WHITE if i == current else GREY),
                       -1 if done or i == current else 2, cv2.LINE_AA)
    return y1


def banner(img, text, color=RED, y=None, scale=0.9):
    """Aviso en una franja de la parte de abajo (por ejemplo "No veo tu mano")."""
    h, w = img.shape[:2]
    tw, _ = text_size(text, scale)
    y = y or h - 60
    rounded_rect(img, (w // 2 - tw // 2 - 40, y - 42, w // 2 + tw // 2 + 40, y + 18), 30, color, 0.88)
    put_text(img, text, (w // 2, y), scale, WHITE, 2, center=True, shadow=False)


# --------------------------------------------------------------------- iconos
def _poly(img, pts, color):
    cv2.fillPoly(img, [np.array(pts, np.int32)], color, cv2.LINE_AA)


def icon_piano(img, c, s, color=None):
    x, y = c
    kw = s // 2
    for i in range(4):
        x1 = x - 2 * kw + i * kw
        cv2.rectangle(img, (x1 + 2, y - s // 2), (x1 + kw - 2, y + s // 2), IVORY, -1, cv2.LINE_AA)
    for i in (1, 2, 3):
        bx = x - 2 * kw + i * kw
        cv2.rectangle(img, (bx - kw // 4, y - s // 2), (bx + kw // 4, y + s // 8), (40, 30, 30), -1)


def icon_fruit(img, c, s, color=None):
    x, y = c
    r = int(s * 0.55)
    cv2.circle(img, (x, y + 4), r, (60, 60, 225), -1, cv2.LINE_AA)
    cv2.circle(img, (x - r // 3, y - r // 3 + 4), r // 4, WHITE, -1, cv2.LINE_AA)
    cv2.ellipse(img, (x + r // 3, y - r), (r // 3, r // 6), -30, 0, 360, XMAS_GREEN, -1, cv2.LINE_AA)
    cv2.line(img, (x - r - 12, y + r + 6), (x + r + 12, y - r - 2), WHITE, 4, cv2.LINE_AA)


def icon_bell(img, c, s, color=GOLD):
    x, y = c
    _poly(img, [(x - s * 0.15, y - s * 0.55), (x + s * 0.15, y - s * 0.55), (x + s * 0.32, y - s * 0.2),
                (x + s * 0.38, y + s * 0.25), (x + s * 0.55, y + s * 0.42), (x - s * 0.55, y + s * 0.42),
                (x - s * 0.38, y + s * 0.25), (x - s * 0.32, y - s * 0.2)], color)
    cv2.circle(img, (x, int(y - s * 0.52)), int(s * 0.17), color, -1, cv2.LINE_AA)
    cv2.circle(img, (x, int(y + s * 0.5)), int(s * 0.13), (40, 120, 180), -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(x - s * 0.22), int(y - s * 0.62)), (int(s * 0.2), int(s * 0.1)), 20, 0, 360,
                XMAS_RED, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(x + s * 0.22), int(y - s * 0.62)), (int(s * 0.2), int(s * 0.1)), -20, 0, 360,
                XMAS_RED, -1, cv2.LINE_AA)


def icon_star(img, c, s, color=GOLD):
    x, y = c
    pts = []
    for i in range(10):
        r = s * (0.6 if i % 2 == 0 else 0.25)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    _poly(img, pts, color)


def icon_tree(img, c, s, color=XMAS_GREEN):
    x, y = c
    for i, (top, base, half) in enumerate([(-0.55, -0.1, 0.32), (-0.3, 0.15, 0.42), (-0.05, 0.42, 0.52)]):
        _poly(img, [(x, y + s * top), (x + s * half, y + s * base), (x - s * half, y + s * base)], color)
    cv2.rectangle(img, (int(x - s * 0.08), int(y + s * 0.42)), (int(x + s * 0.08), int(y + s * 0.6)),
                  (40, 70, 120), -1)
    for dx, dy, col in ((-0.15, 0.0, XMAS_RED), (0.18, 0.25, GOLD), (-0.25, 0.32, (230, 160, 70))):
        cv2.circle(img, (int(x + s * dx), int(y + s * dy)), max(3, int(s * 0.06)), col, -1, cv2.LINE_AA)
    icon_star(img, (x, int(y - s * 0.6)), int(s * 0.3))


def icon_snowflake(img, c, s, color=(250, 225, 190)):
    x, y = c
    for i in range(6):
        a = i * math.pi / 3
        ex, ey = x + s * 0.6 * math.cos(a), y + s * 0.6 * math.sin(a)
        cv2.line(img, (x, y), (int(ex), int(ey)), color, 4, cv2.LINE_AA)
        for side in (-1, 1):
            mx, my = x + s * 0.35 * math.cos(a), y + s * 0.35 * math.sin(a)
            b = a + side * math.pi / 4
            cv2.line(img, (int(mx), int(my)), (int(mx + s * 0.18 * math.cos(b)), int(my + s * 0.18 * math.sin(b))),
                     color, 3, cv2.LINE_AA)
    cv2.circle(img, (x, y), max(3, int(s * 0.08)), color, -1, cv2.LINE_AA)


def icon_note(img, c, s, color=CYAN):
    x, y = c
    cv2.ellipse(img, (int(x - s * 0.18), int(y + s * 0.38)), (int(s * 0.22), int(s * 0.16)), -20, 0, 360,
                color, -1, cv2.LINE_AA)
    cv2.line(img, (int(x + s * 0.02), int(y + s * 0.35)), (int(x + s * 0.02), int(y - s * 0.5)), color, 5, cv2.LINE_AA)
    _poly(img, [(x + s * 0.02, y - s * 0.52), (x + s * 0.4, y - s * 0.25), (x + s * 0.4, y - s * 0.1),
                (x + s * 0.02, y - s * 0.32)], color)


ICONS = {"piano": icon_piano, "fruit": icon_fruit, "bell": icon_bell, "star": icon_star,
         "tree": icon_tree, "snowflake": icon_snowflake, "note": icon_note}


# -------------------------------------------------------------------- botones
class Button:
    def __init__(self, key, label, rect, color=CYAN, sublabel="", icon=None, tag="", hint="", images=()):
        self.images = images  # imágenes de assets/ que se prueban en orden antes que el icono dibujado
        self.key = key
        self.label = label
        self.sublabel = sublabel
        self.rect = rect  # (x1, y1, x2, y2)
        self.color = color
        self.icon = icon
        self.tag = tag    # etiqueta pequeña arriba a la derecha (p.ej. "Tranquila")
        self.hint = hint  # tecla de atajo, se muestra abajo a la izquierda

    def contains(self, point) -> bool:
        if point is None:
            return False
        x1, y1, x2, y2 = self.rect
        return x1 <= point[0] <= x2 and y1 <= point[1] <= y2

    def draw(self, img, progress=0.0):
        x1, y1, x2, y2 = map(int, self.rect)
        active = progress > 0
        pop = int(6 * min(1.0, progress * 4)) if active else 0     # crece un poco al apuntarlo
        x1, y1, x2, y2 = x1 - pop, y1 - pop, x2 + pop, y2 + pop
        rounded_rect(img, (x1, y1, x2, y2), 24, DARK, 0.88, border=self.color if not active else GREEN,
                     border_th=4 if active else 3)
        if active:  # se va rellenando de verde mientras mantiene el dedo
            rounded_rect(img, (x1, y1, x1 + max(48, (x2 - x1) * min(progress, 1.0)), y2), 24, GREEN, 0.35)
        cx, h = (x1 + x2) // 2, y2 - y1
        from rehab import assets  # aquí para evitar una importación circular
        image = next((name for name in self.images if assets.available(name)), None)
        has_icon = image is not None or self.icon in ICONS
        if image is not None:
            assets.draw(img, image, (cx, y1 + int(h * 0.30)), int((x2 - x1) * 0.6), int(h * 0.42))
        elif has_icon:
            ICONS[self.icon](img, (cx, y1 + int(h * 0.30)), int(min(h * 0.22, 60)))
        label_y = y1 + int(h * (0.68 if has_icon else 0.5)) + (0 if self.sublabel else 12)
        label_scale = 1.15 if h > 150 else 0.9
        tw, _ = text_size(self.label, label_scale)
        if tw > (x2 - x1) - 40:  # títulos largos: letra más pequeña para que quepan
            label_scale *= ((x2 - x1) - 40) / tw
        put_text(img, self.label, (cx, label_y), label_scale, WHITE, 2, center=True, shadow=False)
        if self.sublabel:
            put_text(img, self.sublabel, (cx, label_y + 36), 0.6, GREY, 1, center=True, shadow=False)
        if self.tag:
            tw, _ = text_size(self.tag, 0.5)
            rounded_rect(img, (x2 - tw - 34, y1 + 14, x2 - 14, y1 + 46), 16, self.color, 0.9)
            put_text(img, self.tag, (x2 - 24 - tw, y1 + 38), 0.5, DARKER, 2, shadow=False)
        if self.hint:
            put_text(img, self.hint, (x1 + 20, y2 - 16), 0.5, (150, 150, 150), 2, shadow=False)


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


def draw_pointer(img, pointer, progress=0.0):
    """Puntero del dedo índice: un anillo que se llena mientras se mantiene sobre un botón."""
    if pointer is None:
        return
    p = (int(pointer[0]), int(pointer[1]))
    cv2.circle(img, p, 22, (30, 25, 20), 8, cv2.LINE_AA)
    cv2.circle(img, p, 22, WHITE, 3, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(img, p, (22, 22), -90, 0, 360 * min(progress, 1.0), GREEN, 7, cv2.LINE_AA)
    cv2.circle(img, p, 6, YELLOW, -1, cv2.LINE_AA)


# ---------------------------------------------------------------------- nieve
class Snow:
    """Copos de nieve que caen despacio (ambiente navideño)."""

    def __init__(self, count=60, seed=7):
        rng = random.Random(seed)
        # x, y (0-1), radio, velocidad (fracción de pantalla por segundo), fase del balanceo
        self.flakes = [[rng.random(), rng.random(), rng.choice((2, 2, 3, 3, 4)),
                        rng.uniform(0.04, 0.10), rng.uniform(0, 6.28)] for _ in range(count)]
        self.t = 0.0

    def draw(self, img, dt, region=None):
        h, w = img.shape[:2]
        x0, x1 = region if region else (0, w)
        self.t += dt
        for f in self.flakes:
            f[1] += f[3] * dt
            if f[1] > 1.02:
                f[1] -= 1.04
            x = int(x0 + f[0] * (x1 - x0) + 12 * math.sin(self.t * 0.8 + f[4]))
            cv2.circle(img, (x, int(f[1] * h)), f[2], (255, 248, 240), -1, cv2.LINE_AA)
