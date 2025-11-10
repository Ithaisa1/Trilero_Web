# Versión comentada en detalle del juego del Trilero
# --------------------------------------------------
# Esta copia explica el propósito de casi cada bloque y muchas líneas.
# El archivo original (main.py) queda como versión más ligera.
#
# Índice rápido
# 1) Inicialización y recursos (Pygame, ventana, imágenes, transparencia)
# 2) Layout y posiciones (cálculo de vasos y bola)
# 3) Máquina de estados y parámetros (estados, mezcla, bajada)
# 4) Dibujo por frame (función dibujar)
# 5) Lógica del juego (bucle principal, eventos y estados)
# 6) Sonidos y modo trampa
# 7) Cómo ajustar separación, tiempos y dificultad

import pygame  # Motor de juegos 2D
import random  # Aleatoriedad para elegir vaso de la bola y swaps
import os      # Utilidades del sistema (no se usan directamente aquí)
import sys     # Acceso a argv si fuera necesario
from pathlib import Path  # Manejo seguro de rutas
import math    # Funciones matemáticas (interpolación, seno para rebote)

# Ruta base del proyecto
# Escritorio: carpeta del archivo actual
# Web (pygbag/emscripten): usar ruta relativa para que 'assets/' se sirva bien
IS_WEB = (sys.platform == "emscripten") or ("PYGBAG" in os.environ)
BASE_DIR = Path(".") if IS_WEB else Path(__file__).resolve().parent

# Inicialización de Pygame y ventana
pygame.init()
pygame.display.set_caption("Juego del Trilero")

# Tamaño de ventana y superficies principales
ANCHO, ALTO = 800, 600
pantalla = pygame.display.set_mode((ANCHO, ALTO))
reloj = pygame.time.Clock()  # Control del tiempo entre frames

# Carga de imágenes con fallback (si faltan, se usa fondo sólido y placeholders)
fondo = None
vaso_img = None
bola_img = None
try:
    # Cargar y escalar fondo al tamaño de la ventana
    fondo = pygame.image.load(str(BASE_DIR / "assets" / "fondo.jpg")).convert()
    fondo = pygame.transform.scale(fondo, (ANCHO, ALTO))
except Exception:
    fondo = None  # Fondo sólido si falta imagen

try:
    # Vaso con canal alfa (png)
    vaso_img = pygame.image.load(str(BASE_DIR / "assets" / "vaso.png")).convert_alpha()
except Exception:
    vaso_img = None

try:
    # Bola con canal alfa (png)
    bola_img = pygame.image.load(str(BASE_DIR / "assets" / "bola.png")).convert_alpha()
except Exception:
    bola_img = None

# Utilidad: eliminar fondos "planos" de imágenes (colorkey con tolerancia)
def apply_transparency(surf: pygame.Surface, fallback_colors=((255, 255, 255), (0, 0, 0)), tol=15):
    # Asegurar canal alfa
    surf = surf.convert_alpha()
    # Color de la esquina superior izquierda como referencia
    try:
        corner = surf.get_at((0, 0))[:3]
    except Exception:
        corner = None
    w, h = surf.get_size()
    px = pygame.PixelArray(surf)

    # Marca como transparente los píxeles cercanos a un color de referencia
    def clear_color_near(ref):
        if ref is None:
            return
        r0, g0, b0 = ref
        for y in range(h):
            for x in range(w):
                r, g, b, a = surf.unmap_rgb(px[x, y])
                if abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol:
                    px[x, y] = (r, g, b, 0)  # alfa 0 (transparente)

    # Aplicar a esquina y colores comunes (blanco/negro)
    clear_color_near(corner)
    for col in fallback_colors:
        clear_color_near(col)
    del px
    return surf

# Redimensionar y aplicar transparencia a las imágenes del vaso y de la bola
if vaso_img is not None:
    vaso_img = pygame.transform.scale(vaso_img, (150, 150)).convert_alpha()
    vaso_img = apply_transparency(vaso_img)
if bola_img is not None:
    bola_img = pygame.transform.scale(bola_img, (40, 40)).convert_alpha()
    bola_img = apply_transparency(bola_img)

# Dimensiones del vaso para layout y colisiones
VASO_W, VASO_H = 150, 150

# Cálculo de posiciones centradas de los vasos para MENÚ (arriba) y JUEGO (centro)
# Incluye separación amplia entre vasos y márgenes respecto al botón y la bola

def posiciones_centradas():
    sep = 260  # separación horizontal entre vasos
    cx = ANCHO // 2
    # En MENÚ: los vasos quedan bastante por encima del botón (60px) y con margen extra
    y_top = ALTO - 120 - VASO_H - 120
    # En JUEGO: centro ligeramente por debajo del centro geométrico
    y_center = ALTO // 2 - VASO_H // 2 + 40
    xs = [cx - sep - VASO_W // 2, cx - VASO_W // 2, cx + sep - VASO_W // 2]
    top = [(xs[0], y_top), (xs[1], y_top), (xs[2], y_top)]
    mid = [(xs[0], y_center), (xs[1], y_center), (xs[2], y_center)]
    return top, mid

# Posiciones iniciales de vasos arriba y objetivo de juego
vasos_pos_inicial_top, _vasos_pos_juego_base = posiciones_centradas()
# Línea base donde se dibuja la bola en MENÚ (vasos bajarán hasta coincidir su base con esta altura)
BALL_MENU_Y = ALTO - 120 - 80
# Posiciones en juego: misma X y base del vaso alineada con BALL_MENU_Y
vasos_pos_juego = [(x, BALL_MENU_Y - VASO_H) for (x, _y) in _vasos_pos_juego_base]
# Inicialmente, vasos colocados en la posición de MENÚ (arriba)
vasos_pos_inicial = vasos_pos_inicial_top

# Representación de vasos con coordenadas float para interpolación suave
vasos = [{"x": float(x), "y": float(y)} for (x, y) in vasos_pos_inicial]

# Máquina de estados del juego
ESTADO_MENU = "MENU"
ESTADO_BAJAR = "BAJAR"
ESTADO_MOSTRAR = "MOSTRAR"       # (no se usa en este flujo, se salta)
ESTADO_MEZCLA = "MEZCLA"
ESTADO_ESPERA_CLIC = "ESPERA_CLIC"
ESTADO_REVELA = "REVELA"
ESTADO_FIN = "FIN"

estado = ESTADO_MENU
mostrar_ms = 1500  # reservado, si se quisiera mostrar la bola antes de mezclar
timer_ms = mostrar_ms

# Índice del vaso que contiene la bola al inicio de cada ronda
indice_bola = random.randint(0, 2)

# Parámetros y buffers de la mezcla animada (lista de swaps e interpolación)
swap_queue = []
swapping = False
swap_i1 = swap_i2 = None
swap_t = 0.0
swap_duracion = 380.0  # duración de cada intercambio en ms
swap_inicio_1 = (0.0, 0.0)
swap_inicio_2 = (0.0, 0.0)
swap_objetivo_1 = (0.0, 0.0)
swap_objetivo_2 = (0.0, 0.0)

# Animación de bajada desde MENÚ hasta JUEGO
bajar_t = 0.0
bajar_duracion = 600.0  # ms
bajar_inicio = [(float(x), float(y)) for (x, y) in vasos_pos_inicial_top]
bajar_objetivo = [(float(x), float(y)) for (x, y) in vasos_pos_juego]

# Fuentes para HUD y mensajes
font = pygame.font.SysFont(None, 36)
font_small = pygame.font.SysFont(None, 28)
mensaje = "Memoriza la posición de la bola"  # se gestiona por estado
score = 0
rounds = 0

# Dificultades (número de swaps y velocidad)
difficulties = {
    "Fácil": {"swaps": 8, "dur_ms": 420.0},
    "Media": {"swaps": 12, "dur_ms": 360.0},
    "Difícil": {"swaps": 18, "dur_ms": 300.0},
}
diff_names = list(difficulties.keys())
diff_index = 1  # Media por defecto

# Sonidos (si faltan, no se reproducen)
mix_snd = None
ok_snd = None
fail_snd = None
try:
    pygame.mixer.init()
    try:
        mix_snd = pygame.mixer.Sound(str(BASE_DIR / "assets" / "sounds" / "mix.wav"))
    except Exception:
        mix_snd = None
    try:
        ok_snd = pygame.mixer.Sound(str(BASE_DIR / "assets" / "sounds" / "success.wav"))
    except Exception:
        ok_snd = None
    try:
        fail_snd = pygame.mixer.Sound(str(BASE_DIR / "assets" / "sounds" / "fail.wav"))
    except Exception:
        fail_snd = None
except Exception:
    pass

# Modo trampa: muestra la bola también por encima durante mezcla (debug)
modo_trampa = False

# Rects cache de UI (botón y selector de dificultad)
_btn_rect_cache = pygame.Rect(0, 0, 0, 0)
_diff_left_rect = pygame.Rect(0, 0, 0, 0)
_diff_right_rect = pygame.Rect(0, 0, 0, 0)
_diff_val_rect = pygame.Rect(0, 0, 0, 0)

# Dibujo principal por frame
def dibujar():
    # Fondo
    if fondo is not None:
        pantalla.blit(fondo, (0, 0))
    else:
        pantalla.fill((20, 90, 20))

    # Dibuja vasos con o sin pequeño "salto" si llevan bola durante MEZCLA
    def draw_cups(with_lift=True):
        for i, v in enumerate(vasos):
            vx, vy = v["x"], v["y"]
            lift = 0.0
            if with_lift and estado == ESTADO_MEZCLA and swapping and (i == swap_i1 or i == swap_i2) and i == indice_bola:
                p = max(0.0, min(1.0, swap_t / swap_duracion))
                lift = -12.0 * math.sin(math.pi * p)  # salto suave
            draw_pos = (int(vx), int(vy + lift))
            if vaso_img is not None:
                pantalla.blit(vaso_img, draw_pos)
            else:
                pygame.draw.rect(pantalla, (180, 180, 180), pygame.Rect(draw_pos[0], draw_pos[1], VASO_W, VASO_H), border_radius=12)

    # Posición de la bola ligada al vaso que la contiene
    def compute_ball_pos():
        base_x = vasos[indice_bola]["x"]
        base_y = vasos[indice_bola]["y"]
        bx = int(base_x) + 55
        by = int(base_y) + 100
        # Si el vaso se está intercambiando, animar bola en sincronía con rebote sutil
        if estado == ESTADO_MEZCLA and swapping and (indice_bola == swap_i1 or indice_bola == swap_i2):
            if indice_bola == swap_i1:
                start = swap_inicio_1
                target = swap_objetivo_1
            else:
                start = swap_inicio_2
                target = swap_objetivo_2
            p = max(0.0, min(1.0, swap_t / swap_duracion))
            p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
            bx = int(start[0] + (target[0] - start[0]) * p_ease) + 55
            by = int(start[1] + (target[1] - start[1]) * p_ease) + 100
            lift_ball = -10.0 * math.sin(math.pi * p_ease)
            by = int(by + lift_ball)
        return bx, by

    # Dibujo por estado
    if estado == ESTADO_MEZCLA:
        # En mezcla la bola no se ve normalmente: solo vasos
        draw_cups(with_lift=True)
        # Modo trampa: dibujar la bola por ENCIMA de los vasos para depurar su posición real
        if modo_trampa:
            i = indice_bola
            if bola_img is not None:
                bw, bh = bola_img.get_size()
                bx = int(vasos[i]["x"]) + (VASO_W - bw) // 2
                by = int(vasos[i]["y"]) + (VASO_H - bh) // 2
                pantalla.blit(bola_img, (bx, by))
            else:
                r = 20
                bx = int(vasos[i]["x"]) + (VASO_W - 2 * r) // 2
                by = int(vasos[i]["y"]) + (VASO_H - 2 * r) // 2
                pygame.draw.circle(pantalla, (255, 200, 50), (bx + r, by + r), r)
    elif estado == ESTADO_BAJAR:
        # Bajada inicial: solo vasos
        draw_cups(with_lift=False)
    elif estado == ESTADO_MENU:
        # En menú: dibujar primero la bola detrás…
        target_x, _ = vasos_pos_inicial_top[indice_bola]
        if bola_img is not None:
            bw, bh = bola_img.get_size()
            bx = int(target_x + (VASO_W - bw) / 2)
            by = int(BALL_MENU_Y)
            pantalla.blit(bola_img, (bx, by))
        else:
            r = 20
            bx = int(target_x + (VASO_W - 2 * r) / 2)
            by = int(BALL_MENU_Y)
            pygame.draw.circle(pantalla, (255, 50, 50), (bx + r, by + r), r)
        # …y luego los vasos delante
        draw_cups(with_lift=False)
    else:
        # Mostrar/revelar: vasos y bola por encima
        draw_cups(with_lift=False)
        if estado in (ESTADO_MOSTRAR, ESTADO_REVELA):
            bx, by = compute_ball_pos()
            if bola_img is not None:
                pantalla.blit(bola_img, (bx, by))
            else:
                pygame.draw.circle(pantalla, (255, 50, 50), (bx + 20, by + 20), 20)

    # Mensaje en pantalla (posición varía un poco en menú)
    if mensaje:
        surf = font.render(mensaje, True, (255, 255, 255))
        msg_y = 180 if estado != ESTADO_MENU else 240
        rect = surf.get_rect(center=(ANCHO // 2, msg_y))
        pantalla.blit(surf, rect)

    # HUD: marcador arriba izquierda
    hud = font_small.render(f"Puntos: {score}  Ronda: {rounds}", True, (230, 230, 230))
    pantalla.blit(hud, (16, 16))

    # Dificultad arriba derecha (siempre visible; clic/teclas solo en MENÚ/FIN)
    diff_label = font_small.render("Dificultad:", True, (230, 230, 230))
    label_rect = diff_label.get_rect(topright=(ANCHO - 260, 10))  # desplazado a la izquierda para asegurar visibilidad
    pantalla.blit(diff_label, label_rect)
    # Flechas y valor a la derecha del label
    row_y = label_rect.centery - 12
    left_rect = pygame.Rect(label_rect.right + 8, row_y, 24, 24)
    diff_val_surf = font.render(diff_names[diff_index], True, (255, 255, 0))
    diff_val_rect = diff_val_surf.get_rect(midleft=(left_rect.right + 8, left_rect.centery))
    right_rect = pygame.Rect(diff_val_rect.right + 8, row_y, 24, 24)
    pygame.draw.polygon(pantalla, (230, 230, 230), [(left_rect.right, left_rect.top), (left_rect.left, left_rect.centery), (left_rect.right, left_rect.bottom)])
    pygame.draw.polygon(pantalla, (230, 230, 230), [(right_rect.left, right_rect.top), (right_rect.right, right_rect.centery), (right_rect.left, right_rect.bottom)])
    pantalla.blit(diff_val_surf, diff_val_rect)

    # Guardar rects del selector sólo si se puede interactuar (MENÚ/FIN)
    global _diff_left_rect, _diff_right_rect, _diff_val_rect
    if estado in (ESTADO_MENU, ESTADO_FIN):
        _diff_left_rect = left_rect
        _diff_right_rect = right_rect
        _diff_val_rect = diff_val_rect
    else:
        _diff_left_rect = pygame.Rect(0, 0, 0, 0)
        _diff_right_rect = pygame.Rect(0, 0, 0, 0)
        _diff_val_rect = pygame.Rect(0, 0, 0, 0)

    # Botón inferior (Comenzar/Reintentar)
    if estado in (ESTADO_MENU, ESTADO_FIN):
        btn_text = "Comenzar" if estado == ESTADO_MENU else "Reintentar"
        btn_surf = font.render(btn_text, True, (0, 0, 0))
        btn_rect = pygame.Rect(ANCHO // 2 - 100, ALTO - 120, 200, 60)
        pygame.draw.rect(pantalla, (240, 240, 240), btn_rect, border_radius=10)
        pygame.draw.rect(pantalla, (50, 50, 50), btn_rect, width=2, border_radius=10)
        pantalla.blit(btn_surf, btn_surf.get_rect(center=btn_rect.center))
        # Guardar rect para clics
        global _btn_rect_cache
        _btn_rect_cache = btn_rect

    # Presentar frame
    pygame.display.flip()

# Variables de control del bucle principal
seleccion = None
jugando = True
clock_fps = 60

# Bucle del juego
while jugando:
    dt = reloj.tick(clock_fps)  # milisegundos desde el frame anterior

    # Procesamiento de eventos
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            jugando = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r and estado == ESTADO_FIN:
                # Volver a MENÚ (reinicia posiciones arriba y bola visible)
                for i, (x, y) in enumerate(vasos_pos_inicial_top):
                    vasos[i]["x"], vasos[i]["y"] = float(x), float(y)
                indice_bola = random.randint(0, 2)
                estado = ESTADO_MENU
                seleccion = None
                mensaje = "Elige dificultad y pulsa Comenzar"
                swap_queue.clear()
                swapping = False
            if event.key == pygame.K_t:
                # Modo trampa de prueba
                modo_trampa = not modo_trampa
            # Cambiar dificultad por teclado (sólo en MENÚ/FIN)
            if estado in (ESTADO_MENU, ESTADO_FIN):
                if event.key == pygame.K_LEFT:
                    diff_index = (diff_index - 1) % len(diff_names)
                elif event.key == pygame.K_RIGHT:
                    diff_index = (diff_index + 1) % len(diff_names)

        # Clic de selección de vaso en el estado de espera
        if event.type == pygame.MOUSEBUTTONDOWN and estado == ESTADO_ESPERA_CLIC:
            x, y = event.pos
            for i, v in enumerate(vasos):
                rect = pygame.Rect(int(v["x"]), int(v["y"]), VASO_W, VASO_H)
                if rect.collidepoint(x, y):
                    seleccion = i
                    if i == indice_bola:
                        mensaje = "Has acertado! Pulsa R para jugar de nuevo"
                        score += 1
                        if ok_snd: ok_snd.play()
                    else:
                        mensaje = "Has fallado. Pulsa R para jugar de nuevo"
                        if fail_snd: fail_snd.play()
                    estado = ESTADO_REVELA
                    rounds += 1
                    break

        # Clic en botón y selector de dificultad en MENÚ/FIN
        if event.type == pygame.MOUSEBUTTONDOWN and estado in (ESTADO_MENU, ESTADO_FIN):
            x, y = event.pos
            btn_rect = _btn_rect_cache
            # Flechas o nombre de dificultad
            if _diff_left_rect.collidepoint(x, y) or (_diff_val_rect.collidepoint(x, y) and x < _diff_val_rect.centerx):
                diff_index = (diff_index - 1) % len(diff_names)
            elif _diff_right_rect.collidepoint(x, y) or (_diff_val_rect.collidepoint(x, y) and x >= _diff_val_rect.centerx):
                diff_index = (diff_index + 1) % len(diff_names)
            # Botón principal
            if btn_rect.collidepoint(x, y):
                if estado == ESTADO_MENU:
                    # Preparar bajada
                    for i, (px, py) in enumerate(vasos_pos_inicial_top):
                        vasos[i]["x"], vasos[i]["y"] = float(px), float(py)
                    estado = ESTADO_BAJAR
                    bajar_t = 0.0
                    seleccion = None
                    mensaje = ""
                    swap_queue.clear()
                    swapping = False
                else:
                    # Si está en FIN, volver al MENÚ
                    for i, (px, py) in enumerate(vasos_pos_inicial_top):
                        vasos[i]["x"], vasos[i]["y"] = float(px), float(py)
                    indice_bola = random.randint(0, 2)
                    estado = ESTADO_MENU
                    seleccion = None
                    mensaje = "Elige dificultad (←/→) y pulsa Comenzar"

    # Lógica por estado (máquina de estados)
    if estado == ESTADO_MENU:
        mensaje = "Elige dificultad y pulsa Comenzar"
        # Espera interacción

    elif estado == ESTADO_BAJAR:
        # Interpolar desde posición superior hasta posición de juego (alineada con la bola)
        bajar_t += dt
        p = max(0.0, min(1.0, bajar_t / bajar_duracion))
        p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
        for i in range(3):
            sx, sy = bajar_inicio[i]
            tx, ty = vasos_pos_juego[i]
            vasos[i]["x"] = sx + (tx - sx) * p_ease
            vasos[i]["y"] = sy + (ty - sy) * p_ease
        if bajar_t >= bajar_duracion:
            # Fijar posiciones exactas y configurar mezcla
            for i, (tx, ty) in enumerate(vasos_pos_juego):
                vasos[i]["x"], vasos[i]["y"] = tx, ty
            estado = ESTADO_MEZCLA
            mensaje = "Atento a la mezcla..."
            swap_queue = []
            cfg = difficulties[diff_names[diff_index]]
            num_swaps = cfg["swaps"]
            swap_duracion = cfg["dur_ms"]
            for _ in range(num_swaps):
                i1, i2 = random.sample(range(3), 2)
                swap_queue.append((i1, i2))
            swapping = False
            if mix_snd:
                mix_snd.play()

    elif estado == ESTADO_MOSTRAR:
        # (Reservado por si se quisiera mostrar la bola antes de mezclar)
        timer_ms -= dt
        if timer_ms <= 0:
            estado = ESTADO_MEZCLA
            mensaje = "Atento a la mezcla..."
            swap_queue = []
            cfg = difficulties[diff_names[diff_index]]
            num_swaps = cfg["swaps"]
            swap_duracion = cfg["dur_ms"]
            for _ in range(num_swaps):
                i1, i2 = random.sample(range(3), 2)
                swap_queue.append((i1, i2))
            swapping = False
        if mix_snd:
            mix_snd.play()

    elif estado == ESTADO_MEZCLA:
        # Ejecutar secuencia de swaps con interpolación (ease-in-out)
        if not swapping and swap_queue:
            swap_i1, swap_i2 = swap_queue.pop(0)
            swap_t = 0.0
            swap_inicio_1 = (vasos[swap_i1]["x"], vasos[swap_i1]["y"])
            swap_inicio_2 = (vasos[swap_i2]["x"], vasos[swap_i2]["y"])
            swap_objetivo_1 = swap_inicio_2
            swap_objetivo_2 = swap_inicio_1
            swapping = True
        elif swapping:
            swap_t += dt
            p = max(0.0, min(1.0, swap_t / swap_duracion))
            p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
            vasos[swap_i1]["x"] = swap_inicio_1[0] + (swap_objetivo_1[0] - swap_inicio_1[0]) * p_ease
            vasos[swap_i1]["y"] = swap_inicio_1[1] + (swap_objetivo_1[1] - swap_inicio_1[1]) * p_ease
            vasos[swap_i2]["x"] = swap_inicio_2[0] + (swap_objetivo_2[0] - swap_inicio_2[0]) * p_ease
            vasos[swap_i2]["y"] = swap_inicio_2[1] + (swap_objetivo_2[1] - swap_inicio_2[1]) * p_ease
            if swap_t >= swap_duracion:
                vasos[swap_i1]["x"], vasos[swap_i1]["y"] = swap_objetivo_1
                vasos[swap_i2]["x"], vasos[swap_i2]["y"] = swap_objetivo_2
                swapping = False
        else:
            # Fin de mezcla, esperar clic del jugador
            estado = ESTADO_ESPERA_CLIC
            mensaje = "Haz clic en un vaso"

    elif estado == ESTADO_REVELA:
        # Se revela la bola (dibujarla ocurre en dibujar() para este estado)
        estado = ESTADO_FIN

    # Dibujo del frame actual
    dibujar()

# Al salir del bucle
pygame.quit()
