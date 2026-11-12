"""Gráficas de evolución del paciente a partir del historial CSV."""
import os

import matplotlib

matplotlib.use("Agg")  # sin ventanas: dibujamos en memoria y lo mostramos con OpenCV
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import cv2  # noqa: E402

from config import REPORTS_DIR  # noqa: E402
from rehab.session import load_history  # noqa: E402

# Qué columnas pintar de cada modo: (título, eje Y, [(columna, etiqueta)])
CHARTS = {
    "hombro": ("Rango maximo del hombro por sesion", "grados", [
        ("rom_max_izq", "Brazo izquierdo"),
        ("rom_max_der", "Brazo derecho"),
    ]),
    "mano": ("Precision por dedo en cada sesion", "% aciertos", [
        ("prec_indice", "Indice"),
        ("prec_corazon", "Corazon"),
        ("prec_anular", "Anular"),
        ("prec_menique", "Menique"),
    ]),
}


def _figure(game_key: str, patient: str, size=(6.4, 3.6)):
    title, ylabel, series = CHARTS[game_key]
    history = load_history(game_key, patient)
    fig, ax = plt.subplots(figsize=size, dpi=100)
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    for spine in ax.spines.values():
        spine.set_color("#888888")
    ax.tick_params(colors="#dddddd")
    ax.set_title(f"{title} - {patient}", color="white", fontsize=11)
    ax.set_xlabel("Sesion", color="#dddddd")
    ax.set_ylabel(ylabel, color="#dddddd")
    ax.grid(alpha=0.2)

    if not history:
        ax.text(0.5, 0.5, "Sin datos todavia", color="white", ha="center", va="center", transform=ax.transAxes)
    else:
        x = np.arange(1, len(history) + 1)
        for column, label in series:
            y = [float(r[column]) if r.get(column) not in (None, "") else np.nan for r in history]
            ax.plot(x, y, marker="o", label=label)
        ax.set_xticks(x)
        ax.legend(facecolor="#2a2a2a", labelcolor="white", fontsize=8)
    fig.tight_layout()
    return fig


def chart_image(game_key: str, patient: str, size=(6.4, 3.6)):
    """Devuelve la gráfica como imagen BGR para pegarla en la ventana de OpenCV."""
    fig = _figure(game_key, patient, size)
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    plt.close(fig)
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def save_report(game_key: str, patient: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in patient)
    path = os.path.join(REPORTS_DIR, f"{game_key}_{safe}.png")
    fig = _figure(game_key, patient, size=(8, 4.5))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
