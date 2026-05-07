import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import random

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG       = (5, 10, 20)
ACCENT   = (0, 255, 200)
ACCENT_D = (0, 100, 80)
TEXT     = (200, 255, 255)
DIM      = (60, 80, 100)

font_med   = pygame.font.SysFont("monospace", 14, bold=True)
font_big   = pygame.font.SysFont("monospace", 18, bold=True)
font_small = pygame.font.SysFont("monospace", 10)
font_tile  = pygame.font.SysFont("monospace", 18, bold=True)

TILE_COLORS = {
    0:    (15, 25, 40),
    2:    (0, 80, 70),
    4:    (0, 110, 95),
    8:    (0, 140, 120),
    16:   (0, 170, 145),
    32:   (0, 200, 170),
    64:   (0, 230, 195),
    128:  (0, 255, 200),
    256:  (80, 255, 220),
    512:  (140, 255, 235),
    1024: (200, 255, 245),
    2048: (255, 255, 255),
}

def blit_to_fb(surface):
    arr = pygame.surfarray.pixels3d(surface)
    arr = np.transpose(arr, (1, 0, 2))
    r = (arr[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (arr[:, :, 1].astype(np.uint16) >> 2) << 5
    b = (arr[:, :, 2].astype(np.uint16) >> 3)
    rgb565 = (r | g | b).astype("<u2")
    with open("/dev/fb0", "wb") as fb:
        fb.write(rgb565.tobytes())

KEYBOARD_DEVS = []
for dev in glob.glob("/dev/input/event*"):
    try:
        f = open(dev, "rb")
        flags = fcntl.fcntl(f, fcntl.F_GETFL)
        fcntl.fcntl(f, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        KEYBOARD_DEVS.append(f)
    except (PermissionError, OSError):
        pass

EVENT_FORMAT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
KEY_UP = 103; KEY_DOWN = 108; KEY_LEFT = 105; KEY_RIGHT = 106
KEY_W = 17; KEY_S = 31; KEY_A = 30; KEY_D = 32
KEY_R = 19; KEY_ENTER = 28; KEY_SPACE = 57; KEY_ESC = 1; KEY_Q = 16

def poll_keys():
    pressed = []
    if not KEYBOARD_DEVS: return pressed
    ready, _, _ = select.select(KEYBOARD_DEVS, [], [], 0)
    for f in ready:
        try:
            while True:
                data = f.read(EVENT_SIZE)
                if not data or len(data) < EVENT_SIZE: break
                _, _, typ, code, value = struct.unpack(EVENT_FORMAT, data)
                if typ == 1 and value == 1: pressed.append(code)
        except BlockingIOError: pass
    return pressed

def new_grid():
    g = [[0]*4 for _ in range(4)]
    add_tile(g); add_tile(g)
    return g

def add_tile(g):
    empties = [(r,c) for r in range(4) for c in range(4) if g[r][c]==0]
    if empties:
        r,c = random.choice(empties)
        g[r][c] = 4 if random.random() < 0.1 else 2

def slide_row(row):
    new = [n for n in row if n != 0]
    score = 0
    i = 0
    while i < len(new) - 1:
        if new[i] == new[i+1]:
            new[i] *= 2
            score += new[i]
            del new[i+1]
        i += 1
    new += [0] * (4 - len(new))
    return new, score

def move(g, direction):
    """direction: 'L','R','U','D'. Returns (new_grid, score, changed)."""
    changed = False
    score = 0
    new = [row[:] for row in g]
    if direction == "L":
        for r in range(4):
            row, s = slide_row(new[r])
            if row != new[r]: changed = True
            new[r] = row; score += s
    elif direction == "R":
        for r in range(4):
            row, s = slide_row(new[r][::-1])
            row = row[::-1]
            if row != new[r]: changed = True
            new[r] = row; score += s
    elif direction == "U":
        for c in range(4):
            col = [new[r][c] for r in range(4)]
            col, s = slide_row(col)
            for r in range(4):
                if new[r][c] != col[r]: changed = True
                new[r][c] = col[r]
            score += s
    elif direction == "D":
        for c in range(4):
            col = [new[r][c] for r in range(4)][::-1]
            col, s = slide_row(col)
            col = col[::-1]
            for r in range(4):
                if new[r][c] != col[r]: changed = True
                new[r][c] = col[r]
            score += s
    return new, score, changed

def is_game_over(g):
    if any(0 in row for row in g): return False
    for r in range(4):
        for c in range(4):
            if c < 3 and g[r][c] == g[r][c+1]: return False
            if r < 3 and g[r][c] == g[r+1][c]: return False
    return True

grid = new_grid()
score = 0
running = True
won = False

while running:
    for code in poll_keys():
        if code in (KEY_ESC, KEY_Q):
            running = False
        elif code == KEY_R:
            grid = new_grid(); score = 0; won = False
        elif not is_game_over(grid):
            d = None
            if code in (KEY_LEFT, KEY_A): d = "L"
            elif code in (KEY_RIGHT, KEY_D): d = "R"
            elif code in (KEY_UP, KEY_W): d = "U"
            elif code in (KEY_DOWN, KEY_S): d = "D"
            if d:
                new_g, s, changed = move(grid, d)
                if changed:
                    grid = new_g
                    score += s
                    add_tile(grid)
                    if any(2048 in row for row in grid): won = True

    screen.fill(BG)
    title = font_med.render("2048", True, ACCENT)
    screen.blit(title, (10, 8))
    sc = font_med.render(f"SCORE: {score}", True, TEXT)
    screen.blit(sc, (W - 10 - sc.get_width(), 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)

    # Grid
    grid_size = 180
    cell_size = grid_size // 4
    grid_x = (W - grid_size) // 2
    grid_y = 36
    pygame.draw.rect(screen, (10, 20, 35), (grid_x-3, grid_y-3, grid_size+6, grid_size+6), 0)
    
    for r in range(4):
        for c in range(4):
            v = grid[r][c]
            x = grid_x + c * cell_size + 2
            y = grid_y + r * cell_size + 2
            color = TILE_COLORS.get(v, (255, 200, 100))
            pygame.draw.rect(screen, color, (x, y, cell_size-4, cell_size-4))
            if v != 0:
                text_color = BG if v >= 8 else TEXT
                t = font_tile.render(str(v), True, text_color)
                screen.blit(t, (x + (cell_size-4)//2 - t.get_width()//2, y + (cell_size-4)//2 - t.get_height()//2))

    if is_game_over(grid):
        msg = font_big.render("GAME OVER", True, (255, 80, 80))
        screen.blit(msg, (W//2 - msg.get_width()//2, H - 35))
    elif won:
        msg = font_big.render("YOU WIN!", True, ACCENT)
        screen.blit(msg, (W//2 - msg.get_width()//2, H - 35))
    else:
        hint = font_small.render("[ARROWS] MOVE  [R] RESET  [ESC] QUIT", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(20)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
