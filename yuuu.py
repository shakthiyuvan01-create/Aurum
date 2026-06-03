"""
MinePy 3D - Minecraft-inspired game with:
  ✅ True 3D isometric block rendering (top + left + right faces)
  ✅ Block breaking animation with crack overlay + progress bar
  ✅ Day/Night cycle (sun, moon, stars, dynamic sky & lighting)

Controls:
  WASD / Arrow Keys  - Move
  Space              - Jump
  Left Click (hold)  - Break block (with animation)
  Right Click        - Place block
  1-0                - Select hotbar slot
  Scroll             - Change hotbar slot
  E                  - Inventory
  Esc                - Quit
"""

import pygame
import sys
import math
import random

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1100, 660
FPS          = 60

# 3-D isometric tile geometry
TILE_W   = 48          # full tile width  (front face)
TILE_H   = 48          # full tile height (front face)
ISO_W    = 20          # iso top-face horizontal half-width
ISO_H    = 10          # iso top-face vertical  half-height

GRAVITY    = 0.55
JUMP_SPEED = -13
MOVE_SPEED = 4

WORLD_W  = 90
WORLD_H  = 42
SEA_LEVEL = 30

# Day / night
DAY_LENGTH   = 60 * FPS    # frames for one full cycle (60 s)
SUNRISE_FRAC = 0.25
SUNSET_FRAC  = 0.75

# Break times per block hardness (frames at 60fps)
BREAK_TIMES = {
    1: 30,   # grass
    2: 25,   # dirt
    3: 90,   # stone
    4: 60,   # wood
    5: 15,   # leaves
    6: 20,   # sand
    7: 999,  # water (unbreakable)
    8: 35,   # gravel
    9: 20,   # snow
    10:999,  # lava  (unbreakable)
    11:40,   # glass
    12:80,   # brick
    13:95,   # coal ore
    14:100,  # iron ore
    15:110,  # gold ore
}

# ─────────────────────────────────────────────────────────────────────────────
#  Block Definitions  (top, left, right face colours)
# ─────────────────────────────────────────────────────────────────────────────
BLOCKS = {
    0:  None,
    1:  {"name":"Grass",   "top":(95,175,55),   "left":(100,75,45),  "right":(85,62,35)},
    2:  {"name":"Dirt",    "top":(130,95,60),   "left":(115,82,50),  "right":(100,70,40)},
    3:  {"name":"Stone",   "top":(145,145,145), "left":(120,120,120),"right":(100,100,100)},
    4:  {"name":"Wood",    "top":(200,165,80),  "left":(148,105,55), "right":(120,85,40)},
    5:  {"name":"Leaves",  "top":(50,130,35),   "left":(38,112,28),  "right":(30,95,22)},
    6:  {"name":"Sand",    "top":(230,215,155), "left":(210,198,135),"right":(195,183,120)},
    7:  {"name":"Water",   "top":(70,130,230),  "left":(55,115,215), "right":(42,100,200)},
    8:  {"name":"Gravel",  "top":(158,150,145), "left":(140,132,128),"right":(125,118,114)},
    9:  {"name":"Snow",    "top":(245,248,255), "left":(220,228,238),"right":(205,213,225)},
    10: {"name":"Lava",    "top":(245,90,20),   "left":(220,65,10),  "right":(200,50,5)},
    11: {"name":"Glass",   "top":(185,228,248), "left":(165,212,235),"right":(148,198,222)},
    12: {"name":"Brick",   "top":(200,105,70),  "left":(178,88,55),  "right":(158,72,42)},
    13: {"name":"Coal Ore","top":(118,118,118), "left":(100,100,100),"right":(85,85,85)},
    14: {"name":"Iron Ore","top":(165,145,122), "left":(148,128,108),"right":(132,114,95)},
    15: {"name":"Gold Ore","top":(205,192,52),  "left":(188,175,45), "right":(170,158,38)},
}

HOTBAR_BLOCKS = [1, 2, 3, 4, 5, 6, 8, 12, 13, 14]

# ─────────────────────────────────────────────────────────────────────────────
#  Colour helpers
# ─────────────────────────────────────────────────────────────────────────────
def darken(c, a=40):
    return (max(0,c[0]-a), max(0,c[1]-a), max(0,c[2]-a))

def lighten(c, a=20):
    return (min(255,c[0]+a), min(255,c[1]+a), min(255,c[2]+a))

def blend(c1, c2, t):
    return (int(c1[0]*(1-t)+c2[0]*t),
            int(c1[1]*(1-t)+c2[1]*t),
            int(c1[2]*(1-t)+c2[2]*t))

def tint(color, night_factor):
    """Apply night darkening/blue tint to a colour."""
    r = int(color[0] * (0.15 + 0.85 * night_factor))
    g = int(color[1] * (0.15 + 0.85 * night_factor))
    b = int(min(255, color[2] * (0.18 + 0.82 * night_factor) + 30 * (1 - night_factor)))
    return (r, g, b)

# ─────────────────────────────────────────────────────────────────────────────
#  Pre-baked block surface cache   (keyed by (block_id, night_factor_int))
# ─────────────────────────────────────────────────────────────────────────────
_block_cache = {}

def get_block_surf(bx, by, block_id, night_factor):
    """
    Draw a single 3-D isometric block:
      - front face  (TILE_W × TILE_H)
      - top face    (parallelogram above the front face)
      - right-side face (darker, narrower right strip)
    Total canvas: (TILE_W + ISO_W) × (TILE_H + ISO_H)
    Anchor point (top-left of front face): (ISO_W, ISO_H)
    """
    nf_key = int(night_factor * 10)
    key = (bx, by, block_id, nf_key)
    if key in _block_cache:
        return _block_cache[key]

    bd = BLOCKS[block_id]
    W  = TILE_W + ISO_W
    H  = TILE_H + ISO_H

    surf = pygame.Surface((W, H), pygame.SRCALPHA)

    top_c   = tint(bd["top"],   night_factor)
    left_c  = tint(bd["left"],  night_factor)
    right_c = tint(bd["right"], night_factor)

    # ── Front (left) face ──────────────────────────────────────────
    fx, fy = ISO_W, ISO_H
    pygame.draw.rect(surf, left_c, (fx, fy, TILE_W - ISO_W, TILE_H))

    # texture details seeded by position
    random.seed(bx * 997 + by * 31 + block_id * 7)
    for _ in range(4):
        tx = fx + random.randint(1, TILE_W - ISO_W - 3)
        ty = fy + random.randint(2, TILE_H - 3)
        cr = random.randint(-14, 14)
        dc = (max(0,min(255,left_c[0]+cr)),
              max(0,min(255,left_c[1]+cr)),
              max(0,min(255,left_c[2]+cr)))
        r  = random.randint(1, 3)
        pygame.draw.circle(surf, dc, (tx, ty), r)

    # ── Right face (darker strip on right side) ────────────────────
    rx = fx + TILE_W - ISO_W
    right_pts = [
        (rx, fy),
        (rx + ISO_W, fy + ISO_H),
        (rx + ISO_W, fy + ISO_H + TILE_H),
        (rx, fy + TILE_H),
    ]
    pygame.draw.polygon(surf, right_c, right_pts)
    pygame.draw.polygon(surf, darken(right_c, 20), right_pts, 1)

    # ── Top face (parallelogram) ───────────────────────────────────
    #   top-left  (ISO_W, 0)  ──►  top-right  (TILE_W, 0)
    #   bot-left  (0, ISO_H)  ──►  bot-right  (TILE_W - ISO_W, ISO_H)
    top_pts = [
        (ISO_W, 0),
        (TILE_W, 0),
        (TILE_W + ISO_W, ISO_H),
        (ISO_W + ISO_W, ISO_H),   # == (2*ISO_W, ISO_H)
    ]
    # correct the parallelogram to sit flush on front face
    top_pts = [
        (ISO_W,               0),
        (ISO_W + (TILE_W - ISO_W), 0),
        (ISO_W + (TILE_W - ISO_W) + ISO_W, ISO_H),
        (ISO_W + ISO_W,       ISO_H),
    ]
    pygame.draw.polygon(surf, top_c, top_pts)
    pygame.draw.polygon(surf, darken(top_c, 20), top_pts, 1)

    # ── Outline ────────────────────────────────────────────────────
    pygame.draw.rect(surf, darken(left_c, 55),
                     (fx, fy, TILE_W - ISO_W, TILE_H), 1)

    # Water / glass alpha
    if block_id == 7:
        surf.set_alpha(155)
    elif block_id == 11:
        surf.set_alpha(175)

    _block_cache[key] = surf
    return surf


# ─────────────────────────────────────────────────────────────────────────────
#  Crack overlay surfaces (10 stages)
# ─────────────────────────────────────────────────────────────────────────────
_crack_surfs = None

def get_crack_surfs():
    global _crack_surfs
    if _crack_surfs:
        return _crack_surfs
    _crack_surfs = []
    W = TILE_W + ISO_W
    H = TILE_H + ISO_H
    for stage in range(1, 11):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        alpha = int(30 + stage * 18)
        s.fill((0, 0, 0, alpha))
        # Draw crack lines radiating from centre
        cx, cy = ISO_W + (TILE_W - ISO_W)//2, ISO_H + TILE_H//2
        random.seed(stage * 42)
        for _ in range(stage + 2):
            angle = random.uniform(0, math.pi * 2)
            length = random.randint(4, int(4 + stage * 2.5))
            ex = int(cx + math.cos(angle) * length)
            ey = int(cy + math.sin(angle) * length)
            pygame.draw.line(s, (0, 0, 0, min(255, 80 + stage * 15)),
                             (cx, cy), (ex, ey), max(1, stage // 4))
        _crack_surfs.append(s)
    return _crack_surfs


# ─────────────────────────────────────────────────────────────────────────────
#  World generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_world():
    world = [[0] * WORLD_W for _ in range(WORLD_H)]

    # Smooth heightmap
    heights = []
    h = SEA_LEVEL
    for x in range(WORLD_W):
        h += random.randint(-2, 2)
        h = max(SEA_LEVEL - 9, min(SEA_LEVEL + 7, h))
        heights.append(h)

    for x in range(WORLD_W):
        surf = heights[x]
        for y in range(WORLD_H):
            if y < surf - 4:
                world[y][x] = 0
            elif y == surf - 4:
                world[y][x] = 1    # grass
            elif y < surf:
                world[y][x] = 2    # dirt
            else:
                world[y][x] = 3    # stone

        for y in range(surf, WORLD_H):
            r = random.random()
            if   r < 0.030: world[y][x] = 13
            elif r < 0.015: world[y][x] = 14
            elif r < 0.005: world[y][x] = 15

        surf_y = surf - 4
        if surf_y > 1 and random.random() < 0.07 and 2 < x < WORLD_W - 3:
            trunk = random.randint(3, 5)
            for ty in range(trunk):
                yy = surf_y - 1 - ty
                if 0 <= yy < WORLD_H:
                    world[yy][x] = 4
            top = surf_y - trunk
            for ly in range(top - 2, top + 2):
                for lx in range(x - 2, x + 3):
                    if 0 <= ly < WORLD_H and 0 <= lx < WORLD_W:
                        if world[ly][lx] == 0:
                            world[ly][lx] = 5

    return world, heights


# ─────────────────────────────────────────────────────────────────────────────
#  Player
# ─────────────────────────────────────────────────────────────────────────────
class Player:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.width  = 0.75
        self.height = 1.85
        self.selected_slot = 0
        self.inventory = {b: 64 for b in HOTBAR_BLOCKS}
        self.reach = 6

    def selected_block(self):
        return HOTBAR_BLOCKS[self.selected_slot % len(HOTBAR_BLOCKS)]

    def update(self, world, keys):
        dx = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx = -MOVE_SPEED
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx =  MOVE_SPEED

        self.vy += GRAVITY
        if self.vy > 20: self.vy = 20

        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and self.on_ground:
            self.vy = JUMP_SPEED
            self.on_ground = False

        self.x += dx / TILE_W
        self._resolve_x(world)
        self.y += self.vy / TILE_H
        self._resolve_y(world)

    def _solid(self, world, bx, by):
        if bx < 0 or bx >= WORLD_W or by < 0 or by >= WORLD_H:
            return bx < 0 or bx >= WORLD_W
        b = world[by][bx]
        return b not in (0, 7, 11)

    def _resolve_x(self, world):
        bx0 = int(math.floor(self.x))
        bx1 = int(math.floor(self.x + self.width - 0.01))
        by0 = int(math.floor(self.y + 0.05))
        by1 = int(math.floor(self.y + self.height - 0.05))
        for by in range(by0, by1 + 1):
            if self._solid(world, bx0, by):
                self.x = bx0 + 1.0; return
            if self._solid(world, bx1, by):
                self.x = bx1 - self.width; return

    def _resolve_y(self, world):
        bx0 = int(math.floor(self.x + 0.05))
        bx1 = int(math.floor(self.x + self.width - 0.05))
        if self.vy >= 0:
            by = int(math.floor(self.y + self.height))
            for bx in range(bx0, bx1 + 1):
                if self._solid(world, bx, by):
                    self.y = by - self.height
                    self.vy = 0; self.on_ground = True; return
            self.on_ground = False
        else:
            by = int(math.floor(self.y))
            for bx in range(bx0, bx1 + 1):
                if self._solid(world, bx, by):
                    self.y = by + 1.0; self.vy = 0; return


# ─────────────────────────────────────────────────────────────────────────────
#  Camera
# ─────────────────────────────────────────────────────────────────────────────
class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, player):
        tx = player.x * TILE_W - SCREEN_W // 2
        ty = player.y * TILE_H - SCREEN_H // 2
        self.x += (tx - self.x) * 0.12
        self.y += (ty - self.y) * 0.12
        self.x = max(0, min(self.x, WORLD_W * TILE_W - SCREEN_W))
        self.y = max(0, min(self.y, WORLD_H * TILE_H - SCREEN_H))

    def w2s(self, wx, wy):
        return int(wx * TILE_W - self.x), int(wy * TILE_H - self.y)

    def s2w(self, sx, sy):
        return (sx + self.x) / TILE_W, (sy + self.y) / TILE_H


# ─────────────────────────────────────────────────────────────────────────────
#  Day / Night
# ─────────────────────────────────────────────────────────────────────────────
class DayNight:
    def __init__(self):
        self.tick = 0   # starts at dawn

    def update(self):
        self.tick = (self.tick + 1) % DAY_LENGTH

    @property
    def frac(self):
        return self.tick / DAY_LENGTH   # 0.0 → 1.0

    @property
    def light(self):
        """0.0 = midnight dark, 1.0 = noon full bright."""
        f = self.frac
        if   f < 0.25:  return f / 0.25          # dawn
        elif f < 0.50:  return 1.0                # day
        elif f < 0.75:  return (0.75 - f) / 0.25 # dusk
        else:           return 0.0                # night

    def sky_colors(self):
        f   = self.frac
        lgt = self.light

        NOON_TOP  = (100, 180, 255)
        NOON_BOT  = (175, 225, 255)
        DUSK_TOP  = (220, 100, 40)
        DUSK_BOT  = (245, 165, 80)
        NIGHT_TOP = (8,  12,  35)
        NIGHT_BOT = (15, 20,  55)

        if lgt >= 0.5:
            # blend noon ↔ dusk
            t = (1.0 - lgt) * 2       # 0=noon, 1=dusk edge
            top = blend(NOON_TOP, DUSK_TOP, t)
            bot = blend(NOON_BOT, DUSK_BOT, t)
        else:
            # blend dusk ↔ night
            t = 1.0 - lgt * 2         # 0=dusk edge, 1=night
            top = blend(DUSK_TOP, NIGHT_TOP, t)
            bot = blend(DUSK_BOT, NIGHT_BOT, t)
        return top, bot

    def sun_angle(self):
        """Angle in radians: 0=horizon-east, π=horizon-west (noon = π/2)."""
        return math.pi * self.frac  # 0 → π over full day

    def moon_angle(self):
        return math.pi * ((self.frac + 0.5) % 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Sky renderer
# ─────────────────────────────────────────────────────────────────────────────
def draw_sky_gradient(surf, top_c, bot_c):
    for y in range(SCREEN_H):
        t   = y / SCREEN_H
        col = blend(top_c, bot_c, t)
        pygame.draw.line(surf, col, (0, y), (SCREEN_W, y))


def draw_celestial_bodies(surf, dn):
    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    radius = min(SCREEN_W, SCREEN_H) * 0.42

    # ── Sun ──
    sa = dn.sun_angle()
    if 0 < sa < math.pi:
        sx = int(cx + math.cos(math.pi - sa) * radius)
        sy = int(cy - math.sin(sa) * radius * 0.55)
        glow_col = (255, 255, 180, 60)
        for gr in range(28, 0, -4):
            gs = pygame.Surface((gr*2, gr*2), pygame.SRCALPHA)
            g_alpha = max(0, 60 - gr * 2)
            pygame.draw.circle(gs, (255, 240, 100, g_alpha), (gr, gr), gr)
            surf.blit(gs, (sx - gr, sy - gr))
        pygame.draw.circle(surf, (255, 235, 60), (sx, sy), 18)
        pygame.draw.circle(surf, (255, 255, 180), (sx, sy), 12)

    # ── Moon ──
    ma = dn.moon_angle()
    if 0 < ma < math.pi and dn.light < 0.3:
        mx = int(cx + math.cos(math.pi - ma) * radius)
        my = int(cy - math.sin(ma) * radius * 0.55)
        pygame.draw.circle(surf, (220, 225, 235), (mx, my), 14)
        pygame.draw.circle(surf, (200, 205, 218), (mx + 3, my - 2), 4)


def draw_stars(surf, stars, dn):
    brightness = max(0, 1.0 - dn.light * 3)
    if brightness <= 0:
        return
    for (sx, sy, size, twinkle_phase) in stars:
        twinkle = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.003 + twinkle_phase)
        alpha   = int(brightness * twinkle * 220)
        col     = (alpha, alpha, min(255, alpha + 30))
        pygame.draw.circle(surf, col, (sx, sy), size)


# ─────────────────────────────────────────────────────────────────────────────
#  HUD helpers
# ─────────────────────────────────────────────────────────────────────────────
def draw_hotbar(surf, player, font, sfont):
    n      = len(HOTBAR_BLOCKS)
    slot_w = 54
    pad    = 5
    total  = n * (slot_w + pad) - pad
    x0     = (SCREEN_W - total) // 2
    y0     = SCREEN_H - 72

    bg = pygame.Surface((total + 16, slot_w + 16), pygame.SRCALPHA)
    bg.fill((20, 20, 20, 165))
    surf.blit(bg, (x0 - 8, y0 - 8))

    for i, bid in enumerate(HOTBAR_BLOCKS):
        sx  = x0 + i * (slot_w + pad)
        sel = (i == player.selected_slot)
        bw  = 3 if sel else 1
        bc  = (255, 215, 0) if sel else (80, 80, 80)
        pygame.draw.rect(surf, bc, (sx - bw, y0 - bw, slot_w + bw*2, slot_w + bw*2), bw)

        mini = 46
        off  = (slot_w - mini) // 2
        if bid in BLOCKS and BLOCKS[bid]:
            bd = BLOCKS[bid]
            pygame.draw.rect(surf, bd["top"],  (sx+off,      y0+off,      mini, mini//3))
            pygame.draw.rect(surf, bd["left"], (sx+off,      y0+off+mini//3, mini, (mini*2)//3))
            pygame.draw.rect(surf, darken(bd["left"],40),(sx+off,y0+off,mini,mini),1)

        num = sfont.render(str((i+1) % 10), True, (180,180,180))
        surf.blit(num, (sx + 3, y0 + 2))

    sel_bid = player.selected_block()
    if sel_bid in BLOCKS and BLOCKS[sel_bid]:
        label = font.render(BLOCKS[sel_bid]["name"], True, (255,255,255))
        surf.blit(label, ((SCREEN_W - label.get_width())//2, y0 - 24))


def draw_break_progress(surf, camera, bx, by, progress, max_progress):
    """Progress bar + crack overlay over the block being mined."""
    sx, sy = camera.w2s(bx, by)

    # Crack overlay
    stage    = min(9, int(progress / max_progress * 10))
    cracks   = get_crack_surfs()
    surf.blit(cracks[stage], (sx - ISO_W, sy - ISO_H))

    # Progress bar
    bar_w = TILE_W + ISO_W
    bar_h = 7
    bx0   = sx - ISO_W
    by0   = sy + TILE_H + ISO_H + 2
    pygame.draw.rect(surf, (30, 30, 30), (bx0, by0, bar_w, bar_h))
    fill = int((progress / max_progress) * (bar_w - 2))

    # colour shifts red→yellow→green as progress increases
    t   = progress / max_progress
    col = blend((200, 50, 50), (50, 220, 80), t)
    pygame.draw.rect(surf, col, (bx0 + 1, by0 + 1, fill, bar_h - 2))
    pygame.draw.rect(surf, (180, 180, 180), (bx0, by0, bar_w, bar_h), 1)


def draw_crosshair(surf):
    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    pygame.draw.line(surf, (255,255,255), (cx-13,cy), (cx+13,cy), 2)
    pygame.draw.line(surf, (255,255,255), (cx,cy-13), (cx,cy+13), 2)
    pygame.draw.circle(surf, (255,255,255), (cx,cy), 3, 1)


def draw_block_highlight(surf, camera, bx, by):
    sx, sy = camera.w2s(bx, by)
    s = pygame.Surface((TILE_W + ISO_W, TILE_H + ISO_H), pygame.SRCALPHA)
    s.fill((255,255,255,45))
    surf.blit(s, (sx - ISO_W, sy - ISO_H))
    # outline on front face
    pygame.draw.rect(surf, (255,255,255), (sx, sy, TILE_W - ISO_W, TILE_H), 2)


def draw_hud_info(surf, player, dn, font, sfont):
    light_pct = int(dn.light * 100)
    tod_map   = {(0.0,0.25):"🌅 Dawn",(0.25,0.50):"☀ Day",(0.50,0.75):"🌇 Dusk",(0.75,1.0):"🌙 Night"}
    tod = "Day"
    for (lo,hi),label in tod_map.items():
        if lo <= dn.frac < hi:
            tod = label
    info = f"Pos: {int(player.x)},{int(player.y)}  |  {tod}  |  Light: {light_pct}%"
    t = sfont.render(info, True, (255,255,255))
    surf.blit(t, (8, 8))

    lines = ["WASD/↑↓: Move+Jump","Hold LClick: Break (progress bar!)","RClick: Place","1-0 / Scroll: Select block","E: Inventory"]
    for i,ln in enumerate(lines):
        surf.blit(sfont.render(ln, True,(200,200,200)), (8, 28 + i*16))


def draw_inventory(surf, player, font, sfont):
    pw, ph = 510, 390
    px = (SCREEN_W - pw)//2
    py = (SCREEN_H - ph)//2
    bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
    bg.fill((25,25,25,225))
    surf.blit(bg,(px,py))
    pygame.draw.rect(surf,(110,110,110),(px,py,pw,ph),2)
    t = font.render("INVENTORY", True, (220,210,80))
    surf.blit(t, (px+pw//2-t.get_width()//2, py+10))

    cols,sz,pad = 5,66,10
    ox,oy = px+28, py+48
    for i,(bid,cnt) in enumerate(player.inventory.items()):
        row,col = divmod(i,cols)
        sx = ox + col*(sz+pad)
        sy = oy + row*(sz+pad)
        pygame.draw.rect(surf,(55,55,55),(sx,sy,sz,sz))
        pygame.draw.rect(surf,(95,95,95),(sx,sy,sz,sz),1)
        if bid in BLOCKS and BLOCKS[bid]:
            bd=BLOCKS[bid]
            pygame.draw.rect(surf,bd["top"], (sx+4,sy+4,sz-8,(sz-8)//3))
            pygame.draw.rect(surf,bd["left"],(sx+4,sy+4+(sz-8)//3,sz-8,(sz-8)*2//3))
            nm = sfont.render(BLOCKS[bid]["name"],True,(195,195,195))
            surf.blit(nm,(sx+sz//2-nm.get_width()//2, sy+sz-14))
    hint = sfont.render("Press E to close",True,(140,140,140))
    surf.blit(hint,(px+pw-hint.get_width()-10, py+ph-18))


def draw_night_overlay(surf, light):
    """Semi-transparent dark overlay during night."""
    darkness = int((1.0 - light) * 155)
    if darkness <= 0:
        return
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 25, darkness))
    surf.blit(ov, (0, 0))


# ─────────────────────────────────────────────────────────────────────────────
#  Draw player (3-D isometric mini-character)
# ─────────────────────────────────────────────────────────────────────────────
def draw_player(surf, camera, player, dn, anim_tick):
    sx, sy = camera.w2s(player.x, player.y)
    pw = int(player.width  * TILE_W)
    ph = int(player.height * TILE_H)
    nf = max(0.15, dn.light)

    skin_c  = tint((215,175,120), nf)
    body_c  = tint((65,115,200),  nf)
    leg_c   = tint((50,80,158),   nf)
    shoe_c  = tint((40,30,20),    nf)

    # Bob when walking
    bob = int(math.sin(anim_tick * 0.25) * 2) if not player.on_ground else 0

    # Body
    pygame.draw.rect(surf, body_c, (sx, sy + bob, pw, int(ph * 0.55)))
    # iso right-side of body
    right_pts = [(sx+pw, sy+bob),(sx+pw+6,sy+bob+4),(sx+pw+6,sy+bob+int(ph*0.55)+4),(sx+pw,sy+bob+int(ph*0.55))]
    pygame.draw.polygon(surf, darken(body_c,30), right_pts)

    # Head
    hs = int(pw * 1.25)
    hx = sx + pw//2 - hs//2
    hy = sy + bob - hs
    pygame.draw.rect(surf, skin_c, (hx, hy, hs, hs))
    # iso top of head
    top_pts = [(hx,hy),(hx+hs,hy),(hx+hs+6,hy+4),(hx+6,hy+4)]
    pygame.draw.polygon(surf, lighten(skin_c,20), top_pts)
    # iso right of head
    rh_pts  = [(hx+hs,hy),(hx+hs+6,hy+4),(hx+hs+6,hy+hs+4),(hx+hs,hy+hs)]
    pygame.draw.polygon(surf, darken(skin_c,25), rh_pts)
    # eyes
    ey = hy + hs//3
    pygame.draw.rect(surf,(25,25,25),(hx+4, ey,4,4))
    pygame.draw.rect(surf,(25,25,25),(hx+hs-8,ey,4,4))

    # Legs (animated)
    lw = pw//2 - 1
    lh = int(ph*0.35)
    ly = sy + bob + int(ph*0.55)
    leg_swing = int(math.sin(anim_tick * 0.25) * 5) if not player.on_ground else 0
    # left leg
    pygame.draw.rect(surf, leg_c,  (sx, ly - leg_swing, lw, lh))
    pygame.draw.rect(surf, shoe_c, (sx, ly - leg_swing + lh - 4, lw, 4))
    # right leg
    pygame.draw.rect(surf, leg_c,  (sx+lw+2, ly + leg_swing, lw, lh))
    pygame.draw.rect(surf, shoe_c, (sx+lw+2, ly + leg_swing + lh - 4, lw, 4))


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("MinePy 3D – with Day/Night & Block Breaking")
    clock  = pygame.time.Clock()

    try:
        font  = pygame.font.SysFont("Arial", 16, bold=True)
        sfont = pygame.font.SysFont("Arial", 12)
    except:
        font = sfont = pygame.font.Font(None, 18)

    print("Generating world…")
    world, heights = generate_world()

    spawn_x = WORLD_W // 2
    spawn_y = heights[spawn_x] - 5
    player  = Player(spawn_x, spawn_y)
    camera  = Camera()
    camera.x = player.x * TILE_W - SCREEN_W // 2
    camera.y = player.y * TILE_H - SCREEN_H // 2

    dn   = DayNight()
    dn.tick = int(DAY_LENGTH * 0.25)   # start at midday

    # Stars (fixed positions)
    random.seed(999)
    stars = [(random.randint(0,SCREEN_W), random.randint(0,SCREEN_H//2),
              random.randint(1,2), random.uniform(0,6.28))
             for _ in range(120)]

    show_inventory = False
    anim_tick      = 0

    # Block-break state
    breaking = {"bx": -1, "by": -1, "progress": 0, "held": False}

    sky_surf = pygame.Surface((SCREEN_W, SCREEN_H))

    print("World ready! Enjoy MinePy 3D 🎮")

    running = True
    while running:
        clock.tick(FPS)
        dn.update()

        mx, my   = pygame.mouse.get_pos()
        wx, wy   = camera.s2w(mx, my)
        hbx      = int(math.floor(wx))
        hby      = int(math.floor(wy))
        mouse_btns = pygame.mouse.get_pressed()

        # ── Events ──────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if   event.key == pygame.K_ESCAPE: running = False
                elif event.key == pygame.K_e:      show_inventory = not show_inventory
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    player.selected_slot = event.key - pygame.K_1
                elif event.key == pygame.K_0:
                    player.selected_slot = 9

            elif event.type == pygame.MOUSEWHEEL:
                player.selected_slot = (player.selected_slot - event.y) % len(HOTBAR_BLOCKS)

            elif event.type == pygame.MOUSEBUTTONDOWN and not show_inventory:
                dist = math.hypot(wx-(player.x+0.4), wy-(player.y+0.9))
                if event.button == 1:
                    if dist <= player.reach and 0<=hbx<WORLD_W and 0<=hby<WORLD_H:
                        breaking["bx"]       = hbx
                        breaking["by"]       = hby
                        breaking["progress"] = 0
                        breaking["held"]     = True

                elif event.button == 3:
                    if dist <= player.reach and 0<=hbx<WORLD_W and 0<=hby<WORLD_H:
                        if world[hby][hbx] == 0:
                            pr = pygame.Rect(int(player.x*TILE_W),int(player.y*TILE_H),
                                             int(player.width*TILE_W),int(player.height*TILE_H))
                            br = pygame.Rect(hbx*TILE_W, hby*TILE_H, TILE_W, TILE_H)
                            if not pr.colliderect(br):
                                world[hby][hbx] = player.selected_block()

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    breaking["held"]     = False
                    breaking["progress"] = 0

        # ── Breaking logic (hold LMB) ────────────────────────────────────────
        if breaking["held"] and not show_inventory:
            bx_, by_ = breaking["bx"], breaking["by"]
            dist = math.hypot(wx-(player.x+0.4), wy-(player.y+0.9))
            # If cursor moved to different block, reset
            if hbx != bx_ or hby != by_:
                breaking["bx"]       = hbx
                breaking["by"]       = hby
                breaking["progress"] = 0
            elif 0<=bx_<WORLD_W and 0<=by_<WORLD_H and world[by_][bx_] != 0:
                bid      = world[by_][bx_]
                max_prog = BREAK_TIMES.get(bid, 40)
                if bid not in (7, 10):   # unbreakable
                    breaking["progress"] += 1
                    if breaking["progress"] >= max_prog:
                        world[by_][bx_]      = 0
                        breaking["held"]     = False
                        breaking["progress"] = 0

        # ── Update ───────────────────────────────────────────────────────────
        if not show_inventory:
            keys = pygame.key.get_pressed()
            player.update(world, keys)
            if keys[pygame.K_a] or keys[pygame.K_d] or keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]:
                anim_tick += 1

        camera.update(player)
        light = dn.light

        # ── Draw sky ─────────────────────────────────────────────────────────
        top_c, bot_c = dn.sky_colors()
        draw_sky_gradient(sky_surf, top_c, bot_c)
        screen.blit(sky_surf, (0, 0))

        draw_stars(screen, stars, dn)
        draw_celestial_bodies(screen, dn)

        # ── Draw world blocks ────────────────────────────────────────────────
        nf   = max(0.12, light)
        bx0  = max(0, int(camera.x // TILE_W) - 1)
        bx1  = min(WORLD_W, bx0 + SCREEN_W // TILE_W + 4)
        by0  = max(0, int(camera.y // TILE_H) - 1)
        by1  = min(WORLD_H, by0 + SCREEN_H // TILE_H + 4)

        for by in range(by0, by1):
            for bx in range(bx0, bx1):
                bid = world[by][bx]
                if bid == 0:
                    continue
                sx, sy = camera.w2s(bx, by)
                bsurf  = get_block_surf(bx, by, bid, nf)
                # anchor: ISO offset so left-face top-left is at (sx,sy)
                screen.blit(bsurf, (sx - ISO_W, sy - ISO_H))

        # ── Block highlight + break progress ─────────────────────────────────
        dist = math.hypot(wx-(player.x+0.4), wy-(player.y+0.9))
        if dist <= player.reach and 0<=hbx<WORLD_W and 0<=hby<WORLD_H and world[hby][hbx]!=0:
            draw_block_highlight(screen, camera, hbx, hby)

        if breaking["held"]:
            bx_, by_ = breaking["bx"], breaking["by"]
            if 0<=bx_<WORLD_W and 0<=by_<WORLD_H and world[by_][bx_]!=0:
                bid      = world[by_][bx_]
                max_prog = BREAK_TIMES.get(bid, 40)
                draw_break_progress(screen, camera, bx_, by_,
                                    breaking["progress"], max_prog)

        # ── Player ───────────────────────────────────────────────────────────
        draw_player(screen, camera, player, dn, anim_tick)

        # ── Night overlay ────────────────────────────────────────────────────
        draw_night_overlay(screen, light)

        # ── HUD ──────────────────────────────────────────────────────────────
        draw_crosshair(screen)
        draw_hotbar(screen, player, font, sfont)
        draw_hud_info(screen, player, dn, font, sfont)

        if show_inventory:
            draw_inventory(screen, player, font, sfont)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()