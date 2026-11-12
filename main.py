"""Rehab Arcade: juego serio de rehabilitación del miembro superior.

Uso:
    python main.py --paciente "Nombre"  [--camara 0]

Todo se controla sin tocar el ordenador: los botones se pulsan dejando el
dedo índice encima un momento. También hay atajos de teclado:
    1 / 2   elegir modo en el menú
    ENTER   saltar instrucciones / volver al menú desde resultados
    M       quitar / poner la música
    F       pantalla completa
    ESC     volver al menú (o salir si ya estás en el menú)
"""
import argparse
import os
import sys
import time

import cv2

import config
from rehab import audio, ui
from rehab.games import GAMES
from rehab.report import chart_image, save_report
from rehab.session import save_session
from rehab.vision import Tracker, draw_hand, to_px

W, H = config.CAMERA_WIDTH, config.CAMERA_HEIGHT
INDEX_TIP = 8

MENU_BUTTONS = [
    ui.Button("hombro", "1. HOMBRO", (int(W * 0.08), int(H * 0.35), int(W * 0.46), int(H * 0.65)),
              sublabel="Fruit Ninja - rango de movimiento"),
    ui.Button("mano", "2. MANO", (int(W * 0.54), int(H * 0.35), int(W * 0.92), int(H * 0.65)),
              sublabel="Piano de dedos - motricidad fina"),
    ui.Button("salir", "Salir", (int(W * 0.40), int(H * 0.75), int(W * 0.60), int(H * 0.87)), color=ui.RED),
]
BACK_BUTTON = ui.Button("menu", "Menu", (int(W * 0.78), int(H * 0.62), int(W * 0.96), int(H * 0.80)))


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


def hand_pointer(tracker, frame):
    """Detecta la mano y devuelve la punta del índice en píxeles (o None)."""
    hand = tracker.detect_hand(frame)
    if hand is None:
        return None
    draw_hand(frame, hand, color=(200, 200, 200))
    return to_px(hand[INDEX_TIP], W, H)


def draw_menu(frame, patient, progress):
    ui.panel(frame, 0, 0, W, H, alpha=0.35)
    ui.put_text(frame, "REHAB ARCADE", (W // 2, int(H * 0.14)), 2.0, ui.CYAN, 4, center=True)
    ui.put_text(frame, f"Paciente: {patient}", (W // 2, int(H * 0.22)), 0.9, ui.WHITE, 2, center=True)
    ui.put_text(frame, "Deja el dedo indice sobre un boton para elegirlo", (W // 2, int(H * 0.29)),
                0.7, ui.GREY, 1, center=True)
    for button in MENU_BUTTONS:
        button.draw(frame, progress.get(button.key, 0.0))


def draw_results(frame, game, lines, chart, progress):
    ui.panel(frame, 0, 0, W, H, alpha=0.75)
    ui.put_text(frame, f"RESULTADOS - {game.title}", (W // 2, 60), 1.3, ui.CYAN, 3, center=True)
    for i, line in enumerate(lines):
        ui.put_text(frame, line, (60, 120 + i * 40), 0.75, ui.WHITE, 2)
    y0 = H - chart.shape[0] - 20
    frame[y0:y0 + chart.shape[0], 40:40 + chart.shape[1]] = chart
    BACK_BUTTON.draw(frame, progress.get("menu", 0.0))


def main():
    args = parse_args()
    check_models()
    cap = open_camera(args.camara)
    tracker = Tracker(config.POSE_MODEL, config.HAND_MODEL)
    selector = ui.DwellSelector(config.DWELL_TIME)
    audio.mixer.start()

    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(config.WINDOW_NAME, W, H)
    fullscreen = False

    state = "menu"
    game = None
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

            if state == "menu":
                pointer = hand_pointer(tracker, frame)
                selected, progress = selector.update(MENU_BUTTONS, pointer, now)
                draw_menu(frame, args.paciente, progress)
                ui.draw_pointer(frame, pointer)
                choice = selected.key if selected else None

            elif state == "game":
                if game.uses == "pose":
                    landmarks = tracker.detect_pose(frame)
                else:
                    landmarks = tracker.detect_hand(frame)
                game.update(frame, landmarks, dt)
                if game.finished:
                    audio.mixer.set_music(None)
                    result_lines, row = game.results()
                    csv_path = save_session(game.key, row)
                    save_report(game.key, args.paciente)
                    chart = chart_image(game.key, args.paciente, size=(7.0, 3.0))
                    print(f"Sesión guardada en {csv_path}")
                    selector.reset()
                    state = "results"

            elif state == "results":
                pointer = hand_pointer(tracker, frame)
                selected, progress = selector.update([BACK_BUTTON], pointer, now)
                draw_results(frame, game, result_lines, chart, progress)
                ui.draw_pointer(frame, pointer)
                if selected:
                    state = "menu"

            cv2.imshow(config.WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                if state == "menu":
                    break
                state = "menu"  # abandonar partida sin guardar
                audio.mixer.set_music(None)
                selector.reset()
            elif key in (ord("m"), ord("M")):
                print("Musica", "activada" if audio.mixer.toggle_music() else "desactivada")
            elif key in (ord("f"), ord("F")):
                fullscreen = not fullscreen
                cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            elif key == 13:  # ENTER
                if state == "game":
                    game.skip_intro()
                elif state == "results":
                    state = "menu"
            elif state == "menu" and key == ord("1"):
                choice = "hombro"
            elif state == "menu" and key == ord("2"):
                choice = "mano"

            if choice == "salir":
                break
            if choice in GAMES:
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
