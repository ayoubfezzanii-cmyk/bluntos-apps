import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import time
import json

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG = (5, 10, 20); ACCENT = (0, 255, 200); ACCENT_D = (0, 100, 80)
TEXT = (200, 255, 255); DIM = (60, 80, 100); RED = (255, 80, 80); OK = (80, 255, 120)

font_med = pygame.font.SysFont("monospace", 14, bold=True)
font_big = pygame.font.SysFont("monospace", 22, bold=True)
font_huge = pygame.font.SysFont("monospace", 32, bold=True)
font_small = pygame.font.SysFont("monospace", 10)

SAVE_FILE = "/home/bluntcooks/.bluntos_timers.json"

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
KEY_W=17; KEY_S=31; KEY_A=30; KEY_D=32
KEY_UP=103; KEY_DOWN=108; KEY_LEFT=105; KEY_RIGHT=106
KEY_ENTER=28; KEY_SPACE=57; KEY_ESC=1; KEY_Q=16
KEY_N=49; KEY_DEL=14; KEY_R=19

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

def load_timers():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f:
                data = json.load(f)
                # Reset running state - timers start paused on load
                for t in data:
                    t["running"] = False
                return data
        except Exception: pass
    return []

def save_timers(timers):
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(timers, f)
    except Exception: pass

PRESETS = [60, 5*60, 10*60, 25*60, 60*60]  # 1m, 5m, 10m, 25m, 1h
PRESET_LABELS = ["1m", "5m", "10m", "25m", "1h"]

timers = load_timers()
sel = 0
state = "list"  # list, new
new_idx = 1  # default 5m

def fmt(secs):
    s = int(max(0, secs))
    h, m, s = s//3600, (s//60)%60, s%60
    if h: return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

last_tick = time.time()
running = True
while running:
    now = time.time()
    delta = now - last_tick
    last_tick = now
    
    keys = poll_keys()
    for code in keys:
        if state == "list":
            if code in (KEY_ESC, KEY_Q):
                running = False
            elif code == KEY_N:
                state = "new"
                new_idx = 1
            elif timers:
                if code in (KEY_W, KEY_UP):
                    sel = (sel - 1) % len(timers)
                elif code in (KEY_S, KEY_DOWN):
                    sel = (sel + 1) % len(timers)
                elif code in (KEY_ENTER, KEY_SPACE):
                    timers[sel]["running"] = not timers[sel]["running"]
                elif code == KEY_R:
                    timers[sel]["remaining"] = timers[sel]["total"]
                    timers[sel]["running"] = False
                    timers[sel]["done"] = False
                elif code == KEY_DEL:
                    timers.pop(sel)
                    sel = max(0, sel-1)
                    save_timers(timers)
        elif state == "new":
            if code in (KEY_ESC,):
                state = "list"
            elif code in (KEY_LEFT, KEY_A):
                new_idx = max(0, new_idx - 1)
            elif code in (KEY_RIGHT, KEY_D):
                new_idx = min(len(PRESETS)-1, new_idx + 1)
            elif code in (KEY_ENTER, KEY_SPACE):
                t = PRESETS[new_idx]
                timers.append({"label": PRESET_LABELS[new_idx], "total": t, "remaining": t, "running": False, "done": False})
                save_timers(timers)
                state = "list"

    # Tick running timers
    for t in timers:
        if t["running"] and not t["done"]:
            t["remaining"] -= delta
            if t["remaining"] <= 0:
                t["remaining"] = 0
                t["done"] = True
                t["running"] = False

    screen.fill(BG)
    title = font_med.render("TIMERS", True, ACCENT)
    screen.blit(title, (10, 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)

    if state == "list":
        if not timers:
            msg = font_med.render("No timers.", True, DIM)
            screen.blit(msg, (W//2 - msg.get_width()//2, H//2 - 20))
            hint = font_small.render("Press [N] to add", True, ACCENT)
            screen.blit(hint, (W//2 - hint.get_width()//2, H//2))
        else:
            y = 36
            for i, t in enumerate(timers):
                is_sel = (i == sel)
                if is_sel:
                    pygame.draw.rect(screen, (10, 30, 40), (8, y-2, W-16, 36))
                    pygame.draw.rect(screen, ACCENT, (8, y-2, W-16, 36), 1)
                color = OK if t["done"] else (ACCENT if t["running"] else DIM)
                lbl = font_med.render(t["label"], True, color)
                screen.blit(lbl, (16, y))
                rem = font_big.render(fmt(t["remaining"]), True, color)
                screen.blit(rem, (W - 16 - rem.get_width(), y))
                status = "DONE" if t["done"] else ("RUNNING" if t["running"] else "PAUSED")
                s = font_small.render(status, True, color)
                screen.blit(s, (16, y + 18))
                y += 38
                if y > H - 30: break
        hint = font_small.render("[ENTER]START [N]NEW [R]RESET [DEL]REMOVE", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))
    
    elif state == "new":
        msg = font_med.render("NEW TIMER", True, ACCENT)
        screen.blit(msg, (W//2 - msg.get_width()//2, 50))
        # Preset picker
        x = 20
        for i, lbl in enumerate(PRESET_LABELS):
            is_sel = (i == new_idx)
            color = ACCENT if is_sel else DIM
            t = font_big.render(lbl, True, color)
            box_w = (W - 40) // len(PRESETS)
            box_x = 20 + i * box_w
            if is_sel:
                pygame.draw.rect(screen, ACCENT, (box_x+2, 100, box_w-4, 40), 2)
            screen.blit(t, (box_x + box_w//2 - t.get_width()//2, 110))
        hint = font_small.render("[<>] PICK  [ENTER] CREATE  [ESC] CANCEL", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(10)

save_timers(timers)
for f in KEYBOARD_DEVS: f.close()
pygame.quit()
