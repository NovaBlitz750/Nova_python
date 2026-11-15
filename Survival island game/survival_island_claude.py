#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SURVIVAL ISLAND  -  pygame edition
=================================
Your helicopter crashed on a tropical island. Gather resources, craft tools,
hunt, fish, cook, survive the night and repair the helicopter to escape!

Install:  pip install pygame
Run:      python survival_island_pygame.py

CONTROLS
  W A S D / Arrows ... move            Shift ........ sprint
  Mouse .............. aim / target    Hold LEFT .... mine / chop / attack
  RIGHT click ........ use / eat / place / cast & reel fishing rod / shoot bow
                       / open chests / cook (on a campfire) / repair
  1-9 / Mouse wheel .. select hotbar   E ............ inventory + crafting
  M .................. map (needs Map) Q ............ drop held item
  H / F1 ............. help            Esc .......... pause
"""
import math
import random
import sys

import pygame

# ============================================================== CONFIG
TILE = 48                 # pixels per world tile on screen
TEX = 16                  # pixels per generated texture (scaled up -> chunky!)
SW, SH = 1024, 640
FPS = 60
WW, WH = 112, 112         # world size in tiles
REACH = 3.6               # how far you can reach (tiles)
DAY_LENGTH = 300.0        # seconds for a full day/night cycle
START_PHASE = 0.30        # start in the morning
STACK = 64

# ground ids
DEEP, WATER, SAND, GRASS, JUNGLE, HILL, FLOOR = range(7)
LAND = (SAND, GRASS, JUNGLE, HILL)

MAP_COL = {DEEP: (22, 44, 110), WATER: (46, 100, 190), SAND: (225, 210, 152),
           GRASS: (104, 164, 62), JUNGLE: (52, 122, 52), HILL: (132, 132, 138),
           FLOOR: (156, 112, 62)}

SOLID_OBJ = {"tree", "palm", "rock", "bush", "wall", "cupboard", "shelf",
             "chest", "heli", "campfire", "plank"}

# --------------------------------------------------------------- items
FOOD = {"Bread": 10, "Fish": 15, "Crab": 10, "Cooked Meat": 30, "Raw Meat": 5,
        "Cooked Fish": 25, "Cooked Crab": 20, "Coconut": 8, "Seaweed": 3}
COOK = {"Raw Meat": "Cooked Meat", "Fish": "Cooked Fish", "Crab": "Cooked Crab"}
TOOL_DUR = {"Stone Axe": 40, "Stone Knife": 35, "Fishing Rod": 25, "Bow": 45}
WEAPON_DMG = {"Stone Axe": 6, "Stone Knife": 5, "Bow": 2}
PLACEABLE = {"Campfire": "campfire", "Torch": "torch", "Planks": "plank"}
REQUIRED_ITEMS = ["Gasoline Can", "Duct Tape", "Helicopter Manual"]
FISH_LOOT = ["Fish", "Fish", "Fish", "Seaweed", "Crab", "empty", "Stone Axe", "Empty Bottle"]

RECIPES = [
    {"out": "Stone Axe",    "n": 1, "need": {"Branches": 2, "Stones": 2, "Vines": 2}, "info": "40 uses. Chops trees fast."},
    {"out": "Stone Knife",  "n": 1, "need": {"Branches": 1, "Stones": 1, "Vines": 1}, "info": "35 uses. Better hunting drops."},
    {"out": "Fishing Rod",  "n": 1, "need": {"Branches": 2, "Vines": 3},              "info": "25 uses. Fish from the shore."},
    {"out": "Bow",          "n": 1, "need": {"Branches": 3, "Vines": 3},              "info": "45 uses. Shoot from a distance."},
    {"out": "Arrow",        "n": 3, "need": {"Branches": 1, "Stones": 1, "Vines": 1}, "info": "Ammo for the bow (makes 3)."},
    {"out": "Campfire",     "n": 1, "need": {"Branches": 7, "Vines": 5, "Stones": 2}, "keep": {"Stones"}, "info": "Cook food. Lights the night."},
    {"out": "Torch",        "n": 2, "need": {"Branches": 1, "Vines": 1},              "info": "Hold or place to see in the dark."},
    {"out": "Planks",       "n": 2, "need": {"Branches": 4},                          "info": "Placeable wall blocks."},
]

BREAK_TIME = {"tree": 3.2, "palm": 2.4, "rock": 2.4, "bush": 0.8, "plank": 1.0,
              "campfire": 0.6, "torch": 0.1, "glint": 0.6, "sapling": 0.2, "bare_bush": 0.3}
OBJ_PARTICLE = {"tree": (50, 120, 44), "palm": (80, 160, 60), "rock": (130, 130, 135),
                "bush": (60, 150, 60), "bare_bush": (120, 90, 50), "plank": (170, 130, 76),
                "campfire": (110, 80, 40), "torch": (110, 80, 40), "glint": (230, 200, 100),
                "sapling": (80, 170, 70)}

MOBS = {
    "Wild Boar": dict(hp=20, r=0.38, speed=1.1, chase=3.5, dmg=14, hostile=True, aggro=6.0,
                      drop=("Raw Meat", 2, 4)),
    "Snake":     dict(hp=8, r=0.25, speed=0.9, chase=3.1, dmg=8, hostile=True, aggro=4.5,
                      drop=("Raw Meat", 0, 1)),
    "Rabbit":    dict(hp=4, r=0.22, speed=0.8, flee=4.0, fleespeed=4.4, hostile=False,
                      drop=("Raw Meat", 1, 2)),
    "Crab":      dict(hp=6, r=0.25, speed=0.5, flee=1.6, fleespeed=1.3, hostile=False,
                      drop=("Crab", 1, 1)),
}

SPLASHES = ["Now with pygame!", "Don't starve!", "Watch out for boars!", "Craft it!",
            "Beware the night!", "Hold the line... then reel!", "Helicopter not included!",
            "Also try the snake!", "Coconuts!", "Sprint is hungry work!", "100% blocky!",
            "Torches are your friends!", "Rescue pending..."]


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def cc(r, g, b, a=None):
    r, g, b = clamp(int(r), 0, 255), clamp(int(g), 0, 255), clamp(int(b), 0, 255)
    return (r, g, b) if a is None else (r, g, b, clamp(int(a), 0, 255))


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================== WORLD GEN
class Noise:
    def __init__(self, seed, cell):
        rnd = random.Random(seed)
        self.cell = cell
        n = max(WW, WH) // cell + 4
        self.g = [[rnd.random() for _ in range(n)] for _ in range(n)]

    def get(self, x, y):
        fx, fy = x / self.cell, y / self.cell
        x0, y0 = int(fx), int(fy)
        tx, ty = fx - x0, fy - y0
        tx = tx * tx * (3 - 2 * tx)
        ty = ty * ty * (3 - 2 * ty)
        a, b = self.g[y0][x0], self.g[y0][x0 + 1]
        c, d = self.g[y0 + 1][x0], self.g[y0 + 1][x0 + 1]
        return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty


class World:
    def __init__(self, seed=None):
        self.seed = seed if seed is not None else random.randrange(10 ** 9)
        self.rnd = rnd = random.Random(self.seed)
        n1 = Noise(rnd.randrange(10 ** 9), 28)
        n2 = Noise(rnd.randrange(10 ** 9), 14)
        n3 = Noise(rnd.randrange(10 ** 9), 7)
        nm = Noise(rnd.randrange(10 ** 9), 18)
        self.ground = [[DEEP] * WW for _ in range(WH)]
        self.obj = [[None] * WW for _ in range(WH)]
        self.chests = {}
        self.reserved = set()
        self.structs = {}
        self.heli_origin = None
        elev = [[0.0] * WW for _ in range(WH)]
        cx, cy = WW / 2, WH / 2
        for y in range(WH):
            for x in range(WW):
                d = math.hypot((x - cx) / (WW / 2), (y - cy) / (WH / 2))
                e = 0.55 * n1.get(x, y) + 0.30 * n2.get(x, y) + 0.15 * n3.get(x, y)
                e = e * 0.75 + (1 - d ** 1.6) * 0.55 - 0.18
                elev[y][x] = e
                if x < 2 or y < 2 or x > WW - 3 or y > WH - 3 or e < 0.24:
                    g = DEEP
                elif e < 0.31:
                    g = WATER
                elif e < 0.39:
                    g = SAND
                elif e < 0.66:
                    g = JUNGLE if nm.get(x, y) > 0.47 else GRASS
                else:
                    g = HILL
                self.ground[y][x] = g
        self._keep_main_island(elev)
        self._scatter_objects()
        self.spawn = self._pick_spawn()
        self._build_structures()
        self._starter_resources()

    # ---- helpers
    def _keep_main_island(self, elev):
        best, bp = -1, (WW // 2, WH // 2)
        for y in range(WH):
            for x in range(WW):
                if self.ground[y][x] in LAND and elev[y][x] > best:
                    best, bp = elev[y][x], (x, y)
        seen = {bp}
        stack = [bp]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < WW and 0 <= ny < WH and (nx, ny) not in seen \
                        and self.ground[ny][nx] in LAND:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        for y in range(WH):
            for x in range(WW):
                if self.ground[y][x] in LAND and (x, y) not in seen:
                    self.ground[y][x] = WATER

    def _scatter_objects(self):
        rnd = self.rnd
        for y in range(WH):
            for x in range(WW):
                g, r, o = self.ground[y][x], rnd.random(), None
                if g == JUNGLE:
                    o = "tree" if r < 0.30 else "bush" if r < 0.37 else "rock" if r < 0.40 else None
                elif g == GRASS:
                    o = "tree" if r < 0.07 else "bush" if r < 0.11 else "rock" if r < 0.14 else None
                elif g == SAND:
                    o = "palm" if r < 0.012 else "rock" if r < 0.018 else None
                elif g == HILL:
                    o = "rock" if r < 0.10 else "tree" if r < 0.11 else None
                self.obj[y][x] = o

    def _pick_spawn(self):
        cands = []
        for y in range(5, WH - 5):
            for x in range(5, WW - 5):
                if self.ground[y][x] == SAND:
                    ok = True
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            if self.ground[y + dy][x + dx] == DEEP:
                                ok = False
                    if ok:
                        cands.append((x, y))
        if not cands:
            cands = [(x, y) for y in range(WH) for x in range(WW) if self.ground[y][x] in LAND]
        cands.sort(key=lambda p: -math.hypot(p[0] - WW / 2, p[1] - WH / 2))
        top = cands[:max(1, len(cands) // 6)]
        x, y = self.rnd.choice(top)
        return (x + 0.5, y + 0.5)

    def free_rect(self, x, y, w, h, allowed, margin=1):
        for yy in range(y - margin, y + h + margin):
            for xx in range(x - margin, x + w + margin):
                if not (0 <= xx < WW and 0 <= yy < WH):
                    return False
                if self.ground[yy][xx] not in allowed or (xx, yy) in self.reserved:
                    return False
        return True

    def find_spot(self, w, h, allowed, pref=None, tries=6000):
        rnd = self.rnd
        for i in range(tries):
            x, y = rnd.randrange(3, WW - w - 3), rnd.randrange(3, WH - h - 3)
            if self.free_rect(x, y, w, h, allowed) and (pref is None or i > tries // 2 or pref(x, y)):
                return x, y
        return None

    def reserve(self, x, y, w, h, margin=2):
        for yy in range(y - margin, y + h + margin):
            for xx in range(x - margin, x + w + margin):
                self.reserved.add((xx, yy))

    def _clear(self, x, y, w, h):
        for yy in range(y - 1, y + h + 1):
            for xx in range(x - 1, x + w + 1):
                if 0 <= xx < WW and 0 <= yy < WH:
                    self.obj[yy][xx] = None

    def _house(self, x, y, w, h, door_x):
        self._clear(x, y, w, h)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.ground[yy][xx] = FLOOR
                edge = xx in (x, x + w - 1) or yy in (y, y + h - 1)
                self.obj[yy][xx] = "wall" if edge else None
        self.obj[y + h - 1][x + door_x] = "door"
        self.reserve(x, y, w, h)

    def _build_structures(self):
        sx, sy = self.spawn
        # ----- boathouse (near water, reasonably near the player)
        def pref_boat(x, y):
            d = math.hypot(x - sx, y - sy)
            water = any(0 <= y + 5 + k < WH and self.ground[y + 5 + k][x + 2] == WATER for k in range(4))
            return 12 < d < 42 and water
        spot = self.find_spot(5, 4, {SAND, GRASS}, pref_boat) or \
            (int(clamp(sx + 7, 3, WW - 9)), int(clamp(sy - 7, 3, WH - 9)))
        bx, by = spot
        self._house(bx, by, 5, 4, 2)
        self.obj[by + 1][bx + 1] = "cupboard"
        self.obj[by + 1][bx + 3] = "shelf"
        self.chests[(bx + 1, by + 1)] = {"opened": False, "yanks": self.rnd.randint(2, 8)}
        self.chests[(bx + 3, by + 1)] = {"opened": False}
        self.structs["boathouse"] = (bx + 2, by + 1)
        # ----- cabin in the jungle
        def pref_cabin(x, y):
            return self.ground[y + 1][x + 1] == JUNGLE and 18 < math.hypot(x - sx, y - sy) < 60
        spot = self.find_spot(4, 4, {JUNGLE, GRASS}, pref_cabin) or \
            self.find_spot(4, 4, {JUNGLE, GRASS, HILL, SAND}) or \
            (int(clamp(sx - 12, 3, WW - 8)), int(clamp(sy - 12, 3, WH - 8)))
        cx, cy = spot
        self._house(cx, cy, 4, 4, 1)
        self.obj[cy + 1][cx + 2] = "chest"
        self.chests[(cx + 2, cy + 1)] = {"opened": False}
        self.structs["cabin"] = (cx + 1, cy + 1)
        # ----- helicopter crash site on the hills, nearest the island centre
        hills = [(x, y) for y in range(3, WH - 6) for x in range(3, WW - 7) if self.ground[y][x] == HILL]
        hills.sort(key=lambda p: math.hypot(p[0] - WW / 2, p[1] - WH / 2))
        hx = hy = None
        for allowed in ({HILL}, {HILL, GRASS, JUNGLE}):
            for (x, y) in hills:
                if self.free_rect(x, y, 3, 2, allowed):
                    hx, hy = x, y
                    break
            if hx is not None:
                break
        if hx is None:
            hx, hy = WW // 2 - 1, WH // 2 - 1
        self._clear(hx, hy, 3, 2)
        for yy in range(hy - 1, hy + 3):
            for xx in range(hx - 1, hx + 4):
                if self.ground[yy][xx] in (DEEP, WATER):
                    self.ground[yy][xx] = HILL
        for yy in range(hy, hy + 2):
            for xx in range(hx, hx + 3):
                self.obj[yy][xx] = "heli"
        self.heli_origin = (hx, hy)
        self.reserve(hx, hy, 3, 2)
        self.structs["crash"] = (hx + 1.5, hy + 1)
        # ----- the buried key on the beach
        sands = [(x, y) for y in range(WH) for x in range(WW)
                 if self.ground[y][x] == SAND and self.obj[y][x] is None
                 and (x, y) not in self.reserved and 6 < math.hypot(x - sx, y - sy) < 30]
        if not sands:
            sands = [(int(sx) + 2, int(sy))]
        kx, ky = self.rnd.choice(sands)
        self.obj[ky][kx] = "glint"
        self.structs["key"] = (kx, ky)

    def _starter_resources(self):
        sx, sy = int(self.spawn[0]), int(self.spawn[1])
        rnd = self.rnd
        want = ["palm", "palm", "palm", "bush", "bush", "bush", "bush", "rock", "rock", "rock", "rock"]
        tiles = [(x, y) for y in range(sy - 9, sy + 10) for x in range(sx - 9, sx + 10)
                 if 0 <= x < WW and 0 <= y < WH and 3 <= math.hypot(x - sx, y - sy) <= 9
                 and self.ground[y][x] in (SAND, GRASS, JUNGLE) and self.obj[y][x] is None
                 and (x, y) not in self.reserved]
        rnd.shuffle(tiles)
        for o, (x, y) in zip(want, tiles):
            self.obj[y][x] = o

    def rand_tile(self, grounds, min_spawn=9, tries=400):
        sx, sy = self.spawn
        for _ in range(tries):
            x, y = self.rnd.randrange(WW), self.rnd.randrange(WH)
            if self.ground[y][x] in grounds and self.obj[y][x] is None and (x, y) not in self.reserved \
                    and math.hypot(x - sx, y - sy) > min_spawn:
                return x + 0.5, y + 0.5
        return None


# ============================================================== INVENTORY
class Inventory:
    def __init__(self):
        self.slots = [None] * 36          # 0-8 hotbar, 9-35 backpack

    def can_add(self, name):
        if name in TOOL_DUR:
            return any(s is None for s in self.slots)
        return any(s is None or (s["name"] == name and s["n"] < STACK) for s in self.slots)

    def add(self, name, n=1, dur=None):
        """Returns how many items did NOT fit."""
        if name in TOOL_DUR:
            left = n
            for i, s in enumerate(self.slots):
                if left <= 0:
                    break
                if s is None:
                    self.slots[i] = {"name": name, "n": 1, "dur": dur if dur is not None else TOOL_DUR[name]}
                    left -= 1
            return left
        for s in self.slots:
            if s and s["name"] == name and s["n"] < STACK:
                put = min(n, STACK - s["n"])
                s["n"] += put
                n -= put
                if n <= 0:
                    return 0
        for i, s in enumerate(self.slots):
            if s is None:
                put = min(n, STACK)
                self.slots[i] = {"name": name, "n": put, "dur": None}
                n -= put
                if n <= 0:
                    return 0
        return n

    def count(self, name):
        return sum(s["n"] for s in self.slots if s and s["name"] == name)

    def remove(self, name, n):
        for i in range(len(self.slots) - 1, -1, -1):
            s = self.slots[i]
            if s and s["name"] == name and n > 0:
                take = min(n, s["n"])
                s["n"] -= take
                n -= take
                if s["n"] <= 0:
                    self.slots[i] = None
        return n <= 0


# ============================================================== ENTITIES
class Mob:
    def __init__(self, kind, x, y):
        spec = MOBS[kind]
        self.kind, self.x, self.y = kind, x, y
        self.hp = self.maxhp = spec["hp"]
        self.face = random.choice((-1, 1))
        self.timer = random.uniform(0, 3)
        self.dir = (0.0, 0.0)
        self.cd = 0.0
        self.hurt = 0.0
        self.kx = self.ky = 0.0
        self.aggro = False
        self.flee_t = 0.0


class Drop:
    def __init__(self, x, y, name, n=1, dur=None, delay=0.6, pop=True):
        self.x, self.y, self.name, self.n, self.dur = x, y, name, n, dur
        a, sp = random.uniform(0, math.tau), (random.uniform(1.0, 2.4) if pop else 0.0)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        self.delay = delay
        self.age = random.uniform(0, 6)


# ============================================================== TEXT
def draw_text(surf, txt, font, color, pos, anchor="topleft", shadow=True):
    if not txt:
        return pygame.Rect(pos, (0, 0))
    img = font.render(txt, True, color)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(font.render(txt, True, (28, 28, 28)), r.move(2, 2))
    surf.blit(img, r)
    return r


# ============================================================== GAME
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.f_s = pygame.font.Font(None, 20)
        self.f_m = pygame.font.Font(None, 28)
        self.f_l = pygame.font.Font(None, 48)
        self.f_xl = pygame.font.Font(None, 110)
        self.anim = 0.0
        self.build_assets()
        self.dark = pygame.Surface((SW, SH), pygame.SRCALPHA)
        self.state = "title"
        self.help_return = "title"
        self.splash = random.choice(SPLASHES)
        self.btns = []
        self.shake = 0.0
        self.new_game()

    # the player acts as an entity for move_ent()
    @property
    def x(self):
        return self.px

    @x.setter
    def x(self, v):
        self.px = v

    @property
    def y(self):
        return self.py

    @y.setter
    def y(self, v):
        self.py = v

    # ---------------------------------------------------------- assets
    def build_assets(self):
        def sc(s):
            return pygame.transform.scale(s, (TILE, TILE))

        def noise_tex(base, var, seed, speck=None, nspeck=0):
            s = pygame.Surface((TEX, TEX))
            r = random.Random(seed)
            for y in range(TEX):
                for x in range(TEX):
                    v = r.randint(-var, var)
                    s.set_at((x, y), cc(base[0] + v, base[1] + v, base[2] + v))
            if speck:
                for _ in range(nspeck):
                    s.set_at((r.randrange(TEX), r.randrange(TEX)), speck)
            return s

        g = {}
        g[GRASS] = []
        for i in range(4):
            s = noise_tex((92, 152, 58), 10, 100 + i, (68, 122, 44), 14)
            r = random.Random(500 + i)
            if r.random() < 0.5:
                s.set_at((r.randrange(TEX), r.randrange(TEX)), r.choice([(240, 220, 70), (230, 90, 110), (250, 250, 250)]))
            g[GRASS].append(sc(s).convert())
        g[JUNGLE] = [sc(noise_tex((46, 112, 46), 9, 200 + i, (28, 84, 34), 18)).convert() for i in range(4)]
        g[SAND] = [sc(noise_tex((222, 206, 152), 8, 300 + i, (196, 176, 122), 12)).convert() for i in range(4)]
        hills = []
        for i in range(4):
            s = noise_tex((128, 128, 131), 12, 400 + i, (96, 96, 100), 16)
            r = random.Random(900 + i)
            x, y = r.randrange(3, 13), r.randrange(3, 13)
            for _ in range(8):
                s.set_at((clamp(x, 0, 15), clamp(y, 0, 15)), (84, 84, 88))
                x += r.choice((-1, 0, 1))
                y += r.choice((0, 1))
            hills.append(sc(s).convert())
        g[HILL] = hills
        floors = []
        for i in range(4):
            s = noise_tex((166, 124, 72), 6, 600 + i)
            for y in range(TEX):
                for x in range(TEX):
                    if y % 4 == 0:
                        s.set_at((x, y), (116, 82, 44))
                    elif (x == 5 and (y // 4) % 2 == 0) or (x == 12 and (y // 4) % 2 == 1):
                        s.set_at((x, y), (120, 86, 46))
            floors.append(sc(s).convert())
        g[FLOOR] = floors
        self.tex_ground = g

        def water(base, phase, seed):
            s = pygame.Surface((TEX, TEX))
            r = random.Random(seed)
            for y in range(TEX):
                for x in range(TEX):
                    v = r.randint(-5, 5)
                    c = (base[0] + v, base[1] + v, base[2] + v)
                    if (x + y * 2 + phase * 4) % 9 < 2:
                        c = (c[0] + 28, c[1] + 28, c[2] + 20)
                    s.set_at((x, y), cc(*c))
            return sc(s).convert()
        self.tex_water = [[water((50, 104, 205), ph, 10 + ph + v) for v in range(2)] for ph in range(2)]
        self.tex_deep = [[water((28, 62, 150), ph, 20 + ph + v) for v in range(2)] for ph in range(2)]

        # ---- objects (alpha textures)
        def blank():
            return pygame.Surface((TEX, TEX), pygame.SRCALPHA)

        def tree(seed):
            s, r = blank(), random.Random(seed)
            greens = [(34, 98, 34), (44, 120, 40), (58, 140, 48), (28, 80, 30)]
            for y in range(TEX):
                for x in range(TEX):
                    if math.hypot(x - 7.5, y - 7.5) < 7.4 + r.uniform(-0.6, 0.3):
                        c = r.choice(greens)
                        if x + y < 10:
                            c = cc(c[0] + 16, c[1] + 20, c[2] + 10)
                        if x + y > 20:
                            c = cc(c[0] - 14, c[1] - 16, c[2] - 8)
                        s.set_at((x, y), c)
            for p in ((7, 7), (8, 7), (7, 8), (8, 8)):
                s.set_at(p, (96, 64, 30))
            return s

        def palm(seed):
            s, r = blank(), random.Random(seed)
            for a in range(7):
                ang = a * math.tau / 7 + r.uniform(-0.2, 0.2)
                for t in range(0, 8):
                    x, y = 7.5 + math.cos(ang) * t, 7.5 + math.sin(ang) * t
                    c = (60, 160, 60) if t % 2 else (40, 130, 50)
                    for ox, oy in ((0, 0), (1, 0), (0, 1)) if 1 < t < 6 else ((0, 0),):
                        px, py = int(x) + ox, int(y) + oy
                        if 0 <= px < TEX and 0 <= py < TEX:
                            s.set_at((px, py), c)
            for p in ((7, 7), (8, 7), (7, 8), (8, 8)):
                s.set_at(p, (112, 72, 32))
            return s

        def rock(seed):
            s, r = blank(), random.Random(seed)
            for y in range(TEX):
                for x in range(TEX):
                    if math.hypot(x - 7.5, y - 8) < 6 + r.uniform(-0.8, 0.5):
                        v = 134 + r.randint(-8, 8) + (14 if x + y < 12 else -18 if x + y > 18 else 0)
                        s.set_at((x, y), cc(v, v, v + 4))
            return s

        def bush(seed, bare=False):
            s, r = blank(), random.Random(seed)
            for y in range(TEX):
                for x in range(TEX):
                    if bare:
                        if r.random() < 0.10 and math.hypot(x - 7.5, y - 7.5) < 6:
                            s.set_at((x, y), (118, 86, 48))
                    elif math.hypot(x - 7.5, y - 8) < 5.6 + r.uniform(-0.7, 0.5):
                        s.set_at((x, y), r.choice([(46, 130, 50), (62, 154, 60), (36, 106, 44)]))
            if not bare:
                for _ in range(4):
                    s.set_at((r.randrange(4, 12), r.randrange(4, 12)), (214, 60, 90))
            else:
                for i in range(5):
                    s.set_at((4 + i * 2, 5 + (i % 3) * 2), (88, 60, 30))
            return s

        def wall():
            s = pygame.Surface((TEX, TEX))
            r = random.Random(77)
            for y in range(TEX):
                for x in range(TEX):
                    v = r.randint(-5, 5)
                    c = (118 + v, 80 + v, 42 + v)
                    if y % 4 == 0:
                        c = (146, 104, 58)
                    elif y % 4 == 3:
                        c = (82, 54, 26)
                    s.set_at((x, y), cc(*c))
            return s

        def plank_block():
            s = pygame.Surface((TEX, TEX))
            r = random.Random(78)
            for y in range(TEX):
                for x in range(TEX):
                    v = r.randint(-5, 5)
                    c = (176 + v, 136 + v, 80 + v)
                    if y % 4 == 3:
                        c = (126, 92, 50)
                    elif (x == 4 and (y // 4) % 2 == 0) or (x == 11 and (y // 4) % 2 == 1):
                        c = (126, 92, 50)
                    s.set_at((x, y), cc(*c))
            return s

        def rect(s, x, y, w, h, c):
            pygame.draw.rect(s, c, (x, y, w, h))

        def chest():
            s = blank()
            rect(s, 2, 4, 12, 9, (70, 44, 18))
            rect(s, 3, 5, 10, 7, (150, 100, 44))
            rect(s, 3, 7, 10, 1, (80, 50, 20))
            rect(s, 7, 6, 2, 4, (240, 200, 60))
            return s

        def cupboard():
            s = blank()
            rect(s, 1, 1, 14, 14, (60, 46, 36))
            rect(s, 2, 2, 12, 12, (112, 90, 70))
            rect(s, 7, 2, 2, 12, (60, 46, 36))
            rect(s, 6, 7, 1, 2, (240, 200, 60))
            rect(s, 9, 7, 1, 2, (240, 200, 60))
            for p in ((3, 4), (4, 9), (11, 5), (12, 11), (10, 12)):
                s.set_at(p, (176, 98, 40))
            return s

        def shelf():
            s = blank()
            rect(s, 1, 1, 14, 14, (70, 46, 22))
            rect(s, 2, 2, 12, 12, (140, 98, 52))
            rect(s, 2, 7, 12, 1, (70, 46, 22))
            for (x, y, c) in ((3, 4, (200, 60, 60)), (6, 4, (60, 120, 200)), (10, 4, (240, 220, 120)),
                              (4, 10, (230, 200, 140)), (8, 10, (90, 170, 80)), (11, 10, (200, 60, 60))):
                rect(s, x, y, 2, 3, c)
            return s

        def campfire():
            s = blank()
            for a in range(10):
                ang = a * math.tau / 10
                rect(s, int(7.5 + math.cos(ang) * 6.2), int(7.5 + math.sin(ang) * 6.2), 2, 2, (112, 112, 118))
            pygame.draw.line(s, (96, 62, 28), (3, 12), (12, 4), 2)
            pygame.draw.line(s, (116, 76, 36), (3, 4), (12, 12), 2)
            return s

        def torch():
            s = blank()
            rect(s, 7, 6, 2, 8, (110, 74, 34))
            rect(s, 7, 5, 2, 2, (60, 40, 20))
            return s

        def glint():
            s = blank()
            pygame.draw.ellipse(s, (190, 166, 108), (3, 6, 10, 7))
            pygame.draw.ellipse(s, (206, 184, 128), (4, 6, 8, 5))
            s.set_at((8, 8), (255, 220, 80))
            return s

        def sapling():
            s = blank()
            rect(s, 7, 9, 2, 4, (100, 70, 34))
            for (x, y) in ((5, 7), (6, 6), (9, 6), (10, 7), (7, 5), (8, 5)):
                rect(s, x, y, 2, 2, (70, 170, 70))
            return s

        def door():
            s = blank()
            rect(s, 1, 0, 3, 16, (88, 58, 28))
            rect(s, 2, 0, 1, 16, (122, 84, 42))
            rect(s, 3, 7, 1, 2, (240, 200, 60))
            return s

        objs = {
            "tree": [tree(1), tree(2), tree(3)], "palm": [palm(4), palm(5)],
            "rock": [rock(6), rock(7), rock(8)], "bush": [bush(9), bush(10)],
            "bare_bush": [bush(11, True)], "wall": [wall()], "plank": [plank_block()],
            "chest": [chest()], "cupboard": [cupboard()], "shelf": [shelf()],
            "campfire": [campfire()], "torch": [torch()], "glint": [glint()],
            "sapling": [sapling()], "door": [door()],
        }
        self.tex_obj = {k: [sc(s).convert_alpha() for s in v] for k, v in objs.items()}

        # ---- crashed helicopter (3x2 tiles, drawn at full size)
        h = pygame.Surface((TILE * 3, TILE * 2), pygame.SRCALPHA)
        pygame.draw.rect(h, (56, 64, 78), (86, 36, 50, 14))          # tail boom
        pygame.draw.polygon(h, (56, 64, 78), [(124, 36), (140, 14), (144, 18), (136, 40)])
        pygame.draw.ellipse(h, (170, 44, 40), (6, 22, 104, 58))      # hull
        pygame.draw.ellipse(h, (196, 58, 50), (10, 24, 92, 40))
        pygame.draw.ellipse(h, (150, 200, 228), (14, 32, 44, 28))    # cockpit glass
        pygame.draw.line(h, (230, 245, 250), (24, 36), (40, 54), 2)
        pygame.draw.line(h, (30, 30, 36), (20, 50), (34, 38), 2)
        pygame.draw.line(h, (40, 40, 44), (10, 88), (108, 88), 5)     # skid
        pygame.draw.line(h, (40, 40, 44), (30, 78), (28, 88), 4)
        pygame.draw.line(h, (40, 40, 44), (86, 78), (88, 88), 4)
        pygame.draw.line(h, (36, 36, 40), (58, 22), (6, 6), 6)        # rotor (bent)
        pygame.draw.line(h, (36, 36, 40), (58, 22), (112, 12), 6)
        pygame.draw.line(h, (36, 36, 40), (112, 12), (126, 24), 5)
        pygame.draw.circle(h, (30, 30, 34), (58, 22), 6)
        pygame.draw.circle(h, (14, 14, 16), (64, 46), 14)
        pygame.draw.circle(h, (24, 24, 26), (72, 56), 9)
        self.heli_img = h

        # ---- cracks for mining
        self.cracks = []
        r = random.Random(4242)
        for stage in range(1, 11):
            s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            for _ in range(stage * 2):
                x, y = TILE / 2 + r.uniform(-5, 5), TILE / 2 + r.uniform(-5, 5)
                a = r.uniform(0, math.tau)
                pts = [(x, y)]
                for _ in range(2 + stage // 3):
                    a += r.uniform(-0.6, 0.6)
                    x += math.cos(a) * r.uniform(4, 9)
                    y += math.sin(a) * r.uniform(4, 9)
                    pts.append((x, y))
                pygame.draw.lines(s, (20, 20, 20, 170), False, pts, 2)
            self.cracks.append(s)

        # ---- HUD icons
        self.icon_cache = {}
        self.icon_small = {}
        self.heart = {}
        for kind in ("full", "half", "empty"):
            s = pygame.Surface((20, 20), pygame.SRCALPHA)
            for col, off, rad in (((40, 10, 10), 0, 5.5), ((225, 30, 40), 0, 4.5)):
                pygame.draw.circle(s, col, (6, 7), rad)
                pygame.draw.circle(s, col, (14, 7), rad)
                pygame.draw.polygon(s, col, [(0.5, 9), (19.5, 9), (10, 19)] if rad > 5 else [(1.5, 9), (18.5, 9), (10, 17.5)])
            if kind != "full":
                inner = pygame.Surface((20, 20), pygame.SRCALPHA)
                pygame.draw.circle(inner, (50, 20, 20), (6, 7), 4.5)
                pygame.draw.circle(inner, (50, 20, 20), (14, 7), 4.5)
                pygame.draw.polygon(inner, (50, 20, 20), [(1.5, 9), (18.5, 9), (10, 17.5)])
                if kind == "half":
                    inner.fill((0, 0, 0, 0), (0, 0, 10, 20))
                s.blit(inner, (0, 0))
                if kind == "half":
                    pygame.draw.circle(s, (225, 30, 40), (6, 7), 4.5)
                    pygame.draw.polygon(s, (225, 30, 40), [(1.5, 9), (10, 9), (10, 17.5)])
            self.heart[kind] = s
        self.drum = {}
        for kind in ("full", "half", "empty"):
            s = pygame.Surface((20, 20), pygame.SRCALPHA)
            body = (200, 118, 52) if kind != "empty" else (70, 50, 40)
            pygame.draw.circle(s, (60, 34, 14), (7, 12), 7)
            pygame.draw.circle(s, body, (7, 12), 6)
            if kind == "half":
                pygame.draw.circle(s, (70, 50, 40), (7, 12), 6)
                pygame.draw.polygon(s, (200, 118, 52), [(7, 6), (1, 12), (7, 18)])
            pygame.draw.line(s, (240, 236, 220), (11, 8), (17, 2), 3)
            pygame.draw.circle(s, (240, 236, 220), (17, 2), 2)
            pygame.draw.circle(s, (240, 236, 220), (18, 4), 2)
            self.drum[kind] = s

        # ---- misc
        self.shadow = pygame.Surface((TILE, TILE // 2), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 70), (0, 0, TILE, TILE // 2))
        self.mob_sprites = self.build_mob_sprites()
        self.light_cache = {}
        self.dirt = pygame.transform.scale(noise_tex((118, 84, 58), 14, 31337, (80, 56, 38), 30), (64, 64)).convert()

    def build_mob_sprites(self):
        u = 3
        out = {}

        def surf(w, h):
            return pygame.Surface((w * u, h * u), pygame.SRCALPHA)

        def R(s, x, y, w, h, c):
            pygame.draw.rect(s, c, (x * u, y * u, w * u, h * u))
        s = surf(22, 14)
        R(s, 0, 5, 2, 2, (112, 72, 46)); R(s, 2, 3, 15, 8, (112, 72, 46)); R(s, 2, 3, 15, 2, (78, 50, 32))
        R(s, 15, 4, 6, 6, (140, 96, 66)); R(s, 19, 7, 3, 3, (222, 152, 150)); R(s, 17, 5, 1, 1, (10, 10, 10))
        R(s, 19, 10, 1, 2, (245, 245, 235)); R(s, 15, 3, 2, 2, (90, 60, 40))
        for lx in (3, 6, 12, 15):
            R(s, lx, 11, 2, 3, (70, 46, 30))
        out["Wild Boar"] = s
        s = surf(12, 9)
        R(s, 2, 5, 2, 2, (250, 250, 250)); R(s, 3, 4, 6, 4, (230, 225, 215)); R(s, 8, 3, 3, 3, (236, 230, 220))
        R(s, 8, 0, 1, 3, (240, 190, 190)); R(s, 10, 0, 1, 3, (240, 190, 190)); R(s, 10, 4, 1, 1, (10, 10, 10))
        R(s, 4, 8, 2, 1, (200, 195, 185)); R(s, 8, 8, 2, 1, (200, 195, 185))
        out["Rabbit"] = s
        s = surf(20, 9)
        for i in range(15):
            y = 3 + round(1.7 * math.sin(i * 0.9))
            R(s, i, y, 2, 2, (70, 150, 60) if i % 2 else (50, 120, 45))
        R(s, 15, 3, 4, 3, (84, 170, 72)); R(s, 17, 3, 1, 1, (10, 10, 10)); R(s, 19, 4, 1, 1, (220, 40, 40))
        out["Snake"] = s
        s = surf(12, 8)
        R(s, 3, 2, 6, 4, (205, 60, 40)); R(s, 4, 1, 1, 1, (10, 10, 10)); R(s, 7, 1, 1, 1, (10, 10, 10))
        R(s, 0, 0, 3, 3, (228, 84, 52)); R(s, 9, 0, 3, 3, (228, 84, 52))
        for lx in (2, 4, 7, 9):
            R(s, lx, 6, 1, 2, (170, 45, 30))
        out["Crab"] = s
        return out

    def get_icon(self, name):
        if name in self.icon_cache:
            return self.icon_cache[name]
        S = 32
        s = pygame.Surface((S, S), pygame.SRCALPHA)
        d = pygame.draw
        BR, BRD, GY, GYD, GN = (124, 82, 40), (84, 54, 26), (160, 162, 168), (100, 102, 108), (60, 150, 60)
        if name == "Branches":
            d.line(s, BRD, (5, 27), (27, 5), 5); d.line(s, BR, (5, 27), (27, 5), 3)
            d.line(s, BR, (14, 18), (8, 12), 2); d.line(s, BR, (19, 13), (25, 17), 2)
        elif name == "Stones":
            d.polygon(s, GYD, [(5, 22), (9, 11), (18, 8), (25, 14), (26, 24), (14, 27)])
            d.polygon(s, GY, [(7, 21), (10, 12), (18, 10), (23, 15), (23, 22), (14, 24)])
        elif name == "Vines":
            pts = [(16 + 6 * math.sin(i * 0.9), 3 + i * 3) for i in range(10)]
            d.lines(s, (30, 100, 40), False, pts, 5); d.lines(s, (70, 170, 70), False, pts, 3)
            d.ellipse(s, (60, 160, 60), (20, 10, 8, 5)); d.ellipse(s, (60, 160, 60), (4, 18, 8, 5))
        elif name == "Stone Axe":
            d.line(s, BRD, (6, 27), (21, 9), 5); d.line(s, BR, (6, 27), (21, 9), 3)
            d.polygon(s, GYD, [(15, 4), (28, 8), (26, 18), (19, 14)]); d.polygon(s, GY, [(17, 6), (26, 9), (24, 15), (20, 13)])
        elif name == "Stone Knife":
            d.polygon(s, GYD, [(25, 3), (28, 7), (15, 20), (10, 15)]); d.polygon(s, (205, 208, 214), [(25, 5), (26, 7), (15, 18), (12, 15)])
            d.line(s, BR, (11, 16), (5, 26), 5)
        elif name == "Fishing Rod":
            d.line(s, BRD, (5, 28), (24, 6), 4); d.line(s, BR, (5, 28), (24, 6), 2)
            d.line(s, (240, 240, 240), (24, 6), (25, 22), 1); d.circle(s, (220, 50, 50), (25, 24), 3)
        elif name == "Bow":
            d.arc(s, BRD, pygame.Rect(2, 2, 24, 28), -math.pi / 2, math.pi / 2, 5)
            d.arc(s, BR, pygame.Rect(2, 2, 24, 28), -math.pi / 2, math.pi / 2, 3)
            d.line(s, (240, 240, 240), (14, 2), (14, 30), 1)
        elif name == "Arrow":
            d.line(s, (200, 170, 110), (5, 27), (25, 7), 3)
            d.polygon(s, GY, [(29, 3), (21, 6), (26, 11)])
            d.line(s, (240, 240, 240), (4, 22), (9, 27), 2); d.line(s, (240, 240, 240), (4, 26), (6, 28), 2)
        elif name == "Campfire":
            d.line(s, BRD, (5, 26), (27, 20), 5); d.line(s, BR, (5, 20), (27, 26), 5)
            d.polygon(s, (240, 120, 20), [(16, 3), (24, 17), (20, 21), (12, 21), (8, 16)])
            d.polygon(s, (255, 220, 70), [(16, 10), (20, 18), (12, 18)])
        elif name == "Torch":
            d.line(s, BRD, (16, 28), (16, 12), 5); d.line(s, BR, (16, 28), (16, 12), 3)
            d.polygon(s, (240, 120, 20), [(16, 2), (22, 12), (10, 12)]); d.polygon(s, (255, 220, 70), [(16, 6), (19, 12), (13, 12)])
        elif name == "Planks":
            for i, y in enumerate((5, 13, 21)):
                d.rect(s, (110, 76, 40), (3, y, 26, 7)); d.rect(s, (176, 136, 80), (4, y + 1, 24, 5))
                d.line(s, (126, 92, 50), (9 + i * 6, y + 1), (9 + i * 6, y + 5), 1)
        elif name == "Bread":
            d.ellipse(s, (130, 84, 36), (3, 9, 26, 16)); d.ellipse(s, (214, 164, 84), (4, 9, 24, 13))
            for x in (10, 16, 22):
                d.line(s, (150, 100, 44), (x, 11), (x + 2, 17), 2)
        elif name in ("Fish", "Cooked Fish"):
            c1, c2 = ((110, 160, 205), (70, 110, 160)) if name == "Fish" else ((190, 130, 70), (140, 90, 44))
            d.polygon(s, c2, [(24, 16), (31, 9), (31, 23)]); d.ellipse(s, c2, (3, 9, 23, 14)); d.ellipse(s, c1, (4, 9, 21, 11))
            d.circle(s, (15, 15, 15), (9, 15), 2)
        elif name in ("Crab", "Cooked Crab"):
            c = (205, 60, 40) if name == "Crab" else (230, 120, 50)
            d.ellipse(s, c, (7, 13, 18, 12)); d.circle(s, c, (6, 10), 4); d.circle(s, c, (26, 10), 4)
            for x in (9, 13, 19, 23):
                d.line(s, (150, 40, 28), (x, 24), (x - 2, 29), 2)
            d.circle(s, (10, 10, 10), (13, 14), 1); d.circle(s, (10, 10, 10), (19, 14), 1)
        elif name in ("Raw Meat", "Cooked Meat"):
            c1, c2 = ((210, 84, 94), (240, 170, 170)) if name == "Raw Meat" else ((150, 86, 44), (196, 130, 80))
            d.line(s, (240, 236, 220), (20, 20), (28, 28), 4); d.circle(s, (240, 236, 220), (28, 26), 3); d.circle(s, (240, 236, 220), (26, 29), 3)
            d.ellipse(s, c1, (3, 5, 22, 19)); d.ellipse(s, c2, (7, 8, 10, 8))
        elif name == "Coconut":
            d.circle(s, (70, 44, 20), (16, 17), 12); d.circle(s, (118, 76, 38), (16, 17), 11)
            for p in ((12, 13), (19, 13), (16, 19)):
                d.circle(s, (40, 24, 10), p, 2)
        elif name == "Seaweed":
            for x, c in ((10, (30, 110, 60)), (16, (50, 150, 80)), (22, (30, 110, 60))):
                pts = [(x + 3 * math.sin(i * 1.1 + x), 29 - i * 4) for i in range(7)]
                d.lines(s, c, False, pts, 4)
        elif name == "Empty Bottle":
            d.rect(s, (110, 160, 180), (10, 11, 12, 18)); d.rect(s, (180, 225, 240), (11, 12, 10, 16))
            d.rect(s, (110, 160, 180), (13, 4, 6, 8)); d.rect(s, (130, 90, 44), (13, 2, 6, 3))
        elif name == "Key":
            d.circle(s, (170, 130, 20), (10, 10), 7); d.circle(s, (240, 200, 60), (10, 10), 6); d.circle(s, (0, 0, 0, 0), (10, 10), 2)
            d.line(s, (170, 130, 20), (15, 15), (27, 27), 5); d.line(s, (240, 200, 60), (15, 15), (27, 27), 3)
            d.line(s, (240, 200, 60), (22, 22), (26, 18), 3)
        elif name == "Map":
            d.rect(s, (130, 100, 50), (3, 4, 26, 24)); d.rect(s, (226, 206, 152), (4, 5, 24, 22))
            d.line(s, (190, 165, 110), (12, 5), (12, 27), 1); d.line(s, (190, 165, 110), (20, 5), (20, 27), 1)
            d.line(s, (190, 40, 40), (9, 10), (14, 15), 2); d.line(s, (190, 40, 40), (14, 10), (9, 15), 2)
            for x in range(15, 26, 3):
                d.circle(s, (80, 60, 30), (x, 22 - (x - 15) // 2), 1)
        elif name == "Helicopter Manual":
            d.rect(s, (30, 56, 120), (6, 3, 21, 26)); d.rect(s, (50, 90, 170), (7, 4, 19, 24)); d.rect(s, (240, 240, 230), (24, 5, 3, 22))
            d.ellipse(s, (240, 210, 70), (10, 13, 10, 6)); d.line(s, (240, 210, 70), (8, 11), (20, 11), 2); d.line(s, (240, 210, 70), (19, 15), (24, 12), 2)
        elif name == "Gasoline Can":
            d.rect(s, (110, 20, 20), (7, 8, 19, 21)); d.rect(s, (205, 44, 44), (8, 9, 17, 19))
            d.polygon(s, (205, 44, 44), [(20, 8), (27, 3), (29, 5), (24, 8)]); d.rect(s, (110, 20, 20), (9, 5, 8, 4), 2)
            d.polygon(s, (250, 220, 70), [(16, 14), (20, 21), (12, 21)])
        elif name == "Duct Tape":
            d.circle(s, (90, 92, 98), (16, 16), 13); d.circle(s, (165, 168, 176), (16, 16), 12); d.circle(s, (0, 0, 0, 0), (16, 16), 5)
            d.circle(s, (90, 92, 98), (16, 16), 5, 1)
        elif name == "Engine Oil":
            d.rect(s, (24, 24, 30), (8, 7, 17, 22)); d.rect(s, (52, 52, 60), (9, 8, 15, 20)); d.rect(s, (236, 192, 40), (9, 14, 15, 7))
            d.rect(s, (24, 24, 30), (13, 3, 7, 5))
        else:
            d.rect(s, (120, 120, 120), (4, 4, 24, 24)); d.rect(s, (60, 60, 60), (4, 4, 24, 24), 2)
        self.icon_cache[name] = s
        return s

    def get_small_icon(self, name):
        if name not in self.icon_small:
            self.icon_small[name] = pygame.transform.scale(self.get_icon(name), (22, 22))
        return self.icon_small[name]

    def light_sprite(self, radius_px):
        key = int(radius_px // 6) * 6
        if key not in self.light_cache:
            s = pygame.Surface((key * 2, key * 2), pygame.SRCALPHA)
            for r in range(key, 0, -4):
                t = r / key
                pygame.draw.circle(s, (0, 0, 0, int(255 * (1 - t * t))), (key, key), r)
            self.light_cache[key] = s
        return self.light_cache[key]

    # ---------------------------------------------------------- new game
    def new_game(self):
        self.world = World()
        w = self.world
        self.px, self.py = w.spawn
        self.health, self.hunger = 100.0, 100.0
        self.inv = Inventory()
        self.sel = 0
        self.cursor = None
        self.face = "down"
        self.walk, self.moving = 0.0, False
        self.inv_t = 0.0
        self.pkx = self.pky = 0.0
        self.hurt_flash = 0.0
        self.shake = 0.0
        self.swing = 0.0
        self.atk_cd = 0.0
        self.bow_cd = 0.0
        self.clock_t = 0.0
        self.mine_tile, self.mine_prog, self.mine_fx = None, 0.0, 0.0
        self.mobs, self.drops, self.arrows, self.particles = [], [], [], []
        self.regrow = []
        self.fires = set()
        self.log = []
        self.fish = None
        self.hunger_timer = 0.0
        self.regen_timer = 0.0
        self.starve_timer = 0.0
        self.warn_level = 0
        self.spawn_timer = 3.0
        self.smoke_t = 0.0
        self.held_popup = 0.0
        self.death_msg = ""
        self.repair = None
        self.win_t = 0.0
        self.key_found = False
        self.spawn_pos = (self.px, self.py)
        self.cam_x = clamp(self.px * TILE - SW / 2, 0, WW * TILE - SW)
        self.cam_y = clamp(self.py * TILE - SH / 2, 0, WH * TILE - SH)
        self.fog = pygame.Surface((WW, WH))
        self.fog.fill((0, 0, 0))
        self.revealed = [[False] * WW for _ in range(WH)]
        self.last_reveal = None
        self.parrots = [dict(cx=random.uniform(20, WW - 20), cy=random.uniform(20, WH - 20),
                             r=random.uniform(2, 5), ph=random.uniform(0, 6.28), sp=random.uniform(0.4, 0.9),
                             col=random.choice([(220, 40, 40), (40, 160, 220), (240, 190, 40)])) for _ in range(10)]
        # initial wildlife
        for kind, grounds, n in (("Wild Boar", (JUNGLE, HILL, GRASS), 9), ("Snake", (JUNGLE, GRASS), 8),
                                 ("Rabbit", (GRASS, JUNGLE), 16), ("Crab", (SAND,), 14)):
            for _ in range(n):
                p = w.rand_tile(grounds)
                if p:
                    self.mobs.append(Mob(kind, *p))
        hx, hy = w.structs["crash"]
        for _ in range(2):                       # hill guardians
            self.mobs.append(Mob("Wild Boar", hx + random.uniform(-4, 4), hy + random.uniform(2, 5)))
        self.fix_mobs()
        self.reveal(force=True)
        self.add_log("You survived a helicopter crash... Gather branches (hold LEFT click!)", (255, 235, 120))
        self.add_log("Press H for help, E for crafting.", (200, 200, 200))

    def fix_mobs(self):
        keep = []
        for m in self.mobs:
            spec = MOBS[m.kind]
            if self.free(m.x, m.y, spec["r"], True, m.kind == "Crab"):
                keep.append(m)
        self.mobs = keep

    # ---------------------------------------------------------- helpers
    def add_log(self, text, color=(255, 255, 255)):
        self.log.append([text, 6.0, color])
        if len(self.log) > 7:
            self.log.pop(0)

    def held(self):
        return self.inv.slots[self.sel]

    def held_name(self):
        h = self.held()
        return h["name"] if h else None

    def use_tool(self, amount):
        s = self.inv.slots[self.sel]
        if s and s["name"] in TOOL_DUR:
            s["dur"] -= amount
            if s["dur"] <= 0:
                self.add_log(f"Your {s['name']} broke!", (255, 120, 90))
                self.inv.slots[self.sel] = None

    def phase(self):
        return (self.clock_t / DAY_LENGTH + START_PHASE) % 1.0

    def daylight(self):
        return clamp(0.5 + 0.65 * math.sin(math.tau * (self.phase() - 0.25)), 0.0, 1.0)

    def day_number(self):
        return int(self.clock_t / DAY_LENGTH + START_PHASE) + 1

    def tile_ok(self, tx, ty):
        return 0 <= tx < WW and 0 <= ty < WH

    def walk_ok(self, tx, ty, mob=False, water_ok=False):
        if not self.tile_ok(tx, ty):
            return False
        g = self.world.ground[ty][tx]
        if g == DEEP:
            return False
        if mob and (g == FLOOR or (g == WATER and not water_ok)):
            return False
        return self.world.obj[ty][tx] not in SOLID_OBJ

    def free(self, x, y, r, mob=False, water_ok=False):
        for cx in (x - r, x + r):
            for cy in (y - r, y + r):
                if not self.walk_ok(int(math.floor(cx)), int(math.floor(cy)), mob, water_ok):
                    return False
        return True

    def move_ent(self, e, dx, dy, r, mob=True, water_ok=False):
        if dx and self.free(e.x + dx, e.y, r, mob, water_ok):
            e.x += dx
        if dy and self.free(e.x, e.y + dy, r, mob, water_ok):
            e.y += dy

    def burst(self, x, y, color, n=8, speed=2.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.3, 1.0) * speed
            self.particles.append([x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.3, 0.7),
                                   cc(color[0] + random.randint(-20, 20), color[1] + random.randint(-20, 20),
                                      color[2] + random.randint(-20, 20)), random.randint(3, 6)])

    def drop(self, x, y, name, n=1, dur=None, delay=0.6, pop=True):
        self.drops.append(Drop(x, y, name, n, dur, delay, pop))

    def reveal(self, force=False):
        tx, ty = int(self.px), int(self.py)
        if not force and self.last_reveal == (tx, ty):
            return
        self.last_reveal = (tx, ty)
        R = 9
        w = self.world
        for y in range(max(0, ty - R), min(WH, ty + R + 1)):
            for x in range(max(0, tx - R), min(WW, tx + R + 1)):
                if not self.revealed[y][x] and (x - tx) ** 2 + (y - ty) ** 2 <= R * R:
                    self.revealed[y][x] = True
                    c = MAP_COL[w.ground[y][x]]
                    o = w.obj[y][x]
                    if o in ("tree", "palm"):
                        c = (30, 90, 36)
                    elif o in ("wall", "door", "cupboard", "shelf", "chest"):
                        c = (110, 76, 40)
                    self.fog.set_at((x, y), c)

    # ---------------------------------------------------------- target / mouse
    def mouse_world(self):
        mx, my = pygame.mouse.get_pos()
        return (mx + self.cam_x) / TILE, (my + self.cam_y) / TILE

    def target_tile(self):
        wx, wy = self.mouse_world()
        tx, ty = int(math.floor(wx)), int(math.floor(wy))
        if not self.tile_ok(tx, ty):
            return None
        if math.hypot(tx + 0.5 - self.px, ty + 0.5 - self.py) > REACH:
            return None
        return tx, ty

    def mob_at(self, wx, wy):
        best, bd = None, 0.75
        for m in self.mobs:
            d = math.hypot(m.x - wx, m.y - wy)
            if d < bd + MOBS[m.kind]["r"] * 0.5:
                best, bd = m, d
        return best

    # ---------------------------------------------------------- damage
    def hurt_player(self, dmg, ux, uy, source):
        if self.inv_t > 0 or self.state != "play":
            return
        self.health -= dmg
        self.inv_t = 0.7
        self.pkx, self.pky = ux * 7, uy * 7
        self.hurt_flash = 0.3
        self.shake = 0.25
        self.add_log(f"A {source} hit you for {int(dmg)} damage!", (255, 110, 100))
        if self.health <= 0:
            self.die(f"Killed by a {source}")

    def die(self, msg):
        if self.state == "dead":
            return
        self.health = 0
        self.death_msg = msg
        self.state = "dead"
        for s in self.inv.slots:
            if s:
                self.drop(self.px, self.py, s["name"], s["n"], s["dur"], delay=2.0)
        self.inv.slots = [None] * 36
        if self.cursor:
            self.drop(self.px, self.py, self.cursor["name"], self.cursor["n"], self.cursor["dur"], delay=2.0)
            self.cursor = None
        self.fish = None
        self.mine_tile = None

    def respawn(self):
        self.px, self.py = self.spawn_pos
        self.health, self.hunger = 100.0, 80.0
        self.inv_t = 3.0
        self.pkx = self.pky = 0.0
        self.warn_level = 0
        self.state = "play"
        self.add_log("You respawned on the beach. Your items are where you fell!", (255, 235, 120))

    def hurt_mob(self, m, dmg, ux, uy, bonus=False):
        m.hp -= dmg
        m.hurt = 0.3
        m.kx, m.ky = ux * 6, uy * 6
        m.aggro = True
        m.flee_t = 2.5
        self.burst(m.x, m.y, (190, 30, 30), 6)
        if m.hp <= 0:
            self.kill_mob(m, bonus)

    def kill_mob(self, m, bonus):
        if m in self.mobs:
            self.mobs.remove(m)
        item, lo, hi = MOBS[m.kind]["drop"]
        n = random.randint(lo, hi)
        if bonus and hi > 0:
            n += 1
        for _ in range(n):
            self.drop(m.x, m.y, item, 1)
        self.burst(m.x, m.y, (150, 20, 20), 12, 3)
        self.add_log(f"You killed the {m.kind}." + (" (knife bonus!)" if bonus and hi > 0 else ""), (230, 230, 230))

    def player_attack(self, m):
        name = self.held_name()
        dmg = WEAPON_DMG.get(name, 2)
        dx, dy = m.x - self.px, m.y - self.py
        d = math.hypot(dx, dy) or 1.0
        self.hurt_mob(m, dmg, dx / d, dy / d, bonus=(name == "Stone Knife"))
        if name in ("Stone Knife", "Stone Axe"):
            self.use_tool(2)
        self.atk_cd = 0.45
        self.swing = 0.2

    # ---------------------------------------------------------- breaking
    def break_time(self, obj):
        t = BREAK_TIME[obj]
        held = self.held_name()
        if held == "Stone Axe" and obj in ("tree", "palm", "plank"):
            t *= 0.3
        elif held == "Stone Axe" and obj == "rock":
            t *= 0.8
        elif held == "Stone Knife" and obj in ("bush", "bare_bush"):
            t *= 0.5
        return t

    def break_object(self, tx, ty):
        w = self.world
        o = w.obj[ty][tx]
        held = self.held_name()
        cx, cy = tx + 0.5, ty + 0.5
        self.burst(cx, cy, OBJ_PARTICLE.get(o, (150, 150, 150)), 12)
        w.obj[ty][tx] = None
        self.regrow = [r for r in self.regrow if (r[3], r[4]) != (tx, ty)]
        axe = held == "Stone Axe"
        if o == "tree":
            self.drop(cx, cy, "Branches", 4 if axe else 1)
            if random.random() < 0.5:
                self.drop(cx, cy, "Vines", random.randint(1, 2))
            if random.random() < 0.3:
                self.drop(cx, cy, "Stones", 1)
            if axe:
                self.use_tool(4)
            w.obj[ty][tx] = "sapling"
            self.regrow.append([random.uniform(70, 110), "tree", "sapling", tx, ty])
        elif o == "palm":
            self.drop(cx, cy, "Branches", 2 if axe else 1)
            if random.random() < 0.7:
                self.drop(cx, cy, "Coconut", random.randint(1, 2))
            if axe:
                self.use_tool(4)
            w.obj[ty][tx] = "sapling"
            self.regrow.append([random.uniform(80, 120), "palm", "sapling", tx, ty])
        elif o == "rock":
            self.drop(cx, cy, "Stones", random.randint(1, 3))
            if axe:
                self.use_tool(2)
            self.regrow.append([random.uniform(120, 180), "rock", None, tx, ty])
        elif o == "bush":
            self.drop(cx, cy, "Vines", random.randint(1, 3))
            if held == "Stone Knife":
                self.use_tool(1)
            w.obj[ty][tx] = "bare_bush"
            self.regrow.append([random.uniform(45, 70), "bush", "bare_bush", tx, ty])
        elif o == "bare_bush":
            self.regrow.append([random.uniform(45, 70), "bush", None, tx, ty])
        elif o == "plank":
            self.drop(cx, cy, "Planks", 1)
        elif o == "campfire":
            self.drop(cx, cy, "Campfire", 1)
            self.fires.discard((tx, ty))
        elif o == "torch":
            self.drop(cx, cy, "Torch", 1)
        elif o == "glint":
            self.drop(cx, cy, "Key", 1)
            self.key_found = True
            self.add_log("You dug up a rusty old KEY!", (255, 225, 90))

    # ---------------------------------------------------------- right click
    def use_item(self):
        if self.fish is not None:
            self.reel_in()
            return
        w = self.world
        wx, wy = self.mouse_world()
        tgt = self.target_tile()
        if tgt:
            tx, ty = tgt
            o = w.obj[ty][tx]
            if o in ("cupboard", "shelf", "chest", "heli", "campfire"):
                self.interact(o, tx, ty)
                return
        held = self.held()
        if not held:
            return
        name = held["name"]
        if name in FOOD:
            self.eat(held)
        elif name == "Fishing Rod":
            self.cast(wx, wy)
        elif name == "Bow":
            self.shoot(wx, wy)
        elif name in PLACEABLE and tgt:
            self.place(held, *tgt)

    def interact(self, o, tx, ty):
        w = self.world
        cx, cy = tx + 0.5, ty + 0.5
        if o == "campfire":
            held = self.held()
            if held and held["name"] in COOK:
                raw, n = held["name"], held["n"]
                self.inv.slots[self.sel] = None
                left = self.inv.add(COOK[raw], n)
                if left:
                    self.drop(self.px, self.py, COOK[raw], left)
                self.add_log(f"You cook {n} {raw} over the campfire and get {n} {COOK[raw]}.", (255, 200, 120))
                self.burst(cx, cy, (110, 110, 110), 10, 1.0)
            else:
                self.add_log("Hold raw meat, fish or crab and right-click the campfire to cook it.", (220, 220, 220))
        elif o == "cupboard":
            st = w.chests[(tx, ty)]
            if st["opened"]:
                self.add_log("The cupboard is empty.", (200, 200, 200))
            elif self.inv.count("Key") <= 0:
                self.add_log("The cupboard is locked tight. You need a key...", (255, 180, 120))
            else:
                st["yanks"] -= 1
                self.shake = 0.12
                if st["yanks"] > 0:
                    self.add_log(random.choice(["The rusty lock won't budge... you yank harder!",
                                                "Attempt failed, try again!", "Clunk! Still stuck. Keep yanking!"]),
                                 (255, 220, 140))
                else:
                    st["opened"] = True
                    self.inv.remove("Key", 1)
                    self.add_log("Attempt successful! Inside: a gasoline can, duct tape and engine oil.", (140, 255, 140))
                    for it in ("Gasoline Can", "Duct Tape", "Engine Oil"):
                        self.drop(cx, cy + 0.7, it, 1)
        elif o == "shelf":
            st = w.chests[(tx, ty)]
            if st["opened"]:
                self.add_log("Nothing else on the shelf.", (200, 200, 200))
            else:
                st["opened"] = True
                self.add_log("You find a map and 10 pieces of bread!", (140, 255, 140))
                self.drop(cx, cy + 0.7, "Map", 1)
                self.drop(cx, cy + 0.7, "Bread", 10)
        elif o == "chest":
            st = w.chests[(tx, ty)]
            if st["opened"]:
                self.add_log("The chest is empty.", (200, 200, 200))
            else:
                st["opened"] = True
                self.add_log("Wooden planks, bread and a helicopter manual! You can now control a helicopter.", (140, 255, 140))
                self.drop(cx, cy + 0.7, "Planks", 15)
                self.drop(cx, cy + 0.7, "Bread", 10)
                self.drop(cx, cy + 0.7, "Helicopter Manual", 1)
        elif o == "heli":
            self.add_log("You stand in front of the wrecked helicopter...", (220, 220, 220))
            missing = [it for it in REQUIRED_ITEMS if self.inv.count(it) <= 0]
            if missing:
                self.add_log("You can't repair it yet. You still need: " + ", ".join(missing), (255, 180, 120))
            else:
                self.repair = {"stage": 0, "count": 0, "need": [1, random.randint(3, 10), random.randint(2, 7)]}
                self.state = "repair"

    def eat(self, held):
        if self.hunger >= 100:
            self.add_log("You're not hungry.", (200, 200, 200))
            return
        name = held["name"]
        self.hunger = min(100.0, self.hunger + FOOD[name])
        held["n"] -= 1
        if held["n"] <= 0:
            self.inv.slots[self.sel] = None
        self.burst(self.px, self.py - 0.3, (200, 160, 90), 6, 1.2)
        self.add_log(f"You eat the {name}. Hunger is now {int(self.hunger)}.", (255, 235, 160))
        if name == "Raw Meat" and random.random() < 0.35:
            self.health -= 6
            self.hurt_flash = 0.2
            self.add_log("Raw meat... you feel sick! (-6 health)", (170, 230, 100))
            if self.health <= 0:
                self.die("Died of food poisoning")

    def place(self, held, tx, ty):
        w = self.world
        name = held["name"]
        obj = PLACEABLE[name]
        if w.ground[ty][tx] in (DEEP, WATER) or w.obj[ty][tx] is not None:
            return
        if obj in SOLID_OBJ and math.hypot(tx + 0.5 - self.px, ty + 0.5 - self.py) < 0.85:
            return
        w.obj[ty][tx] = obj
        if obj == "campfire":
            self.fires.add((tx, ty))
        held["n"] -= 1
        if held["n"] <= 0:
            self.inv.slots[self.sel] = None
        self.burst(tx + 0.5, ty + 0.5, OBJ_PARTICLE[obj], 5, 1.0)

    def shoot(self, wx, wy):
        if self.bow_cd > 0:
            return
        if self.inv.count("Arrow") <= 0:
            self.add_log("You have no arrows!", (255, 180, 120))
            return
        dx, dy = wx - self.px, wy - self.py
        d = math.hypot(dx, dy) or 1.0
        self.arrows.append([self.px, self.py, dx / d * 15, dy / d * 15, 1.3])
        self.inv.remove("Arrow", 1)
        self.use_tool(2)
        self.bow_cd = 0.5
        self.swing = 0.15

    def cast(self, wx, wy):
        tx, ty = int(math.floor(wx)), int(math.floor(wy))
        if not self.tile_ok(tx, ty) or self.world.ground[ty][tx] not in (WATER, DEEP) \
                or math.hypot(wx - self.px, wy - self.py) > 7:
            self.add_log("Aim at water to cast your line.", (200, 200, 200))
            return
        self.fish = {"x": wx, "y": wy, "t": random.uniform(2.0, 6.0), "bite": False, "bt": 0.0}
        self.add_log("You cast your line... right-click again when you see a splash (!)", (200, 230, 255))

    def reel_in(self):
        f = self.fish
        self.fish = None
        if not f["bite"]:
            self.add_log("You reeled in too early.", (200, 200, 200))
            self.use_tool(2)
            return
        loot = random.choice(FISH_LOOT)
        self.burst(f["x"], f["y"], (180, 220, 255), 10)
        if loot == "empty":
            self.add_log("Attempt failed, nothing found.", (200, 200, 200))
        elif loot == "Stone Axe":
            self.add_log("Attempt successful! You hooked an old Stone Axe!", (140, 255, 140))
            self.drop(self.px, self.py, "Stone Axe", 1, 40)
        else:
            self.add_log(f"Attempt successful! You caught: {loot}!", (140, 255, 140))
            self.drop(self.px, self.py, loot, 1)
        self.use_tool(2)

    def craft(self, rec):
        need = rec["need"]
        if not all(self.inv.count(k) >= v for k, v in need.items()):
            self.add_log(f"You don't have enough materials to craft {rec['out']}.", (255, 180, 120))
            return
        if not self.inv.can_add(rec["out"]):
            self.add_log("Your inventory is full!", (255, 180, 120))
            return
        for k, v in need.items():
            if k not in rec.get("keep", ()):
                self.inv.remove(k, v)
        left = self.inv.add(rec["out"], rec["n"])
        if left:
            self.drop(self.px, self.py, rec["out"], left)
        self.add_log(f"Crafted {rec['out']}!" + (f" (x{rec['n']})" if rec["n"] > 1 else ""), (140, 255, 140))

    # ---------------------------------------------------------- UPDATE
    def update(self, dt):
        self.clock_t += dt
        keys = pygame.key.get_pressed()
        mb = pygame.mouse.get_pressed()
        self.inv_t = max(0.0, self.inv_t - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.shake = max(0.0, self.shake - dt)
        self.swing = max(0.0, self.swing - dt)
        self.atk_cd = max(0.0, self.atk_cd - dt)
        self.bow_cd = max(0.0, self.bow_cd - dt)
        self.held_popup = max(0.0, self.held_popup - dt)

        # ---- movement
        dx = (1 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0) - (1 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0)
        dy = (1 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0) - (1 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0)
        self.moving = bool(dx or dy)
        spd = 4.0
        sprint = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and self.hunger > 6 and self.moving
        if sprint:
            spd = 6.2
        tx, ty = int(self.px), int(self.py)
        if self.tile_ok(tx, ty) and self.world.ground[ty][tx] == WATER:
            spd *= 0.55
        if self.hunger <= 10:
            spd *= 0.8
        if self.moving:
            n = math.hypot(dx, dy)
            vx, vy = dx / n * spd * dt, dy / n * spd * dt
            self.move_ent(self, vx, vy, 0.28, False)
            self.walk += dt * (1.5 if sprint else 1.0)
        if abs(self.pkx) > 0.05 or abs(self.pky) > 0.05:
            self.move_ent(self, self.pkx * dt, self.pky * dt, 0.28, False)
            decay = max(0.0, 1 - dt * 9)
            self.pkx *= decay
            self.pky *= decay
        # face the mouse
        mx, my = pygame.mouse.get_pos()
        ang = math.atan2(my - (self.py * TILE - self.cam_y), mx - (self.px * TILE - self.cam_x))
        if abs(math.cos(ang)) > abs(math.sin(ang)):
            self.face = "right" if math.cos(ang) > 0 else "left"
        else:
            self.face = "down" if math.sin(ang) > 0 else "up"

        # ---- hunger / health
        drain = 1 / 9.0
        if sprint:
            drain *= 2.4
        if mb[0]:
            drain *= 1.3
        self.hunger = max(0.0, self.hunger - drain * dt)
        lvl = 3 if self.hunger <= 0 else 2 if self.hunger <= 10 else 1 if self.hunger <= 25 else 0
        if lvl > self.warn_level:
            self.add_log(["", "Your stomach growls... you need to eat soon.", "You're weak with hunger...",
                          "You're starving!"][lvl], (255, 170, 90))
        self.warn_level = lvl
        if self.hunger > 25:
            self.warn_level = 0
        if self.hunger <= 0:
            self.starve_timer += dt
            if self.starve_timer >= 2.0:
                self.starve_timer = 0
                self.health -= 2
                self.hurt_flash = 0.2
                if self.health <= 0:
                    self.die("Starved to death")
        if self.health < 100 and self.hunger > 30:
            self.regen_timer += dt
            if self.regen_timer >= 2.0:
                self.regen_timer = 0
                regen = 4 if self.hunger > 80 else 2 if self.hunger > 60 else 1
                self.health = min(100.0, self.health + regen)
                self.hunger = max(0.0, self.hunger - 0.4)

        # ---- left mouse: attack / mine
        wx, wy = self.mouse_world()
        target = self.target_tile()
        w = self.world
        if mb[0]:
            m = self.mob_at(wx, wy)
            if m and math.hypot(m.x - self.px, m.y - self.py) < 2.1:
                self.mine_tile, self.mine_prog = None, 0.0
                if self.atk_cd <= 0:
                    self.player_attack(m)
            elif target and w.obj[target[1]][target[0]] in BREAK_TIME:
                if target != self.mine_tile:
                    self.mine_tile, self.mine_prog = target, 0.0
                o = w.obj[target[1]][target[0]]
                self.mine_prog += dt / self.break_time(o)
                self.mine_fx -= dt
                self.swing = max(self.swing, 0.08)
                if self.mine_fx <= 0:
                    self.mine_fx = 0.16
                    self.burst(target[0] + 0.5, target[1] + 0.5, OBJ_PARTICLE.get(o, (150, 150, 150)), 2, 1.2)
                if self.mine_prog >= 1.0:
                    self.break_object(*target)
                    self.mine_tile, self.mine_prog = None, 0.0
            else:
                self.mine_tile, self.mine_prog = None, 0.0
        else:
            self.mine_tile, self.mine_prog = None, 0.0

        # ---- fishing
        if self.fish:
            f = self.fish
            if self.held_name() != "Fishing Rod" or math.hypot(f["x"] - self.px, f["y"] - self.py) > 9:
                self.fish = None
                self.add_log("You reel in your line.", (200, 200, 200))
            else:
                f["t"] -= dt
                if not f["bite"] and f["t"] <= 0:
                    f["bite"], f["bt"] = True, 1.1
                    self.burst(f["x"], f["y"], (200, 230, 255), 8)
                elif f["bite"]:
                    f["bt"] -= dt
                    if f["bt"] <= 0:
                        self.add_log("The fish got away...", (200, 200, 200))
                        self.fish = None

        # ---- arrows
        for a in self.arrows[:]:
            a[0] += a[2] * dt
            a[1] += a[3] * dt
            a[4] -= dt
            hit = a[4] <= 0
            tx, ty = int(math.floor(a[0])), int(math.floor(a[1]))
            if not self.tile_ok(tx, ty) or w.obj[ty][tx] in SOLID_OBJ:
                hit = True
                self.burst(a[0], a[1], (200, 170, 110), 3, 1.0)
            else:
                for m in self.mobs[:]:
                    if math.hypot(m.x - a[0], m.y - a[1]) < MOBS[m.kind]["r"] + 0.2:
                        d = math.hypot(a[2], a[3]) or 1
                        self.hurt_mob(m, 7, a[2] / d, a[3] / d, bonus=False)
                        hit = True
                        break
            if hit:
                self.arrows.remove(a)

        # ---- mobs
        for m in self.mobs[:]:
            self.update_mob(m, dt)
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = random.uniform(4, 8)
            night = self.daylight() < 0.35
            hostile = sum(1 for m in self.mobs if MOBS[m.kind]["hostile"])
            if hostile < (30 if night else 19):
                self.try_spawn(random.choice(["Wild Boar", "Snake", "Snake"]))
            if len(self.mobs) - hostile < 30:
                self.try_spawn(random.choice(["Rabbit", "Crab"]))

        # ---- drops
        for d in self.drops[:]:
            d.age += dt
            d.delay -= dt
            if abs(d.vx) > 0.05 or abs(d.vy) > 0.05:
                nx, ny = d.x + d.vx * dt, d.y + d.vy * dt
                if self.walk_ok(int(math.floor(nx)), int(math.floor(ny)), True, False):
                    d.x, d.y = nx, ny
                k = max(0.0, 1 - dt * 5)
                d.vx *= k
                d.vy *= k
            if d.delay <= 0 and self.state == "play":
                dist = math.hypot(self.px - d.x, self.py - d.y)
                if dist < 2.3 and self.inv.can_add(d.name):
                    if dist > 0.01:
                        step = min(dist, 7 * dt)
                        d.x += (self.px - d.x) / dist * step
                        d.y += (self.py - d.y) / dist * step
                    if dist < 0.5:
                        left = self.inv.add(d.name, d.n, d.dur)
                        self.add_log(f"+{d.n - left} {d.name}", (255, 255, 255))
                        if left:
                            d.n = left
                        else:
                            self.drops.remove(d)

        # ---- regrow
        for r in self.regrow[:]:
            r[0] -= dt
            if r[0] <= 0:
                if w.obj[r[4]][r[3]] == r[2] and not (r[1] in SOLID_OBJ and math.hypot(r[3] + .5 - self.px, r[4] + .5 - self.py) < 1.0):
                    w.obj[r[4]][r[3]] = r[1]
                    self.regrow.remove(r)
                elif w.obj[r[4]][r[3]] != r[2]:
                    self.regrow.remove(r)
                else:
                    r[0] = 4.0

        # ---- ambient particles
        self.smoke_t -= dt
        if self.smoke_t <= 0:
            self.smoke_t = 0.22
            for (fx, fy) in self.fires:
                if abs(fx - self.px) < 14 and abs(fy - self.py) < 10:
                    self.particles.append([fx + 0.5 + random.uniform(-.15, .15), fy + 0.3, random.uniform(-.1, .1), -1.0,
                                           1.0, (90, 90, 96), 4])
            hx, hy = w.heli_origin
            if abs(hx - self.px) < 14 and abs(hy - self.py) < 10:
                self.particles.append([hx + 1.2 + random.uniform(-.2, .2), hy + 0.6, random.uniform(-.2, .2), -0.9,
                                       1.8, (70, 70, 76), 6])
        self.update_particles(dt)
        for ptc in self.parrots:
            ptc["ph"] += ptc["sp"] * dt
        for lg in self.log[:]:
            lg[1] -= dt
            if lg[1] <= 0:
                self.log.remove(lg)
        self.reveal()
        self.cam_update(dt)

    def update_particles(self, dt):
        for p in self.particles[:]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
            if p[4] <= 0:
                self.particles.remove(p)

    def cam_update(self, dt):
        tx = clamp(self.px * TILE - SW / 2, 0, WW * TILE - SW)
        ty = clamp(self.py * TILE - SH / 2, 0, WH * TILE - SH)
        k = min(1.0, dt * 9)
        self.cam_x += (tx - self.cam_x) * k
        self.cam_y += (ty - self.cam_y) * k

    def try_spawn(self, kind):
        grounds = {"Wild Boar": (JUNGLE, GRASS, HILL), "Snake": (JUNGLE, GRASS), "Rabbit": (GRASS, JUNGLE), "Crab": (SAND,)}[kind]
        for _ in range(14):
            a, d = random.uniform(0, math.tau), random.uniform(17, 26)
            x, y = self.px + math.cos(a) * d, self.py + math.sin(a) * d
            tx, ty = int(math.floor(x)), int(math.floor(y))
            if self.tile_ok(tx, ty) and self.world.ground[ty][tx] in grounds and self.world.obj[ty][tx] is None:
                self.mobs.append(Mob(kind, tx + 0.5, ty + 0.5))
                return

    def update_mob(self, m, dt):
        spec = MOBS[m.kind]
        dx, dy = self.px - m.x, self.py - m.y
        dist = math.hypot(dx, dy)
        m.hurt = max(0.0, m.hurt - dt)
        m.cd = max(0.0, m.cd - dt)
        m.flee_t = max(0.0, m.flee_t - dt)
        water_ok = m.kind == "Crab"
        if abs(m.kx) > 0.05 or abs(m.ky) > 0.05:
            self.move_ent(m, m.kx * dt, m.ky * dt, spec["r"], True, water_ok)
            k = max(0.0, 1 - dt * 8)
            m.kx *= k
            m.ky *= k
        vx = vy = 0.0
        if spec["hostile"]:
            night_bonus = 2.0 if self.daylight() < 0.35 else 0.0
            if dist < spec["aggro"] + night_bonus or (m.aggro and dist < 14):
                m.aggro = True
            else:
                m.aggro = False
        if spec["hostile"] and m.aggro and dist > 0.01:
            ux, uy = dx / dist, dy / dist
            vx, vy = ux * spec["chase"], uy * spec["chase"]
            if dist < 0.9 and m.cd <= 0:
                self.hurt_player(spec["dmg"], ux, uy, m.kind)
                m.cd = 1.2
            if dist < 0.75:
                vx = vy = 0.0
        elif not spec["hostile"] and (dist < spec["flee"] or m.flee_t > 0) and dist > 0.01:
            vx, vy = -dx / dist * spec["fleespeed"], -dy / dist * spec["fleespeed"]
        else:
            m.timer -= dt
            if m.timer <= 0:
                m.timer = random.uniform(1.0, 3.5)
                if random.random() < 0.45:
                    m.dir = (0.0, 0.0)
                else:
                    a = random.uniform(0, math.tau)
                    m.dir = (math.cos(a), math.sin(a))
            vx, vy = m.dir[0] * spec["speed"], m.dir[1] * spec["speed"]
        if vx or vy:
            ox, oy = m.x, m.y
            self.move_ent(m, vx * dt, vy * dt, spec["r"], True, water_ok)
            if (m.x, m.y) == (ox, oy):
                m.timer = 0
            if abs(vx) > 0.1:
                m.face = 1 if vx > 0 else -1

    # ---------------------------------------------------------- REPAIR
    def repair_press(self):
        r = self.repair
        if r is None or r["stage"] >= 3:
            return
        r["count"] += 1
        self.burst(self.px, self.py, (255, 220, 120), 4, 1.5)
        if r["count"] >= r["need"][r["stage"]]:
            r["stage"] += 1
            r["count"] = 0
            if r["stage"] >= 3:
                self.win_t = 0.0

    def update_repair(self, dt):
        self.update_particles(dt)
        r = self.repair
        if r and r["stage"] >= 3:
            self.win_t += dt
            if self.win_t > 3.5:
                self.state = "win"
                self.win_t = 0.0

    # ---------------------------------------------------------- EVENTS
    def start_game(self):
        self.state = "play"

    def do_action(self, act):
        if act == "play":
            self.state = "play"
        elif act == "help":
            self.help_return = self.state
            self.state = "help"
        elif act == "quit":
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif act == "resume":
            self.state = "play"
        elif act == "title":
            self.state = "title"
            self.splash = random.choice(SPLASHES)
        elif act == "newworld":
            self.new_game()
            self.state = "play"
        elif act == "respawn":
            self.respawn()

    def handle_event(self, e):
        st = self.state
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and st in ("title", "pause", "dead", "win"):
            for b in self.btns:
                if b["rect"].collidepoint(e.pos):
                    self.do_action(b["act"])
                    return
        if st == "title":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "play"
        elif st == "help":
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.state = self.help_return
        elif st == "play":
            self.play_event(e)
        elif st == "inv":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_e, pygame.K_ESCAPE):
                self.close_inv()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                self.inv_click(e.pos, e.button)
        elif st == "map":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_m, pygame.K_ESCAPE, pygame.K_e):
                self.state = "play"
        elif st == "pause":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.state = "play"
        elif st == "repair":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE and self.repair and self.repair["stage"] < 3:
                    self.state = "play"
                    self.repair = None
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_e):
                    self.repair_press()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                self.repair_press()
        elif st == "dead":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_r, pygame.K_RETURN):
                self.respawn()
        elif st == "win":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                self.new_game()
                self.state = "play"

    def play_event(self, e):
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.state = "pause"
            elif k == pygame.K_e:
                self.state = "inv"
            elif k == pygame.K_m:
                if self.inv.count("Map") > 0:
                    self.state = "map"
                else:
                    self.add_log("You need a Map. Try searching the old boathouse...", (255, 220, 140))
            elif k in (pygame.K_h, pygame.K_F1):
                self.help_return = "play"
                self.state = "help"
            elif k == pygame.K_q:
                s = self.held()
                if s:
                    if s["name"] in TOOL_DUR or s["n"] == 1:
                        self.inv.slots[self.sel] = None
                        self.drop(self.px, self.py, s["name"], 1, s["dur"], delay=1.5)
                    else:
                        s["n"] -= 1
                        self.drop(self.px, self.py, s["name"], 1, None, delay=1.5)
            elif pygame.K_1 <= k <= pygame.K_9:
                self.select(k - pygame.K_1)
        elif e.type == pygame.MOUSEWHEEL:
            self.select((self.sel - e.y) % 9)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            self.use_item()

    def select(self, i):
        if i != self.sel:
            self.sel = i
            self.mine_tile, self.mine_prog = None, 0.0
        self.held_popup = 2.0

    def close_inv(self):
        if self.cursor:
            c = self.cursor
            left = self.inv.add(c["name"], c["n"], c["dur"])
            if left:
                self.drop(self.px, self.py, c["name"], left, c["dur"])
            self.cursor = None
        self.state = "play"

    def inv_layout(self):
        panel = pygame.Rect(22, 50, 980, 540)
        slots = {}
        gx, gy = panel.x + 450, panel.y + 64
        for i in range(9, 36):
            c, r = (i - 9) % 9, (i - 9) // 9
            slots[i] = pygame.Rect(gx + c * 54, gy + r * 54, 52, 52)
        for i in range(9):
            slots[i] = pygame.Rect(gx + i * 54, gy + 3 * 54 + 14, 52, 52)
        recipes = [pygame.Rect(panel.x + 20, panel.y + 50 + i * 60, 400, 56) for i in range(len(RECIPES))]
        return {"panel": panel, "slots": slots, "recipes": recipes}

    def inv_click(self, pos, button):
        lay = self.inv_layout()
        for i, r in lay["slots"].items():
            if r.collidepoint(pos):
                self.slot_click(i, button)
                return
        if button == 1:
            for i, r in enumerate(lay["recipes"]):
                if r.collidepoint(pos):
                    self.craft(RECIPES[i])
                    return

    def slot_click(self, i, button):
        s, c = self.inv.slots[i], self.cursor
        if button == 1 or (button == 3 and c is None and (s is None or s["n"] <= 1)):
            if c is None:
                self.inv.slots[i], self.cursor = None, s
            elif s is None:
                self.inv.slots[i], self.cursor = c, None
            elif s["name"] == c["name"] and c["name"] not in TOOL_DUR:
                put = min(c["n"], STACK - s["n"])
                s["n"] += put
                c["n"] -= put
                if c["n"] <= 0:
                    self.cursor = None
            else:
                self.inv.slots[i], self.cursor = c, s
        elif button == 3:
            if c is None:
                half = (s["n"] + 1) // 2
                self.cursor = {"name": s["name"], "n": half, "dur": s["dur"]}
                s["n"] -= half
            elif c["name"] not in TOOL_DUR and (s is None or (s["name"] == c["name"] and s["n"] < STACK)):
                if s is None:
                    self.inv.slots[i] = {"name": c["name"], "n": 1, "dur": c["dur"]}
                else:
                    s["n"] += 1
                c["n"] -= 1
                if c["n"] <= 0:
                    self.cursor = None

    # ---------------------------------------------------------- DRAW
    def draw(self):
        self.btns = []
        st = self.state
        if st == "title":
            self.draw_title()
        elif st == "help":
            self.draw_help()
        else:
            self.draw_game()
            if st == "inv":
                self.draw_inventory()
            elif st == "map":
                self.draw_map()
            elif st == "pause":
                self.draw_pause()
            elif st == "repair":
                self.draw_repair()
            elif st == "dead":
                self.draw_dead()
            elif st == "win":
                self.draw_win()

    def draw_game(self):
        scr = self.screen
        w = self.world
        shx = shy = 0
        if self.shake > 0:
            shx, shy = random.randint(-4, 4), random.randint(-4, 4)
        cam_x, cam_y = int(self.cam_x) + shx, int(self.cam_y) + shy
        x0, y0 = max(0, cam_x // TILE), max(0, cam_y // TILE)
        x1, y1 = min(WW, (cam_x + SW) // TILE + 1), min(WH, (cam_y + SH) // TILE + 1)
        tw = self.anim
        for y in range(y0, y1):
            for x in range(x0, x1):
                sx, sy = x * TILE - cam_x, y * TILE - cam_y
                g = w.ground[y][x]
                if g == WATER or g == DEEP:
                    fr = int(tw * 1.2 + x * 0.35 + y * 0.2) % 2
                    scr.blit((self.tex_water if g == WATER else self.tex_deep)[fr][(x * 3 + y * 5) % 2], (sx, sy))
                else:
                    lst = self.tex_ground[g]
                    scr.blit(lst[(x * 7 + y * 13) % len(lst)], (sx, sy))
                o = w.obj[y][x]
                if o and o != "heli":
                    self.draw_obj(o, x, y, sx, sy)
        # helicopter wreck
        hx, hy = w.heli_origin
        scr.blit(self.heli_img, (hx * TILE - cam_x, hy * TILE - cam_y))
        # mining cracks + target outline
        tgt = self.target_tile() if self.state == "play" else None
        if self.mine_tile and self.mine_prog > 0:
            sx, sy = self.mine_tile[0] * TILE - cam_x, self.mine_tile[1] * TILE - cam_y
            scr.blit(self.cracks[min(9, int(self.mine_prog * 10))], (sx, sy))
        if tgt:
            o = w.obj[tgt[1]][tgt[0]]
            col = (255, 255, 120) if o in ("cupboard", "shelf", "chest", "heli", "campfire") else (255, 255, 255)
            pygame.draw.rect(scr, col, (tgt[0] * TILE - cam_x, tgt[1] * TILE - cam_y, TILE, TILE), 3)
        # drops
        for d in self.drops:
            sx, sy = d.x * TILE - cam_x, d.y * TILE - cam_y
            if -30 < sx < SW + 30 and -30 < sy < SH + 30:
                bob = math.sin(d.age * 3) * 3
                pygame.draw.ellipse(scr, (0, 0, 0), (sx - 8, sy + 4, 16, 6))
                ic = self.get_small_icon(d.name)
                scr.blit(ic, (int(sx - 11), int(sy - 14 + bob)))
                if d.n > 1:
                    draw_text(scr, str(d.n), self.f_s, (255, 255, 255), (sx + 10, sy + 4), "bottomright")
        # entities sorted by y
        ents = [("m", m.y, m) for m in self.mobs] + [("p", self.py, None)]
        ents.sort(key=lambda t: t[1])
        for kind, _, m in ents:
            if kind == "m":
                self.draw_mob(m, cam_x, cam_y)
            elif self.state != "dead":
                self.draw_player(self.px * TILE - cam_x, self.py * TILE - cam_y)
        # fishing line
        if self.fish:
            f = self.fish
            bx, by = f["x"] * TILE - cam_x, f["y"] * TILE - cam_y
            pygame.draw.line(scr, (240, 240, 240), (self.px * TILE - cam_x, self.py * TILE - cam_y - 14), (bx, by), 1)
            bob = math.sin(tw * 5) * 2 + (6 if f["bite"] and int(tw * 12) % 2 else 0)
            pygame.draw.circle(scr, (255, 255, 255), (bx, by + bob), 5)
            pygame.draw.circle(scr, (220, 40, 40), (bx, by + bob - 2), 4)
            pygame.draw.circle(scr, (150, 200, 255), (bx, by), 12 + int((tw * 20) % 8), 1)
            if f["bite"]:
                draw_text(scr, "!", self.f_l, (255, 80, 60), (bx, by - 26), "center")
        # arrows
        for a in self.arrows:
            sx, sy = a[0] * TILE - cam_x, a[1] * TILE - cam_y
            n = math.hypot(a[2], a[3]) or 1
            ex, ey = sx - a[2] / n * 16, sy - a[3] / n * 16
            pygame.draw.line(scr, (210, 180, 120), (ex, ey), (sx, sy), 3)
            pygame.draw.circle(scr, (170, 172, 178), (sx, sy), 3)
        # parrots (flying high above everything)
        for p in self.parrots:
            ang = p["ph"]
            x = (p["cx"] + math.cos(ang) * p["r"] * 3) * TILE - cam_x
            y = (p["cy"] + math.sin(ang * 1.3) * p["r"] * 2) * TILE - cam_y
            if -40 < x < SW + 40 and -40 < y < SH + 40:
                pygame.draw.ellipse(scr, (0, 0, 0), (x - 6, y + 22, 12, 5))
                flap = math.sin(self.anim * 14 + ang * 5) * 7
                pygame.draw.polygon(scr, p["col"], [(x - 3, y), (x - 14, y - 4 + flap), (x - 2, y + 4)])
                pygame.draw.polygon(scr, p["col"], [(x + 3, y), (x + 14, y - 4 + flap), (x + 2, y + 4)])
                pygame.draw.ellipse(scr, p["col"], (x - 4, y - 5, 8, 12))
                pygame.draw.circle(scr, (250, 250, 250), (x, y - 5), 2)
        # particles
        for p in self.particles:
            sx, sy = p[0] * TILE - cam_x, p[1] * TILE - cam_y
            pygame.draw.rect(scr, p[5], (sx - p[6] // 2, sy - p[6] // 2, p[6], p[6]))
        self.draw_lighting(cam_x, cam_y)
        if self.hurt_flash > 0:
            ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
            ov.fill((220, 20, 20, int(150 * self.hurt_flash / 0.3)))
            scr.blit(ov, (0, 0))
        self.draw_hud()

    def draw_obj(self, o, x, y, sx, sy):
        scr = self.screen
        lst = self.tex_obj.get(o)
        if lst:
            scr.blit(lst[(x * 5 + y * 11) % len(lst)], (sx, sy))
        t = self.anim
        if o == "campfire":
            fl = 1 + 0.18 * math.sin(t * 13 + x)
            cx, cy = sx + TILE // 2, sy + TILE // 2
            pygame.draw.polygon(scr, (236, 110, 20), [(cx, cy - 18 * fl), (cx + 10, cy + 2), (cx, cy + 8), (cx - 10, cy + 2)])
            pygame.draw.polygon(scr, (255, 214, 70), [(cx, cy - 10 * fl), (cx + 5, cy + 3), (cx - 5, cy + 3)])
        elif o == "torch":
            cx, cy = sx + TILE // 2, sy + TILE // 2 - 10
            fl = 1 + 0.2 * math.sin(t * 15 + y)
            pygame.draw.polygon(scr, (240, 120, 20), [(cx, cy - 9 * fl), (cx + 5, cy + 2), (cx - 5, cy + 2)])
            pygame.draw.polygon(scr, (255, 220, 70), [(cx, cy - 4 * fl), (cx + 2, cy + 2), (cx - 2, cy + 2)])
        elif o == "glint":
            if int(t * 2 + x) % 2 == 0:
                cx, cy = sx + 24, sy + 18
                pygame.draw.line(scr, (255, 240, 140), (cx - 6, cy), (cx + 6, cy), 2)
                pygame.draw.line(scr, (255, 240, 140), (cx, cy - 6), (cx, cy + 6), 2)

    def draw_mob(self, m, cam_x, cam_y):
        scr = self.screen
        sx, sy = m.x * TILE - cam_x, m.y * TILE - cam_y
        if not (-80 < sx < SW + 80 and -80 < sy < SH + 80):
            return
        spr = self.mob_sprites[m.kind]
        if m.face < 0:
            spr = pygame.transform.flip(spr, True, False)
        if m.hurt > 0:
            spr = spr.copy()
            spr.fill((140, 0, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        r = spr.get_rect(midbottom=(sx, sy + MOBS[m.kind]["r"] * TILE))
        pygame.draw.ellipse(scr, (0, 0, 0), (r.centerx - r.w // 3, r.bottom - 4, r.w * 2 // 3, 7))
        scr.blit(spr, r)
        if m.hp < m.maxhp:
            bw = 30
            pygame.draw.rect(scr, (20, 20, 20), (sx - bw // 2 - 1, r.top - 9, bw + 2, 6))
            pygame.draw.rect(scr, (210, 50, 50), (sx - bw // 2, r.top - 8, int(bw * m.hp / m.maxhp), 4))
        if m.kind in ("Wild Boar", "Snake") and m.aggro:
            draw_text(scr, "!", self.f_m, (255, 70, 60), (sx, r.top - 18), "center")

    def draw_player(self, cx, cy):
        scr = self.screen
        cx, cy = int(cx), int(cy)
        u = TILE / 16.0
        scr.blit(self.shadow, (cx - TILE // 2, cy - 4))
        walk = math.sin(self.walk * 11) * 2 * u if self.moving else 0
        flash = self.inv_t > 0 and int(self.anim * 20) % 2 == 0
        shirt = (220, 70, 70) if flash else (0, 172, 172)
        skin = (214, 160, 120)
        hair = (70, 44, 24)
        R = lambda x, y, w, h, c: pygame.draw.rect(scr, c, (cx + x * u, cy + y * u, w * u, h * u))
        R(-4, 1 + walk / u * 0.5, 3.6, 5, (48, 48, 150))
        R(0.5, 1 - walk / u * 0.5, 3.6, 5, (48, 48, 150))
        reach = -3 if self.swing > 0 else 0
        R(-8, -6 + walk / u * 0.4, 3, 7, skin)
        R(-5, -6, 10, 8, shirt)
        arm_y = -6 - walk / u * 0.4 + (reach if self.face in ("down", "right") else 0)
        R(5, arm_y, 3, 7, skin)
        R(-5, -14, 10, 8, skin)
        if self.face == "down":
            R(-5, -14, 10, 3, hair)
            R(-3.5, -10, 2, 2, (255, 255, 255)); R(1.5, -10, 2, 2, (255, 255, 255))
            R(-3, -10, 1, 2, (60, 80, 200)); R(2, -10, 1, 2, (60, 80, 200))
        elif self.face == "up":
            R(-5, -14, 10, 8, hair)
        elif self.face == "right":
            R(-5, -14, 7, 8, hair); R(-5, -14, 10, 3, hair)
            R(2.5, -10, 2, 2, (255, 255, 255)); R(3.5, -10, 1, 2, (60, 80, 200))
        else:
            R(-2, -14, 7, 8, hair); R(-5, -14, 10, 3, hair)
            R(-4.5, -10, 2, 2, (255, 255, 255)); R(-4.5, -10, 1, 2, (60, 80, 200))
        h = self.held()
        if h:
            ic = self.get_small_icon(h["name"])
            ox = -26 if self.face == "left" else 8
            oy = -22 + (-6 if self.swing > 0 else 0)
            if self.face == "up":
                ox, oy = 4, -30
            scr.blit(ic, (cx + ox, cy + oy + (6 if self.face == "down" else 0)))

    def draw_lighting(self, cam_x, cam_y):
        k = 1 - self.daylight()
        alpha = int(214 * k ** 1.15)
        if alpha < 8:
            return
        warm = max(0.0, 1 - abs(k - 0.4) / 0.3)
        col = (int(8 + 62 * warm), int(10 + 20 * warm), int(38 - 18 * warm), alpha)
        d = self.dark
        d.fill(col)
        lights = []
        px, py = self.px * TILE - cam_x, self.py * TILE - cam_y
        r = 2.6
        if self.held_name() == "Torch":
            r = 7.0
        lights.append((px, py - 10, r * TILE * (1 + 0.03 * math.sin(self.anim * 9))))
        w = self.world
        x0, y0 = max(0, int(cam_x // TILE) - 9), max(0, int(cam_y // TILE) - 9)
        x1, y1 = min(WW, int((cam_x + SW) // TILE) + 10), min(WH, int((cam_y + SH) // TILE) + 10)
        for y in range(y0, y1):
            row = w.obj[y]
            for x in range(x0, x1):
                o = row[x]
                if o == "campfire":
                    lights.append((x * TILE - cam_x + TILE // 2, y * TILE - cam_y + TILE // 2,
                                   8.0 * TILE * (1 + 0.04 * math.sin(self.anim * 11 + x))))
                elif o == "torch":
                    lights.append((x * TILE - cam_x + TILE // 2, y * TILE - cam_y + TILE // 2,
                                   6.0 * TILE * (1 + 0.05 * math.sin(self.anim * 13 + y))))
        for (lx, ly, lr) in lights:
            spr = self.light_sprite(lr)
            d.blit(spr, (int(lx - spr.get_width() // 2), int(ly - spr.get_height() // 2)), special_flags=pygame.BLEND_RGBA_SUB)
        self.screen.blit(d, (0, 0))

    # ---------------------------------------------------------- HUD
    def draw_hud(self):
        scr = self.screen
        # hotbar
        x0 = (SW - 9 * 54) // 2
        y0 = SH - 66
        for i in range(9):
            r = pygame.Rect(x0 + i * 54, y0, 52, 52)
            self.draw_slot(r, self.inv.slots[i], i == self.sel)
            draw_text(scr, str(i + 1), self.f_s, (200, 200, 200), (r.x + 4, r.y + 3), shadow=True)
        # hearts + hunger
        hy = y0 - 26
        for i in range(10):
            v = self.health - i * 10
            kind = "full" if v >= 10 else "half" if v >= 5 else "empty"
            jig = (math.sin(self.anim * 20 + i) * 2) if self.health <= 25 else 0
            scr.blit(self.heart[kind], (x0 + i * 21, hy + jig))
        for i in range(10):
            v = self.hunger - (9 - i) * 10
            kind = "full" if v >= 10 else "half" if v >= 5 else "empty"
            jig = (math.sin(self.anim * 25 + i) * 2) if self.hunger <= 20 else 0
            scr.blit(self.drum[kind], (x0 + 8 * 54 + 52 - 20 - i * 21, hy + jig))
        # held item popup
        h = self.held()
        if h and self.held_popup > 0:
            a = clamp(int(255 * min(1, self.held_popup)), 0, 255)
            img = self.f_m.render(h["name"], True, (255, 255, 255))
            img.set_alpha(a)
            scr.blit(img, img.get_rect(midbottom=(SW // 2, hy - 6)))
        # clock
        ph = self.phase()
        hh = int(ph * 24)
        mm = int((ph * 24 - hh) * 60)
        day = self.daylight() > 0.45
        pygame.draw.circle(scr, (250, 220, 80) if day else (210, 215, 235), (24, 24), 10)
        if not day:
            pygame.draw.circle(scr, (30, 34, 60), (28, 21), 8)
        draw_text(scr, f"Day {self.day_number()}   {hh:02d}:{mm:02d}", self.f_m, (255, 255, 255), (44, 14))
        # coordinates / hints
        draw_text(scr, f"Position: {int(self.px)}, {int(self.py)}", self.f_s, (210, 210, 210), (14, 42))
        # log
        y = 62
        for text, t, col in self.log:
            img = self.f_s.render(text, True, col)
            img.set_alpha(int(255 * min(1.0, t / 1.5)))
            sh = self.f_s.render(text, True, (20, 20, 20))
            sh.set_alpha(int(255 * min(1.0, t / 1.5)))
            scr.blit(sh, (16, y + 1))
            scr.blit(img, (14, y))
            y += 20
        self.draw_minimap()
        # mining progress
        if self.mine_tile and self.mine_prog > 0:
            bw = 80
            pygame.draw.rect(scr, (20, 20, 20), (SW // 2 - bw // 2 - 2, 80, bw + 4, 12))
            pygame.draw.rect(scr, (120, 220, 90), (SW // 2 - bw // 2, 82, int(bw * self.mine_prog), 8))

    def draw_slot(self, r, s, selected=False, small=False):
        scr = self.screen
        pygame.draw.rect(scr, (30, 30, 34), r)
        pygame.draw.rect(scr, (90, 90, 98), r.inflate(-4, -4))
        pygame.draw.rect(scr, (60, 60, 66), r.inflate(-8, -8))
        if selected:
            pygame.draw.rect(scr, (255, 255, 255), r.inflate(4, 4), 4)
        if s:
            ic = self.get_icon(s["name"])
            scr.blit(ic, ic.get_rect(center=r.center))
            if s["n"] > 1:
                draw_text(scr, str(s["n"]), self.f_s, (255, 255, 255), (r.right - 5, r.bottom - 3), "bottomright")
            mx = TOOL_DUR.get(s["name"])
            if mx and s["dur"] is not None and s["dur"] < mx:
                f = clamp(s["dur"] / mx, 0, 1)
                pygame.draw.rect(scr, (20, 20, 20), (r.x + 8, r.bottom - 9, r.w - 16, 5))
                pygame.draw.rect(scr, cc(255 * (1 - f) + 60, 220 * f + 20, 40), (r.x + 8, r.bottom - 9, int((r.w - 16) * f), 4))

    def draw_minimap(self):
        scr = self.screen
        R = 28
        tmp = pygame.Surface((R * 2, R * 2))
        tmp.fill((14, 14, 20))
        ox, oy = int(self.px) - R, int(self.py) - R
        tmp.blit(self.fog, (-ox, -oy))
        mm = pygame.transform.scale(tmp, (R * 4, R * 4))
        pos = (SW - R * 4 - 14, 14)
        pygame.draw.rect(scr, (20, 20, 24), (pos[0] - 4, pos[1] - 4, R * 4 + 8, R * 4 + 8))
        scr.blit(mm, pos)
        if self.inv.count("Map") > 0:
            cx, cy = self.world.structs["crash"]
            mx, my = (cx - ox) * 2 + pos[0], (cy - oy) * 2 + pos[1]
            if pos[0] <= mx < pos[0] + R * 4 and pos[1] <= my < pos[1] + R * 4:
                pygame.draw.circle(scr, (255, 60, 60), (mx, my), 4)
        pygame.draw.circle(scr, (255, 255, 255), (pos[0] + R * 2, pos[1] + R * 2), 3)
        pygame.draw.rect(scr, (200, 200, 210), (pos[0] - 4, pos[1] - 4, R * 4 + 8, R * 4 + 8), 2)

    # ---------------------------------------------------------- overlays
    def shade(self, a=150):
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, a))
        self.screen.blit(ov, (0, 0))

    def button(self, rect, label, act):
        mx, my = pygame.mouse.get_pos()
        hov = rect.collidepoint((mx, my))
        scr = self.screen
        pygame.draw.rect(scr, (20, 20, 20), rect.inflate(4, 4))
        pygame.draw.rect(scr, (120, 120, 170) if hov else (112, 112, 112), rect)
        pygame.draw.rect(scr, (170, 170, 220) if hov else (160, 160, 160), (rect.x, rect.y, rect.w, 4))
        pygame.draw.rect(scr, (80, 80, 120) if hov else (70, 70, 70), (rect.x, rect.bottom - 4, rect.w, 4))
        draw_text(scr, label, self.f_m, (255, 255, 160) if hov else (255, 255, 255), rect.center, "center")
        self.btns.append({"rect": rect, "act": act})

    def draw_title(self):
        scr = self.screen
        for y in range(0, SH, 64):
            for x in range(0, SW, 64):
                scr.blit(self.dirt, (x, y))
        self.shade(120)
        # logo
        for i in range(8, 0, -1):
            draw_text(scr, "SURVIVAL", self.f_xl, (60 + i * 8, 60 + i * 8, 60 + i * 8), (SW // 2 + i, 70 + i), "midtop", False)
        draw_text(scr, "SURVIVAL", self.f_xl, (236, 236, 236), (SW // 2, 70), "midtop", False)
        for i in range(8, 0, -1):
            draw_text(scr, "ISLAND", self.f_xl, (40 + i * 6, 90 + i * 8, 40 + i * 4), (SW // 2 + i, 170 + i), "midtop", False)
        draw_text(scr, "ISLAND", self.f_xl, (120, 220, 90), (SW // 2, 170), "midtop", False)
        # splash
        sp = self.f_m.render(self.splash, True, (255, 255, 60))
        sh = self.f_m.render(self.splash, True, (60, 60, 0))
        k = 1 + 0.06 * math.sin(self.anim * 5)
        for img, off in ((sh, 2), (sp, 0)):
            t = pygame.transform.rotate(pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k))), 14)
            scr.blit(t, t.get_rect(center=(SW // 2 + 250 + off, 215 + off)))
        self.button(pygame.Rect(SW // 2 - 160, 340, 320, 48), "Play", "play")
        self.button(pygame.Rect(SW // 2 - 160, 400, 320, 48), "New World", "newworld")
        self.button(pygame.Rect(SW // 2 - 160, 460, 320, 48), "How to Play", "help")
        self.button(pygame.Rect(SW // 2 - 160, 520, 320, 48), "Quit Game", "quit")
        draw_text(scr, "pygame edition", self.f_s, (220, 220, 220), (8, SH - 8), "bottomleft")

    def draw_help(self):
        scr = self.screen
        for y in range(0, SH, 64):
            for x in range(0, SW, 64):
                scr.blit(self.dirt, (x, y))
        self.shade(170)
        draw_text(scr, "HOW TO PLAY", self.f_l, (255, 255, 120), (SW // 2, 30), "midtop")
        lines = [
            ("GOAL", (120, 220, 90)),
            ("Find a Gasoline Can, Duct Tape and the Helicopter Manual, then repair the crashed helicopter on the hills!", None),
            ("", None),
            ("CONTROLS", (120, 220, 90)),
            ("W A S D / Arrows: move     Shift: sprint (costs hunger)", None),
            ("Hold LEFT mouse on a block: chop / mine / attack      RIGHT mouse: use / eat / place / interact", None),
            ("1-9 or mouse wheel: select item      E: inventory + crafting      Q: drop      M: map      Esc: pause", None),
            ("", None),
            ("SURVIVAL TIPS", (120, 220, 90)),
            ("- Punch trees, rocks and bushes for Branches, Stones and Vines. Craft an Axe to chop faster!", None),
            ("- Hold raw meat/fish/crab and right-click a Campfire to cook it. Watch your hunger!", None),
            ("- Boars and snakes bite. Craft a Knife or Bow. Night makes them bolder - carry a Torch.", None),
            ("- Right-click water with a Fishing Rod, then right-click again when you see a splash (!).", None),
            ("- A rusty KEY is buried on the beach (look for the sparkle). The boathouse has a locked cupboard.", None),
            ("- The abandoned cabin in the jungle hides the Helicopter Manual. The Map shows the crash site.", None),
            ("- When you die you drop everything where you fell. Run back and grab it!", None),
            ("", None),
            ("Click or press any key to go back.", (200, 200, 200)),
        ]
        y = 90
        for text, col in lines:
            draw_text(scr, text, self.f_m if col else self.f_s, col or (255, 255, 255), (60, y))
            y += 30 if col else 24

    def draw_pause(self):
        self.shade(150)
        draw_text(self.screen, "Game Paused", self.f_l, (255, 255, 255), (SW // 2, 170), "center")
        self.button(pygame.Rect(SW // 2 - 160, 230, 320, 48), "Resume", "resume")
        self.button(pygame.Rect(SW // 2 - 160, 290, 320, 48), "How to Play", "help")
        self.button(pygame.Rect(SW // 2 - 160, 350, 320, 48), "Quit to Title", "title")

    def draw_dead(self):
        scr = self.screen
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((120, 0, 0, 150))
        scr.blit(ov, (0, 0))
        draw_text(scr, "You Died!", self.f_xl, (255, 255, 255), (SW // 2, 150), "center")
        draw_text(scr, self.death_msg, self.f_m, (255, 220, 220), (SW // 2, 220), "center")
        draw_text(scr, "Your items dropped where you fell.", self.f_s, (255, 220, 220), (SW // 2, 250), "center")
        self.button(pygame.Rect(SW // 2 - 160, 300, 320, 48), "Respawn", "respawn")
        self.button(pygame.Rect(SW // 2 - 160, 360, 320, 48), "Title Screen", "title")

    def draw_win(self):
        scr = self.screen
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((10, 30, 60, 200))
        scr.blit(ov, (0, 0))
        draw_text(scr, "YOU WIN!", self.f_xl, (255, 235, 90), (SW // 2, 130), "center")
        draw_text(scr, "The helicopter engine roars to life...", self.f_m, (255, 255, 255), (SW // 2, 210), "center")
        draw_text(scr, "You escape the island and reach a city!", self.f_m, (255, 255, 255), (SW // 2, 245), "center")
        draw_text(scr, f"Time survived: {self.day_number()} day(s)   |   Press R for a new island", self.f_s, (210, 220, 255), (SW // 2, 290), "center")
        self.button(pygame.Rect(SW // 2 - 160, 340, 320, 48), "New World", "newworld")
        self.button(pygame.Rect(SW // 2 - 160, 400, 320, 48), "Title Screen", "title")

    def draw_repair(self):
        scr = self.screen
        self.shade(170)
        r = self.repair
        panel = pygame.Rect(SW // 2 - 330, 130, 660, 360)
        pygame.draw.rect(scr, (24, 24, 28), panel.inflate(8, 8))
        pygame.draw.rect(scr, (60, 62, 70), panel)
        draw_text(scr, "REPAIR THE HELICOPTER", self.f_l, (255, 235, 120), (SW // 2, panel.y + 14), "midtop")
        prompts = ["Press SPACE / click to pour in the gasoline...", "Press SPACE / click to fix the copter blades!",
                   "Press SPACE / click to try and start the helicopter..."]
        done = ["Tank full!", "Blades fixed!", "The helicopter starts and the engine roars to life!"]
        y = panel.y + 80
        for i in range(3):
            if r["stage"] > i:
                txt, col = done[i], (140, 255, 140)
            elif r["stage"] == i:
                txt, col = prompts[i], (255, 255, 255)
            else:
                txt, col = prompts[i].split("...")[0].split("!")[0].replace("Press SPACE / click to ", "").capitalize(), (140, 140, 140)
            draw_text(scr, txt, self.f_m, col, (panel.x + 30, y))
            bw = 600
            pygame.draw.rect(scr, (20, 20, 20), (panel.x + 28, y + 30, bw + 4, 18))
            if r["stage"] > i:
                frac = 1.0
            elif r["stage"] == i:
                frac = r["count"] / r["need"][i]
            else:
                frac = 0.0
            pygame.draw.rect(scr, (240, 190, 50) if r["stage"] == i else (110, 210, 90), (panel.x + 30, y + 32, int(bw * frac), 14))
            y += 78
        if r["stage"] >= 3:
            draw_text(scr, "You get into the helicopter... the key is already there.", self.f_s, (255, 255, 255), (SW // 2, panel.bottom - 24), "center")
            ang = self.anim * 20
            cx, cy = SW // 2, panel.bottom + 40
            for k in range(2):
                a = ang + k * math.pi
                pygame.draw.line(scr, (230, 230, 230), (cx - math.cos(a) * 120, cy - math.sin(a) * 12), (cx + math.cos(a) * 120, cy + math.sin(a) * 12), 6)
        else:
            draw_text(scr, "Esc: step back", self.f_s, (200, 200, 200), (SW // 2, panel.bottom - 22), "center")

    def draw_inventory(self):
        scr = self.screen
        self.shade(170)
        lay = self.inv_layout()
        p = lay["panel"]
        pygame.draw.rect(scr, (20, 20, 24), p.inflate(8, 8))
        pygame.draw.rect(scr, (198, 198, 198), p)
        pygame.draw.rect(scr, (60, 60, 64), p, 3)
        draw_text(scr, "Crafting", self.f_m, (50, 50, 50), (p.x + 20, p.y + 16), shadow=False)
        draw_text(scr, "Inventory", self.f_m, (50, 50, 50), (p.x + 450, p.y + 16), shadow=False)
        mx, my = pygame.mouse.get_pos()
        hover_item = None
        for i, rect in enumerate(lay["recipes"]):
            rec = RECIPES[i]
            ok = all(self.inv.count(k) >= v for k, v in rec["need"].items())
            hov = rect.collidepoint((mx, my))
            pygame.draw.rect(scr, (40, 40, 44), rect)
            pygame.draw.rect(scr, (150, 190, 150) if ok and hov else (120, 150, 120) if ok else (130, 110, 110) if hov else (100, 100, 104), rect.inflate(-4, -4))
            ic = self.get_icon(rec["out"])
            scr.blit(ic, (rect.x + 8, rect.y + 12))
            label = rec["out"] + (f" x{rec['n']}" if rec["n"] > 1 else "")
            draw_text(scr, label, self.f_s, (255, 255, 255), (rect.x + 48, rect.y + 7))
            xx = rect.x + 48
            for k, v in rec["need"].items():
                have = self.inv.count(k)
                scr.blit(self.get_small_icon(k), (xx, rect.y + 28))
                col = (170, 255, 170) if have >= v else (255, 140, 140)
                draw_text(scr, f"{have}/{v}", self.f_s, col, (xx + 24, rect.y + 32))
                xx += 74
            if hov:
                hover_item = ("tip", rec["info"])
        for i, rect in lay["slots"].items():
            self.draw_slot(rect, self.inv.slots[i], i == self.sel)
            if rect.collidepoint((mx, my)) and self.inv.slots[i]:
                hover_item = ("name", self.inv.slots[i]["name"])
        gy = p.y + 64
        draw_text(scr, "Hotbar", self.f_s, (60, 60, 60), (p.x + 450, gy + 3 * 54 + 2), shadow=False)
        notes = ["Left-click: pick up / place stack", "Right-click: split stack / place one",
                 "Click a recipe to craft it.", "Campfire stones are not consumed.",
                 "Hotbar slot 1-9 = what you hold."]
        for i, n in enumerate(notes):
            draw_text(scr, n, self.f_s, (70, 70, 70), (p.x + 450, p.y + 330 + i * 22), shadow=False)
        if self.cursor:
            ic = self.get_icon(self.cursor["name"])
            scr.blit(ic, ic.get_rect(center=(mx, my)))
            if self.cursor["n"] > 1:
                draw_text(scr, str(self.cursor["n"]), self.f_s, (255, 255, 255), (mx + 14, my + 14), "bottomright")
        elif hover_item:
            img = self.f_s.render(hover_item[1], True, (255, 255, 255))
            r = img.get_rect(topleft=(mx + 14, my + 12)).inflate(10, 6)
            r.clamp_ip(pygame.Rect(0, 0, SW, SH))
            pygame.draw.rect(scr, (20, 10, 40), r)
            pygame.draw.rect(scr, (90, 50, 160), r, 2)
            scr.blit(img, (r.x + 5, r.y + 3))

    def draw_map(self):
        scr = self.screen
        self.shade(190)
        S = 5
        big = pygame.transform.scale(self.fog, (WW * S, WH * S))
        pos = ((SW - WW * S) // 2, (SH - WH * S) // 2 + 8)
        pygame.draw.rect(scr, (130, 96, 50), (pos[0] - 10, pos[1] - 10, WW * S + 20, WH * S + 20))
        pygame.draw.rect(scr, (236, 216, 160), (pos[0] - 6, pos[1] - 6, WW * S + 12, WH * S + 12))
        scr.blit(big, pos)
        st = self.world.structs
        for name, col in (("boathouse", (150, 100, 50)), ("cabin", (100, 70, 30))):
            x, y = st[name]
            if self.revealed[int(y)][int(x)]:
                pygame.draw.rect(scr, (20, 20, 20), (pos[0] + x * S - 4, pos[1] + y * S - 4, 9, 9))
                pygame.draw.rect(scr, col, (pos[0] + x * S - 3, pos[1] + y * S - 3, 7, 7))
        x, y = st["crash"]
        cx, cy = pos[0] + x * S, pos[1] + y * S
        pygame.draw.line(scr, (255, 40, 40), (cx - 7, cy - 7), (cx + 7, cy + 7), 4)
        pygame.draw.line(scr, (255, 40, 40), (cx - 7, cy + 7), (cx + 7, cy - 7), 4)
        blink = int(self.anim * 3) % 2
        px, py = pos[0] + self.px * S, pos[1] + self.py * S
        pygame.draw.circle(scr, (20, 20, 20), (px, py), 6)
        pygame.draw.circle(scr, (255, 255, 255) if blink else (255, 220, 60), (px, py), 4)
        draw_text(scr, "ISLAND MAP", self.f_l, (255, 255, 255), (SW // 2, 4), "midtop")
        draw_text(scr, "X crash site     brown squares: buildings     white dot: you     (M / Esc to close)",
                  self.f_s, (255, 255, 255), (SW // 2, SH - 8), "midbottom")

    # ---------------------------------------------------------- loop
    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.anim += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(e)
            if self.state == "play":
                self.update(dt)
            elif self.state == "repair":
                self.update_repair(dt)
            elif self.state in ("dead", "win"):
                self.update_particles(dt)
                self.cam_update(dt)
                for m in self.mobs[:]:
                    if self.state == "dead":
                        self.update_mob(m, dt)
                self.clock_t += dt if self.state == "dead" else 0
            self.draw()
            pygame.display.flip()


def main():
    pygame.init()
    pygame.display.set_caption("Survival Island")
    screen = pygame.display.set_mode((SW, SH))
    Game(screen).run()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()