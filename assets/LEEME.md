# Imágenes del juego

Deja aquí imágenes **PNG** con el nombre exacto de la tabla y el juego las usará automáticamente al arrancar. No hay que tocar código.

Todas son **opcionales**: si falta alguna, el juego la dibuja por código (por eso funciona aunque esta carpeta esté vacía). Puedes poner solo las que quieras.

Los prompts para generarlas con IA, todas con el mismo estilo, están en [PROMPTS.md](PROMPTS.md).

**Recomendaciones:**
- Fondo **transparente** (PNG con canal alfa) en todo lo que no sea un fondo de pantalla. Si la imagen no tiene transparencia pero su fondo es de **un color liso** (por ejemplo magenta #FF00FF), el juego lo quita solo.
- La imagen se escala sola. Los tamaños son orientativos: mejor más grande que más pequeña.
- Usa imágenes propias o con licencia libre (por ejemplo CC0) y cítalas en el README del proyecto.

## Trineo volador (modo hombro)

| Archivo | Qué es | Tamaño orientativo | Notas |
|---|---|---|---|
| `trineo.png` | El trineo (con Papá Noel y/o renos si quieres) | 600 x 300 | **Mirando a la derecha.** Se inclina solo al subir y bajar. También sale en el botón del menú. |
| `regalo_1.png`, `regalo_2.png`, `regalo_3.png` | Tres regalos distintos | 256 x 256 | Cuadrados. Salen al azar. |
| `estrella.png` | Estrella dorada (premio especial, arriba del todo) | 256 x 256 | Cuadrada. |
| `fondo_cielo.png` | Cielo de noche | 1280 x 720 | Sin transparencia. Sustituye al degradado, la luna y las estrellas. |
| `colinas.png` | Colinas nevadas de primer plano | 1280 x 300 | Transparente por arriba. **Tiene que repetirse sin cortes** (el borde derecho debe empalmar con el izquierdo), porque se desplaza en bucle. |

## Menús

| Archivo | Qué es | Tamaño orientativo | Notas |
|---|---|---|---|
| `logo.png` | Logo "Rehab Arcade" | 800 x 200 | Sustituye al título en texto. |
| `fondo_menu.png` | Fondo de los menús | 1280 x 720 | Si no está, se usa el paisaje nevado animado. |
| `icono_hombro.png` | Icono del botón Hombro | 256 x 256 | Si no está, se usa `trineo.png`. |
| `icono_mano.png` | Icono del botón Mano | 256 x 256 | |
| `icono_jingle.png` | Icono de *Jingle Bells* | 256 x 256 | |
| `icono_nochedepaz.png` | Icono de *Noche de paz* | 256 x 256 | |
| `icono_wewish.png` | Icono de *We Wish You a Merry Christmas* | 256 x 256 | |
| `icono_deck.png` | Icono de *Deck the Halls* | 256 x 256 | |
| `icono_himno.png` | Icono del *Himno de la alegría* | 256 x 256 | |

## Piano de dedos (modo mano)

| Archivo | Qué es | Tamaño orientativo | Notas |
|---|---|---|---|
| `nota.png` | Una nota que cae | 128 x 64 | **En blanco o gris**: el juego la tiñe del color de cada dedo (rojo, amarillo, verde, azul). Se estira a lo alto según lo que dure la nota. |
| `tecla.png` | Una tecla de piano | 130 x 160 | **En blanco o gris** (tipo marfil). Al pulsarla se tiñe del color del dedo. |
| `fondo_piano.png` | Fondo del panel de las notas | 560 x 640 | Puede ser semitransparente para que se vea la cámara detrás. |
