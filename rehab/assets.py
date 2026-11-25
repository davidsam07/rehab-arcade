"""Imágenes del juego (carpeta assets/).

Cada imagen se busca como assets/<nombre>.png (con transparencia). Si no
existe, se usa un dibujo hecho por código (las funciones _draw_* de abajo),
así el juego siempre funciona aunque falten imágenes. La lista de imágenes
que se pueden poner está en assets/LEEME.md.

Las imágenes se escalan una vez a cada tamaño que se pide y se guardan en
caché ya "premultiplicadas" para pegarlas rápido (ver ui._blend).
"""
import math
import os
from functools import lru_cache

import cv2
import numpy as np

import config
from rehab import ui

ASSETS_DIR = config.ASSETS_DIR
_FALLBACKS = {}
# Imágenes que son fondos completos: a estas no se les quita el fondo
_OPAQUE = {"fondo_cielo", "fondo_menu", "fondo_piano"}


def _fallback(name):
    """Registra un dibujo por código para cuando no haya imagen."""
    def deco(fn):
        _FALLBACKS[name] = fn
        return fn
    return deco


@lru_cache(maxsize=None)
def load(name: str):
    """Imagen BGRA de assets/<name>.png, o None si no está."""
    path = os.path.join(ASSETS_DIR, f"{name}.png")
    if not os.path.exists(path):
        return None
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Aviso: no se pudo leer {path}")
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    if name not in _OPAQUE:
        if img[..., 3].min() == 255:
            img = remove_flat_background(img)
        img = _trim(img)
    return img


def _trim(img, pad=4):
    """Recorta el margen transparente sobrante, para que todas las imágenes ocupen su tamaño real."""
    ys, xs = np.nonzero(img[..., 3] > 16)
    if len(xs) == 0:
        return img
    h, w = img.shape[:2]
    return img[max(0, ys.min() - pad):min(h, ys.max() + pad + 1), max(0, xs.min() - pad):min(w, xs.max() + pad + 1)]


def remove_flat_background(img, tolerance=32):
    """Quita un fondo de color liso (p.ej. magenta) a una imagen sin transparencia.

    Las IA de imágenes casi nunca generan PNG transparentes. Si las esquinas
    son del mismo color, se "rellena" el fondo desde ellas (como el bote de
    pintura de un editor) y esa zona se vuelve transparente.
    """
    bgr = np.ascontiguousarray(img[..., :3])
    h, w = bgr.shape[:2]
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    ref = bgr[0, 0].astype(int)
    seeds = [(x, y) for x, y in corners if np.abs(bgr[y, x].astype(int) - ref).max() <= tolerance]
    if len(seeds) < 2:  # las esquinas no coinciden: no parece un fondo liso
        return img
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 8 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    diff = (tolerance,) * 3
    for x, y in seeds:
        if mask[y + 1, x + 1] == 0:
            cv2.floodFill(bgr, mask, (x, y), 0, diff, diff, flags)
    alpha = np.where(mask[1:-1, 1:-1] > 0, 0, 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(cv2.erode(alpha, np.ones((3, 3), np.uint8)), (3, 3), 0)  # borde suave, sin halo
    out = img.copy()
    out[..., 3] = alpha
    return out


def has(name: str) -> bool:
    return load(name) is not None


def available(name: str) -> bool:
    """True si hay imagen o dibujo por código para ese nombre."""
    return has(name) or name in _FALLBACKS


def _source(name, w, h):
    img = load(name)
    if img is None and name in _FALLBACKS:
        # Se dibuja al doble de tamaño y se reduce: bordes suaves (antialiasing)
        big = _FALLBACKS[name](max(2, 2 * w), max(2, 2 * h))
        img = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA)
    return img


@lru_cache(maxsize=1024)
def _prepared(name, w, h, keep_aspect, angle, tint):
    src = _source(name, w, h)
    if src is None:
        return None
    sh, sw = src.shape[:2]
    if keep_aspect:
        s = min(w / sw, h / sh)
        w, h = max(1, int(sw * s)), max(1, int(sh * s))
    img = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA if w < sw else cv2.INTER_LINEAR)
    if tint is not None:  # tiñe una imagen gris/blanca con un color (p.ej. el de cada dedo)
        bgr = cv2.multiply(img[..., :3], np.full((h, w, 3), tint, np.uint8), scale=1 / 255)
        img = np.dstack([bgr, img[..., 3]])
    if angle:
        diag = int(math.hypot(w, h)) + 2
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        m[0, 2] += (diag - w) / 2
        m[1, 2] += (diag - h) / 2
        img = cv2.warpAffine(img, m, (diag, diag), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    alpha = cv2.merge([img[..., 3]] * 3)
    pre = cv2.multiply(np.ascontiguousarray(img[..., :3]), alpha, scale=1 / 255)
    return 255 - alpha, pre


def draw(img, name, center, w, h, angle=0.0, tint=None) -> bool:
    """Pega la imagen centrada en `center`, cabiendo en w x h (sin deformarla)."""
    item = _prepared(name, int(w), int(h), True, round(angle / 3) * 3, tint)
    if item is None:
        return False
    inv, pre = item
    ui._blend(img, inv, pre, int(center[0] - inv.shape[1] / 2), int(center[1] - inv.shape[0] / 2))
    return True


def draw_rect(img, name, rect, tint=None) -> bool:
    """Pega la imagen estirada para llenar exactamente el rectángulo (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = (int(v) for v in rect)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return False
    item = _prepared(name, x2 - x1, y2 - y1, False, 0, tint)
    if item is None:
        return False
    ui._blend(img, item[0], item[1], x1, y1)
    return True


@lru_cache(maxsize=8)
def background(name, w, h):
    """Fondo a pantalla completa (BGR), o None si no hay imagen."""
    img = load(name)
    if img is None:
        return None
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    alpha = img[..., 3:].astype(np.float32) / 255
    return (img[..., :3] * alpha).astype(np.uint8)


# ------------------------------------------------- dibujos por código (BGRA)
def _canvas(w, h):
    return np.zeros((h, w, 4), np.uint8)


def _c(color, a=255):
    return (int(color[0]), int(color[1]), int(color[2]), a)


@_fallback("trineo")
def _draw_sleigh(w, h):
    """Trineo rojo con un saco de regalos y un reno delante (mirando a la derecha)."""
    img = _canvas(w, h)
    aa = cv2.LINE_AA

    def pt(x, y):  # coordenadas en una rejilla de 100 x 50
        return int(x * w / 100), int(y * h / 50)

    gold, red, dark_red = (60, 190, 240), (50, 45, 205), (40, 30, 150)
    brown, dark_brown = (45, 85, 140), (30, 55, 95)
    # Reno (delante, a la derecha)
    cv2.ellipse(img, pt(80, 26), (int(10 * w / 100), int(6 * h / 50)), -10, 0, 360, _c(brown), -1, aa)
    for lx, ly in ((73, 30), (76, 31), (84, 29), (87, 28)):  # patas estiradas al galope
        cv2.line(img, pt(lx, ly), pt(lx + (-5 if lx < 80 else 5), ly + 9), _c(dark_brown), max(2, int(w / 70)), aa)
    cv2.line(img, pt(88, 23), pt(93, 15), _c(brown), max(3, int(w / 40)), aa)   # cuello
    cv2.ellipse(img, pt(95, 14), (int(4 * w / 100), int(3 * h / 50)), 15, 0, 360, _c(brown), -1, aa)  # cabeza
    for dx in (-2, 1):  # cuernos
        base = pt(93 + dx, 11)
        cv2.line(img, base, pt(91 + dx, 4), _c(dark_brown), max(2, int(w / 90)), aa)
        cv2.line(img, pt(91.5 + dx, 7), pt(88 + dx, 5), _c(dark_brown), max(2, int(w / 110)), aa)
    cv2.circle(img, pt(97, 13), max(1, int(w / 160)), _c((20, 20, 20)), -1, aa)  # ojo
    # Riendas
    cv2.line(img, pt(52, 22), pt(88, 22), _c(gold), max(1, int(w / 200)), aa)
    # Saco de regalos
    cv2.ellipse(img, pt(25, 14), (int(14 * w / 100), int(12 * h / 50)), 0, 0, 360, _c((70, 120, 160)), -1, aa)
    for (gx, gy, col) in ((18, 6, (60, 170, 60)), (30, 4, (200, 90, 50)), (24, 1, (60, 60, 220))):
        cv2.rectangle(img, pt(gx - 4, gy - 4), pt(gx + 4, gy + 4), _c(col), -1, aa)
        cv2.line(img, pt(gx, gy - 4), pt(gx, gy + 4), _c(gold), max(1, int(w / 150)), aa)
    # Cuerpo del trineo
    body = np.array([pt(8, 18), pt(52, 18), pt(58, 12), pt(62, 14), pt(58, 36), pt(14, 36), pt(6, 28)], np.int32)
    cv2.fillPoly(img, [body], _c(red), aa)
    cv2.fillPoly(img, [np.array([pt(10, 30), pt(56, 30), pt(58, 36), pt(14, 36)], np.int32)], _c(dark_red), aa)
    cv2.line(img, pt(10, 22), pt(55, 22), _c(gold), max(2, int(w / 90)), aa)
    # Patines dorados
    cv2.line(img, pt(12, 36), pt(14, 43), _c(gold), max(2, int(w / 70)), aa)
    cv2.line(img, pt(50, 36), pt(48, 43), _c(gold), max(2, int(w / 70)), aa)
    cv2.line(img, pt(4, 43), pt(60, 43), _c(gold), max(3, int(w / 55)), aa)
    cv2.ellipse(img, pt(62, 39), (int(4 * w / 100), int(4 * h / 50)), 0, -90, 90, _c(gold), max(3, int(w / 55)), aa)
    return img


def _gift(w, h, box, ribbon):
    img = _canvas(w, h)
    aa = cv2.LINE_AA
    s = min(w, h)
    x0, y0 = (w - s) // 2, (h - s) // 2

    def p(x, y):
        return int(x0 + x * s), int(y0 + y * s)

    light = tuple(min(255, int(c * 1.25 + 20)) for c in box)
    dark = tuple(int(c * 0.7) for c in box)
    cv2.rectangle(img, p(0.12, 0.38), p(0.88, 0.95), _c(box), -1, aa)              # caja
    cv2.rectangle(img, p(0.12, 0.38), p(0.30, 0.95), _c(light), -1, aa)             # brillo
    cv2.rectangle(img, p(0.70, 0.38), p(0.88, 0.95), _c(dark), -1, aa)              # sombra
    cv2.rectangle(img, p(0.06, 0.26), p(0.94, 0.42), _c(light), -1, aa)             # tapa
    cv2.rectangle(img, p(0.44, 0.26), p(0.56, 0.95), _c(ribbon), -1, aa)            # cinta
    for side in (-1, 1):                                                            # lazo
        cv2.ellipse(img, p(0.5 + side * 0.15, 0.17), (int(0.16 * s), int(0.1 * s)), side * 25, 0, 360,
                    _c(ribbon), -1, aa)
        cv2.ellipse(img, p(0.5 + side * 0.15, 0.17), (int(0.07 * s), int(0.04 * s)), side * 25, 0, 360,
                    _c(tuple(int(c * 0.75) for c in ribbon)), -1, aa)
    cv2.circle(img, p(0.5, 0.24), int(0.06 * s), _c(ribbon), -1, aa)
    return img


@_fallback("regalo_1")
def _gift1(w, h):
    return _gift(w, h, (60, 55, 210), (60, 200, 245))


@_fallback("regalo_2")
def _gift2(w, h):
    return _gift(w, h, (70, 160, 50), (60, 60, 220))


@_fallback("regalo_3")
def _gift3(w, h):
    return _gift(w, h, (190, 110, 50), (240, 240, 250))


@_fallback("estrella")
def _star(w, h):
    """Estrella dorada con halo."""
    img = _canvas(w, h)
    cx, cy, s = w / 2, h / 2, min(w, h) / 2

    def star_pts(r_out, r_in):
        pts = []
        for i in range(10):
            r = r_out if i % 2 == 0 else r_in
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return np.array(pts, np.int32)

    halo = np.zeros((h, w), np.uint8)
    cv2.circle(halo, (int(cx), int(cy)), int(s * 0.75), 110, -1, cv2.LINE_AA)
    halo = cv2.GaussianBlur(halo, (0, 0), s * 0.18)
    img[..., :3] = (120, 230, 255)
    img[..., 3] = halo
    cv2.fillPoly(img, [star_pts(s * 0.9, s * 0.38)], _c((40, 190, 250)), cv2.LINE_AA)
    cv2.fillPoly(img, [star_pts(s * 0.55, s * 0.22)], _c((140, 235, 255)), cv2.LINE_AA)
    return img


@_fallback("nota")
def _note(w, h):
    """Nota del piano en blanco/gris: el juego la tiñe con el color de cada dedo."""
    img = _canvas(w, h)
    r = int(min(w, h) * 0.3)
    mask = ui._round_mask(w, h, r)
    img[..., :3] = 235
    img[..., 3] = mask
    shade = np.linspace(1.0, 0.72, h, dtype=np.float32)[:, None, None]   # degradado vertical
    img[..., :3] = (img[..., :3] * shade).astype(np.uint8)
    cv2.rectangle(img, (int(w * 0.12), int(h * 0.12)), (int(w * 0.88), int(h * 0.12) + max(2, h // 12)),
                  (255, 255, 255, 255), -1)                                      # brillo de arriba
    return img
