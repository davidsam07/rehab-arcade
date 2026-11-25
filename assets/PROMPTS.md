# Prompts para generar las imágenes

Prompts para generar con IA (ChatGPT, Gemini, Midjourney, Ideogram, Leonardo...) todas las imágenes de [LEEME.md](LEEME.md) con **el mismo estilo**: el del juego, una noche de Navidad acogedora en estilo vectorial plano.

## Cómo conseguir que todas salgan con el mismo estilo

1. **Genera primero el trineo** (`trineo.png`). Es la imagen principal y marca el estilo.
2. Para todas las demás, **adjunta el trineo como imagen de referencia** y añade al prompt: *"Match the exact art style, outline thickness, shading and color palette of the attached reference image."* Si es posible, genéralas todas en la misma conversación.
3. Los prompts ya llevan el bloque de estilo común (**ESTILO**). No lo quites, aunque parezca repetido: es lo que mantiene la coherencia.
4. **Fondo:** los objetos se piden sobre **fondo magenta liso (#FF00FF)**. No hace falta recortarlos: el juego quita solo el fondo si es un color liso. Si tu generador permite PNG transparente, mejor aún.
5. Guarda cada imagen como **PNG** con el nombre exacto en la carpeta `assets/` y reinicia el juego.

**Bloque de estilo común (ya incluido en cada prompt):**

> 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, soft warm glow highlights, high quality, crisp edges, no text, no watermark

---

## Trineo volador

### `trineo.png`: trineo (hazlo primero)
Proporción 2:1, mirando a la derecha.
```
A red wooden Christmas sleigh with golden curled runners, carrying a big brown sack full of colorful wrapped presents, pulled by one friendly brown reindeer with small antlers galloping in front, side view facing right, flying pose, a few golden sparkles behind. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, soft warm glow highlights, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF), no shadow on the background. Aspect ratio 2:1.
```

### `regalo_1.png`, `regalo_2.png`, `regalo_3.png`: tres regalos
Cuadrados. Genera el mismo prompt tres veces cambiando los colores marcados entre [corchetes].
```
A single cute wrapped Christmas present box seen from the front with a slight top view, [cranberry red] wrapping paper with a small subtle pattern, [shiny gold] ribbon cross and a big fluffy bow on top, small highlight on the upper left. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, soft warm glow highlights, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF), no shadow on the background. Square 1:1.
```
- `regalo_2`: *[pine green]* con cinta *[cranberry red]*.
- `regalo_3`: *[royal blue]* con cinta *[snowy white]*.

### `estrella.png`: estrella dorada (premio especial)
Cuadrada.
```
A single shining five-pointed golden star with a soft rounded shape, a lighter gold inner star, small sparkle twinkles around it and a gentle warm glow, magical Christmas reward collectible. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, soft warm glow highlights, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF), no shadow on the background. Square 1:1.
```

### `fondo_cielo.png`: cielo de noche
Proporción 16:9, sin magenta: es un fondo completo.
```
Night winter sky background for a side-scrolling game, deep navy blue at the top fading to soft purple and mauve near the horizon, a big glowing full moon in the upper right, many small twinkling stars, a few soft wispy clouds, calm and magical atmosphere, empty lower third with no ground or objects (it will be covered by hills). 2D casual game background, flat vector illustration with soft gradients, cozy Christmas night theme, color palette of deep navy blue, warm gold, soft purple and snowy white, high quality, no text, no watermark. Aspect ratio 16:9.
```

### `colinas.png`: colinas nevadas de primer plano
Muy panorámica (unos 4:1). **Tiene que empalmar el borde izquierdo con el derecho**, porque se repite en bucle.
```
Seamless horizontally tileable strip of snowy rolling hills for a side-scrolling game foreground, soft white snow with light blue shading, a few small dark green pine trees with snow on their branches, two small cozy wooden cottages with glowing warm yellow windows and smoking chimneys, the left and right edges must match perfectly so it tiles seamlessly, only the hills in the lower part and everything above the hills is empty. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, high quality, no text, no watermark. Plain solid flat magenta background (#FF00FF) above the hills. Aspect ratio 4:1.
```

---

## Menús

### `logo.png`: logo del juego
Proporción 4:1. Aquí sí lleva texto.
```
Game logo with the text "Rehab Arcade" in big bold rounded friendly letters, warm gold letters with a white highlight and a dark navy outline, a little snow cap on top of some letters, a small holly leaf with red berries and a few golden sparkles as decoration, festive and cheerful video game title. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, clean dark navy outlines of medium thickness, high quality, crisp edges, no watermark. The text must read exactly "Rehab Arcade". Centered with empty margin, plain solid flat magenta background (#FF00FF). Aspect ratio 4:1.
```

### `fondo_menu.png`: fondo de los menús
Proporción 16:9, sin magenta. Opcional: si no lo pones, se usa el paisaje animado.
```
Cozy Christmas night landscape background for a game main menu, snowy hills with pine trees and small cottages with glowing windows at the bottom, big full moon and starry deep navy sky, gentle falling snow, a large calm empty area in the center for menu buttons, magical and peaceful. 2D casual game background, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, high quality, no text, no watermark. Aspect ratio 16:9.
```

### `icono_hombro.png`: botón del modo hombro
Cuadrado. Opcional: si no lo pones, se usa el trineo.
```
Game menu icon: a happy elderly person seen from the front raising both arms to the sides like wings, with a small red Christmas sleigh flying above them and golden sparkles, representing shoulder exercise. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF). Square 1:1.
```

### `icono_mano.png`: botón del modo mano
Cuadrado.
```
Game menu icon: a friendly hand doing a pinch gesture (thumb touching the index fingertip) above a few glossy piano keys, with small colorful music notes floating around (red, yellow, green, blue), representing finger exercise. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF). Square 1:1.
```

### Iconos de las canciones
Todos cuadrados. Usa este prompt cambiando el texto entre [corchetes] por el de cada canción:
```
Game menu icon: [OBJETO]. 2D casual game asset, flat vector illustration with soft gradients and subtle cel shading, cozy Christmas night theme, color palette of deep navy blue, warm gold, cranberry red, pine green and snowy white, rounded friendly shapes, clean dark navy outlines of medium thickness, soft warm glow highlights, high quality, crisp edges, no text, no watermark. Single object centered with generous empty margin around it, plain solid flat magenta background (#FF00FF). Square 1:1.
```

| Archivo | [OBJETO] |
|---|---|
| `icono_jingle.png` | `two shiny golden jingle bells tied together with a red ribbon bow and a sprig of holly` |
| `icono_nochedepaz.png` | `a calm glowing golden star above a small snowy village at night, peaceful and silent` |
| `icono_wewish.png` | `a small decorated Christmas tree with colorful baubles, a golden star on top and two presents under it` |
| `icono_deck.png` | `a festive holly garland with green leaves, red berries and a golden ribbon, with a big snowflake` |
| `icono_himno.png` | `a golden music note with a small laurel wreath and sparkles, classical and joyful` |

---

## Piano de dedos

**Importante:** `nota.png` y `tecla.png` tienen que ser **blancas o grises**, sin color: el juego las tiñe del color de cada dedo.

### `nota.png`: nota que cae
Proporción 2:1.
```
A single glossy rounded rectangle game tile for a rhythm game falling note, pure white and light grey only (no color at all, it will be tinted in code), soft vertical gradient from white at the top to light grey at the bottom, a thin bright glossy highlight line near the top edge, smooth rounded corners. 2D casual game asset, flat vector illustration with soft gradients, clean edges, high quality, no text, no watermark. Single object centered filling most of the image, plain solid flat magenta background (#FF00FF). Aspect ratio 2:1.
```

### `tecla.png`: tecla de piano
Proporción 4:5, vertical.
```
A single ivory piano key seen from the front for a rhythm game, white and very light warm grey only (no color, it will be tinted in code), soft rounded bottom corners, gentle glossy highlight and a subtle shadow at the bottom, clean and simple. 2D casual game asset, flat vector illustration with soft gradients, clean dark navy outline of medium thickness, high quality, no text, no watermark. Single object centered filling most of the image, plain solid flat magenta background (#FF00FF). Aspect ratio 4:5.
```

### `fondo_piano.png`: fondo del panel de notas
Proporción 7:8, vertical, sin magenta.
```
Vertical background panel for a rhythm game note highway, dark navy blue with a very subtle starry pattern and soft frosty snowflake decorations in the corners, a thin warm gold ornamental border with rounded corners, mostly dark and calm in the middle so colorful notes stand out, four faint vertical lanes. 2D casual game UI, flat vector illustration with soft gradients, cozy Christmas night theme, color palette of deep navy blue, warm gold and snowy white, high quality, no text, no watermark. Aspect ratio 7:8.
```
