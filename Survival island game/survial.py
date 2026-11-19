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
import json
import os

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
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survival_island_3d_save.json")

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