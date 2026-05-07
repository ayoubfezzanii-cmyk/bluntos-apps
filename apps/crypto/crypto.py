import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import time
import threading
import requests

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG = (5, 10, 20); ACCENT = (0, 255, 200); ACCENT_D = (0, 100, 80)
TEXT = (200, 255, 255); DIM = (60, 80, 100); GREEN = (80, 255, 120); RED = (255, 80, 80)

font_med = pygame.font.SysFont("monospace", 14, bold=True)
font_big = pygame.font.SysFont("monospace", 18, bold=True)
font_huge = pygame.font.SysFont("monospace", 28, bold=True)
font_small = pygame.font.SysFont("monospace", 10)

# CoinGecko free API - no key needed
COINS = [
    {"id":"bitcoin",  "sym":"BTC"},
    {"id":"ethereum", "sym":"ETH"},
    {"id":"solana",   "sym":"SOL"},
    {"id":"cardano",  "sym":"ADA"},
    {"id":"dogecoin", "sym":"DOGE"},
]

data_lock = threading.Lock()
prices = {}  # {sym: {price, change_24h, history: [...]}}

def blit_to_fb(surface):
    arr = pygame.surfarray.pixels3d(surface)
    arr = np.transpose(arr, (1, 0, 2))
    r = (arr[:,:,0].astype(np.uint16)>>3)<<11
    g = (arr[:,:,1].astype(np.uint16)>>2)<<5
    b = (arr[:,:,2].astype(np.uint16)>>3)
    rgb565 = (r|g|b).astype("<u2")
    with open("/dev/fb0", "wb") as fb: fb.write(rgb565.tobytes())

def fetch_loop():
    global prices
    while True:
        try:
            ids = ",".join(c["id"] for c in COINS)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
            r = requests.get(url, timeout=10)
            d = r.json()
            with data_lock:
                for c in COINS:
                    if c["id"] in d:
                        sym = c["sym"]
                        new_price = d[c["id"]]["usd"]
                        if sym not in prices:
                            prices[sym] = {"history": []}
                        prices[sym]["price"] = new_price
                        prices[sym]["change"] = d[c["id"]].get("usd_24h_change", 0)
                        prices[sym]["history"].append(new_price)
                        if len(prices[sym]["history"]) > 60:
                            prices[sym]["history"].pop(0)
        except Exception as e:
            print(f"Crypto fetch error: {e}")
        time.sleep(60)  # 1 minute - CoinGecko free tier rate limit

threading.Thread(target=fetch_loop, daemon=True).start()

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

state = "list"  # list, detail
sel = 0
running = True

def fmt_price(p):
    if p >= 1000: return f"${p:,.0f}"
    if p >= 1: return f"${p:,.2f}"
    return f"${p:.4f}"

while running:
    for code in poll_keys():
        if state == "list":
            if code in (KEY_ESC, KEY_Q):
                running = False
            elif code in (KEY_W, KEY_UP):
                sel = (sel - 1) % len(COINS)
            elif code in (KEY_S, KEY_DOWN):
                sel = (sel + 1) % len(COINS)
            elif code in (KEY_ENTER, KEY_SPACE):
                state = "detail"
        elif state == "detail":
            if code in (KEY_ESC, KEY_Q):
                state = "list"

    screen.fill(BG)
    title = font_med.render("CRYPTO", True, ACCENT)
    screen.blit(title, (10, 8))
    pygame.draw.line(screen, ACCENT_D, (0, 28), (W, 28), 1)

    with data_lock:
        local = dict(prices)

    if state == "list":
        y = 36
        for i, c in enumerate(COINS):
            is_sel = (i == sel)
            if is_sel:
                pygame.draw.rect(screen, (10, 30, 40), (8, y-2, W-16, 32))
                pygame.draw.rect(screen, ACCENT, (8, y-2, W-16, 32), 1)
            sym = c["sym"]
            color = ACCENT if is_sel else TEXT
            s = font_med.render(sym, True, color)
            screen.blit(s, (16, y+8))
            if sym in local and "price" in local[sym]:
                price_str = fmt_price(local[sym]["price"])
                p = font_med.render(price_str, True, TEXT)
                screen.blit(p, (130, y+8))
                ch = local[sym].get("change", 0)
                ch_color = GREEN if ch >= 0 else RED
                ch_str = f"{ch:+.2f}%"
                c_t = font_med.render(ch_str, True, ch_color)
                screen.blit(c_t, (W - 16 - c_t.get_width(), y+8))
            else:
                p = font_small.render("loading...", True, DIM)
                screen.blit(p, (130, y+10))
            y += 36
        hint = font_small.render("[W/S] NAV  [ENTER] DETAIL  [ESC] QUIT", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))
    
    elif state == "detail":
        sym = COINS[sel]["sym"]
        s = font_huge.render(sym, True, ACCENT)
        screen.blit(s, (16, 36))
        if sym in local and "price" in local[sym]:
            p = font_big.render(fmt_price(local[sym]["price"]), True, TEXT)
            screen.blit(p, (16, 75))
            ch = local[sym].get("change", 0)
            ch_color = GREEN if ch >= 0 else RED
            c_t = font_med.render(f"24H {ch:+.2f}%", True, ch_color)
            screen.blit(c_t, (16, 100))
            # Tiny chart of history
            hist = local[sym].get("history", [])
            if len(hist) > 1:
                chart_x, chart_y, cw, ch_h = 16, 130, W-32, 70
                pygame.draw.rect(screen, ACCENT_D, (chart_x, chart_y, cw, ch_h), 1)
                mn, mx = min(hist), max(hist)
                if mx == mn: mx = mn + 1
                pts = []
                for i, v in enumerate(hist):
                    x = chart_x + int(i * cw / (len(hist)-1))
                    y = chart_y + ch_h - int((v - mn) / (mx - mn) * ch_h)
                    pts.append((x, y))
                if len(pts) >= 2:
                    pygame.draw.lines(screen, ACCENT, False, pts, 1)
        else:
            p = font_med.render("Loading...", True, DIM)
            screen.blit(p, (16, 80))
        hint = font_small.render("[ESC] BACK", True, DIM)
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(10)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
