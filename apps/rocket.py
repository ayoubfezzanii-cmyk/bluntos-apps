import pygame
import numpy as np
import os
import select
import struct
import glob
import fcntl
import random
import time

# Framebuffer Setup
os.environ["SDL_VIDEODRIVER"] = "dummy"
W, H = 320, 240
pygame.init()
screen = pygame.Surface((W, H))
clock = pygame.time.Clock()

# Cyberpunk Palette
BG = (2, 4, 12); STAR = (200, 255, 255); TRAIL = (0, 100, 150)

def blit_to_fb(surface):
    arr = pygame.surfarray.pixels3d(surface)
    arr = np.transpose(arr, (1, 0, 2))
    r = (arr[:,:,0].astype(np.uint16)>>3)<<11
    g = (arr[:,:,1].astype(np.uint16)>>2)<<5
    b = (arr[:,:,2].astype(np.uint16)>>3)
    rgb565 = (r|g|b).astype("<u2")
    with open("/dev/fb0", "wb") as fb: fb.write(rgb565.tobytes())

# Input Handling
KEYBOARD_DEVS = []
for dev in glob.glob("/dev/input/event*"):
    try:
        f = open(dev, "rb")
        fcntl.fcntl(f, fcntl.F_SETFL, fcntl.fcntl(f, fcntl.F_GETFL) | os.O_NONBLOCK)
        KEYBOARD_DEVS.append(f)
    except: pass

def poll_keys():
    pressed = []
    ready, _, _ = select.select(KEYBOARD_DEVS, [], [], 0)
    for f in ready:
        try:
            while True:
                data = f.read(16)
                if not data: break
                _, _, typ, code, val = struct.unpack("llHHI", data)
                if typ == 1 and val == 1: pressed.append(code)
        except: pass
    return pressed

# Star Class for 3D logic
class Star:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = random.uniform(-W, W)
        self.y = random.uniform(-H, H)
        self.z = random.uniform(1, W)
        self.pz = self.z # Previous Z for trails

    def update(self, speed):
        self.pz = self.z
        self.z -= speed
        if self.z < 1:
            self.reset()
            self.pz = self.z

    def draw(self, surf):
        # 3D to 2D projection: x' = x/z, y' = y/z
        sx = int((self.x / self.z) * 100 + W/2)
        sy = int((self.y / self.z) * 100 + H/2)
        
        px = int((self.x / self.pz) * 100 + W/2)
        py = int((self.y / self.pz) * 100 + H/2)

        if 0 <= sx < W and 0 <= sy < H:
            # Draw trail
            pygame.draw.line(surf, TRAIL, (px, py), (sx, sy), 1)
            # Draw star head
            pygame.draw.circle(surf, STAR, (sx, sy), 1)

# Initialize 100 stars
stars = [Star() for _ in range(100)]
warp_speed = 5
running = True

while running:
    for code in poll_keys():
        if code == 1: # ESC
            running = False
        if code == 103: # UP
            warp_speed = min(20, warp_speed + 2)
        if code == 108: # DOWN
            warp_speed = max(1, warp_speed - 2)

    screen.fill(BG)
    
    # Update and draw stars
    for s in stars:
        s.update(warp_speed)
        s.draw(screen)

    # HUD Overlay
    font = pygame.font.SysFont("monospace", 10, bold=True)
    hud = font.render(f"VELOCITY: {warp_speed*1000} LY/S", True, (0, 255, 200))
    screen.blit(hud, (10, 10))
    
    hint = font.render("[UP/DN] WARP  [ESC] QUIT", True, (60, 60, 80))
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 15))

    blit_to_fb(screen)
    clock.tick(30)

pygame.quit()
