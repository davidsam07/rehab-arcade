"""Cálculos geométricos sobre puntos en píxeles."""
import math


def distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle_deg(a, b, c) -> float:
    """Ángulo en grados en el vértice b, formado por los segmentos b->a y b->c.

    Ejemplo: angle_deg(cadera, hombro, codo) es la apertura del hombro:
    0º = brazo pegado al cuerpo, 90º = brazo en horizontal, 180º = brazo arriba.
    """
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def point_at_angle(origin, length: float, angle: float, outward: int) -> tuple:
    """Punto a `length` px de `origin`, con `angle` grados medidos desde la vertical hacia abajo.

    `outward` es +1 si el brazo abre hacia la derecha de la pantalla y -1 si abre hacia la izquierda.
    En imagen la y crece hacia abajo, por eso 0º apunta abajo y 180º arriba.
    """
    rad = math.radians(angle)
    return (origin[0] + outward * length * math.sin(rad), origin[1] + length * math.cos(rad))
