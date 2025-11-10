import pygame
import random
import os
import sys
from pathlib import Path
import math
import asyncio
import traceback

# --- Ruta base del proyecto
# En escritorio: carpeta del archivo actual
# En web (pygbag/emscripten): usar ruta relativa para que 'assets/' se sirva correctamente
IS_WEB = (sys.platform == "emscripten") or ("PYGBAG" in os.environ)
BASE_DIR = Path(".") if IS_WEB else Path(__file__).resolve().parent
WEB_DEBUG = IS_WEB  # activar superposición y dibujos simplificados en navegador

# --- Inicialización ---
pygame.init()
pygame.display.set_caption("Juego del Trilero")

# --- Configuración de pantalla ---
# Resolución objetivo 640x480 con escala desde el diseño base 800x600
BASE_W, BASE_H = 800, 600
ANCHO, ALTO = 640, 480
SCALE = min(ANCHO / BASE_W, ALTO / BASE_H)
def S(v: float) -> int:
    return int(round(v * SCALE))

flags = pygame.SCALED if IS_WEB else 0
pantalla = pygame.display.set_mode((ANCHO, ALTO), flags)
reloj = pygame.time.Clock()

# --- Cargar imágenes (en web se dibujan formas para máxima compatibilidad) ---
fondo = None
vaso_img = None
bola_img = None
if not IS_WEB:
    try:
        fondo = pygame.image.load(str(BASE_DIR / "assets" / "fondo.jpg")).convert()
        fondo = pygame.transform.scale(fondo, (ANCHO, ALTO))
    except Exception:
        fondo = None
    try:
        vaso_img = pygame.image.load(str(BASE_DIR / "assets" / "vaso.png")).convert_alpha()
    except Exception:
        vaso_img = None
    try:
        bola_img = pygame.image.load(str(BASE_DIR / "assets" / "bola.png")).convert_alpha()
    except Exception:
        bola_img = None

# --- Utilidades de imagen ---
# Escalar las imágenes para que queden más uniformes y aplicar transparencia por colorkey con tolerancia
def apply_transparency(surf: pygame.Surface, fallback_colors=((255, 255, 255), (0, 0, 0)), tol=15):
    surf = surf.convert_alpha()
    try:
        corner = surf.get_at((0, 0))[:3]
    except Exception:
        corner = None
    w, h = surf.get_size()
    px = pygame.PixelArray(surf)
    # Helper: marcar transparente si color está cerca de 'ref'
    def clear_color_near(ref):
        if ref is None:
            return
        r0, g0, b0 = ref
        for y in range(h):
            for x in range(w):
                r, g, b, a = surf.unmap_rgb(px[x, y])
                if abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol:
                    px[x, y] = (r, g, b, 0)
    # Aplicar tolerancia a esquina y a fallback comunes
    clear_color_near(corner)
    for col in fallback_colors:
        clear_color_near(col)
    del px
    return surf

if not IS_WEB:
    if vaso_img is not None:
        vaso_img = pygame.transform.scale(vaso_img, (150, 150)).convert_alpha()
        vaso_img = apply_transparency(vaso_img)
    if bola_img is not None:
        bola_img = pygame.transform.scale(bola_img, (40, 40)).convert_alpha()
        bola_img = apply_transparency(bola_img)

# --- Posiciones y estado iniciales ---
VASO_W, VASO_H = S(150), S(150)

def posiciones_centradas():
    sep = S(260)  # separación proporcional
    cx = ANCHO // 2
    # En el menú, vasos por encima del botón (escala de 120 px)
    y_top = ALTO - S(120) - VASO_H - S(120)
    # Centro ligeramente más bajo
    y_center = ALTO // 2 - VASO_H // 2 + S(40)
    xs = [cx - sep - VASO_W // 2, cx - VASO_W // 2, cx + sep - VASO_W // 2]
    top = [(xs[0], y_top), (xs[1], y_top), (xs[2], y_top)]
    mid = [(xs[0], y_center), (xs[1], y_center), (xs[2], y_center)]
    return top, mid

# Posiciones: arriba (pre-juego) y juego (centradas)
vasos_pos_inicial_top, _vasos_pos_juego_base = posiciones_centradas()
# Línea base de la bola en el menú (los vasos bajarán hasta alinear su base con esta altura)
# Más separación con el botón: bola 80 px (escalado) por encima del botón
BALL_MENU_Y = ALTO - S(120) - S(80)
# Posiciones de juego: misma X que base, y alineada a BALL_MENU_Y (base del vaso coincide con la bola)
vasos_pos_juego = [(x, BALL_MENU_Y - VASO_H) for (x, _y) in _vasos_pos_juego_base]
vasos_pos_inicial = vasos_pos_inicial_top

# Representación de vasos como objetos con posiciones float para animación
vasos = [{"x": float(x), "y": float(y)} for (x, y) in vasos_pos_inicial]

# --- Estados del juego ---
ESTADO_MENU = "MENU"
ESTADO_BAJAR = "BAJAR"
ESTADO_MOSTRAR = "MOSTRAR"
ESTADO_MEZCLA = "MEZCLA"
ESTADO_ESPERA_CLIC = "ESPERA_CLIC"
ESTADO_REVELA = "REVELA"
ESTADO_FIN = "FIN"

estado = ESTADO_MENU
mostrar_ms = 1500  # ms mostrando la bola al inicio (no usada si saltamos MOSTRAR)
timer_ms = mostrar_ms

# Índice del vaso que contiene la bola
indice_bola = random.randint(0, 2)

# --- Parámetros y buffers de la mezcla animada ---
swap_queue = []  # lista de pares (i1, i2)
swapping = False
swap_i1 = swap_i2 = None
swap_t = 0.0
swap_duracion = 380.0  # ms por intercambio (se ajusta con dificultad)
swap_inicio_1 = (0.0, 0.0)
swap_inicio_2 = (0.0, 0.0)
swap_objetivo_1 = (0.0, 0.0)
swap_objetivo_2 = (0.0, 0.0)

# --- Animación de bajada inicial ---
bajar_t = 0.0
bajar_duracion = 600.0  # ms
bajar_inicio = [(float(x), float(y)) for (x, y) in vasos_pos_inicial_top]
bajar_objetivo = [(float(x), float(y)) for (x, y) in vasos_pos_juego]

# --- Fuente para mensajes y HUD ---
if IS_WEB:
    # En web usamos la fuente por defecto para evitar problemas de SysFont
    font = pygame.font.Font(None, S(36))
    font_small = pygame.font.Font(None, S(28))
else:
    font = pygame.font.SysFont(None, S(36))
    font_small = pygame.font.SysFont(None, S(28))
mensaje = "Memoriza la posición de la bola"
score = 0
rounds = 0

# --- Dificultades disponibles ---
difficulties = {
    "Fácil": {"swaps": 8, "dur_ms": 420.0},
    "Media": {"swaps": 12, "dur_ms": 360.0},
    "Difícil": {"swaps": 18, "dur_ms": 300.0},
}
diff_names = list(difficulties.keys())
diff_index = 1  # Media por defecto

# --- Sonidos (fallback silencioso) ---
mix_snd = None
ok_snd = None
fail_snd = None
# En web, evitar inicializar mixer para prevenir bloqueos por políticas de audio
if not IS_WEB:
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

# --- Modo trampa (mostrar bola durante mezcla encima de los vasos) ---
modo_trampa = False

# Rects UI (se recalculan al dibujar)
_btn_rect_cache = pygame.Rect(0, 0, 0, 0)
_diff_left_rect = pygame.Rect(0, 0, 0, 0)
_diff_right_rect = pygame.Rect(0, 0, 0, 0)
_diff_val_rect = pygame.Rect(0, 0, 0, 0)

# --- Función para dibujar todo ---
def dibujar():
    # Fondo
    if WEB_DEBUG:
        # Colores por estado para diagnóstico rápido en web
        bg = {
            ESTADO_MENU: (40, 80, 200),        # azul
            ESTADO_BAJAR: (220, 140, 60),      # naranja
            ESTADO_MEZCLA: (130, 70, 170),     # morado
            ESTADO_ESPERA_CLIC: (40, 160, 160),# turquesa
            ESTADO_REVELA: (220, 200, 60),     # amarillo
            ESTADO_FIN: (60, 180, 80),         # verde
        }.get(estado, (30, 30, 30))
        pantalla.fill(bg)
    else:
        if fondo is not None:
            pantalla.blit(fondo, (0, 0))
        else:
            pantalla.fill((20, 90, 20))

    # Dibuja los vasos; si with_lift y el vaso tiene la bola en MEZCLA, hace un pequeño "salto"
    def draw_cups(with_lift=True):
        for i, v in enumerate(vasos):
            vx, vy = v["x"], v["y"]
            lift = 0.0
            if with_lift and estado == ESTADO_MEZCLA and swapping and (i == swap_i1 or i == swap_i2) and i == indice_bola:
                p = max(0.0, min(1.0, swap_t / swap_duracion))
                lift = -12.0 * SCALE * math.sin(math.pi * p)
            draw_pos = (int(vx), int(vy + lift))
            if WEB_DEBUG:
                pygame.draw.rect(pantalla, (200, 200, 200), pygame.Rect(draw_pos[0], draw_pos[1], VASO_W, VASO_H), width=0, border_radius=12)
                pygame.draw.rect(pantalla, (50, 50, 50), pygame.Rect(draw_pos[0], draw_pos[1], VASO_W, VASO_H), width=2, border_radius=12)
            else:
                if vaso_img is not None:
                    pantalla.blit(vaso_img, draw_pos)
                else:
                    pygame.draw.rect(pantalla, (180, 180, 180), pygame.Rect(draw_pos[0], draw_pos[1], VASO_W, VASO_H), border_radius=12)

    # Calcula la posición de la bola ligada al vaso que la contiene
    def compute_ball_pos():
        # Posición estándar ligada al vaso de la bola
        base_x = vasos[indice_bola]["x"]
        base_y = vasos[indice_bola]["y"]
        bx = int(base_x) + S(55)
        by = int(base_y) + S(100)
        # Durante mezcla, si el vaso con bola está en swap, mover sincronizado con el vaso (sin retardo) y con ligero rebote
        if estado == ESTADO_MEZCLA and swapping and (indice_bola == swap_i1 or indice_bola == swap_i2):
            # Obtener inicio/objetivo del vaso de la bola
            if indice_bola == swap_i1:
                start = swap_inicio_1
                target = swap_objetivo_1
            else:
                start = swap_inicio_2
                target = swap_objetivo_2
            p = max(0.0, min(1.0, swap_t / swap_duracion))
            p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
            bx = int(start[0] + (target[0] - start[0]) * p_ease) + S(55)
            by = int(start[1] + (target[1] - start[1]) * p_ease) + S(100)
            # Rebote suave (solo vertical, muy sutil)
            lift_ball = -10.0 * SCALE * math.sin(math.pi * p_ease)
            by = int(by + lift_ball)
        return bx, by

    if estado == ESTADO_MEZCLA:
        # Durante la mezcla la bola NO debe verse normalmente. Solo animamos los vasos.
        draw_cups(with_lift=True)
        # Modo trampa: dibujar la bola por ENCIMA de los vasos para mostrar su posición real
        if modo_trampa or WEB_DEBUG:
            i = indice_bola
            # Centrar la bola sobre el vaso actual
            if bola_img is not None and not WEB_DEBUG:
                bw, bh = bola_img.get_size()
                bx = int(vasos[i]["x"]) + (VASO_W - bw) // 2
                by = int(vasos[i]["y"]) + (VASO_H - bh) // 2
                pantalla.blit(bola_img, (bx, by))
            else:
                r = S(20)
                bx = int(vasos[i]["x"]) + (VASO_W - 2 * r) // 2
                by = int(vasos[i]["y"]) + (VASO_H - 2 * r) // 2
                pygame.draw.circle(pantalla, (255, 200, 50), (bx + r, by + r), r)
    elif estado == ESTADO_BAJAR:
        # Solo vasos descendiendo desde arriba; no mostrar bola
        draw_cups(with_lift=False)
    elif estado == ESTADO_MENU:
        # En menú: bola DETRÁS (debajo) de los vasos para que éstos queden por delante
        # Posicionar la bola centrada bajo el vaso elegido y alineada a BALL_MENU_Y
        target_x, _ = vasos_pos_inicial_top[indice_bola]
        if bola_img is not None and not WEB_DEBUG:
            bw, bh = bola_img.get_size()
            bx = int(target_x + (VASO_W - bw) / 2)
            by = int(BALL_MENU_Y)
            pantalla.blit(bola_img, (bx, by))
        else:
            r = 20
            bx = int(target_x + (VASO_W - 2 * r) / 2)
            by = int(BALL_MENU_Y)
            pygame.draw.circle(pantalla, (255, 50, 50), (bx + r, by + r), r)
        # Dibujar vasos por delante
        draw_cups(with_lift=False)
    else:
        # Otros estados: dibujar vasos y, si corresponde, la bola por encima
        draw_cups(with_lift=False)
        if estado in (ESTADO_MOSTRAR, ESTADO_REVELA):
            bx, by = compute_ball_pos()
            if bola_img is not None and not WEB_DEBUG:
                pantalla.blit(bola_img, (bx, by))
            else:
                pygame.draw.circle(pantalla, (255, 50, 50), (bx + S(20), by + S(20)), S(20))

    # Dibujar mensaje si existe (más abajo) y aún más bajo en el menú
    if mensaje:
        surf = font.render(mensaje, True, (255, 255, 255))
        msg_y = 180 if estado != ESTADO_MENU else 240
        rect = surf.get_rect(center=(ANCHO // 2, msg_y))
        pantalla.blit(surf, rect)

    # HUD con marcador (esquina superior izquierda)
    hud = font_small.render(f"Puntos: {score}  Ronda: {rounds}", True, (230, 230, 230))
    pantalla.blit(hud, (16, 16))

    # Dificultad en esquina superior derecha (visible SIEMPRE; clic/teclas solo en MENÚ/FIN)
    diff_label = font_small.render("Dificultad:", True, (230, 230, 230))
    # Mover el bloque de dificultad hacia la izquierda proporcionalmente
    label_rect = diff_label.get_rect(topright=(ANCHO - S(260), S(10)))
    pantalla.blit(diff_label, label_rect)
    # Flechas y valor a la derecha de la palabra 'Dificultad'
    row_y = label_rect.centery - S(12)
    left_rect = pygame.Rect(label_rect.right + S(8), row_y, S(24), S(24))
    diff_val_surf = font.render(diff_names[diff_index], True, (255, 255, 0))
    diff_val_rect = diff_val_surf.get_rect(midleft=(left_rect.right + S(8), left_rect.centery))
    right_rect = pygame.Rect(diff_val_rect.right + S(8), row_y, S(24), S(24))
    pygame.draw.polygon(pantalla, (230, 230, 230), [(left_rect.right, left_rect.top), (left_rect.left, left_rect.centery), (left_rect.right, left_rect.bottom)])
    pygame.draw.polygon(pantalla, (230, 230, 230), [(right_rect.left, right_rect.top), (right_rect.right, right_rect.centery), (right_rect.left, right_rect.bottom)])
    pantalla.blit(diff_val_surf, diff_val_rect)
    # Guardar rects solo si estamos en MENÚ/FIN, para permitir clic
    global _diff_left_rect, _diff_right_rect, _diff_val_rect
    if estado in (ESTADO_MENU, ESTADO_FIN):
        _diff_left_rect = left_rect
        _diff_right_rect = right_rect
        _diff_val_rect = diff_val_rect
    else:
        _diff_left_rect = pygame.Rect(0, 0, 0, 0)
        _diff_right_rect = pygame.Rect(0, 0, 0, 0)
        _diff_val_rect = pygame.Rect(0, 0, 0, 0)

    # Botones (menú/fin)
    if estado in (ESTADO_MENU, ESTADO_FIN):
        # Botón Reintentar/Comenzar
        btn_text = "Comenzar" if estado == ESTADO_MENU else "Reintentar"
        btn_surf = font.render(btn_text, True, (0, 0, 0))
        btn_rect = pygame.Rect(ANCHO // 2 - S(100), ALTO - S(120), S(200), S(60))
        pygame.draw.rect(pantalla, (240, 240, 240), btn_rect, border_radius=10)
        pygame.draw.rect(pantalla, (50, 50, 50), btn_rect, width=2, border_radius=10)
        pantalla.blit(btn_surf, btn_surf.get_rect(center=btn_rect.center))
        # Guardar rect del botón para clics
        global _btn_rect_cache
        _btn_rect_cache = btn_rect

    # HUD de depuración en WEB: estado y guías visuales
    if WEB_DEBUG:
        debug_txt = f"WEB Estado: {estado}  FPS~{int(reloj.get_fps())}  Bola:{indice_bola}"
        dbg = font_small.render(debug_txt, True, (255, 80, 80))
        pantalla.blit(dbg, (16, ALTO - 28))
        # Borde del canvas
        pygame.draw.rect(pantalla, (255, 0, 0), pygame.Rect(0, 0, ANCHO, ALTO), width=2)
        # Texto grande centrado con el estado
        title = font.render(estado, True, (255, 255, 255))
        pantalla.blit(title, title.get_rect(center=(ANCHO//2, 60)))

    pygame.display.flip()

# --- Bucle principal (desktop/web) ---
seleccion = None

def handle_events():
    global jugando, estado, seleccion, mensaje, indice_bola, swap_queue, swapping, bajar_t, score, rounds, diff_index, modo_trampa
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            jugando = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r and estado == ESTADO_FIN:
                # Volver al MENÚ (bola visible) y reiniciar posiciones arriba
                for i, (x, y) in enumerate(vasos_pos_inicial_top):
                    vasos[i]["x"], vasos[i]["y"] = float(x), float(y)
                indice_bola = random.randint(0, 2)
                estado = ESTADO_MENU
                seleccion = None
                mensaje = "Elige dificultad y pulsa Comenzar"
                swap_queue.clear()
                swapping = False
            # Modo trampa
            if event.key == pygame.K_t:
                modo_trampa = not modo_trampa
            # Cambiar dificultad en menú/fin usando teclado (UI superior derecha eliminada)
            if estado in (ESTADO_MENU, ESTADO_FIN):
                if event.key == pygame.K_LEFT:
                    diff_index = (diff_index - 1) % len(diff_names)
                elif event.key == pygame.K_RIGHT:
                    diff_index = (diff_index + 1) % len(diff_names)

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

        # Clic en botón o en flechas de dificultad (menú/fin)
        if event.type == pygame.MOUSEBUTTONDOWN and estado in (ESTADO_MENU, ESTADO_FIN):
            x, y = event.pos
            btn_rect = _btn_rect_cache
            if _diff_left_rect.collidepoint(x, y) or (_diff_val_rect.collidepoint(x, y) and x < _diff_val_rect.centerx):
                diff_index = (diff_index - 1) % len(diff_names)
            elif _diff_right_rect.collidepoint(x, y) or (_diff_val_rect.collidepoint(x, y) and x >= _diff_val_rect.centerx):
                diff_index = (diff_index + 1) % len(diff_names)
            if btn_rect.collidepoint(x, y):
                if estado == ESTADO_MENU:
                    # Comenzar: animación de bajada
                    for i, (px, py) in enumerate(vasos_pos_inicial_top):
                        vasos[i]["x"], vasos[i]["y"] = float(px), float(py)
                    # mantener la misma posicion de la bola que se mostró en el menú
                    estado = ESTADO_BAJAR
                    bajar_t = 0.0
                    seleccion = None
                    mensaje = ""
                    swap_queue.clear()
                    swapping = False
                else:
                    # En FIN: volver a MENÚ (bola visible) en lugar de comenzar directo
                    for i, (px, py) in enumerate(vasos_pos_inicial_top):
                        vasos[i]["x"], vasos[i]["y"] = float(px), float(py)
                    indice_bola = random.randint(0, 2)
                    estado = ESTADO_MENU
                    seleccion = None
                    mensaje = "Elige dificultad (←/→) y pulsa Comenzar"

def update_logic(dt):
    global estado, mensaje, swap_queue, swapping, swap_i1, swap_i2, swap_t, swap_inicio_1, swap_inicio_2, swap_objetivo_1, swap_objetivo_2, bajar_t, score, rounds, swap_duracion
    # Lógica de estados
    if estado == ESTADO_MENU:
        # Mensaje simple de menú (sin paréntesis)
        mensaje = "Elige dificultad y pulsa Comenzar"
        # Nada más; espera interacción
    elif estado == ESTADO_BAJAR:
        # Interpolar posiciones desde top a juego
        bajar_t += dt
        p = max(0.0, min(1.0, bajar_t / bajar_duracion))
        p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
        for i in range(3):
            sx, sy = bajar_inicio[i]
            tx, ty = bajar_objetivo[i]
            vasos[i]["x"] = sx + (tx - sx) * p_ease
            vasos[i]["y"] = sy + (ty - sy) * p_ease
        if bajar_t >= bajar_duracion:
            # Asegurar posiciones finales
            for i, (tx, ty) in enumerate(vasos_pos_juego):
                vasos[i]["x"], vasos[i]["y"] = tx, ty
            # Saltar fase de mostrar: comenzar mezcla directamente
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
        timer_ms -= dt
        if timer_ms <= 0:
            # Preparar mezcla
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
        # Iniciar sonido de mezcla si existe
        if mix_snd:
            mix_snd.play()

    elif estado == ESTADO_MEZCLA:
        if not swapping and swap_queue:
            swap_i1, swap_i2 = swap_queue.pop(0)
            swap_t = 0.0
            # Capturar posiciones iniciales y objetivos
            swap_inicio_1 = (vasos[swap_i1]["x"], vasos[swap_i1]["y"])
            swap_inicio_2 = (vasos[swap_i2]["x"], vasos[swap_i2]["y"])
            swap_objetivo_1 = swap_inicio_2
            swap_objetivo_2 = swap_inicio_1
            swapping = True
        elif swapping:
            swap_t += dt
            p = max(0.0, min(1.0, swap_t / swap_duracion))
            # Suavizado (ease-in-out)
            p_ease = 0.5 - 0.5 * math.cos(math.pi * p)
            # Interpolación
            vasos[swap_i1]["x"] = swap_inicio_1[0] + (swap_objetivo_1[0] - swap_inicio_1[0]) * p_ease
            vasos[swap_i1]["y"] = swap_inicio_1[1] + (swap_objetivo_1[1] - swap_inicio_1[1]) * p_ease
            vasos[swap_i2]["x"] = swap_inicio_2[0] + (swap_objetivo_2[0] - swap_inicio_2[0]) * p_ease
            vasos[swap_i2]["y"] = swap_inicio_2[1] + (swap_objetivo_2[1] - swap_inicio_2[1]) * p_ease
            if swap_t >= swap_duracion:
                # Asegurar posiciones finales exactas
                vasos[swap_i1]["x"], vasos[swap_i1]["y"] = swap_objetivo_1
                vasos[swap_i2]["x"], vasos[swap_i2]["y"] = swap_objetivo_2
                swapping = False
        else:
            # Terminar mezcla
            estado = ESTADO_ESPERA_CLIC
            mensaje = "Haz clic en un vaso"

    elif estado == ESTADO_REVELA:
        # Se muestra la bola y se pasa a FIN (esperando R)
        estado = ESTADO_FIN

def loop_desktop():
    global jugando
    jugando = True
    clock_fps = 60
    while jugando:
        dt = reloj.tick(clock_fps)
        handle_events()
        update_logic(dt)
        dibujar()

async def loop_web():
    global jugando
    jugando = True
    clock_fps = 60
    while jugando:
        dt = reloj.tick(clock_fps)
        try:
            handle_events()
            update_logic(dt)
            dibujar()
        except Exception:
            # Mostrar overlay de error en web para depurar
            err = traceback.format_exc()
            pantalla.fill((30, 0, 0))
            y = 20
            for line in ("EXCEPCION EN WEB:",) + tuple(err.splitlines()[-10:]):
                surf = pygame.font.Font(None, 22).render(line, True, (255, 200, 200))
                pantalla.blit(surf, (10, y))
                y += 22
            pygame.display.flip()
        await asyncio.sleep(0)  # ceder control al navegador

async def main():  # entrada esperada por pygbag
    await loop_web()

if __name__ == "__main__" and (not IS_WEB):
    loop_desktop()
    pygame.quit()
elif IS_WEB:
    # Salvaguarda: programa la corrutina por si el runtime no la invoca automáticamente
    try:
        asyncio.get_event_loop().create_task(main())
    except Exception:
        pass
