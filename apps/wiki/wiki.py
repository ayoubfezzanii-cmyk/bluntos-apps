import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import requests
import re
import threading
import textwrap

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG = (5, 10, 20); ACCENT = (0, 255, 200); ACCENT_D = (0, 100, 80)
TEXT = (200, 255, 255); DIM = (60, 80, 100)

font_med = pygame.font.SysFont("monospace", 14, bold=True)
font_small = pygame.font.SysFont("monospace", 10)
font_body = pygame.font.SysFont("monospace", 12)

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
KEY_W=17; KEY_S=31; KEY_UP=103; KEY_DOWN=108
KEY_LEFT=105; KEY_RIGHT=106; KEY_A=30; KEY_D=32
KEY_N=49; KEY_R=19; KEY_ENTER=28; KEY_SPACE=57; KEY_ESC=1; KEY_Q=16

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

article = {"title": "Loading...", "extract": "", "loading": True}
art_lock = threading.Lock()

def fetch_random():
    with art_lock:
        article["loading"] = True
        article["title"] = "Loading..."
        article["extract"] = ""
    try:
        r = requests.get("https://en.wikipedia.org/api/rest_v1/page/random/summary", timeout=10)
        d = r.json()
        with art_lock:
            article["title"] = d.get("title", "Unknown")
            article["extract"] = d.get("extract", "No content.")
            article["loading"] = False
    except Exception as e:
        with art_lock:
            article["title"] = "Error"
            article["extract"] = f"Could not load article: {e}"
            article["loading"] = False

def fetch_async():
    threading.Thread(target=fetch_random, daemon=True).start()

fetch_async()

scroll = 0
LINES_PER_PAGE = 12
LINE_H = 13
running = True

while running:
    keys = poll_keys()
    
    with art_lock:
        title = article["title"]
        text = article["extract"]
        loading = article["loading"]
    
    # Wrap text
    paragraphs = text.split("\n")
    lines = []
    for p in paragraphs:
        wrapped = textwrap.wrap(p, 38)
        lines.extend(wrapped if wrapped else [""])
    
    for code in keys:
        if code in (KEY_ESC, KEY_Q):
            running = False
        elif code in (KEY_N, KEY_R):
            fetch_async()
            scroll = 0
        elif code in (KEY_DOWN, KEY_S):
            scroll = min(max(0, len(lines) - LINES_PER_PAGE), scroll + 1)
        elif code in (KEY_UP, KEY_W):
            scroll = max(0, scroll - 1)
        elif code in (KEY_RIGHT, KEY_D, KEY_SPACE):
            scroll = min(max(0, len(lines) - LINES_PER_PAGE), scroll + LINES_PER_PAGE)
        elif code in (KEY_LEFT, KEY_A):
            scroll = max(0, scroll - LINES_PER_PAGE)

    screen.fill(BG)
    # Title
    t_disp = title if len(title) <= 30 else title[:27] + "..."
    t = font_med.render(t_disp, True, ACCENT)
    screen.blit(t, (10, 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)
    
    # Body
    if loading:
        m = font_med.render("Fetching from Wikipedia...", True, DIM)
        screen.blit(m, (W//2 - m.get_width()//2, H//2))
    else:
        y = 34
        end = min(len(lines), scroll + LINES_PER_PAGE)
        for i in range(scroll, end):
            t = font_body.render(lines[i], True, TEXT)
            screen.blit(t, (10, y))
            y += LINE_H
        # Scroll indicator
        if len(lines) > LINES_PER_PAGE:
            sb_h = max(20, int(LINES_PER_PAGE / len(lines) * (LINES_PER_PAGE * LINE_H)))
            sb_y = 34 + int(scroll / len(lines) * (LINES_PER_PAGE * LINE_H))
            pygame.draw.rect(screen, ACCENT_D, (W-6, sb_y, 3, sb_h))
    
    hint = font_small.render("[N] NEW  [W/S] SCROLL  [ESC] QUIT", True, DIM)
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(15)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
