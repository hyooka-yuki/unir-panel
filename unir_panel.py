#!/usr/bin/env python3
"""Unir panel: une capturas de un paneo de anime (vertical, horizontal o diagonal) en una sola imagen.

uso: unir_panel.py [--difuminado PX] [--brillo] [--salida archivo.png] capturas...  (o una carpeta)
Las capturas se ordenan por nombre (los nombres de captura llevan la hora, así que queda en orden temporal).
Deja la imagen junto a la primera captura con el nombre de la última + 1 ms
(screenshot-…-18h27m01s959 → …-18h27m01s960), así queda en orden con las capturas. Si el nombre no
trae la hora, usa `unida-<nombre>.png`. PNG con transparencia
en las esquinas que la cámara no cubre (paneos diagonales).
"""
import sys, os, re, argparse, cv2, numpy as np

EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ap = argparse.ArgumentParser()
ap.add_argument("rutas", nargs="+")
ap.add_argument("--difuminado", type=int, default=160, help="ancho del difuminado en px (def 160)")
ap.add_argument("--salida")
ap.add_argument("--brillo", action="store_true",
                help="iguala el brillo de cada captura con la anterior (apagado por defecto: el difuminado suele bastar)")
args = ap.parse_args()

paths = []
for r in args.rutas:
    if os.path.isdir(r):
        paths += [os.path.join(r, f) for f in os.listdir(r)
                  if os.path.splitext(f)[1].lower() in EXT and not f.startswith(".")]
    elif os.path.splitext(r)[1].lower() in EXT:
        paths.append(r)
paths = sorted(set(paths), key=lambda p: os.path.basename(p))
if len(paths) < 2: sys.exit("Error: hacen falta al menos 2 capturas.")

TS = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})h(\d{2})m(\d{2})s(\d{3})")

def nombre_salida():
    if args.salida: return args.salida
    from datetime import datetime, timedelta
    carpeta = os.path.dirname(os.path.abspath(paths[0]))
    ultimo = os.path.splitext(os.path.basename(paths[-1]))[0]
    m = TS.search(ultimo)
    if m:  # mismo estilo de nombre que las capturas, 1 ms después de la última
        t = datetime(*map(int, m.groups()[:6]), int(m.group(7)) * 1000)
        while True:
            t += timedelta(milliseconds=1)
            nuevo = t.strftime("%Y-%m-%d-%Hh%Mm%Ss") + f"{t.microsecond // 1000:03d}"
            out = os.path.join(carpeta, ultimo[:m.start()] + nuevo + ultimo[m.end():] + ".png")
            if not os.path.exists(out): return out
    base = "unida-" + os.path.splitext(os.path.basename(paths[0]))[0]
    out = os.path.join(carpeta, base + ".png"); k = 2
    while os.path.exists(out):
        out = os.path.join(carpeta, f"{base} {k}.png"); k += 1
    return out

FEATHER = args.difuminado
imgs = [cv2.imread(p, cv2.IMREAD_COLOR) for p in paths]
for p, im in zip(paths, imgs):
    if im is None: sys.exit(f"Error: no se pudo leer {os.path.basename(p)} (¿está descargada de iCloud?)")
desde_carpeta = any(os.path.isdir(r) for r in args.rutas)
if desde_carpeta:
    from collections import Counter
    tam = Counter(im.shape[:2] for im in imgs).most_common(1)[0][0]
    fuera = [os.path.basename(p) for p, im in zip(paths, imgs) if im.shape[:2] != tam]
    if fuera: print("ignoradas (otro tamaño, ¿panel ya unido?): " + ", ".join(fuera))
    paths, imgs = zip(*[(p, im) for p, im in zip(paths, imgs) if im.shape[:2] == tam])
    paths, imgs = list(paths), list(imgs)
    if len(paths) < 2: sys.exit("Error: hacen falta al menos 2 capturas.")
H, W = imgs[0].shape[:2]
if any(im.shape[:2] != (H, W) for im in imgs): sys.exit("Error: las capturas no tienen todas el mismo tamaño.")
print(f"{len(paths)} capturas: " + ", ".join(os.path.basename(p) for p in paths))

sift = cv2.SIFT_create(nfeatures=5000)
bf = cv2.BFMatcher(cv2.NORM_L2)

def lineart(g):
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, np.ones((7, 7), np.uint8))
    return (bh > 30) & (g < 140)

def lineart_score(ga, gb, d):
    """fracción del lineart de b que coincide con a al aplicar el desplazamiento d."""
    dx, dy = int(d[0]), int(d[1]); h, w = ga.shape
    ax0, ay0 = max(dx, 0), max(dy, 0); bx0, by0 = max(-dx, 0), max(-dy, 0)
    ww, hh = w - abs(dx), h - abs(dy)
    if ww < 50 or hh < 50: return 0.0
    A = ga[ay0:ay0+hh, ax0:ax0+ww].astype(int); B = gb[by0:by0+hh, bx0:bx0+ww].astype(int)
    m = lineart(gb[by0:by0+hh, bx0:bx0+ww])
    return float((np.abs(A - B)[m] < 30).mean()) if m.sum() > 200 else 0.0

def shift(a, b):
    """desplazamiento (dx,dy) de b respecto de a: un punto en a(x,y) está en b(x-dx,y-dy)."""
    ga, gb = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in (a, b))
    ka, da = sift.detectAndCompute(ga, None); kb, db = sift.detectAndCompute(gb, None)
    good = []
    if da is not None and db is not None and len(ka) > 2 and len(kb) > 2:
        for m in bf.knnMatch(db, da, k=2):
            if len(m) == 2 and m[0].distance < 0.75 * m[1].distance: good.append(m[0])
    if len(good) >= 8:
        v = np.array([np.subtract(ka[m.trainIdx].pt, kb[m.queryIdx].pt) for m in good])
        # agrupa los movimientos (cámara/personaje, fondo con parallax, ruido) con RANSAC repetido
        rem = np.ones(len(v), bool); cands = []
        for _ in range(3):
            best = None
            for c in v[rem][:400]:
                inl = rem & (np.linalg.norm(v - c, axis=1) < 2.5)
                if best is None or inl.sum() > best.sum(): best = inl
            if best is None or best.sum() < 8: break
            cands.append((np.median(v[best], axis=0), int(best.sum()))); rem &= ~best
        # prioridad al personaje: gana el movimiento que mejor alinea el lineart (trazos oscuros finos)
        if not cands: return np.array([0, 0]), 0, len(v)
        top = cands[0][1]
        cands = [c for c in cands if c[1] >= 0.2 * top]
        if len(cands) > 1:
            sc = [lineart_score(ga, gb, np.round(c[0]).astype(int)) for c in cands]
            print("   candidatos:", [(np.round(c[0]).astype(int).tolist(), c[1], round(x, 3)) for c, x in zip(cands, sc)])
            k = int(np.argmax(sc))
        else: k = 0
        d = cands[k][0]; n, tot = cands[k][1], len(v)
    else:  # pocas texturas: correlación de fase
        (d0, d1), r = cv2.phaseCorrelate(np.float32(gb), np.float32(ga)); d = np.array([d0, d1])
        n, tot = (8 if r > 0.1 else 0), 0  # 8 = "confiable" para el chequeo de abajo
    return np.round(d).astype(int), n, tot

pos = [np.array([0, 0])]
for i in range(1, len(imgs)):
    d, n, tot = shift(imgs[i-1], imgs[i])
    if n < 8 or abs(d[0]) >= W * 0.9 or abs(d[1]) >= H * 0.9:
        sys.exit(f"Error: no encontré cómo encajan {os.path.basename(paths[i-1])} y {os.path.basename(paths[i])}. "
                 "¿Son del mismo paneo y se solapan bastante?")
    pos.append(pos[-1] + d)
    print(f"{i}->{i+1}: dx {d[0]:+d} dy {d[1]:+d}  ({n}/{tot} puntos coinciden)")
pos = np.array(pos); pos -= pos.min(0)
CW, CH = int(pos[:, 0].max() + W), int(pos[:, 1].max() + H)
canvas = np.zeros((CH, CW, 3), np.float32)
valid = np.zeros((CH, CW), bool)

def dp_seam(cost):
    """camino de costo mínimo de izquierda a derecha (una fila por columna, salto ±1)."""
    h, w = cost.shape; acc = cost.copy(); back = np.zeros((h, w), np.int8)
    for x in range(1, w):
        prev = acc[:, x-1]
        up = np.r_[np.inf, prev[:-1]]; dn = np.r_[prev[1:], np.inf]
        st = np.stack([up, prev, dn]); k = st.argmin(0)
        acc[:, x] += st[k, np.arange(h)]; back[:, x] = k - 1
    path = np.zeros(w, int); path[-1] = acc[:, -1].argmin()
    for x in range(w-1, 0, -1): path[x-1] = path[x] + back[path[x], x]
    return path

for i, img in enumerate(imgs):
    x, y = pos[i]; R = (slice(y, y+H), slice(x, x+W))
    cur = img.astype(np.float32); cov = valid[R]
    if not cov.any():
        canvas[R] = cur; valid[R] = True; continue
    prev = canvas[R]
    gain = np.ones(3, np.float32)
    if args.brillo:
        gain = np.median(prev[cov] + 1, 0) / np.median(cur[cov] + 1, 0)
        cur = np.clip(cur * gain, 0, 255)
    d = pos[i] - pos[i-1]
    vertical = abs(d[1]) >= abs(d[0])
    # costo: diferencia entre frames, ensanchada al ancho del pincel para que el difuminado no toque lo animado
    diff = np.abs(prev - cur).mean(2)
    diff = cv2.blur(cv2.dilate(diff, np.ones((5, 5))), (FEATHER // 2 | 1, FEATHER // 2 | 1))
    cost = np.where(cov, diff, 1e3)
    # lejos del borde del frame, para que el difuminado quepa
    edge = np.zeros_like(cov); m = FEATHER // 2
    edge[m:-m, m:-m] = True; cost[~edge] += 1e3
    c = cost if vertical else cost.T
    path = dp_seam(c)
    idx = np.arange(c.shape[0])[:, None]
    sgn = d[1] if vertical else d[0]
    hard = (idx > path[None, :]) if sgn > 0 else (idx <= path[None, :])
    hard = hard if vertical else hard.T
    # Mezcla por distancias: se marcan las zonas que deben ser 100 % nuevo y 100 % viejo, dejando una
    # franja de FEATHER px alrededor del corte y de cada borde (horizontal o vertical). En la franja,
    # alpha = d_viejo / (d_viejo + d_nuevo): continua siempre, también en esquinas donde se cruzan bordes.
    F = FEATHER; dt = lambda m: cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)
    inR = np.zeros((CH, CW), bool); inR[R] = True
    viejo_fuera = valid & ~inR                                   # imagen anterior fuera del frame nuevo
    d_vf = dt(~viejo_fuera)[R] if viejo_fuera.any() else np.full((H, W), 1e9, np.float32)
    d_vacio = dt(cov)                                            # distancia a la zona solo-nueva del frame
    d_corte_n, d_corte_v = dt(hard), dt(~hard)                   # distancia al corte desde cada lado
    req_n = ~cov | (cov & hard & (d_corte_n > F / 2) & (d_vf > F))
    req_v = cov & ~hard & (d_corte_v > F / 2) & (d_vacio > F)
    RV = viejo_fuera.copy(); RV[R] |= req_v
    RN = np.zeros((CH, CW), bool); RN[R] = req_n
    if RV.any():
        dV, dN = dt(~RV)[R], dt(~RN)[R]
        t = dV / (dV + dN + 1e-6)
        a = t * t * (3 - 2 * t)                                  # smoothstep: caída de pincel suave
    else:
        a = np.ones((H, W), np.float32)
    a[~cov] = 1.0
    a = a[..., None]
    canvas[R] = cur * a + prev * (1 - a)
    valid[R] = True
    print(f"frame {i+1}: " + (f"ganancia {np.round(gain, 3)}  " if args.brillo else "") + f"costo medio del corte {c[path, np.arange(len(path))].mean():.2f}")

out = nombre_salida()
rgba = np.dstack([np.clip(canvas.round(), 0, 255).astype(np.uint8), (valid * 255).astype(np.uint8)])
cv2.imwrite(out, rgba)
print(f"tamaño {CW}x{CH}" + ("" if valid.all() else "  (las esquinas sin imagen quedan transparentes)"))
print(f"Listo: {len(paths)} capturas → {os.path.basename(out)} ({CW}×{CH})")
print(f"Salida: {out}")
