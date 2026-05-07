import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import requests
import threading
import textwrap
import time
import math

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

# Cyberpunk Palette
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
        fcntl.fcntl(f, fcntl.F_SETFL, fcntl.fcntl(f, fcntl.F_GETFL) | os.O_NONBLOCK)
        KEYBOARD_DEVS.append(f)
    except: pass

EVENT_FORMAT = "llHHI"; EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
KEY_W=17; KEY_S=31; KEY_UP=103; KEY_DOWN=108; KEY_ESC=1; KEY_Q=16; KEY_N=49

# Replicating your "article" dictionary structure for the launcher
article = {"title": "Neural Link: Active", "extract": "Initializing...", "loading": True}
art_lock = threading.Lock()

def fetch_system_data():
    while True:
        with art_lock:
            article["loading"] = True
        
        # Get real CPU load
        with open("/proc/loadavg", "r") as f:
            load = f.read().split()[0]
        
        # Create a "futuristic" data readout
        timestamp = time.strftime("%H:%M:%S")
        sys_info = (
            f"TIMESTAMP: {timestamp}\n"
            f"CPU_LOAD_1M: {load}\n"
            f"NEURAL_SYNC: STABLE\n"
            f"FRAMEBUFFER: /dev/fb0\n"
            f"UPLINK_STATUS: CONNECTED\n"
            f"--------------------------\n"
            f"System is monitoring hardware interrupts and neural pathways..."
        )
        
        with art_lock:
            article["extract"] = sys_info
            article["loading"] = False
        time.sleep(2)

def fetch_async():
    threading.Thread(target=fetch_system_data, daemon=True).start()

fetch_async()

scroll = 0
LINES_PER_PAGE = 12
LINE_H = 13
running = True
angle = 0

while running:
    keys = poll_keys() if 'poll_keys' in globals() else [] # Fallback
    # Using your exact input polling logic
    ready, _, _ = select.select(KEYBOARD_DEVS, [], [], 0)
    for f in ready:
        try:
            data = f.read(EVENT_SIZE)
            if data:
                _, _, typ, code, val = struct.unpack(EVENT_FORMAT, data)
                if typ == 1 and val == 1:
                    if code in (KEY_ESC, KEY_Q): running = False
                    elif code in (KEY_DOWN, KEY_S): scroll += 1
                    elif code in (KEY_UP, KEY_W): scroll = max(0, scroll - 1)
        except: pass

    with art_lock:
        title = article["title"]
        text = article["extract"]
        loading = article["loading"]

    paragraphs = text.split("\n")
    lines = []
    for p in paragraphs:
        wrapped = textwrap.wrap(p, 38)
        lines.extend(wrapped if wrapped else [""])

    screen.fill(BG)
    
    # Futuristic Animated Header
    angle += 0.1
    pulse = int(abs(math.sin(angle)) * 5)
    pygame.draw.circle(screen, ACCENT, (W-30, 15), 5 + pulse, 1)
    
    t = font_med.render(title, True, ACCENT)
    screen.blit(t, (10, 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)

    # Body (Exactly matching your Wikipedia App layout)
    y = 34
    end = min(len(lines), scroll + LINES_PER_PAGE)
    for i in range(scroll, end):
        t = font_body.render(lines[i], True, TEXT)
        screen.blit(t, (10, y))
        y += LINE_H

    hint = font_small.render("[W/S] SCROLL  [ESC] QUIT", True, DIM)
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(20)

pygame.quit()
