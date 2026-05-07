import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import random
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG = (5, 10, 20); ACCENT = (0, 255, 200); ACCENT_D = (0, 100, 80)
TEXT = (200, 255, 255); DIM = (60, 80, 100)

font_med = pygame.font.SysFont("monospace", 14, bold=True)
font_big = pygame.font.SysFont("monospace", 18, bold=True)
font_small = pygame.font.SysFont("monospace", 10)

# 7 tetrominoes
SHAPES = {
    "I": [[1,1,1,1]],
    "O": [[1,1],[1,1]],
    "T": [[0,1,0],[1,1,1]],
    "S": [[0,1,1],[1,1,0]],
    "Z": [[1,1,0],[0,1,1]],
    "J": [[1,0,0],[1,1,1]],
    "L": [[0,0,1],[1,1,1]],
}
COLORS = {
    "I": (0, 255, 200), "O": (255, 230, 80),  "T": (200, 100, 255),
    "S": (80, 255, 100),"Z": (255, 80, 80),   "J": (80, 150, 255),"L": (255, 160, 60),
}

COLS, ROWS = 10, 18
CELL = 11
GRID_X = 14
GRID_Y = 32

def blit_to_fb(surface):
    arr = pygame.surfarray.pixels3d(surface)
    arr = np.transpose(arr, (1, 0, 2))
    r = (arr[:,:,0].astype(np.uint16)>>3)<<11
    g = (arr[:,:,1].astype(np.uint16)>>2)<<5
    b = (arr[:,:,2].astype(np.uint16)>>3)
    rgb565 = (r|g|b).astype("<u2")
    with open("/dev/fb0", "wb") as fb: fb.write(rgb565.tobytes())

KEYBOARD_DEVS = []
for dev in glob.glob("/dev/input/event*"):
    try:
        f = open(dev, "rb")
        flags = fcntl.fcntl(f, fcntl.F_GETFL)
        fcntl.fcntl(f, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        KEYBOARD_DEVS.append(f)
    except (PermissionError, OSError): pass

EVENT_FORMAT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
KEY_UP=103; KEY_DOWN=108; KEY_LEFT=105; KEY_RIGHT=106
KEY_W=17; KEY_S=31; KEY_A=30; KEY_D=32
KEY_SPACE=57; KEY_ESC=1; KEY_Q=16; KEY_R=19; KEY_ENTER=28

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

def rotate(shape):
    return [list(row) for row in zip(*shape[::-1])]

def new_piece():
    k = random.choice(list(SHAPES.keys()))
    return {"shape": [row[:] for row in SHAPES[k]], "color": COLORS[k], "x": COLS//2 - len(SHAPES[k][0])//2, "y": 0}

def collides(grid, piece, dx=0, dy=0, shape=None):
    s = shape if shape else piece["shape"]
    for r, row in enumerate(s):
        for c, v in enumerate(row):
            if not v: continue
            nx, ny = piece["x"]+c+dx, piece["y"]+r+dy
            if nx<0 or nx>=COLS or ny>=ROWS: return True
            if ny>=0 and grid[ny][nx]: return True
    return False

def merge(grid, piece):
    for r, row in enumerate(piece["shape"]):
        for c, v in enumerate(row):
            if v and piece["y"]+r >= 0:
                grid[piece["y"]+r][piece["x"]+c] = piece["color"]

def clear_lines(grid):
    new = [row for row in grid if not all(row)]
    cleared = ROWS - len(new)
    for _ in range(cleared):
        new.insert(0, [0]*COLS)
    return new, cleared

grid = [[0]*COLS for _ in range(ROWS)]
piece = new_piece()
score = 0
lines = 0
last_drop = time.time()
drop_speed = 0.5
running = True
game_over = False

while running:
    now = time.time()
    for code in poll_keys():
        if code in (KEY_ESC, KEY_Q):
            running = False
        elif code == KEY_R:
            grid = [[0]*COLS for _ in range(ROWS)]
            piece = new_piece(); score = 0; lines = 0; game_over = False
        elif not game_over:
            if code in (KEY_LEFT, KEY_A) and not collides(grid, piece, dx=-1):
                piece["x"] -= 1
            elif code in (KEY_RIGHT, KEY_D) and not collides(grid, piece, dx=1):
                piece["x"] += 1
            elif code in (KEY_DOWN, KEY_S) and not collides(grid, piece, dy=1):
                piece["y"] += 1
                score += 1
            elif code in (KEY_UP, KEY_W):
                rot = rotate(piece["shape"])
                if not collides(grid, piece, shape=rot):
                    piece["shape"] = rot
            elif code == KEY_SPACE:
                while not collides(grid, piece, dy=1):
                    piece["y"] += 1
                    score += 2
                last_drop = 0  # force drop next tick

    if not game_over and now - last_drop > drop_speed:
        last_drop = now
        if not collides(grid, piece, dy=1):
            piece["y"] += 1
        else:
            merge(grid, piece)
            grid, cleared = clear_lines(grid)
            if cleared:
                lines += cleared
                score += [0, 100, 300, 500, 800][cleared]
                drop_speed = max(0.1, 0.5 - lines * 0.02)
            piece = new_piece()
            if collides(grid, piece):
                game_over = True

    screen.fill(BG)
    title = font_med.render("TETRIS", True, ACCENT)
    screen.blit(title, (10, 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)

    # Playfield border
    pf_w = COLS*CELL; pf_h = ROWS*CELL
    pygame.draw.rect(screen, ACCENT_D, (GRID_X-2, GRID_Y-2, pf_w+4, pf_h+4), 1)
    
    # Grid
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c]:
                pygame.draw.rect(screen, grid[r][c], (GRID_X+c*CELL, GRID_Y+r*CELL, CELL-1, CELL-1))
    
    # Current piece
    if not game_over:
        for r, row in enumerate(piece["shape"]):
            for c, v in enumerate(row):
                if v:
                    pygame.draw.rect(screen, piece["color"], (GRID_X+(piece["x"]+c)*CELL, GRID_Y+(piece["y"]+r)*CELL, CELL-1, CELL-1))

    # Side panel
    sx = GRID_X + pf_w + 12
    s = font_small.render("SCORE", True, ACCENT_D); screen.blit(s, (sx, GRID_Y))
    s = font_med.render(str(score), True, TEXT); screen.blit(s, (sx, GRID_Y+12))
    s = font_small.render("LINES", True, ACCENT_D); screen.blit(s, (sx, GRID_Y+40))
    s = font_med.render(str(lines), True, TEXT); screen.blit(s, (sx, GRID_Y+52))

    if game_over:
        msg = font_big.render("GAME OVER", True, (255, 80, 80))
        screen.blit(msg, (W//2 - msg.get_width()//2, H//2))
        h = font_small.render("[R] RESTART", True, DIM)
        screen.blit(h, (W//2 - h.get_width()//2, H//2 + 22))
    
    hint = font_small.render("[ARROWS] MOVE  [UP] ROT  [SP] DROP", True, DIM)
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(30)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
