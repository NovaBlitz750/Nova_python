#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SURVIVAL ISLAND 3D  -  first-person voxel edition (Ursina)
==========================================================
Your helicopter crashed on a tropical island. Gather resources, craft tools,
hunt, fish, cook, BUILD a shelter, survive the night and repair the
helicopter to escape!  Same island generator, items, recipes and animals as
the 2D pygame version - now in 3D with free block building.

Install:  pip install ursina
Run:      python survival_island_3d.py        (this file is fully standalone)

CONTROLS
  W A S D ........ move             Shift ........ sprint      Space ... jump
  Mouse .......... look             Hold LEFT .... mine / chop / attack / break blocks
  RIGHT click .... place block / eat / cast & reel / shoot bow / open / cook / repair
  1-9 / wheel .... hotbar           E ............ inventory + crafting
  Q .............. drop item        M ............ map (needs Map)
  H / F1 ......... help             Esc .......... pause
"""
import math
import random
import sys

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



# ============================================================== 3D LAYER (Ursina)
import time as _pytime
from ursina import (Ursina, Entity, Text, Mesh, Button, color, camera, window,
                    mouse, scene, held_keys, destroy)

CH = 16                              # chunk size in tiles
EYE, PW, PH = 1.62, 0.30, 1.75       # eye height, player radius, player height
GRAV, JUMP = 27.0, 8.4
SEA = -0.25                          # visual water level
BUILD_REACH = 5.0

# ---- building materials: name -> (colour, seconds to break)
BLOCKS = {"Planks": ((178, 136, 80), 0.55),
          "Stone Block": ((128, 128, 136), 1.0),
          "Thatch": ((218, 192, 98), 0.35)}
PLACEABLE = {"Campfire": "campfire", "Torch": "torch"}
PLACEABLE.update({k: "block" for k in BLOCKS})
RECIPES[-1] = {"out": "Planks", "n": 4, "need": {"Branches": 4},
               "info": "Building block. Right-click to place, stack them up!"}
RECIPES += [
    {"out": "Stone Block", "n": 2, "need": {"Stones": 3}, "info": "Sturdy building block (makes 2)."},
    {"out": "Thatch", "n": 4, "need": {"Vines": 3, "Branches": 1}, "info": "Light roofing block (makes 4)."},
]

# collision height of each object (in blocks) and extra "targetable" heights
OBJ_H = {"tree": 3, "palm": 3, "rock": 1, "bush": 1, "wall": 3, "cupboard": 1,
         "shelf": 2, "chest": 1, "heli": 2, "campfire": 1}
HIT_H = {"glint": 0.4, "sapling": 0.6, "bare_bush": 0.5, "torch": 1.0}

TOP_RGB = {SAND: (226, 210, 150), GRASS: (104, 168, 64), JUNGLE: (54, 128, 54),
           HILL: (128, 130, 136), FLOOR: (160, 114, 64), WATER: (52, 110, 200), DEEP: (24, 52, 124)}
SIDE_RGB = {SAND: (200, 184, 130), GRASS: (112, 84, 54), JUNGLE: (98, 76, 48),
            HILL: (110, 110, 118), FLOOR: (120, 84, 48), WATER: (40, 90, 170), DEEP: (20, 44, 104)}
ITEM_RGB = {"Branches": (130, 92, 52), "Stones": (140, 140, 146), "Vines": (60, 150, 70),
            "Coconut": (110, 76, 44), "Fish": (120, 170, 200), "Raw Meat": (220, 110, 120),
            "Cooked Meat": (150, 90, 50), "Bread": (220, 180, 110), "Key": (240, 210, 90),
            "Campfire": (255, 140, 40), "Torch": (255, 170, 40), "Map": (230, 210, 160),
            "Gasoline Can": (200, 40, 40), "Duct Tape": (150, 150, 150), "Arrow": (200, 200, 200)}


def item_rgb(name):
    if name in BLOCKS:
        return BLOCKS[name][0]
    if name in ITEM_RGB:
        return ITEM_RGB[name]
    h = sum(ord(c) * (i + 3) for i, c in enumerate(name))
    return (80 + h * 7 % 150, 80 + h * 13 % 150, 80 + h * 29 % 150)


def col3(rgb, a=1.0):
    return color.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, a)


# ---------------------------------------------------------------- mesh helpers
_cc = {}


def shade(rgb, s):
    k = (rgb, s)
    c = _cc.get(k)
    if c is None:
        c = _cc[k] = color.Color(min(1.0, rgb[0] * s / 255), min(1.0, rgb[1] * s / 255),
                                 min(1.0, rgb[2] * s / 255), 1)
    return c


def quad(V, C, a, b, c, d, col):
    V += (a, b, c, a, c, d)
    C += (col,) * 6


def box(V, C, x0, y0, z0, x1, y1, z1, rgb, bottom=False):
    t, sx, sz = shade(rgb, 1.0), shade(rgb, 0.8), shade(rgb, 0.66)
    quad(V, C, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), t)
    quad(V, C, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1), sx)
    quad(V, C, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), sx)
    quad(V, C, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), sz)
    quad(V, C, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), sz)
    if bottom:
        quad(V, C, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), shade(rgb, 0.5))


# ---------------------------------------------------------------- island (voxel view of the World)
class Island:
    def __init__(self, world):
        self.w = world
        self.blocks = {}                       # (x, y, z) -> block name   (player-built)
        self.cblocks = {}                      # chunk -> set of block keys
        self.tops = [[self._top(x, z) for x in range(WW)] for z in range(WH)]
        hx, hy = world.heli_origin             # keep the helicopter level
        m = max(self.tops[hy + j][hx + i] for i in range(3) for j in range(2))
        for i in range(3):
            for j in range(2):
                self.tops[hy + j][hx + i] = m

    def _top(self, x, z):
        g = self.w.ground[z][x]
        if g == DEEP:
            return -3
        if g == WATER:
            return -1
        if g == HILL:
            return 1 + (hash((x // 3, z // 3)) & 1)
        return 0

    def vis(self, x, z):
        if not (0 <= x < WW and 0 <= z < WH):
            return -2.0
        return SEA if self.w.ground[z][x] in (DEEP, WATER) else float(self.tops[z][x])

    def solid(self, x, y, z):
        if not (0 <= x < WW and 0 <= z < WH):
            return True
        t = self.tops[z][x]
        if y < t or (x, y, z) in self.blocks:
            return True
        if y == t + 3 and self.w.ground[z][x] == FLOOR:      # house roofs
            return True
        h = OBJ_H.get(self.w.obj[z][x], 0)
        return h > 0 and t <= y < t + h

    def floor_under(self, x, y, z):
        ix, iz = int(math.floor(x)), int(math.floor(z))
        iy = int(math.floor(y))
        while iy > -4:
            if self.solid(ix, iy - 1, iz):
                return iy
            iy -= 1
        return -3

    # ---- block editing
    def set_block(self, key, name):
        self.blocks[key] = name
        self.cblocks.setdefault((key[0] // CH, key[2] // CH), set()).add(key)

    def del_block(self, key):
        name = self.blocks.pop(key, None)
        self.cblocks.get((key[0] // CH, key[2] // CH), set()).discard(key)
        return name

    # ---- geometry
    def tile_geo(self, V, C, x, z):
        w = self.w
        g = w.ground[z][x]
        vt = self.vis(x, z)
        j = 0.93 + ((x * 73 ^ z * 151) & 15) * 0.009
        b = TOP_RGB[g]
        quad(V, C, (x, vt, z), (x + 1, vt, z), (x + 1, vt, z + 1), (x, vt, z + 1),
             shade((int(b[0] * j), int(b[1] * j), int(b[2] * j)), 1.0))
        s = SIDE_RGB[g]
        for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nv = self.vis(x + dx, z + dz)
            if nv < vt - 0.01:
                sh = shade(s, 0.85 if dx else 0.7)
                if dx == -1:
                    quad(V, C, (x, nv, z), (x, nv, z + 1), (x, vt, z + 1), (x, vt, z), sh)
                elif dx == 1:
                    quad(V, C, (x + 1, nv, z), (x + 1, nv, z + 1), (x + 1, vt, z + 1), (x + 1, vt, z), sh)
                elif dz == -1:
                    quad(V, C, (x, nv, z), (x + 1, nv, z), (x + 1, vt, z), (x, vt, z), sh)
                else:
                    quad(V, C, (x, nv, z + 1), (x + 1, nv, z + 1), (x + 1, vt, z + 1), (x, vt, z + 1), sh)
        t = self.tops[z][x]
        o = w.obj[z][x]
        if o:
            self.obj_geo(V, C, o, x, z, t)
        if g == FLOOR:                                            # roofs on the houses
            box(V, C, x, t + 3, z, x + 1, t + 3.3, z + 1, (120, 82, 48), True)

    def obj_geo(self, V, C, o, x, z, t):
        B = lambda a, b, c, d, e, f, rgb, bt=False: box(V, C, x + a, t + b, z + c, x + d, t + e, z + f, rgb, bt)
        if o == "tree":
            B(.35, 0, .35, .65, 1.6, .65, (98, 68, 40))
            B(-.1, 1.3, -.1, 1.1, 2.1, 1.1, (46, 120, 48), True)
            B(.2, 2.1, .2, .8, 2.6, .8, (58, 142, 56), True)
        elif o == "palm":
            B(.4, 0, .4, .6, 2.3, .6, (150, 120, 70))
            B(-.6, 2.3, .4, 1.6, 2.42, .6, (70, 154, 60), True)
            B(.4, 2.3, -.6, .6, 2.42, 1.6, (70, 154, 60), True)
            B(.42, 2.1, .42, .58, 2.3, .58, (110, 76, 44))
        elif o == "rock":
            B(.12, 0, .12, .88, .6, .88, (128, 128, 134))
            B(.3, .6, .3, .7, .95, .7, (150, 150, 156))
        elif o == "bush":
            B(.08, 0, .08, .92, .75, .92, (58, 150, 58), True)
        elif o == "bare_bush":
            B(.2, 0, .2, .8, .45, .8, (122, 92, 52))
        elif o == "sapling":
            B(.4, 0, .4, .6, .55, .6, (80, 172, 70))
        elif o == "glint":
            B(.25, 0, .25, .75, .06, .75, (240, 210, 90))
            B(.46, 0, .46, .54, .5, .54, (255, 235, 130))
        elif o == "campfire":
            B(.15, 0, .2, .85, .2, .34, (100, 70, 40))
            B(.15, 0, .66, .85, .2, .8, (100, 70, 40))
            B(.33, .2, .33, .67, .75, .67, (255, 140, 30))
            B(.42, .2, .42, .58, .5, .58, (255, 225, 90))
        elif o == "torch":
            B(.45, 0, .45, .55, .7, .55, (110, 80, 40))
            B(.38, .7, .38, .62, 1.0, .62, (255, 170, 40))
        elif o == "wall":
            B(0, 0, 0, 1, 3, 1, (160, 118, 70))
            B(-.01, 1.45, -.01, 1.01, 1.55, 1.01, (120, 86, 50))
        elif o == "door":
            B(0, 2, 0, 1, 3, 1, (130, 90, 50))
        elif o == "cupboard":
            B(.08, 0, .08, .92, 1.0, .92, (130, 90, 50))
            B(.46, .1, .06, .54, .9, .1, (80, 52, 28))
        elif o == "shelf":
            B(.08, 0, .08, .92, 2.0, .92, (150, 110, 60))
            B(.12, .5, .04, .88, .56, .1, (90, 64, 34))
            B(.12, 1.1, .04, .88, 1.16, .1, (90, 64, 34))
        elif o == "chest":
            B(.1, 0, .15, .9, .6, .85, (150, 100, 40))
            B(.1, .6, .15, .9, .8, .85, (120, 78, 30))
            B(.45, .4, .1, .55, .65, .16, (240, 210, 90))
        elif o == "heli":
            B(0, 0, 0, 1, 1.6, 1, (62, 92, 124), True)
            B(.1, 1.6, .1, .9, 1.75, .9, (44, 44, 50))

    def build_chunk(self, cx, cz):
        V, C = [], []
        for z in range(cz * CH, min((cz + 1) * CH, WH)):
            for x in range(cx * CH, min((cx + 1) * CH, WW)):
                self.tile_geo(V, C, x, z)
        for k in self.cblocks.get((cx, cz), ()):
            box(V, C, k[0], k[1], k[2], k[0] + 1, k[1] + 1, k[2] + 1, BLOCKS[self.blocks[k]][0], True)
        return V, C


# ---------------------------------------------------------------- mob models
def _legs(sz, h, rgb, sx=.18, zz=.3):
    return [((sz, h, sz), (a, h / 2, b), rgb) for a in (-sx, sx) for b in (-zz, zz)]


MOB_PARTS = {
    "Wild Boar": [((.55, .5, .9), (0, .55, 0), (96, 62, 42)), ((.42, .4, .4), (0, .6, .62), (84, 54, 36)),
                  ((.22, .16, .14), (0, .55, .84), (226, 150, 150))] + _legs(.13, .3, (70, 44, 30)),
    "Snake": [((.16, .12, .35), (0, .08, i * .3), (64, 142, 52) if i else (200, 190, 60))
              for i in range(-2, 3)],
    "Rabbit": [((.3, .28, .42), (0, .22, 0), (214, 204, 194)), ((.22, .2, .2), (0, .34, .26), (224, 214, 204)),
               ((.06, .22, .06), (-.06, .52, .27), (224, 214, 204)), ((.06, .22, .06), (.06, .52, .27), (224, 214, 204))],
    "Crab": [((.42, .16, .3), (0, .12, 0), (206, 70, 50)), ((.14, .1, .14), (-.26, .14, .2), (230, 90, 60)),
             ((.14, .1, .14), (.26, .14, .2), (230, 90, 60))],
}


def make_mob_entity(kind):
    e = Entity()
    for sc, pos, rgb in MOB_PARTS[kind]:
        Entity(parent=e, model='cube', scale=sc, position=pos, color=col3(rgb))
    return e


HELP = ("SURVIVAL ISLAND 3D\n\n"
        "WASD ... move        Shift ... sprint        Space ... jump\n"
        "Mouse ... look       Hold LEFT ... mine / chop / attack / break blocks\n"
        "RIGHT click ... place block / eat / cast & reel / shoot / open / cook / repair\n"
        "1-9 / wheel ... hotbar     E ... inventory + crafting     Q ... drop item\n"
        "M ... map (needs Map)      H ... this help      Esc ... pause\n\n"
        "BUILDING: craft Planks, Stone Blocks or Thatch (press E), hold them\n"
        "and right-click to place. Stack blocks to build walls, towers and\n"
        "roofs. Hold left-click on a block to take it back.\n\n"
        "GOAL: find the key, open the boathouse cupboard, find the manual in\n"
        "the cabin chest, then repair the helicopter on the hill!")


# ================================================================ GAME
class Game3D(Entity):
    def __init__(self):
        super().__init__()
        self.cents, self.mob_ents, self.drop_ents, self.fx, self.arrows = {}, [], [], [], []
        self.rig = Entity()
        self.piv = Entity(parent=self.rig, y=EYE)
        camera.parent = self.piv
        camera.position, camera.rotation = (0, 0, 0), (0, 0, 0)
        camera.fov = 85
        try:
            camera.clip_plane_far = 170
            camera.clip_plane_near = 0.05
        except Exception:
            pass
        self.sel_box = Entity(model='wireframe_cube', color=color.black, scale=1.02, enabled=False)
        self.bobber = Entity(model='cube', color=color.red, scale=.16, enabled=False)
        self.hand = Entity(parent=camera, model='cube', scale=(.14, .14, .5), position=(.42, -.36, .75),
                           rotation=(8, -18, 0), color=col3((224, 172, 130)))
        self.rotor = Entity(enabled=False)
        for a in (0, 90):
            Entity(parent=self.rotor, model='cube', scale=(4.6, .05, .22), rotation_y=a, color=col3((40, 40, 46)))
        self.state, self.panel = "play", None
        self.splash_t = 14.0
        self._last = _pytime.perf_counter()
        self.build_ui()
        self.new_game()
        self.set_panel(None)

    # ------------------------------------------------------------ UI
    def label(self, text='', x=0, y=0, scale=1.0, origin=(0, 0), col=color.white):
        return Text(text=text, parent=camera.ui, position=(x, y), origin=origin, scale=scale, color=col)

    def build_ui(self):
        ui = camera.ui
        self.dark = Entity(parent=ui, model='quad', scale=(4, 2), color=col3((0, 0, 14), 0), z=.5)
        self.red = Entity(parent=ui, model='quad', scale=(4, 2), color=col3((200, 0, 0), 0), z=.45)
        self.label('+', 0, 0, 1.6)
        for i, (nm, yy, rgb) in enumerate((("HP", -.34, (210, 50, 50)), ("FOOD", -.385, (220, 150, 50)))):
            self.label(nm, -.86, yy + .065, .7, (-.5, 0))
            Entity(parent=ui, model='quad', origin=(-.5, 0), position=(-.78, yy + .065), scale=(.3, .026), color=col3((20, 20, 20)))
            f = Entity(parent=ui, model='quad', origin=(-.5, 0), position=(-.78, yy + .065), scale=(.3, .02), color=col3(rgb), z=-.01)
            setattr(self, "bar_hp" if i == 0 else "bar_food", f)
        self.slot_q, self.slot_t = [], []
        for i in range(9):
            q = Entity(parent=ui, model='quad', position=(-.36 + i * .09, -.44), scale=(.08, .08), color=col3((30, 30, 34), .8))
            t = self.label('', -.36 + i * .09, -.44, .55)
            self.slot_q.append(q)
            self.slot_t.append(t)
        self.t_log = self.label('', -.86, .46, .7, (-.5, .5))
        self.t_clock = self.label('', .86, .47, .8, (.5, .5))
        self.t_msg = self.label('', 0, .12, 1.4)
        self.t_sub = self.label('', 0, .0, .8)
        self.t_tip = self.label('', 0, -.36, .8, col=col3((255, 235, 140)))
        self.help_root = Entity(parent=ui, enabled=False)
        Entity(parent=self.help_root, model='quad', scale=(1.5, .75), color=col3((10, 10, 20), .88), z=.1)
        Text(text=HELP, parent=self.help_root, position=(-.7, .34), origin=(-.5, .5), scale=.78)

        # inventory + crafting
        r = self.inv_root = Entity(parent=ui, enabled=False)
        Entity(parent=r, model='quad', scale=(1.72, .8), color=col3((16, 16, 24), .93), z=.1)
        Text(text="CRAFTING  (click a recipe)", parent=r, position=(-.82, .37), origin=(-.5, .5), scale=.8)
        Text(text="INVENTORY  (click a slot to swap it into your held slot)", parent=r, position=(.0, .37), origin=(-.5, .5), scale=.8)
        self.rec_b, self.rec_t = [], []
        for i, rec in enumerate(RECIPES):
            b = Button(parent=r, text=rec["out"] + (f" x{rec['n']}" if rec["n"] > 1 else ""), scale=(.26, .052),
                       position=(-.66, .31 - i * .068), color=col3((50, 90, 60)))
            b.on_click = lambda rec=rec: self.craft(rec)
            self.rec_b.append(b)
            self.rec_t.append(Text(text='', parent=r, position=(-.52, .325 - i * .068), origin=(-.5, .5), scale=.62))
        self.inv_b = []
        for i in range(36):
            row, col_ = (3, i) if i < 9 else ((i - 9) // 9, (i - 9) % 9)
            x = .06 + col_ * .082
            y = .27 - row * .082 - (.03 if row == 3 else 0)
            b = Button(parent=r, text='', scale=(.075, .075), position=(x, y), color=col3((50, 50, 60)))
            b.on_click = lambda i=i: self.slot_click(i)
            self.inv_b.append(b)
        # map
        self.map_root = Entity(parent=ui, enabled=False)
        Entity(parent=self.map_root, model='quad', scale=(1.0, .96), color=col3((130, 96, 50)), z=.3)
        self.map_mesh = Entity(parent=self.map_root, z=.2)
        self.map_dot = Entity(parent=self.map_root, model='quad', scale=.016, color=col3((255, 255, 255)), z=-.1)
        self.map_x = Entity(parent=self.map_root, model='quad', scale=.014, color=col3((255, 40, 40)), rotation_z=45, z=-.1)
        Text(text="ISLAND MAP   (X = crash site, M / Esc to close)", parent=self.map_root, position=(0, .5), origin=(0, .5), scale=.8)

    def set_panel(self, p):
        self.panel = p
        self.inv_root.enabled = p == "inv"
        self.map_root.enabled = p == "map"
        self.help_root.enabled = p == "help"
        mouse.locked = (p is None and self.state == "play")
        if p == "inv":
            self.refresh_inv()
        elif p == "map":
            self.build_map()

    def refresh_inv(self):
        for i, b in enumerate(self.inv_b):
            s = self.inv.slots[i]
            b.text = f"{s['name'][:7]}\n{s['n']}" if s else ""
            b.color = col3((120, 160, 90) if i == self.sel else (50, 50, 60))
        for i, rec in enumerate(RECIPES):
            ok = all(self.inv.count(k) >= v for k, v in rec["need"].items())
            self.rec_b[i].color = col3((60, 130, 70) if ok else (80, 56, 56))
            self.rec_t[i].text = "  ".join(f"{k} {self.inv.count(k)}/{v}" for k, v in rec["need"].items())

    def slot_click(self, i):
        s = self.inv.slots
        s[i], s[self.sel] = s[self.sel], s[i]
        self.refresh_inv()

    def build_map(self):
        V, C = [], []
        S = .0082
        for z in range(WH):
            for x in range(WW):
                if self.revealed[z][x]:
                    c = shade(MAP_COL[self.world.ground[z][x]], 1.0)
                    X, Y = (x - WW / 2) * S, (z - WH / 2) * S
                    quad(V, C, (X, Y, 0), (X + S, Y, 0), (X + S, Y + S, 0), (X, Y + S, 0), c)
        if V:
            self.map_mesh.model = Mesh(vertices=V, colors=C)
        self.map_mesh.double_sided = True
        cx, cz = self.world.structs["crash"]
        self.map_x.position = ((cx - WW / 2) * S, (cz - WH / 2) * S, -.1)

    # ------------------------------------------------------------ game state
    def new_game(self):
        for e in list(self.cents.values()) + self.mob_ents + self.drop_ents + [f[0] for f in self.fx] + [a[7] for a in self.arrows]:
            destroy(e)
        self.cents, self.mob_ents, self.drop_ents, self.fx, self.arrows = {}, [], [], [], []
        self.world = w = World()
        self.isl = Island(w)
        self.px, self.pz = w.spawn
        self.ph = float(self.isl.tops[int(self.pz)][int(self.px)])
        self.vy, self.grounded = 0.0, True
        self.rig.rotation_y, self.piv.rotation_x = 0, 0
        self.health, self.hunger = 100.0, 100.0
        self.inv, self.sel = Inventory(), 0
        self.clock_t = 0.0
        self.atk_cd = self.bow_cd = self.swing = self.hurt_flash = 0.0
        self.mine_key, self.mine_prog, self.mine_fx = None, 0.0, 0.0
        self.mobs, self.drops, self.regrow, self.lights = [], [], [], set()
        self.fish, self.repair, self.target = None, None, None
        self.hunger_warn, self.regen_t, self.starve_t, self.spawn_t = 0, 0.0, 0.0, 20.0
        self.log, self.log_str, self.death_msg, self.key_found = [], "", "", False
        self.revealed = [[False] * WW for _ in range(WH)]
        self.last_rev = None
        self.dirty_chunks = set()
        self.state = "play"
        for kind, grounds, n in (("Wild Boar", (JUNGLE, HILL, GRASS), 9), ("Snake", (JUNGLE, GRASS), 8),
                                 ("Rabbit", (GRASS, JUNGLE), 16), ("Crab", (SAND,), 14)):
            for _ in range(n):
                p = w.rand_tile(grounds)
                if p:
                    self.add_mob(kind, *p)
        hx, hy = w.structs["crash"]
        for _ in range(2):
            self.add_mob("Wild Boar", hx + random.uniform(-4, 4), hy + random.uniform(2, 5))
        for m in self.mobs[:]:
            if not self.mob_free(m.x, m.y, MOBS[m.kind]["r"], m.kind == "Crab"):
                self.remove_mob(m)
        for cz in range((WH + CH - 1) // CH):
            for cx in range((WW + CH - 1) // CH):
                self.cents[(cx, cz)] = Entity(double_sided=True)
                self.rebuild(cx, cz)
        ox, oz = hx, hy
        self.rotor.position = (ox, float(self.isl.tops[int(hy)][int(hx)]) + 1.85, oz)
        self.rotor.enabled = True
        self.reveal(True)
        self.add_log("You survived a helicopter crash... Gather branches (hold LEFT click on a tree)!", (255, 235, 120))
        self.add_log("Press H for help, E for crafting and building.", (200, 200, 200))

    def add_mob(self, kind, x, y):
        m = Mob(kind, x, y)
        m.ent = make_mob_entity(kind)
        self.mobs.append(m)
        self.mob_ents.append(m.ent)

    def remove_mob(self, m):
        if m in self.mobs:
            self.mobs.remove(m)
        if m.ent in self.mob_ents:
            self.mob_ents.remove(m.ent)
        destroy(m.ent)

    def rebuild(self, cx, cz):
        V, C = self.isl.build_chunk(cx, cz)
        e = self.cents[(cx, cz)]
        if V:
            e.model = Mesh(vertices=V, colors=C)

    def mark(self, tx, tz):
        self.dirty_chunks.add((tx // CH, tz // CH))

    def add_log(self, text, col=(255, 255, 255)):
        self.log.append([text, 7.0])
        self.log = self.log[-7:]

    # ------------------------------------------------------------ helpers
    def held(self):
        return self.inv.slots[self.sel]

    def held_name(self):
        h = self.held()
        return h["name"] if h else None

    def use_tool(self, n):
        s = self.inv.slots[self.sel]
        if s and s["name"] in TOOL_DUR:
            s["dur"] -= n
            if s["dur"] <= 0:
                self.add_log(f"Your {s['name']} broke!")
                self.inv.slots[self.sel] = None

    def phase(self):
        return (self.clock_t / DAY_LENGTH + START_PHASE) % 1.0

    def daylight(self):
        return clamp(0.5 + 0.65 * math.sin(math.tau * (self.phase() - 0.25)), 0.0, 1.0)

    def look_dir(self):
        y, p = math.radians(self.rig.rotation_y), math.radians(self.piv.rotation_x)
        return (math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p))

    def eye(self):
        return (self.px, self.ph + EYE, self.pz)

    def blocked(self, x, y, z):
        isl = self.isl
        for ix in range(int(math.floor(x - PW)), int(math.floor(x + PW)) + 1):
            for iz in range(int(math.floor(z - PW)), int(math.floor(z + PW)) + 1):
                if not (0 <= ix < WW and 0 <= iz < WH):
                    return True
                if self.world.ground[iz][ix] == DEEP and y < 4:
                    return True
                for iy in range(int(math.floor(y)), int(math.floor(y + PH - 1e-3)) + 1):
                    if isl.solid(ix, iy, iz):
                        return True
        return False

    def mob_free(self, x, z, r, water_ok=False):
        w, isl = self.world, self.isl
        for cx in (x - r, x + r):
            for cz in (z - r, z + r):
                tx, tz = int(math.floor(cx)), int(math.floor(cz))
                if not (0 <= tx < WW and 0 <= tz < WH):
                    return False
                g = w.ground[tz][tx]
                if g == DEEP or g == FLOOR or (g == WATER and not water_ok) or w.obj[tz][tx] in SOLID_OBJ:
                    return False
                t = isl.tops[tz][tx]
                if (tx, t, tz) in isl.blocks or (tx, t + 1, tz) in isl.blocks:
                    return False
        return True

    def raycast(self, reach=BUILD_REACH, water=False):
        isl, w = self.isl, self.world
        ox, oy, oz = self.eye()
        dx, dy, dz = self.look_dir()
        prev = cell = (int(math.floor(ox)), int(math.floor(oy)), int(math.floor(oz)))
        t = 0.0
        while t < reach:
            t += 0.04
            x, y, z = ox + dx * t, oy + dy * t, oz + dz * t
            c = (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
            if c != cell:
                prev, cell = cell, c
            ix, iy, iz = c
            if not (0 <= ix < WW and 0 <= iz < WH):
                return None
            top = isl.tops[iz][ix]
            if water and y < SEA and w.ground[iz][ix] in (WATER, DEEP):
                return ("water", (x, z))
            if c in isl.blocks:
                return ("blk", c, prev)
            o = w.obj[iz][ix]
            if o and top <= y < top + max(OBJ_H.get(o, 0), HIT_H.get(o, 0)):
                return ("obj", (ix, iz), prev)
            if y < top or (iy == top + 3 and w.ground[iz][ix] == FLOOR):
                return ("ter", c, prev)
        return None

    def burst(self, x, h, z, rgb, n=8):
        for _ in range(n):
            e = Entity(model='cube', scale=.09, color=col3(rgb), position=(x, h, z))
            self.fx.append([e, [random.uniform(-1.5, 1.5), random.uniform(1.5, 4), random.uniform(-1.5, 1.5)],
                            random.uniform(.4, .8)])

    def drop(self, x, z, name, n=1, dur=None, delay=.6, pop=True, h=None):
        d = Drop(x, z, name, n, dur, delay, pop)
        d.h = (h if h is not None else self.isl.floor_under(x, self.ph + 2, z)) + .3
        d.vh = 3.0 if pop else 0.0
        d.ent = Entity(model='cube', scale=.24, color=col3(item_rgb(name)), position=(x, d.h, z))
        self.drops.append(d)
        self.drop_ents.append(d.ent)

    def reveal(self, force=False):
        cell = (int(self.px) // 3, int(self.pz) // 3)
        if not force and cell == self.last_rev:
            return
        self.last_rev = cell
        for z in range(int(self.pz) - 11, int(self.pz) + 12):
            for x in range(int(self.px) - 11, int(self.px) + 12):
                if 0 <= x < WW and 0 <= z < WH and math.hypot(x - self.px, z - self.pz) < 11:
                    self.revealed[z][x] = True

    # ------------------------------------------------------------ combat / damage
    def hurt_player(self, dmg, src):
        self.health -= dmg
        self.hurt_flash = .3
        self.add_log(f"The {src} hits you! (-{int(dmg)})")
        if self.health <= 0:
            self.die(f"Killed by a {src}")

    def die(self, msg):
        self.state, self.death_msg = "dead", msg
        mouse.locked = False

    def hurt_mob(self, m, dmg, kx, kz):
        m.hp -= dmg
        m.hurt = .3
        m.kx, m.ky = kx * 4, kz * 4
        if m.hp <= 0:
            self.kill_mob(m)

    def kill_mob(self, m):
        spec = MOBS[m.kind]
        name, lo, hi = spec["drop"]
        n = random.randint(lo, hi) + (1 if self.held_name() == "Stone Knife" and hi > 0 else 0)
        h = self.isl.floor_under(m.x, self.ph + 2, m.y)
        self.burst(m.x, h + .4, m.y, (180, 40, 40), 8)
        if n > 0:
            self.drop(m.x, m.y, name, n)
        self.remove_mob(m)

    def mob_in_view(self, reach=2.7):
        ox, oy, oz = self.eye()
        dx, dy, dz = self.look_dir()
        best, bd = None, 1e9
        for m in self.mobs:
            vx, vy, vz = m.x - ox, self.isl.floor_under(m.x, self.ph + 2, m.y) + .35 - oy, m.y - oz
            d = math.sqrt(vx * vx + vy * vy + vz * vz)
            if d < reach and d > 0 and (vx * dx + vy * dy + vz * dz) / d > .9 and d < bd:
                best, bd = m, d
        return best

    def player_attack(self, m):
        dmg = WEAPON_DMG.get(self.held_name(), 2)
        if self.held_name() in ("Stone Axe", "Stone Knife"):
            self.use_tool(1)
        self.atk_cd, self.swing = .45, .2
        dx, dz = m.x - self.px, m.y - self.pz
        d = math.hypot(dx, dz) or 1
        self.hurt_mob(m, dmg, dx / d, dz / d)

    # ------------------------------------------------------------ world interaction
    def break_time(self, o):
        t, held = BREAK_TIME[o], self.held_name()
        if held == "Stone Axe" and o in ("tree", "palm"):
            t *= .3
        elif held == "Stone Axe" and o == "rock":
            t *= .8
        elif held == "Stone Knife" and o in ("bush", "bare_bush"):
            t *= .5
        return t

    def break_object(self, tx, tz):
        w = self.world
        o = w.obj[tz][tx]
        held = self.held_name()
        axe = held == "Stone Axe"
        cx, cz = tx + .5, tz + .5
        top = self.isl.tops[tz][tx]
        self.burst(cx, top + .6, cz, OBJ_PARTICLE.get(o, (150, 150, 150)), 12)
        w.obj[tz][tx] = None
        self.regrow = [r for r in self.regrow if (r[3], r[4]) != (tx, tz)]
        d = lambda *a: self.drop(cx, cz, *a, h=top)
        if o == "tree":
            d("Branches", 4 if axe else 1)
            if random.random() < .5:
                d("Vines", random.randint(1, 2))
            if random.random() < .3:
                d("Stones", 1)
            if axe:
                self.use_tool(4)
            w.obj[tz][tx] = "sapling"
            self.regrow.append([random.uniform(70, 110), "tree", "sapling", tx, tz])
        elif o == "palm":
            d("Branches", 2 if axe else 1)
            if random.random() < .7:
                d("Coconut", random.randint(1, 2))
            if axe:
                self.use_tool(4)
            w.obj[tz][tx] = "sapling"
            self.regrow.append([random.uniform(80, 120), "palm", "sapling", tx, tz])
        elif o == "rock":
            d("Stones", random.randint(1, 3))
            if axe:
                self.use_tool(2)
            self.regrow.append([random.uniform(120, 180), "rock", None, tx, tz])
        elif o == "bush":
            d("Vines", random.randint(1, 3))
            if held == "Stone Knife":
                self.use_tool(1)
            w.obj[tz][tx] = "bare_bush"
            self.regrow.append([random.uniform(45, 70), "bush", "bare_bush", tx, tz])
        elif o == "bare_bush":
            self.regrow.append([random.uniform(45, 70), "bush", None, tx, tz])
        elif o == "campfire":
            d("Campfire", 1)
            self.lights.discard((tx, tz))
        elif o == "torch":
            d("Torch", 1)
            self.lights.discard((tx, tz))
        elif o == "glint":
            d("Key", 1)
            self.key_found = True
            self.add_log("You dug up a rusty old KEY!")
        self.mark(tx, tz)

    def break_block(self, cell):
        name = self.isl.del_block(cell)
        if name:
            self.burst(cell[0] + .5, cell[1] + .5, cell[2] + .5, BLOCKS[name][0], 10)
            self.drop(cell[0] + .5, cell[2] + .5, name, 1, h=cell[1], pop=False)
            self.mark(cell[0], cell[2])

    def place_block(self, held, hit):
        if not hit or hit[0] == "water":
            return
        x, y, z = hit[2]
        if not (0 <= x < WW and 0 <= z < WH) or self.isl.solid(x, y, z) or y > 40:
            return
        if self.world.ground[z][x] == DEEP:
            return
        if (x + 1 > self.px - PW and x < self.px + PW and z + 1 > self.pz - PW and z < self.pz + PW
                and y + 1 > self.ph and y < self.ph + PH):
            return                                                  # would trap the player
        self.isl.set_block((x, y, z), held["name"])
        held["n"] -= 1
        if held["n"] <= 0:
            self.inv.slots[self.sel] = None
        self.mark(x, z)

    def place_obj(self, held, hit):
        if not hit or hit[0] == "water":
            return
        x, y, z = hit[2]
        if not (0 <= x < WW and 0 <= z < WH):
            return
        w, name = self.world, held["name"]
        if y != self.isl.tops[z][x] or w.obj[z][x] is not None or w.ground[z][x] in (DEEP, WATER) \
                or (x, y, z) in self.isl.blocks:
            self.add_log("Place campfires and torches on free ground.")
            return
        w.obj[z][x] = PLACEABLE[name]
        self.lights.add((x, z))
        held["n"] -= 1
        if held["n"] <= 0:
            self.inv.slots[self.sel] = None
        self.mark(x, z)

    def use_item(self):
        if self.fish is not None:
            return self.reel_in()
        hit = self.raycast()
        if hit and hit[0] == "obj":
            o = self.world.obj[hit[1][1]][hit[1][0]]
            if o in ("cupboard", "shelf", "chest", "heli", "campfire"):
                return self.interact(o, *hit[1])
        held = self.held()
        if not held:
            return
        n = held["name"]
        if n in FOOD:
            self.eat(held)
        elif n == "Fishing Rod":
            self.cast()
        elif n == "Bow":
            self.shoot()
        elif n in BLOCKS:
            self.place_block(held, hit)
        elif n in ("Campfire", "Torch"):
            self.place_obj(held, hit)

    def interact(self, o, tx, tz):
        w = self.world
        cx, cz = tx + .5, tz + .5
        top = self.isl.tops[tz][tx]
        if o == "campfire":
            held = self.held()
            if held and held["name"] in COOK:
                raw, n = held["name"], held["n"]
                self.inv.slots[self.sel] = None
                left = self.inv.add(COOK[raw], n)
                if left:
                    self.drop(self.px, self.pz, COOK[raw], left)
                self.add_log(f"You cook {n} {raw} and get {n} {COOK[raw]}.")
            else:
                self.add_log("Hold raw meat, fish or crab and right-click the campfire to cook it.")
        elif o == "cupboard":
            st = w.chests[(tx, tz)]
            if st["opened"]:
                self.add_log("The cupboard is empty.")
            elif self.inv.count("Key") <= 0:
                self.add_log("The cupboard is locked tight. You need a key...")
            else:
                st["yanks"] -= 1
                if st["yanks"] > 0:
                    self.add_log(random.choice(["The rusty lock won't budge... you yank harder!",
                                                "Attempt failed, try again!", "Clunk! Still stuck. Keep yanking!"]))
                else:
                    st["opened"] = True
                    self.inv.remove("Key", 1)
                    self.add_log("Attempt successful! Inside: a gasoline can, duct tape and engine oil.")
                    for it in ("Gasoline Can", "Duct Tape", "Engine Oil"):
                        self.drop(self.px, self.pz, it, 1)
        elif o == "shelf":
            st = w.chests[(tx, tz)]
            if st["opened"]:
                self.add_log("Nothing else on the shelf.")
            else:
                st["opened"] = True
                self.add_log("You find a map and 10 pieces of bread!")
                self.drop(self.px, self.pz, "Map", 1)
                self.drop(self.px, self.pz, "Bread", 10)
        elif o == "chest":
            st = w.chests[(tx, tz)]
            if st["opened"]:
                self.add_log("The chest is empty.")
            else:
                st["opened"] = True
                self.add_log("Planks, bread and a helicopter manual! You can now control a helicopter.")
                self.drop(self.px, self.pz, "Planks", 15)
                self.drop(self.px, self.pz, "Bread", 10)
                self.drop(self.px, self.pz, "Helicopter Manual", 1)
        elif o == "heli":
            self.repair_click()

    def repair_click(self):
        if self.state != "play":
            return
        missing = [it for it in REQUIRED_ITEMS if self.inv.count(it) <= 0]
        if missing:
            self.add_log("You can't repair it yet. You still need: " + ", ".join(missing))
            return
        if self.repair is None:
            self.repair = {"stage": 0, "count": 0, "need": [1, random.randint(3, 10), random.randint(2, 7)]}
        r = self.repair
        r["count"] += 1
        self.swing = .2
        prompts = ["Pouring in the gasoline...", "Fixing the copter blades...", "Trying to start the engine..."]
        done = ["Tank full!", "Blades fixed!", "The engine roars to life!"]
        if r["count"] >= r["need"][r["stage"]]:
            self.add_log(done[r["stage"]])
            r["stage"] += 1
            r["count"] = 0
            if r["stage"] >= 3:
                self.state = "win"
                mouse.locked = False
        else:
            self.add_log(prompts[r["stage"]] + " (keep right-clicking)")

    def eat(self, held):
        if self.hunger >= 100:
            self.add_log("You're not hungry.")
            return
        name = held["name"]
        self.hunger = min(100.0, self.hunger + FOOD[name])
        held["n"] -= 1
        if held["n"] <= 0:
            self.inv.slots[self.sel] = None
        self.add_log(f"You eat the {name}. Hunger is now {int(self.hunger)}.")
        if name == "Raw Meat" and random.random() < .35:
            self.health -= 6
            self.hurt_flash = .25
            self.add_log("Raw meat... you feel sick! (-6 health)")
            if self.health <= 0:
                self.die("Died of food poisoning")

    def shoot(self):
        if self.bow_cd > 0:
            return
        if self.inv.count("Arrow") <= 0:
            self.add_log("You have no arrows!")
            return
        ox, oy, oz = self.eye()
        dx, dy, dz = self.look_dir()
        e = Entity(model='cube', scale=(.05, .05, .5), color=col3((220, 220, 200)), position=(ox, oy, oz),
                   rotation_y=self.rig.rotation_y, rotation_x=self.piv.rotation_x)
        self.arrows.append([ox, oy, oz, dx * 24, dy * 24, dz * 24, 1.6, e])
        self.inv.remove("Arrow", 1)
        self.use_tool(2)
        self.bow_cd, self.swing = .5, .15

    def cast(self):
        hit = self.raycast(7.5, True)
        if not hit or hit[0] != "water":
            self.add_log("Aim at water to cast your line.")
            return
        self.fish = {"x": hit[1][0], "z": hit[1][1], "t": random.uniform(2, 6), "bite": False, "bt": 0.0}
        self.add_log("You cast your line... right-click again when it splashes (!)")

    def reel_in(self):
        f, self.fish = self.fish, None
        if not f["bite"]:
            self.add_log("You reeled in too early.")
            self.use_tool(2)
            return
        loot = random.choice(FISH_LOOT)
        self.burst(f["x"], SEA, f["z"], (180, 220, 255), 10)
        if loot == "empty":
            self.add_log("Attempt failed, nothing found.")
        elif loot == "Stone Axe":
            self.add_log("Attempt successful! You hooked an old Stone Axe!")
            self.drop(self.px, self.pz, "Stone Axe", 1, 40)
        else:
            self.add_log(f"Attempt successful! You caught: {loot}!")
            self.drop(self.px, self.pz, loot, 1)
        self.use_tool(2)

    def craft(self, rec):
        need = rec["need"]
        if not all(self.inv.count(k) >= v for k, v in need.items()):
            self.add_log(f"You don't have enough materials to craft {rec['out']}.")
        elif not self.inv.can_add(rec["out"]):
            self.add_log("Your inventory is full!")
        else:
            for k, v in need.items():
                if k not in rec.get("keep", ()):
                    self.inv.remove(k, v)
            left = self.inv.add(rec["out"], rec["n"])
            if left:
                self.drop(self.px, self.pz, rec["out"], left)
            self.add_log(f"Crafted {rec['out']}!" + (f" (x{rec['n']})" if rec["n"] > 1 else ""))
        self.refresh_inv()

    # ------------------------------------------------------------ update
    def update(self):
        now = _pytime.perf_counter()
        dt = min(now - self._last, .05)
        self._last = now
        if self.state == "play" and self.panel is None:
            self.update_play(dt)
        elif self.state == "win":
            self.rotor.rotation_y += 1400 * dt
        else:
            self.rotor.rotation_y += 40 * dt
        self.update_visuals(dt)

    def update_play(self, dt):
        self.clock_t += dt
        self.atk_cd = max(0.0, self.atk_cd - dt)
        self.bow_cd = max(0.0, self.bow_cd - dt)
        self.swing = max(0.0, self.swing - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.splash_t = max(0.0, self.splash_t - dt)
        # ---- look
        self.rig.rotation_y += mouse.velocity[0] * 40
        self.piv.rotation_x = clamp(self.piv.rotation_x - mouse.velocity[1] * 40, -89, 89)
        # ---- move
        yaw = math.radians(self.rig.rotation_y)
        ax = (held_keys['d'] or held_keys['right arrow']) - (held_keys['a'] or held_keys['left arrow'])
        az = (held_keys['w'] or held_keys['up arrow']) - (held_keys['s'] or held_keys['down arrow'])
        mx = math.sin(yaw) * az + math.cos(yaw) * ax
        mz = math.cos(yaw) * az - math.sin(yaw) * ax
        n = math.hypot(mx, mz)
        moving = n > 0
        sprint = bool(held_keys['left shift']) and self.hunger > 6 and moving
        spd = 6.2 if sprint else 4.0
        tx, tz = int(self.px), int(self.pz)
        in_water = 0 <= tx < WW and 0 <= tz < WH and self.world.ground[tz][tx] == WATER and self.ph < -.3
        if in_water:
            spd *= .55
        if self.hunger <= 10:
            spd *= .8
        if moving:
            nx = self.px + mx / n * spd * dt
            if not self.blocked(nx, self.ph, self.pz):
                self.px = nx
            nz = self.pz + mz / n * spd * dt
            if not self.blocked(self.px, self.ph, nz):
                self.pz = nz
        self.vy -= GRAV * dt
        if held_keys['space'] and self.grounded:
            self.vy = JUMP * (.7 if in_water else 1)
        ny = self.ph + self.vy * dt
        if self.blocked(self.px, ny, self.pz):
            if self.vy < 0:
                self.ph, self.grounded = math.floor(ny) + 1.0, True
            else:
                self.ph = math.floor(ny + PH) - PH - .001
                self.grounded = False
            self.vy = 0.0
        else:
            self.ph, self.grounded = ny, False
        if self.ph < -6:
            self.px, self.pz = self.world.spawn
            self.ph, self.vy = 0.0, 0.0
        self.rig.position = (self.px, self.ph, self.pz)
        self.reveal()
        # ---- hunger / health  (same rules as the 2D game)
        drain = 1 / 9.0 * (2.4 if sprint else 1) * (1.3 if held_keys['left mouse'] else 1)
        self.hunger = max(0.0, self.hunger - drain * dt)
        lvl = 3 if self.hunger <= 0 else 2 if self.hunger <= 10 else 1 if self.hunger <= 25 else 0
        if lvl > self.hunger_warn:
            self.add_log(["", "Your stomach growls... you need to eat soon.", "You're weak with hunger...",
                          "You're starving!"][lvl])
        self.hunger_warn = lvl if self.hunger <= 25 else 0
        if self.hunger <= 0:
            self.starve_t += dt
            if self.starve_t >= 2:
                self.starve_t = 0
                self.health -= 2
                self.hurt_flash = .2
                if self.health <= 0:
                    self.die("Starved to death")
        if self.health < 100 and self.hunger > 30:
            self.regen_t += dt
            if self.regen_t >= 2:
                self.regen_t = 0
                self.health = min(100.0, self.health + (4 if self.hunger > 80 else 2 if self.hunger > 60 else 1))
                self.hunger = max(0.0, self.hunger - .4)
        # ---- aim / mine / attack
        hit = self.raycast()
        self.target = hit
        tgt = None
        if hit and hit[0] == "blk":
            tgt = ("blk", hit[1], BLOCKS[self.isl.blocks[hit[1]]][1] * (.5 if self.held_name() == "Stone Axe" else 1))
        elif hit and hit[0] == "obj":
            o = self.world.obj[hit[1][1]][hit[1][0]]
            if o in BREAK_TIME:
                tgt = ("obj", hit[1], self.break_time(o))
        if hit and hit[0] in ("blk", "obj", "ter"):
            c = hit[1] if hit[0] != "obj" else (hit[1][0], int(self.isl.tops[hit[1][1]][hit[1][0]]), hit[1][1])
            self.sel_box.position = (c[0] + .5, c[1] + .5, c[2] + .5)
            self.sel_box.enabled = hit[0] != "ter"
        else:
            self.sel_box.enabled = False
        if held_keys['left mouse']:
            m = self.mob_in_view()
            if m:
                self.mine_key, self.mine_prog = None, 0.0
                if self.atk_cd <= 0:
                    self.player_attack(m)
            elif tgt:
                key = (tgt[0], tgt[1])
                if key != self.mine_key:
                    self.mine_key, self.mine_prog = key, 0.0
                self.mine_prog += dt / tgt[2]
                self.swing = max(self.swing, .1)
                self.mine_fx -= dt
                if self.mine_fx <= 0:
                    self.mine_fx = .18
                    p = hit[1] if hit[0] == "blk" else (hit[1][0], self.isl.tops[hit[1][1]][hit[1][0]], hit[1][1])
                    self.burst(p[0] + .5, p[1] + .6, p[2] + .5, (150, 130, 100), 2)
                if self.mine_prog >= 1.0:
                    if tgt[0] == "blk":
                        self.break_block(tgt[1])
                    else:
                        self.break_object(*tgt[1])
                    self.mine_key, self.mine_prog = None, 0.0
            else:
                self.mine_key, self.mine_prog = None, 0.0
        else:
            self.mine_key, self.mine_prog = None, 0.0
        # ---- fishing
        f = self.fish
        if f:
            if self.held_name() != "Fishing Rod" or math.hypot(f["x"] - self.px, f["z"] - self.pz) > 9:
                self.fish = None
                self.add_log("You reel in your line.")
            else:
                f["t"] -= dt
                if not f["bite"] and f["t"] <= 0:
                    f["bite"], f["bt"] = True, 1.1
                    self.burst(f["x"], SEA, f["z"], (200, 230, 255), 8)
                elif f["bite"]:
                    f["bt"] -= dt
                    if f["bt"] <= 0:
                        self.fish = None
                        self.add_log("The fish got away...")
        # ---- world
        for m in self.mobs[:]:
            self.update_mob(m, dt)
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = 25.0
            if len(self.mobs) < 50:
                kind = random.choice(["Wild Boar", "Snake", "Rabbit"] if self.daylight() < .4 else ["Rabbit", "Rabbit", "Crab"])
                p = self.world.rand_tile((SAND,) if kind == "Crab" else (GRASS, JUNGLE), 16)
                if p and math.hypot(p[0] - self.px, p[1] - self.pz) > 16:
                    self.add_mob(kind, *p)
        self.update_drops(dt)
        self.update_arrows(dt)
        for r in self.regrow[:]:
            r[0] -= dt
            if r[0] <= 0:
                _, final, place, tx, tz = r
                self.regrow.remove(r)
                top = self.isl.tops[tz][tx]
                if self.world.obj[tz][tx] == place and not any((tx, top + k, tz) in self.isl.blocks for k in range(3)) \
                        and math.hypot(tx + .5 - self.px, tz + .5 - self.pz) > 1.5:
                    self.world.obj[tz][tx] = final
                    self.mark(tx, tz)
        for fx in self.fx[:]:
            fx[2] -= dt
            fx[1][1] -= 12 * dt
            e = fx[0]
            e.position = (e.x + fx[1][0] * dt, e.y + fx[1][1] * dt, e.z + fx[1][2] * dt)
            if fx[2] <= 0:
                self.fx.remove(fx)
                destroy(e)
        for _ in range(2):
            if self.dirty_chunks:
                self.rebuild(*self.dirty_chunks.pop())

    def update_mob(self, m, dt):
        spec = MOBS[m.kind]
        r = spec["r"]
        dx, dz = self.px - m.x, self.pz - m.y
        d = math.hypot(dx, dz)
        m.hurt = max(0.0, m.hurt - dt)
        m.cd = max(0.0, m.cd - dt)
        vx = vz = 0.0
        if spec["hostile"] and d < spec["aggro"] and abs(self.ph - self.isl.tops[int(m.y)][int(m.x)]) < 2.5:
            vx, vz = dx / (d or 1) * spec["chase"], dz / (d or 1) * spec["chase"]
            if d < 1.0 and m.cd <= 0:
                m.cd = 1.2
                self.hurt_player(spec["dmg"], m.kind.lower())
        elif not spec["hostile"] and d < spec["flee"]:
            vx, vz = -dx / (d or 1) * spec["fleespeed"], -dz / (d or 1) * spec["fleespeed"]
        else:
            m.timer -= dt
            if m.timer <= 0:
                m.timer = random.uniform(1, 3.5)
                a = random.uniform(0, math.tau)
                m.dir = (math.cos(a), math.sin(a)) if random.random() < .6 else (0.0, 0.0)
            vx, vz = m.dir[0] * spec["speed"], m.dir[1] * spec["speed"]
        vx += m.kx
        vz += m.ky
        m.kx *= max(0.0, 1 - dt * 8)
        m.ky *= max(0.0, 1 - dt * 8)
        water_ok = m.kind == "Crab"
        if vx and self.mob_free(m.x + vx * dt, m.y, r, water_ok):
            m.x += vx * dt
        if vz and self.mob_free(m.x, m.y + vz * dt, r, water_ok):
            m.y += vz * dt
        if vx or vz:
            m.ent.rotation_y = math.degrees(math.atan2(vx, vz))
        h = self.isl.tops[int(m.y)][int(m.x)]
        m.ent.position = (m.x, h + (.05 if m.hurt > 0 else 0), m.y)

    def update_drops(self, dt):
        for d in self.drops[:]:
            d.age += dt
            d.delay -= dt
            d.x += d.vx * dt
            d.y += d.vy * dt
            tx, tz = int(math.floor(d.x)), int(math.floor(d.y))
            if not (0 <= tx < WW and 0 <= tz < WH) or self.isl.solid(tx, int(math.floor(d.h)), tz):
                d.x -= d.vx * dt
                d.y -= d.vy * dt
                d.vx = d.vy = 0.0
            f = max(0.0, 1 - dt * 4)
            d.vx *= f
            d.vy *= f
            fl = self.isl.floor_under(d.x, d.h + .3, d.y) + .3
            d.vh -= 14 * dt
            d.h = max(fl, d.h + d.vh * dt)
            if d.h <= fl:
                d.vh = 0.0
            d.ent.position = (d.x, d.h + math.sin(d.age * 3) * .05, d.y)
            d.ent.rotation_y += 90 * dt
            if d.delay <= 0 and math.hypot(d.x - self.px, d.y - self.pz) < 1.4 and abs(d.h - self.ph) < 2.2:
                left = self.inv.add(d.name, d.n, d.dur)
                if left < d.n:
                    self.add_log(f"+{d.n - left} {d.name}")
                if left <= 0:
                    self.drops.remove(d)
                    self.drop_ents.remove(d.ent)
                    destroy(d.ent)
                else:
                    d.n = left

    def update_arrows(self, dt):
        for a in self.arrows[:]:
            a[0] += a[3] * dt
            a[1] += a[4] * dt
            a[2] += a[5] * dt
            a[4] -= 6 * dt
            a[6] -= dt
            a[7].position = (a[0], a[1], a[2])
            dead = a[6] <= 0 or self.isl.solid(int(math.floor(a[0])), int(math.floor(a[1])), int(math.floor(a[2])))
            if not dead:
                for m in self.mobs[:]:
                    h = self.isl.tops[int(m.y)][int(m.x)]
                    if math.hypot(m.x - a[0], m.y - a[2]) < .6 and h - .2 < a[1] < h + 1.1:
                        n = math.hypot(a[3], a[5]) or 1
                        self.hurt_mob(m, WEAPON_DMG["Bow"] + 5, a[3] / n, a[5] / n)
                        dead = True
                        break
            if dead:
                self.arrows.remove(a)
                destroy(a[7])

    def update_visuals(self, dt):
        # ---- day / night
        dl = self.daylight()
        sky = (int(8 + 127 * dl), int(10 + 190 * dl), int(28 + 222 * dl))
        window.color = col3(sky)
        try:
            scene.fog_color = col3(sky)
            scene.fog_density = (35, 130) if dl > .4 else (10, 45)
        except Exception:
            pass
        lit = 0.0
        for (lx, lz) in self.lights:
            lit = max(lit, 1 - math.hypot(lx + .5 - self.px, lz + .5 - self.pz) / 9)
        if self.held_name() == "Torch":
            lit = max(lit, .45)
        self.dark.color = col3((0, 0, 14), (1 - dl) * .7 * (1 - clamp(lit, 0, .8)))
        self.red.color = col3((200, 0, 0), min(.45, self.hurt_flash * 1.6))
        # ---- held item
        h = self.held_name()
        self.hand.color = col3(item_rgb(h) if h else (224, 172, 130))
        sw = math.sin(self.swing * 30) * 30 if self.swing > 0 else 0
        self.hand.rotation = (8 + sw, -18, 0)
        # ---- fishing bobber
        f = self.fish
        self.bobber.enabled = bool(f)
        if f:
            self.bobber.position = (f["x"], SEA + .05 - (.12 if f["bite"] else 0), f["z"])
        # ---- HUD
        self.bar_hp.scale_x = .3 * clamp(self.health / 100, 0, 1)
        self.bar_food.scale_x = .3 * clamp(self.hunger / 100, 0, 1)
        for i in range(9):
            s = self.inv.slots[i]
            self.slot_q[i].color = col3((200, 200, 90) if i == self.sel else (30, 30, 34), .85)
            self.slot_t[i].text = f"{s['name'][:6]}\n{s['n']}" if s else ""
        for l in self.log:
            l[1] -= dt
        self.log = [l for l in self.log if l[1] > 0]
        txt = "\n".join(l[0] for l in self.log)
        if txt != self.log_str:
            self.log_str, self.t_log.text = txt, txt
        ph = self.phase() * 24
        self.t_clock.text = f"Day {int(self.clock_t / DAY_LENGTH + START_PHASE) + 1}   {int(ph):02d}:{int((ph % 1) * 60):02d}"
        tip = ""
        if self.fish and self.fish["bite"]:
            tip = "!!  BITE - right-click to reel in!  !!"
        elif self.splash_t > 0:
            tip = "Press H for help   |   E: craft & build"
        self.t_tip.text = tip
        if self.state == "dead":
            self.t_msg.text, self.t_sub.text = "YOU DIED", f"{self.death_msg}\n\nPress R to try again"
        elif self.state == "win":
            self.t_msg.text, self.t_sub.text = "YOU ESCAPED!", "The helicopter lifts off the island...\n\nPress R to play again"
        elif self.panel == "pause":
            self.t_msg.text, self.t_sub.text = "PAUSED", "Esc: resume     (close the window to quit)"
        else:
            self.t_msg.text = self.t_sub.text = ""
        if self.panel == "map":
            self.map_dot.position = ((self.px - WW / 2) * .0082, (self.pz - WH / 2) * .0082, -.1)
            self.map_dot.color = col3((255, 255, 255) if int(_pytime.perf_counter() * 3) % 2 else (255, 60, 60))

    # ------------------------------------------------------------ input
    def input(self, key):
        if key == "escape":
            if self.state != "play":
                return
            self.set_panel(None if self.panel else "pause")
            return
        if self.state != "play":
            if key == "r":
                self.new_game()
                self.set_panel(None)
            return
        if key == "e":
            self.set_panel(None if self.panel == "inv" else "inv" if self.panel is None else self.panel)
        elif key == "m" and self.inv.count("Map") > 0:
            self.set_panel(None if self.panel == "map" else "map" if self.panel is None else self.panel)
        elif key == "m" and self.panel is None:
            self.add_log("You need a Map to open the map.")
        elif key in ("h", "f1"):
            self.set_panel(None if self.panel == "help" else "help" if self.panel is None else self.panel)
        if self.panel is not None:
            return
        if key == "right mouse down":
            self.use_item()
        elif key in tuple("123456789"):
            self.sel = int(key) - 1
        elif key == "scroll up":
            self.sel = (self.sel - 1) % 9
        elif key == "scroll down":
            self.sel = (self.sel + 1) % 9
        elif key == "q":
            s = self.held()
            if s:
                self.inv.slots[self.sel] = None
                dx, dy, dz = self.look_dir()
                self.drop(self.px + dx, self.pz + dz, s["name"], s["n"], s["dur"], delay=1.5, pop=False)


def main():
    app = Ursina(title="Survival Island 3D", borderless=False)
    window.exit_button.visible = False
    Game3D()
    app.run()


if __name__ == "__main__":
    main()