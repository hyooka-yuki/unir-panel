# unir panel

Une las capturas de un paneo de anime (cuando la cámara recorre una imagen que no cabe en pantalla) en una sola imagen. Funciona con paneos verticales, horizontales y diagonales, con cualquier cantidad de capturas, y aguanta lo que suele romper a los programas de panorámicas: bocas que se mueven, pelo, destellos que parpadean y fondos con parallax.

**Versión web, sin instalar nada:** [hyooka.pages.dev/panel](https://hyooka.pages.dev/panel). Corre este mismo script en el navegador (Pyodide + OpenCV) y las capturas no salen de tu equipo.

*English below.*

## Cómo sacar las capturas

1. Pausa el episodio al empezar el paneo y avanza de a poco mientras la cámara se mueve, sacando una captura cada tanto.
2. Que cada captura comparta al menos un tercio de pantalla con la anterior.
3. Sin recortar ni cambiar el tamaño: todas tienen que medir lo mismo.

El orden es por nombre de archivo. Las capturas de casi cualquier reproductor llevan la hora en el nombre, así que quedan en orden solas.

## Uso

Necesita Python 3.9 o más nuevo.

```sh
git clone https://github.com/hyooka-yuki/unir-panel.git
cd unir-panel
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python unir_panel.py captura1.png captura2.png captura3.png
.venv/bin/python unir_panel.py carpeta-con-capturas/
```

Opciones:

| Opción | Qué hace |
|---|---|
| `--difuminado PX` | Ancho de la transición en el corte (160 por defecto). Más ancho esconde mejor el corte; más angosto evita fantasmas si hay mucha animación. |
| `--brillo` | Iguala el brillo de cada captura con la anterior. Apagado por defecto: con personajes que se mueven puede quemar la imagen. |
| `--salida archivo.png` | Dónde guardar el resultado. |

Sin `--salida`, el panel queda junto a las capturas con el nombre de la última más 1 ms (`…-18h27m01s959` → `…-18h27m01s960`), así queda ordenado justo después de ellas. Si los nombres no llevan la hora, se llama `unida-<nombre>.png`.

Al pasar una carpeta, se ignoran las imágenes de otro tamaño (por ejemplo, un panel ya unido).

### Acción rápida en macOS

Para usarlo con clic derecho en Finder (*Acciones rápidas → Unir panel*):

1. Abre **Automator** → **Nuevo documento** → **Acción rápida**.
2. Arriba: «El flujo de trabajo recibe» **archivos o carpetas** en **Finder**.
3. Agrega **Ejecutar script de shell**, con shell `/bin/zsh` y «Pasar datos de entrada» **como argumentos**:
   ```sh
   "$HOME/ruta/a/unir-panel/unir_panel.sh" "$@"
   ```
4. Guárdala como «Unir panel».

`unir_panel.sh` avisa con notificaciones, abre el resultado en Vista Previa y deja el detalle en `ultimo-panel.log`.

## Cómo decide

- **Movimiento de cámara:** busca puntos en común entre cada par de capturas (SIFT) y se queda con los que se mueven igual. Lo animado se descarta solo.
- **Prioridad al personaje:** si hay varios movimientos (fondo con parallax), gana el que mejor alinea el lineart.
- **Corte:** pasa por donde las dos capturas se parecen más, así esquiva caras que cambian de expresión.
- **Difuminado:** la mezcla se calcula por distancias, así no quedan líneas en el corte ni en las esquinas donde se cruzan dos bordes.
- En los paneos diagonales, las esquinas que la cámara no cubre quedan **transparentes**.

## Límites

- Solo desplazamiento: no maneja zoom ni rotación de cámara.
- Puede quedar algún destello semitransparente en el fondo, si parpadea entre capturas.
- Si dos capturas no encajan (no son del mismo paneo o se solapan muy poco), avisa y no genera nada.

---

## English

Stitches the screenshots of an anime camera pan into a single image: vertical, horizontal or diagonal, any number of frames. It handles what usually breaks panorama tools: moving mouths, hair, flickering sparkles and parallax backgrounds.

**Web version, nothing to install:** [hyooka.pages.dev/panel](https://hyooka.pages.dev/panel) (Spanish UI). It runs this same script in your browser with Pyodide + OpenCV; your screenshots never leave your device.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python unir_panel.py frame1.png frame2.png frame3.png   # or a folder
```

- Take screenshots along the pan, each one overlapping the previous by at least a third of the screen, all the same size.
- Frames are ordered by file name (screenshot names usually include the time).
- `--difuminado PX` blend width (default 160) · `--brillo` match brightness between frames (off by default) · `--salida file.png` output path.
- How it works: SIFT matches between consecutive frames, grouped by motion so animated parts are ignored; when there is parallax, the motion that best aligns the line art wins; the seam follows the area where both frames are most alike, blended by distance. Uncovered corners in diagonal pans are left transparent.
- Translation only (no camera zoom or rotation).

## Licencia

[MIT](LICENSE). Hecho por [hyōka](https://www.instagram.com/hyooka.yuki/) · [hyooka.pages.dev](https://hyooka.pages.dev)
