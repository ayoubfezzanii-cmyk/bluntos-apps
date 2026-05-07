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

BG     = (5, 10, 20)
ACCENT = (0, 255, 200)
DIM    = (60, 80, 100)
RED    = (255, 80, 80)
TEXT   = (200, 255, 255)

font_med   = pygame.font.SysFont("monospace", 14, bold=True)
font_big   = pygame.font.SysFont("monospace", 22, bold=True)
font_small = pygame.font.SysFont("monospace", 10)

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
KEY_ENTER = 28; KEY_SPACE = 57; KEY_ESC = 1; KEY_Q = 16

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
                if typ == 1 and value == 1:
                    pressed.append(code)
        except BlockingIOError:
            pass
    return pressed

CELL = 10
COLS = W // CELL
ROWS = (H - 30) // CELL
PLAY_Y = 30

def reset():
    return {
        "snake": [(COLS//2, ROWS//2)],
        "dir": (1, 0),
        "food": (random.randint(0, COLS-1), random.randint(0, ROWS-1)),
        "score": 0,
        "dead": False,
    }

state = reset()
paused = False
frame = 0
running = True
move_timer = 0

while running:
    for code in poll_keys():
        if code in (KEY_ESC, KEY_Q):
            running = False
        elif state["dead"]:
            if code in (KEY_ENTER, KEY_SPACE):
                state = reset()
        else:
            if code in (KEY_UP, KEY_W) and state["dir"] != (0, 1):
                state["dir"] = (0, -1)
            elif code in (KEY_DOWN, KEY_S) and state["dir"] != (0, -1):
                state["dir"] = (0, 1)
            elif code in (KEY_LEFT, KEY_A) and state["dir"] != (1, 0):
                state["dir"] = (-1, 0)
            elif code in (KEY_RIGHT, KEY_D) and state["dir"] != (-1, 0):
                state["dir"] = (1, 0)
            elif code == KEY_SPACE:
                paused = not paused

    if not state["dead"] and not paused:
        move_timer += 1
        if move_timer >= 4:
            move_timer = 0
            head = state["snake"][0]
            new_head = (head[0] + state["dir"][0], head[1] + state["dir"][1])
            if (new_head[0] < 0 or new_head[0] >= COLS or
                new_head[1] < 0 or new_head[1] >= ROWS or
                new_head in state["snake"]):
                state["dead"] = True
            else:
                state["snake"].insert(0, new_head)
                if new_head == state["food"]:
                    state["score"] += 1
                    while True:
                        f = (random.randint(0, COLS-1), random.randint(0, ROWS-1))
                        if f not in state["snake"]:
                            state["food"] = f
                            break
                else:
                    state["snake"].pop()

    screen.fill(BG)
    title = font_med.render("SNAKE", True, ACCENT)
    screen.blit(title, (10, 8))
    score = font_med.render(f"SCORE: {state['score']}", True, TEXT)
    screen.blit(score, (W - 10 - score.get_width(), 8))
    pygame.draw.line(screen, DIM, (0, PLAY_Y - 2), (W, PLAY_Y - 2), 1)
    fx, fy = state["food"]
    pygame.draw.rect(screen, RED, (fx*CELL+1, PLAY_Y + fy*CELL+1, CELL-2, CELL-2))
    for i, (x, y) in enumerate(state["snake"]):
        c = ACCENT if i == 0 else (0, 180, 140)
        pygame.draw.rect(screen, c, (x*CELL+1, PLAY_Y + y*CELL+1, CELL-2, CELL-2))
    if state["dead"]:
        msg = font_big.render("GAME OVER", True, RED)
        screen.blit(msg, (W//2 - msg.get_width()//2, H//2 - 20))
        hint = font_small.render("ENTER to restart  ESC to quit", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H//2 + 10))

    blit_to_fb(screen)
    clock.tick(30)
    frame += 1

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
