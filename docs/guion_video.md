# Guion del vídeo: Rehab Arcade (≈ 10 min)

IPM · Práctica 2 · IPM mediante visión por computador

Duración total: unos **9:45**, con margen hasta los 10 minutos. Cada parte indica **qué se ve** en pantalla y **qué se dice**. El texto está para decirlo con vuestras palabras, no para leerlo tal cual. Si lo grabáis entre los dos, el reparto natural es que **A** lleve el modo hombro y **B** el modo mano.

> ⚠️ Las cifras de la parte 2 son las que se citan habitualmente (Sociedad Española de Neurología y literatura de rehabilitación). Comprobad la fuente antes de grabar y ponedla en pantalla.

---

## Antes de grabar (checklist)

- [ ] **Quitar el silencio del altavoz de Windows**: la música es parte de la demo.
- [ ] Buena luz de frente (no a contraluz con la ventana detrás) y fondo despejado.
- [ ] Para el modo hombro: sentado o de pie a **1,5 – 2 m** de la cámara, que se vea de cintura para arriba con los codos dentro del encuadre.
- [ ] Silenciar notificaciones y cerrar apps que usen la cámara.
- [ ] Juego en pantalla completa (tecla **F**) y grabación con OBS (captura de pantalla + micrófono).
- [ ] Ejecutar con un paciente de demo para tener gráfica limpia: `python main.py --paciente "Demo"`. Jugad antes 2 o 3 partidas para que la gráfica de evolución tenga varios puntos.
- [ ] (Si usáis el paciente Bicho: la **sesión 6** del hombro marca 179° por un fallo de detección; borrad esa fila de `data/hombro.csv` antes de grabar).

---

## 1. Presentación (0:00 – 0:30)

**Se ve:** el menú del juego en pantalla completa, con la nieve y la cámara pequeña.

**Se dice:**
> Hola, somos [nombre y apellidos] y [nombre y apellidos]. Esta es nuestra práctica 2 de Interacción Persona-Máquina: **Rehab Arcade**, un juego serio para la rehabilitación del brazo y la mano después de un ictus, que se juega solo con la webcam gracias a la visión por computador.

---

## 2. La problemática (0:30 – 2:00)

**Se ve:** 2–3 diapositivas sencillas, o la cámara hablando, con las cifras en texto.

**Se dice (ideas clave):**
- El **ictus** es una de las principales causas de discapacidad en adultos. En España lo sufren **unas 110.000–120.000 personas al año** (SEN).
- La gran mayoría tiene afectado el **miembro superior** (hombro, brazo y mano), y muchas no recuperan del todo la función del brazo. Eso les quita autonomía para vestirse, comer o asearse.
- La recuperación depende de **repetir muchísimas veces** los movimientos (neuroplasticidad). Pero:
  - las sesiones con el fisioterapeuta son **cortas y caras**, y desplazarse al centro cuesta, sobre todo a personas mayores;
  - los ejercicios en casa son **repetitivos y aburridos**, y mucha gente **los abandona**;
  - en casa **nadie mide el progreso**: el terapeuta no sabe si se han hecho ni cómo han ido.
- Muchas soluciones tecnológicas (robots, guantes con sensores, realidad virtual) son caras y difíciles de usar en casa.

**Frase puente:**
> Nuestra pregunta fue: ¿podemos convertir esos ejercicios en un juego que motive, que se adapte a cada paciente y que mida su evolución, usando solo una webcam normal?

---

## 3. Nuestra solución (2:00 – 3:15)

**Se ve:** el menú, señalando con el dedo los dos modos (sin elegir todavía).

**Se dice:**
- **Rehab Arcade** tiene dos minijuegos, uno para cada zona que más se afecta:
  - **Hombro → Trineo volador**: trabaja la **abducción del hombro** (subir los brazos por los lados).
  - **Mano → Piano de dedos**: trabaja la **pinza** del pulgar con cada dedo, es decir, la **motricidad fina**.
- **Sin mandos, sin sensores, sin tocar el ordenador**: todo con la webcam y MediaPipe de Google.
- Pensado para **personas mayores** (principios de IPM):
  - botones grandes que se pulsan **dejando el dedo quieto encima** (*dwell*), sin ratón;
  - textos grandes, alto contraste e instrucciones paso a paso;
  - una **cámara pequeña** para que el paciente se vea y sepa si le está detectando;
  - sin "game over": si no le ve, el juego se pausa; los fallos no castigan.
- **Se adapta a cada paciente**: primero calibra su rango de movimiento y luego ajusta la dificultad en tiempo real.
- **Mide la evolución**: cada partida se guarda y se enseña una gráfica de progreso para el paciente y su terapeuta.
- Ambientación **navideña**, con música y arte propios, para que apetezca jugar.

---

## 4. Cómo está implementado (3:15 – 4:45)

**Se ve:** VS Code con la estructura del proyecto y, de fondo, el README o un esquema sencillo.

**Se dice:**
- **Python + OpenCV + MediaPipe** (`PoseLandmarker` para el cuerpo y `HandLandmarker` para la mano, en modo **VIDEO**, que aprovecha el seguimiento entre frames).
- **Arquitectura** (`rehab/`):
  - `vision.py`: los detectores de MediaPipe;
  - `games/base.py`: las fases comunes (instrucciones → calibración → cuenta atrás → juego);
  - `sleigh_flight.py` y `finger_piano.py`: un archivo por minijuego (uno cada uno);
  - `audio.py`: música sintetizada con numpy, sin archivos de audio; `ui.py`: interfaz; `session.py` y `report.py`: CSV y gráficas.
- **Métrica del hombro:** el ángulo entre la vertical y el segmento **hombro → codo** (landmarks 11-13 y 12-14). Se normaliza por el máximo de la calibración de cada lado: "100 %" significa *tu* máximo.
- **Métrica de la mano:** la distancia de la **punta del pulgar (4)** a cada punta de dedo (8, 12, 16, 20), **dividida por el tamaño de la mano** (muñeca → nudillo del corazón). Así da igual lo cerca que esté la mano de la cámara.
- Detalles que nos dieron guerra:
  - **Histéresis en la pinza**: un umbral para cerrar y otro para soltar, para que el temblor no cuente dobles. Además se suelta en cuanto el dedo se separa de su punto más cerrado (al principio el pulgar se quedaba "enganchado").
  - **Sincronía con la música**: el audio de Windows salía con unos **200 ms de retraso**. El juego usa el reloj del audio y compensa ese retraso y el de la cámara.
  - **Dificultad adaptativa**: según los aciertos recientes cambian la altura de los regalos y la velocidad del trineo, o el tempo de la canción y el número de notas del piano. Los dedos que más fallan reciben más notas.

---

## 5. Demo: modo hombro (4:45 – 6:45)

**Se ve:** la pantalla del juego en pantalla completa, con la persona que juega en la cámara pequeña. **Juega A, habla A.**

1. **Menú** (5 s): dejar el dedo en **Hombro** y enseñar cómo se carga el botón.
2. **Instrucciones** (5 s): se pueden saltar con ENTER.
3. **Calibración** (≈ 15 s): subir los brazos por los lados lo máximo posible y explicar que se mide el ángulo de cada hombro (se ven los grados en pantalla).
4. **Juego** (≈ 60 s). Comentar mientras se juega:
   - "Si subo los brazos, el trineo sube; si los bajo, baja."
   - La **barra de la izquierda**: altura de los brazos respecto a *mi* máximo. La raya amarilla es mi calibración.
   - La **flecha** que indica si hay que subir o bajar.
   - Las **estrellas** salen en lo más alto para animar a estirar un poco más del máximo.
   - Apartarse un momento de la cámara para enseñar que **se pausa** y no se pierden regalos.
5. **Resultados** (≈ 20 s): regalos, altura máxima (% de la calibración), **grados de cada hombro antes y durante el juego** y la **gráfica de evolución por sesiones**.

---

## 6. Demo: modo mano (6:45 – 9:00)

**Se ve:** igual que antes. **Juega B, habla B.**

1. **Menú → Mano → Elegir canción** (10 s): las 5 canciones (4 navideñas y el Himno de la alegría, todas de dominio público), elegida con el dedo.
2. **Calibración guiada** (≈ 30 s, se puede acelerar en edición): mano abierta y pinza con cada dedo. Explicar que es **lenta a propósito** para personas mayores (preparar → medir → "¡Muy bien!") y que, si no llega a cerrar la pinza, se mide su mejor intento.
3. **Juego** (≈ 60 s). Comentar:
   - Las notas caen **al ritmo de la música** por 4 carriles, como un piano: graves al índice y agudas al meñique.
   - La **mano guía** de la izquierda es mi mano redibujada en grande, con el dedo que toca iluminado y su nombre.
   - **Notas largas** ("MANTÉN"): hay que mantener la pinza, un ejercicio isométrico de fuerza.
   - Las notas demasiado seguidas las toca el ordenador, así el paciente solo hace las que puede.
   - La velocidad (arriba, en %) se adapta a cómo voy.
4. **Resultados** (≈ 20 s): precisión **por dedo**, el **dedo a trabajar más**, el desfase con el ritmo, las notas largas aguantadas y la gráfica de evolución.

---

## 7. Conclusiones (9:00 – 9:45)

**Se ve:** el menú o una diapositiva final.

**Se dice:**
- **Qué aporta:** rehabilitación en casa **sin hardware especial**, motivadora y adaptada a cada paciente, que además **registra su progreso** (los CSV se pueden abrir en Excel y compartir con el terapeuta).
- **Limitaciones:**
  - depende de la luz y de colocarse a la distancia adecuada de la cámara;
  - la detección 2D no ve bien los movimientos hacia la cámara;
  - **no está validado clínicamente**: es un prototipo.
- **Mejoras futuras:** más ejercicios (codo, muñeca), un modo terapeuta para fijar objetivos, enviar los informes al terapeuta y probarlo con pacientes reales.

**Cierre:**
> Gracias por vernos. El código y las instrucciones de instalación están en el README.

---

## Consejos de grabación

- Grabad cada parte por separado y montadlas después: es más fácil repetir solo lo que sale mal.
- En la demo, **hablad mientras jugáis** y no os quedéis callados más de 5 segundos.
- Si una parte se alarga, acelerad en edición la calibración o la intro (×2) con un texto tipo "acelerado ×2".
- Comprobad el volumen: la música no debe tapar vuestra voz. Se puede bajar con `MUSIC_VOLUME` en `config.py`, o quitarla con la tecla **M**.
