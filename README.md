# Juego del Trilero (Pygame)

Un minijuego tipo "trilero" desarrollado con Pygame. Incluye animaciones suaves, selector de dificultad, rondas y puntuación, y una versión del código ampliamente documentada.

## Características

- Animación de mezcla con interpolación (ease-in-out) y swaps configurables.
- Máquina de estados clara: MENÚ → BAJAR → MEZCLA → ESPERA_CLIC → REVELA → FIN.
- Bola visible en el MENÚ bajo uno de los vasos; oculta durante la mezcla (tapada por los vasos) y revelada al seleccionar.
- Dificultad seleccionable (Fácil, Media, Difícil).
- Puntuación y número de rondas en HUD.
- Rutas seguras y fallback si faltan imágenes/sonidos.
- Transparencia de imágenes con colorkey (con tolerancia) para eliminar fondos planos.
- Archivo `main_comentado.py` con comentarios detallados.

## Requisitos

- Python 3.10+
- Pygame CE 2.5+ (probado con pygame-ce 2.5.6)

Instalación:

```bash
pip install pygame-ce
```

## Estructura del proyecto

```
Trilero/
├─ assets/
│  ├─ fondo.jpg               # opcional
│  ├─ vaso.png                # requerido (o se usa placeholder)
│  ├─ bola.png                # requerido (o se usa placeholder)
│  └─ sounds/
│     ├─ mix.wav              # opcional
│     ├─ success.wav          # opcional
│     └─ fail.wav             # opcional
├─ main.py                    # juego principal (comentarios ligeros)
├─ main_comentado.py          # juego muy documentado (comentarios detallados)
└─ README.md
```

## Cómo jugar

1. Ejecuta `main.py`.
2. MENÚ:
   - Verás los vasos arriba y la bola visible debajo de uno de ellos.
   - Cambia la **dificultad** con las teclas ← → o clic en las flechas (arriba derecha).
   - Pulsa el botón **Comenzar**.
3. BAJAR: los vasos descienden hasta la altura de la bola.
4. MEZCLA: los vasos se intercambian varias veces (según la dificultad). La bola queda oculta bajo los vasos.
5. ESPERA_CLIC: haz clic en el vaso que crees que oculta la bola.
6. REVELA/FIN: se muestra si has acertado, se actualiza la puntuación y puedes **Reintentar** o pulsar **R** para volver al MENÚ.

## Controles

- Mouse: seleccionar vaso y pulsar botones de UI.
- ← →: cambiar dificultad (en MENÚ/FIN).
- R: en FIN, volver al MENÚ.
- T: modo trampa (debug). Mientras la mezcla está en curso, la bola se muestra por ENCIMA de los vasos para que puedas seguirla. En otros estados, el juego mantiene el comportamiento normal (en MENÚ la bola aparece debajo; en MEZCLA está oculta si el modo trampa está apagado; en REVELA se muestra).

## Dificultad

- Fácil: 8 intercambios, más lentos.
- Media: 12 intercambios, velocidad media.
- Difícil: 18 intercambios, más rápidos.

Puedes ajustar los valores en `difficulties` dentro de `main.py`.

## Ajustes rápidos

- Separación entre vasos: función `posiciones_centradas()` (variable `sep`).
- Altura y márgenes en MENÚ: `posiciones_centradas()` y la constante `BALL_MENU_Y`.
- Duración de bajada: `bajar_duracion`.
- Duración de cada intercambio: `swap_duracion` (se ajusta por dificultad).
- Intensidad del “salto” del vaso con bola: en `draw_cups()` (amplitud `12.0`).
- Rebote de la bola: en `compute_ball_pos()` (amplitud `10.0`).

## Recursos gráficos y transparencia

- `main.py` intenta eliminar fondos planos de `vaso.png` y `bola.png` con colorkey + tolerancia.
- Para mejores resultados, usa PNG con canal alfa transparente.
- Si ves halos, aumenta la tolerancia en `apply_transparency()` o exporta con alfa real.

## Errores conocidos / Notas

- Si faltan imágenes o sonidos, el juego seguirá funcionando con placeholders/silencio.
- Dependiendo de la plataforma, el renderizado de fuentes puede variar ligeramente.

## Créditos y licencia

- Código creado para fines educativos y de demostración.
- Imágenes/sonidos: usa recursos libres de derechos o propios.

## Desarrollo

- `main_comentado.py` contiene explicaciones claras de cada sección.
- Se recomienda modificar primero `main.py` y usar `main_comentado.py` como guía.

---

## Instalación rápida

- Python 3.10+
- Entorno virtual recomendado

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

## Ejecutar en escritorio

```bash
python main.py
```

## Build Windows (ZIP listo para itch.io)

- Genera `dist/Trilero` y `dist/Trilero-Windows.zip`.

```bat
build_windows.bat
```

## Build Web (HTML5 con pygbag)

- Requiere `pyproject.toml` (ya incluido).
- Genera `build/web` y `build/web.zip` listo para itch.io (HTML).

```bat
web_build.bat
```

### Probar localmente el build web

```bash
py -m http.server 8000 -d build/web
# Abrir http://localhost:8000
```

## Publicar en itch.io

- HTML5 (recomendado):
  - Opción 1: Subir `build/web.zip` como "HTML" (contiene `index.html` en la raíz del zip).
  - Opción 2 (butler):
    ```bash
    butler login
    butler push build/web TU_USUARIO/trilero:html5
    ```
- Windows:
  - Subir `dist/Trilero-Windows.zip` como build de Windows.

## Subir a GitHub

```bash
git init
git add .
git commit -m "feat: Trilero con builds Windows y Web"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/Trilero.git
git push -u origin main
```

## Licencia

Elige una licencia (por ejemplo, MIT). Si no especificas otra, se recomienda MIT.
