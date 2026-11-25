"""Rehab Arcade: juego serio de rehabilitación del miembro superior.

Uso:
    python main.py --paciente "Nombre"  [--camara 0]

Todo se controla sin tocar el ordenador: los botones se pulsan dejando el
dedo índice encima un momento. También hay atajos de teclado:
    1 / 2   elegir modo en el menú (1-5 para elegir canción)
    ENTER   saltar instrucciones / volver al menú desde resultados
    M       quitar / poner la música
    F       pantalla completa
    ESC     volver al menú (o salir si ya estás en el menú)
"""
import argparse
import math
import os
import sys
import time

import cv2

import config
from rehab import assets, audio, ui
from rehab.games import GAMES
from rehab.games.finger_piano import FingerPiano
from rehab.report import chart_image, save_report
from rehab.scene import WinterScene
from rehab.session import save_session
from rehab.songs import SONGS
from rehab.vision import Tracker, draw_hand

W, H = config.CAMERA_WIDTH, config.CAMERA_HEIGHT
INDEX_TIP = 8

MENU_BUTTONS = [
    ui.Button("hombro", "Hombro", (int(W * 0.08), int(H * 0.34), int(W * 0.47), int(H * 0.74)),
              sublabel="Trineo volador: recoge regalos", images=("icono_hombro", "trineo"), color=ui.ORANGE,
              hint="tecla 1"),
    ui.Button("mano", "Mano", (int(W * 0.53), int(H * 0.34), int(W * 0.92), int(H * 0.74)),
              sublabel="Piano de dedos: toca canciones", icon="piano", images=("icono_mano",), color=ui.CYAN,
              hint="tecla 2"),
    ui.Button("salir", "Salir", (int(W * 0.42), int(H * 0.80), int(W * 0.58), int(H * 0.91)), color=ui.RED),
]


def _song_buttons():
    """Tarjetas de canciones: 3 arriba y 2 abajo, con el botón de volver."""
    buttons = []
    cw, ch, gap = int(W * 0.27), int(H * 0.29), int(W * 0.035)
    rows = [list(SONGS.values())[:3], list(SONGS.values())[3:]]
    for r, songs in enumerate(rows):
        total = len(songs) * cw + (len(songs) - 1) * gap
        x = (W - total) // 2
        y = int(H * 0.24) + r * (ch + int(H * 0.04))
        for song in songs:
            n = len(buttons) + 1
            buttons.append(ui.Button(song.key, song.title, (x, y, x + cw, y + ch), sublabel=song.subtitle,
                                     icon=song.icon, tag=song.mood, hint=f"tecla {n}", images=(f"icono_{song.key}",),
                                     color=ui.GOLD if song.christmas else ui.CYAN))
            x += cw + gap
    return buttons


SONG_BUTTONS = _song_buttons()
BACK_SONGS = ui.Button("volver", "Volver", (int(W * 0.03), int(H * 0.86), int(W * 0.17), int(H * 0.96)),
                       color=ui.GREY)
AGAIN_BUTTON = ui.Button("otra", "Otra vez", (int(W * 0.62), int(H * 0.60), int(W * 0.96), int(H * 0.75)),
                         color=ui.GREEN)
BACK_BUTTON = ui.Button("menu", "Menú", (int(W * 0.62), int(H * 0.79), int(W * 0.96), int(H * 0.94)))


def parse_args():
    parser = argparse.ArgumentParser(description="Rehab Arcade")
    parser.add_argument("--paciente", default="invitado", help="nombre del paciente (para su historial)")
    parser.add_argument("--camara", type=int, default=0, help="índice de la webcam (0, 1, ...)")
    return parser.parse_args()


def check_models():
    missing = [p for p in (config.POSE_MODEL, config.HAND_MODEL) if not os.path.exists(p)]
    if missing:
        print("Faltan modelos de MediaPipe:", *missing, sep="\n  ")
        print("Ejecuta primero:  python download_models.py")
        sys.exit(1)


def open_camera(index):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    if not cap.isOpened():
        print(f"No se pudo abrir la cámara {index}. Prueba con --camara 1 o cierra otras apps que la usen.")
        sys.exit(1)
    return cap


class HandPointer:
    """Puntero de los menús a partir de la punta del dedo índice.

    - Zona cómoda: solo se usa el centro de la imagen de la cámara y se estira
      a toda la pantalla, así se llega a todos los botones sin estirar el brazo
      (por ejemplo, al botón de abajo estando sentado).
    - Suavizado: filtra el temblor de la mano y de la detección.
    - Si la mano se pierde un instante, el puntero se queda donde estaba.
    """

    ZONE = (0.15, 0.10, 0.85, 0.72)   # x1, y1, x2, y2 de la imagen (0-1) que se estira a la pantalla
    FOLLOW = 14.0                     # rapidez del suavizado (1/s)
    LOST_TIME = 0.5                   # s sin ver la mano antes de quitar el puntero

    def __init__(self):
        self.pos = None
        self.lost = 0.0

    def update(self, hand, dt):
        if hand is None:
            self.lost += dt
            if self.lost > self.LOST_TIME:
                self.pos = None
            return self.pos
        self.lost = 0.0
        x1, y1, x2, y2 = self.ZONE
        tip = hand[INDEX_TIP]
        x = min(1.0, max(0.0, (tip.x - x1) / (x2 - x1))) * W
        y = min(1.0, max(0.0, (tip.y - y1) / (y2 - y1))) * H
        if self.pos is None:
            self.pos = (x, y)
        else:
            k = 1 - math.exp(-self.FOLLOW * dt)
            self.pos = (self.pos[0] + (x - self.pos[0]) * k, self.pos[1] + (y - self.pos[1]) * k)
        return self.pos


def draw_menu_camera(frame, cam, hand, top=False):
    """Cámara en pequeño con la mano y la zona en la que hay que moverla.

    Va abajo a la derecha; en resultados (top=True) arriba a la derecha, porque abajo están los botones.
    """
    ch, cw = cam.shape[:2]
    x1, y1, x2, y2 = HandPointer.ZONE
    cv2.rectangle(cam, (int(x1 * cw), int(y1 * ch)), (int(x2 * cw), int(y2 * ch)), ui.YELLOW, 1, cv2.LINE_AA)
    if hand is not None:
        draw_hand(cam, hand, color=(255, 220, 120))
    x, y = W - cw - 20, (130 if top else H - ch - 20)
    ui.rounded_rect(frame, (x - 5, y - 5, x + cw + 5, y + ch + 5), 14, ui.DARK, 0.9,
                    border=ui.WHITE if hand is not None else ui.ORANGE)
    frame[y:y + ch, x:x + cw] = cam
    ui.put_text(frame, "Tú", (x + 10, y + 26), 0.6, ui.WHITE, 2)
    if hand is None:
        ui.put_text(frame, "Levanta la mano", (x + cw // 2, y - 16), 0.65, ui.ORANGE, 2, center=True)


def menu_background(frame, scene, dt):
    """Fondo de los menús: assets/fondo_menu.png si existe; si no, el paisaje nevado animado."""
    image = assets.background("fondo_menu", W, H)
    if image is not None:
        frame[:] = image
    else:
        scene.draw(frame, dt, speed=30.0)


def footer(frame, text):
    ui.put_text(frame, text, ((W - int(W * 0.2) - 40) // 2, H - 18), 0.55, (200, 200, 200), 1, center=True)


def draw_menu(frame, patient, progress):
    if not assets.draw(frame, "logo", (W // 2, int(H * 0.12)), int(W * 0.5), int(H * 0.16)):
        ui.put_text(frame, "Rehab Arcade", (W // 2, int(H * 0.15)), 2.1, ui.WHITE, 2, center=True)
    ui.put_text(frame, f"Hola, {patient}. ¿Qué quieres entrenar hoy?", (W // 2, int(H * 0.25)), 0.95,
                ui.YELLOW, 2, center=True)
    for button in MENU_BUTTONS:
        button.draw(frame, progress.get(button.key, 0.0))
    footer(frame, "Deja el dedo índice quieto sobre un botón para elegirlo   ·   F: pantalla completa   ·   ESC: salir")


def draw_songs(frame, progress):
    ui.dim(frame, 0.25)
    ui.put_text(frame, "Elige una canción", (W // 2, int(H * 0.12)), 1.6, ui.WHITE, 2, center=True)
    ui.put_text(frame, "Las notas caerán al ritmo de la música", (W // 2, int(H * 0.19)), 0.8, ui.GOLD, 2,
                center=True)
    for button in SONG_BUTTONS + [BACK_SONGS]:
        button.draw(frame, progress.get(button.key, 0.0))
    footer(frame, "Teclas 1-5 para elegir   ·   ESC: volver")


def draw_results(frame, game, patient, lines, chart, progress):
    ui.dim(frame, 0.55)
    ui.put_text(frame, f"¡Buen trabajo, {patient}!", (W // 2, 62), 1.4, ui.YELLOW, 2, center=True)
    ui.put_text(frame, game.title, (W // 2, 102), 0.75, ui.CYAN, 2, center=True)
    line_h = 36
    card = (40, 125, W - int(W * 0.2) - 60, 125 + 26 + line_h * len(lines))  # a la derecha va la cámara
    ui.rounded_rect(frame, card, 22, ui.DARK, 0.9)
    for i, line in enumerate(lines):
        ui.put_text(frame, line, (70, card[1] + 44 + i * line_h), 0.68, ui.WHITE, 2, shadow=False)
    ch, cw = chart.shape[:2]
    y0 = min(H - ch - 20, card[3] + 18)
    frame[y0:y0 + ch, 40:40 + cw] = chart
    AGAIN_BUTTON.draw(frame, progress.get("otra", 0.0))
    BACK_BUTTON.draw(frame, progress.get("menu", 0.0))


def main():
    args = parse_args()
    check_models()
    cap = open_camera(args.camara)
    tracker = Tracker(config.POSE_MODEL, config.HAND_MODEL)
    selector = ui.DwellSelector(config.DWELL_TIME)
    scene = WinterScene(W, H)
    pointer_filter = HandPointer()
    audio.mixer.start()

    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(config.WINDOW_NAME, W, H)
    fullscreen = False

    state = "menu"
    game = None
    hand_calibration = None      # medida de la mano: se reutiliza entre canciones
    result_lines, chart = [], None
    last = time.monotonic()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("La cámara ha dejado de enviar imágenes.")
                break
            frame = cv2.resize(cv2.flip(frame, 1), (W, H))  # espejo: más natural para el usuario
            now = time.monotonic()
            dt = min(now - last, 0.1)  # si un frame tarda mucho, no saltamos el juego
            last = now
            choice = None

            if state in ("menu", "songs", "results"):
                hand = tracker.detect_hand(frame)
                pointer = pointer_filter.update(hand, dt)
                cam = cv2.resize(frame, (int(W * 0.2), int(H * 0.2)), interpolation=cv2.INTER_AREA)
                menu_background(frame, scene, dt)
                buttons = {"menu": MENU_BUTTONS, "songs": SONG_BUTTONS + [BACK_SONGS],
                           "results": [AGAIN_BUTTON, BACK_BUTTON]}[state]
                selected, progress = selector.update(buttons, pointer, now)
                if state == "menu":
                    draw_menu(frame, args.paciente, progress)
                elif state == "songs":
                    draw_songs(frame, progress)
                else:
                    draw_results(frame, game, args.paciente, result_lines, chart, progress)
                draw_menu_camera(frame, cam, hand, top=state == "results")
                ui.draw_pointer(frame, pointer, max(progress.values(), default=0.0))
                choice = selected.key if selected else None

            elif state == "game":
                if game.uses == "pose":
                    landmarks = tracker.detect_pose(frame)
                else:
                    landmarks = tracker.detect_hand(frame)
                game.update(frame, landmarks, dt)
                if game.finished:
                    audio.mixer.stop_all()
                    if isinstance(game, FingerPiano) and game.calibration_data():
                        hand_calibration = game.calibration_data()
                    result_lines, row = game.results()
                    csv_path = save_session(game.key, row)
                    save_report(game.key, args.paciente)
                    chart = chart_image(game.key, args.paciente, size=(7.0, 2.9))
                    print(f"Sesión guardada en {csv_path}")
                    selector.reset()
                    state = "results"

            cv2.imshow(config.WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                if state == "menu":
                    break
                if state == "game" and isinstance(game, FingerPiano) and game.calibration_data():
                    hand_calibration = game.calibration_data()
                state = "menu"  # abandonar partida sin guardar
                audio.mixer.stop_all()
                selector.reset()
            elif key in (ord("m"), ord("M")):
                print("Música", "activada" if audio.mixer.toggle_music() else "desactivada")
            elif key in (ord("f"), ord("F")):
                fullscreen = not fullscreen
                cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            elif key == 13:  # ENTER
                if state == "game":
                    game.skip_intro()
                elif state == "results":
                    choice = "menu"
            elif state == "menu" and key in (ord("1"), ord("2")):
                choice = "hombro" if key == ord("1") else "mano"
            elif state == "songs" and ord("1") <= key < ord("1") + len(SONGS):
                choice = list(SONGS)[key - ord("1")]

            if choice == "salir":
                break
            if choice == "otra":  # repetir: el piano vuelve a elegir canción, el hombro empieza otra partida
                choice = "mano" if isinstance(game, FingerPiano) else game.key
            if choice in ("menu", "volver"):
                state = "menu"
                selector.reset()
            elif choice == "mano":
                state = "songs"
                selector.reset()
            elif choice in SONGS:
                game = FingerPiano(args.paciente, choice, hand_calibration)
                state = "game"
            elif choice in GAMES:
                game = GAMES[choice](args.paciente)
                state = "game"

            # Cerrar con la X de la ventana
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        tracker.close()
        audio.mixer.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
