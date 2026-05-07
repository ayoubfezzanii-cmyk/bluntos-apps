import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import random
import math

os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

BG = (0, 5, 15); ACCENT = (0, 255, 200); ACCENT_D = (0, 100, 80)
TEXT = (200, 255, 255); DIM = (60, 80, 100); RED = (255, 80, 80)

font_med = pygame.font.SysFont("monospace", 14, bold=True)
font_big = pygame.font.SysFont("monospace", 18, bold=True)
font_small = pygame.font.SysFont("monospace", 10)

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
KEY_UP=103; KEY_LEFT=105; KEY_RIGHT=106; KEY_W=17; KEY_A=30; KEY_D=32
KEY_SPACE=57; KEY_ESC=1; KEY_Q=16; KEY_R=19

# Polling: track held keys
keys_held = set()

def poll_keys_held():
    if not KEYBOARD_DEVS: return
    ready, _, _ = select.select(KEYBOARD_DEVS, [], [], 0)
    for f in ready:
        try:
            while True:
                data = f.read(EVENT_SIZE)
                if not data or len(data) < EVENT_SIZE: break
                _, _, typ, code, value = struct.unpack(EVENT_FORMAT, data)
                if typ == 1:
                    if value == 1: keys_held.add(code)
                    elif value == 0: keys_held.discard(code)
        except BlockingIOError: pass

def new_asteroid(level):
    side = random.randint(0,3)
    if side == 0: x, y = 0, random.randint(0,H)
    elif side == 1: x, y = W, random.randint(0,H)
    elif side == 2: x, y = random.randint(0,W), 0
    else: x, y = random.randint(0,W), H
    angle = random.uniform(0, 2*math.pi)
    speed = random.uniform(0.5, 1.5) + level*0.2
    return {"x":x, "y":y, "vx":math.cos(angle)*speed, "vy":math.sin(angle)*speed, "size":3, "r":18}

def split_asteroid(a):
    if a["size"] <= 1: return []
    new = []
    for _ in range(2):
        angle = random.uniform(0, 2*math.pi)
        speed = math.hypot(a["vx"], a["vy"]) * 1.3
        new.append({"x":a["x"], "y":a["y"], "vx":math.cos(angle)*speed, "vy":math.sin(angle)*speed,
                    "size":a["size"]-1, "r":a["r"]//1.5})
    return new

def reset_game():
    return {"x":W/2,"y":H/2,"vx":0,"vy":0,"angle":-math.pi/2,"alive":True,"score":0,"level":1,"lives":3}, [new_asteroid(1) for _ in range(3)], []

ship, asteroids, bullets = reset_game()
shoot_cooldown = 0
respawn_timer = 0
running = True

while running:
    poll_keys_held()
    
    if KEY_ESC in keys_held or KEY_Q in keys_held:
        running = False
    
    if KEY_R in keys_held:
        ship, asteroids, bullets = reset_game()
        keys_held.discard(KEY_R)

    if ship["alive"]:
        if KEY_LEFT in keys_held or KEY_A in keys_held:
            ship["angle"] -= 0.1
        if KEY_RIGHT in keys_held or KEY_D in keys_held:
            ship["angle"] += 0.1
        if KEY_UP in keys_held or KEY_W in keys_held:
            ship["vx"] += math.cos(ship["angle"]) * 0.15
            ship["vy"] += math.sin(ship["angle"]) * 0.15
        # Friction
        ship["vx"] *= 0.99; ship["vy"] *= 0.99
        ship["x"] = (ship["x"] + ship["vx"]) % W
        ship["y"] = (ship["y"] + ship["vy"]) % H
        
        if KEY_SPACE in keys_held and shoot_cooldown <= 0:
            bullets.append({"x":ship["x"],"y":ship["y"],
                           "vx":math.cos(ship["angle"])*5+ship["vx"],
                           "vy":math.sin(ship["angle"])*5+ship["vy"], "life":40})
            shoot_cooldown = 8
    
    shoot_cooldown -= 1
    
    # Update bullets
    for b in bullets[:]:
        b["x"] = (b["x"] + b["vx"]) % W
        b["y"] = (b["y"] + b["vy"]) % H
        b["life"] -= 1
        if b["life"] <= 0: bullets.remove(b)
    
    # Update asteroids
    for a in asteroids:
        a["x"] = (a["x"] + a["vx"]) % W
        a["y"] = (a["y"] + a["vy"]) % H
    
    # Bullet vs asteroid
    for b in bullets[:]:
        for a in asteroids[:]:
            if math.hypot(b["x"]-a["x"], b["y"]-a["y"]) < a["r"]:
                bullets.remove(b)
                asteroids.remove(a)
                ship["score"] += 100 // a["size"]
                asteroids.extend(split_asteroid(a))
                break
    
    # Ship vs asteroid
    if ship["alive"] and respawn_timer <= 0:
        for a in asteroids:
            if math.hypot(ship["x"]-a["x"], ship["y"]-a["y"]) < a["r"] + 5:
                ship["lives"] -= 1
                if ship["lives"] <= 0:
                    ship["alive"] = False
                else:
                    ship["x"] = W/2; ship["y"] = H/2; ship["vx"]=0; ship["vy"]=0
                    respawn_timer = 60
                break
    respawn_timer -= 1
    
    # Next level
    if not asteroids and ship["alive"]:
        ship["level"] += 1
        asteroids = [new_asteroid(ship["level"]) for _ in range(2 + ship["level"])]
    
    # Render
    screen.fill(BG)
    
    # Asteroids (polygons)
    for a in asteroids:
        pts = []
        n = 8
        for i in range(n):
            ang = i * 2*math.pi/n
            r = a["r"] * (0.7 + 0.3 * ((i*7) % 5)/5)
            pts.append((a["x"] + math.cos(ang)*r, a["y"] + math.sin(ang)*r))
        pygame.draw.polygon(screen, ACCENT_D, pts, 1)
    
    # Bullets
    for b in bullets:
        pygame.draw.circle(screen, ACCENT, (int(b["x"]), int(b["y"])), 1)
    
    # Ship
    if ship["alive"] and (respawn_timer <= 0 or respawn_timer % 10 < 5):
        nose = (ship["x"]+math.cos(ship["angle"])*8, ship["y"]+math.sin(ship["angle"])*8)
        left = (ship["x"]+math.cos(ship["angle"]+2.5)*6, ship["y"]+math.sin(ship["angle"]+2.5)*6)
        right = (ship["x"]+math.cos(ship["angle"]-2.5)*6, ship["y"]+math.sin(ship["angle"]-2.5)*6)
        pygame.draw.polygon(screen, ACCENT, [nose, left, right], 1)
    
    # HUD
    s = font_small.render(f"SCORE {ship['score']}", True, ACCENT)
    screen.blit(s, (8, 8))
    l = font_small.render(f"LIVES {ship['lives']}  LVL {ship['level']}", True, TEXT)
    screen.blit(l, (W - 8 - l.get_width(), 8))
    
    if not ship["alive"]:
        m = font_big.render("GAME OVER", True, RED)
        screen.blit(m, (W//2 - m.get_width()//2, H//2))
        h = font_small.render("[R] RESTART  [ESC] QUIT", True, DIM)
        screen.blit(h, (W//2 - h.get_width()//2, H//2 + 22))
    else:
        h = font_small.render("[<>]ROT [^]THRUST [SP]FIRE", True, DIM)
        screen.blit(h, (W//2 - h.get_width()//2, H - 14))

    blit_to_fb(screen)
    clock.tick(30)

for f in KEYBOARD_DEVS: f.close()
pygame.quit()
