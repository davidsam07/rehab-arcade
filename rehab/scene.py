"""Paisaje nevado de noche con scroll en capas (parallax), dibujado por código.

Se usa de fondo en los menús y en el trineo volador. Las capas lejanas se
mueven más despacio que las cercanas, lo que da sensación de profundidad.
Cada capa se genera una sola vez como una tira que se repite sin cortes, y
en cada frame solo se copia la parte visible (muy rápido).

Si hay imágenes en assets/ se usan en su lugar:
  - fondo_cielo.png: el cielo (sustituye al degradado, la luna y las estrellas).
  - colinas.png: capa de colinas cercanas que se repite en horizontal (con transparencia).
"""
import math
import random

import cv2
import numpy as np

from rehab import assets, ui


def _profile(w, base, amps, rng):
    """Perfil de colinas que se repite cada w píxeles (suma de senos de periodo entero)."""
    x = np.arange(w)
    y = np.full(w, float(base))
    for k, a in amps:
        y += a * np.sin(2 * np.pi * k * x / w + rng.uniform(0, 6.28))
    return y.astype(np.int32)


def _layer_from_profile(w, h, profile, color):
    img = np.zeros((h, w, 3), np.uint8)
    mask = np.zeros((h, w), np.uint8)
    pts = np.array([(0, h)] + [(x, int(y)) for x, y in enumerate(profile)] + [(w - 1, h)], np.int32)
    cv2.fillPoly(mask, [pts], 255)
    img[mask > 0] = color
    return img, mask


class WinterScene:
    def __init__(self, w, h, seed=4):
        self.w, self.h = w, h
        rng = random.Random(seed)
        self.t = 0.0
        self.scroll = 0.0
        self.sky = assets.background("fondo_cielo", w, h)
        if self.sky is None:
            self.sky = self._make_sky(rng)
            self.stars = [(rng.randrange(w), rng.randrange(int(h * 0.6)), rng.uniform(0, 6.28), rng.choice((1, 1, 2)))
                          for _ in range(90)]
        else:
            self.stars = []
        self.layers = [  # (imagen, máscara, velocidad relativa)
            self._mountains(rng) + (0.15,),
            self._hills(rng) + (0.45,),
        ]
        custom = assets.load("colinas")
        if custom is not None:  # capa de colinas del usuario: sustituye a la cercana
            ch = int(custom.shape[0] * w / custom.shape[1])
            custom = cv2.resize(custom, (w, ch))
            img = np.zeros((h, w, 3), np.uint8)
            mask = np.zeros((h, w), np.uint8)
            img[h - ch:] = custom[..., :3]
            mask[h - ch:] = (custom[..., 3] > 127).astype(np.uint8) * 255
            self.layers[1] = (img, mask, 0.45)
        # Cada capa se duplica en horizontal para poder recortar cualquier ventana sin salirse
        self.layers = [(np.concatenate([i, i], 1), np.concatenate([m, m], 1), s) for i, m, s in self.layers]
        self.snow = ui.Snow(80, seed=seed)

    # ------------------------------------------------------------- capas
    def _make_sky(self, rng):
        w, h = self.w, self.h
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        top, bottom = np.array([45, 18, 10], np.float32), np.array([110, 55, 60], np.float32)  # azul noche -> malva
        sky = np.empty((h, w, 3), np.float32)
        sky[:] = (top * (1 - t) + bottom * t)[:, None, :]
        sky = sky.astype(np.uint8)
        # Luna con halo
        mx, my, r = int(w * 0.80), int(h * 0.20), int(h * 0.07)
        glow = np.zeros((h, w), np.uint8)
        cv2.circle(glow, (mx, my), int(r * 2.6), 90, -1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(glow, (0, 0), r)
        sky = cv2.add(sky, cv2.merge([glow, glow, (glow * 0.9).astype(np.uint8)]))
        cv2.circle(sky, (mx, my), r, (215, 240, 250), -1, cv2.LINE_AA)
        cv2.circle(sky, (mx - r // 3, my - r // 4), r // 5, (190, 215, 228), -1, cv2.LINE_AA)
        cv2.circle(sky, (mx + r // 3, my + r // 3), r // 7, (195, 220, 232), -1, cv2.LINE_AA)
        return sky

    def _mountains(self, rng):
        w, h = self.w, self.h
        prof = _profile(w, h * 0.62, [(2, h * 0.05), (3, h * 0.04), (7, h * 0.015)], rng)
        img, mask = _layer_from_profile(w, h, prof, (105, 52, 62))   # morado oscuro, a juego con el cielo
        # Cumbres nevadas
        for x in range(w):
            y = prof[x]
            cv2.line(img, (x, y), (x, y + int(h * 0.025)), (200, 170, 185), 1)
        return img, mask

    def _hills(self, rng):
        w, h = self.w, self.h
        prof = _profile(w, h * 0.80, [(1, h * 0.035), (2, h * 0.03), (5, h * 0.012)], rng)
        img, mask = _layer_from_profile(w, h, prof, (235, 225, 220))       # nieve
        shade = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        img = (img * (1 - 0.18 * shade)).astype(np.uint8)
        # Árboles y casitas con las ventanas encendidas
        for _ in range(9):
            x = rng.randrange(20, w - 20)
            y = int(prof[x])
            s = rng.randint(28, 52)
            for k, (top, base, half) in enumerate([(-1.0, -0.45, 0.32), (-0.75, -0.2, 0.42), (-0.5, 0.05, 0.5)]):
                pts = np.array([(x, y + top * s * 1.6), (x + half * s, y + base * s * 1.6),
                                (x - half * s, y + base * s * 1.6)], np.int32)
                cv2.fillPoly(img, [pts], (55, 95, 40), cv2.LINE_AA)
                cv2.fillPoly(mask, [pts], 255, cv2.LINE_AA)
        for _ in range(4):
            x = rng.randrange(60, w - 60)
            y = int(prof[x]) + 6
            bw, bh = rng.randint(50, 70), rng.randint(36, 48)
            body = (x - bw // 2, y - bh, x + bw // 2, y)
            cv2.rectangle(img, body[:2], body[2:], (60, 75, 125), -1)
            cv2.rectangle(mask, body[:2], body[2:], 255, -1)
            roof = np.array([(x - bw // 2 - 8, y - bh), (x + bw // 2 + 8, y - bh), (x, y - bh - 30)], np.int32)
            cv2.fillPoly(img, [roof], (240, 235, 235), cv2.LINE_AA)
            cv2.fillPoly(mask, [roof], 255, cv2.LINE_AA)
            for wx in (x - bw // 4, x + bw // 4):
                cv2.rectangle(img, (wx - 7, y - bh + 10), (wx + 7, y - bh + 24), (80, 210, 255), -1)
            cv2.rectangle(img, (x + bw // 4 - 4, y - bh - 26), (x + bw // 4 + 6, y - bh - 8), (50, 60, 110), -1)
            cv2.rectangle(mask, (x + bw // 4 - 4, y - bh - 26), (x + bw // 4 + 6, y - bh - 8), 255, -1)
        return img, mask

    # ------------------------------------------------------------- dibujo
    def draw(self, frame, dt, speed=40.0, snow=True):
        """Pinta el paisaje en `frame`. speed: px/s de la capa más cercana."""
        self.t += dt
        self.scroll += speed * dt
        frame[:] = self.sky
        for x, y, phase, r in self.stars:  # estrellas que titilan
            b = 0.55 + 0.45 * math.sin(self.t * 2.2 + phase)
            c = int(150 + 105 * b)
            cv2.circle(frame, (x, y), r, (c, c, c), -1, cv2.LINE_AA)
        for img, mask, rel in self.layers:
            off = int(self.scroll * rel) % self.w
            cv2.copyTo(img[:, off:off + self.w], mask[:, off:off + self.w], frame)
        if snow:
            self.snow.draw(frame, dt)
        return frame
