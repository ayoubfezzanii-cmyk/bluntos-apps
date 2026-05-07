import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG     = (5, 10, 20)
ACCENT = (0, 255, 200)
DIM    = (60, 80, 100)
TEXT   = (200, 255, 255)
RED    = (255, 100, 100)
GREEN  = (100, 255, 150)

font_huge  = pygame.font.SysFont("monospace", 64, bold=True)
font_big   = pygame.font.SysFont("monospace", 18, bold=True)
font_med   = pygame.font.SysFont("monospace", 14, bold=True)
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
KEY_ENTER = 28; KEY_SPACE = 57; KEY_ESC = 1; KEY_Q = 16; KEY_R = 19

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

WORK = 25 * 60
BREAK = 5 * 60

mode = "WORK"
remaining = WORK
running_timer = False
last_tick = time.time()
sessions = 0
running = True

while running:
    now = time.time()
    delta = now - last_tick
    last_tick = now
    
    for code in poll_keys():
        if code in (KEY_ESC, KEY_Q):
            running = False
        elif code in (KEY_ENTER, KEY_SPACE):
            running_timer = not running_timer
        elif code == KEY_R:
            remaining = WORK if mode == "WORK" else BREAK
            running_timer = False

    if running_timer:
        remaining -= delta
        if remaining <= 0:
            if mode == "WORK":
                sessions += 1
                mode = "BREAK"
                remaining = BREAK
            else:
                mode = "WORK"
                remaining = WORK
            running_timer = False

    screen.fill(BG)
    color = ACCENT if mode == "WORK" else GREEN
    label = font_big.render(mode, True, color)
    screen.blit(label, (W//2 - label.get_width()//2, 12))
    
    mins = int(remaining) // 60
    secs = int(remaining) % 60
    time_str = f"{mins:02d}:{secs:02d}"
    t = font_huge.render(time_str, True, color)
    screen.blit(t, (W//2 - t.get_width()//2, 60))
    
    status = "RUNNING" if running_timer else "PAUSED"
    s = font_med.render(status, True, TEXT if running_timer else DIM)
    screen.blit(s, (W//2 - s.get_width()//2, 140))
    
    sess = font_small.render(f"SESSIONS: {sessions}", True, ACCENT)
    screen.blit(sess, (W//2 - sess.get_width()//2, 170))
    
    hint = font_small.render("[ENTER] START/PAUSE  [R] RESET  [ESC] QUIT", True, DIM)
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 16))

    blit_to_fb(screen)
    clock.tick(10)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
