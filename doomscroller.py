"""
DOOMSCROLLER!
A sidescrolling hazard gauntlet made with pygame.

Reach the flag at the end of each level. Your score depends on how fast you
got there and how many times you got hit. Three hits or a fall into a pit
and you die (the level restarts).

Controls
  Left / Right  or  A / D     run
  Space / Up / W / Z          jump (hold for higher, tap for a short hop)
  P or Esc                    pause
  R                           restart the current level
  Enter                       confirm / continue

Run with:  python doomscroller.py
"""

import json
import math
import os
import random
import sys
from array import array

import pygame

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
GAME_TITLE = "Doomscroller!"
W, H = 960, 560
T = 40                      # tile size in pixels
ROWS = H // T               # 14 rows of tiles fill the screen height
FPS = 60

GRAVITY = 0.6
MAX_FALL = 15
RUN_SPEED = 5.0
ACCEL = 0.9
AIR_ACCEL = 0.6
FRICTION = 0.7
JUMP_VEL = -12.5
JUMP_CUT = -4.0             # releasing jump early clamps upward speed to this
COYOTE_FRAMES = 6           # grace period to jump after running off a ledge
BUFFER_FRAMES = 8           # jump pressed slightly before landing still counts

MAX_HITS = 3
INVULN_FRAMES = 90
KNOCKBACK_LOCK = 14

COMPLETE_BONUS = 5000
TIME_BONUS_PER_SEC = 100    # per second finished under par
HIT_PENALTY = 1500

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "doomscroller_highscore.json")

JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w, pygame.K_z)
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)

# --------------------------------------------------------------------------
# Level building blocks
#
# Each chunk is a small piece of level, written bottom-aligned (the last two
# lines are usually the ground). Levels are made by gluing chunks together.
#
#   #  solid block          =  metal platform (solid)
#   ^  floor spikes         v  ceiling spikes
#   A  swinging axe pivot   C  crusher (falls to the floor below)
#   S  sliding floor saw    s  rising/falling saw
#   F  flame jet nozzle     R  arrow launcher (fires left)
#   M  moving platform      P  player start      E  exit flag
# --------------------------------------------------------------------------
CHUNKS = {
    "start": [
        "............",
        "..P.........",
        "############",
        "############",
    ],
    "flat": [
        "######",
        "######",
    ],
    "spike1": [
        "...^...",
        "#######",
        "#######",
    ],
    "spike2": [
        "...^^...",
        "########",
        "########",
    ],
    "spike3": [
        "...^^^....",
        "##########",
        "##########",
    ],
    "spike4": [
        "...^^^^.....",
        "############",
        "############",
    ],
    "pit3": [
        "###...###",
        "###...###",
    ],
    "pit_plat": [
        ".....===.....",
        ".............",
        "###.......###",
        "###.......###",
    ],
    "tower": [
        ".....##.....",
        "..^^^##^^^..",
        "############",
        "############",
    ],
    "axe": [
        "....A.....",
        "..........",
        "..........",
        "..........",
        "##########",
        "##########",
    ],
    "axe2": [
        "....A.....A.....",
        "................",
        "................",
        "................",
        "################",
        "################",
    ],
    "axe_pit": [
        "......A.......",
        "..............",
        "..............",
        "..............",
        "#####...######",
        "#####...######",
    ],
    "saw": [
        ".....S......",
        "############",
        "############",
    ],
    "vsaw": [
        ".....s....",
        "##########",
        "##########",
    ],
    "vsaw2": [
        "....s....s....",
        "##############",
        "##############",
    ],
    "flame": [
        "####F#####",
        "##########",
    ],
    "flame_row": [
        "##F###F###F###",
        "##############",
    ],
    "crusher": [
        "....C.......",
        "............",
        "............",
        "............",
        "............",
        "############",
        "############",
    ],
    "crusher2": [
        "...C.....C.....",
        "...............",
        "...............",
        "...............",
        "...............",
        "###############",
        "###############",
    ],
    "arrows": [
        "..............R###",
        "##################",
        "##################",
    ],
    "low_ceiling": [
        "################",
        "vvvvvvvvvvvvvvvv",
        "................",
        "................",
        "....^......^....",
        "################",
        "################",
    ],
    "mplat": [
        "......M.......",
        "..............",
        "##..........##",
        "##..........##",
    ],
    "spike_plats": [
        ".....==....==...",
        "..^^^^^^^^^^^^..",
        "################",
        "################",
    ],
    "exit": [
        ".....E......",
        "############",
        "############",
    ],
}

LEVELS = [
    {
        "name": "The Gauntlet",
        "par": 45,
        "theme": 0,
        "speed": 1.0,
        "chunks": ["start", "flat", "spike1", "flat", "spike2", "pit3", "flat",
                   "saw", "spike3", "axe", "flat", "pit_plat", "flame", "flat",
                   "tower", "vsaw", "flat", "spike4", "axe", "pit3", "exit"],
    },
    {
        "name": "The Axe Factory",
        "par": 60,
        "theme": 1,
        "speed": 1.15,
        "chunks": ["start", "axe", "flame", "spike3", "axe2", "pit3", "crusher",
                   "flat", "saw", "mplat", "flame_row", "low_ceiling", "flat",
                   "arrows", "flat", "crusher2", "axe_pit", "vsaw", "pit_plat",
                   "axe2", "exit"],
    },
    {
        "name": "Into the Abyss",
        "par": 75,
        "theme": 2,
        "speed": 1.3,
        "chunks": ["start", "spike_plats", "axe_pit", "flame_row", "mplat",
                   "crusher2", "low_ceiling", "vsaw2", "arrows", "flat", "pit_plat",
                   "axe2", "saw", "mplat", "spike4", "crusher", "flame_row",
                   "axe_pit", "tower", "vsaw2", "axe2", "exit"],
    },
]

THEMES = [
    {   # dusk
        "sky_top": (35, 8, 30), "sky_bot": (160, 55, 40), "moon": (255, 190, 120),
        "far": (80, 28, 45), "near": (48, 16, 32),
        "block": (92, 70, 82), "block_dark": (66, 48, 60), "block_top": (150, 35, 50),
        "plate": (120, 110, 125),
    },
    {   # factory
        "sky_top": (14, 14, 22), "sky_bot": (90, 70, 55), "moon": (230, 210, 170),
        "far": (55, 48, 52), "near": (32, 30, 36),
        "block": (88, 88, 98), "block_dark": (62, 62, 72), "block_top": (190, 110, 40),
        "plate": (140, 130, 120),
    },
    {   # abyss
        "sky_top": (4, 0, 10), "sky_bot": (70, 0, 35), "moon": (200, 60, 90),
        "far": (40, 6, 34), "near": (22, 0, 22),
        "block": (62, 44, 74), "block_dark": (42, 28, 52), "block_top": (130, 0, 90),
        "plate": (100, 80, 120),
    },
]

SOLID = set("#=FR")


def build_grid(chunk_names):
    rows = [""] * ROWS
    for name in chunk_names:
        lines = CHUNKS[name]
        width = max(len(line) for line in lines)
        padded = (["." * width] * (ROWS - len(lines))
                  + [line.ljust(width, ".") for line in lines])
        for i in range(ROWS):
            rows[i] += padded[i]
    return rows


def circle_rect(cx, cy, r, rect):
    nx = max(rect.left, min(cx, rect.right))
    ny = max(rect.top, min(cy, rect.bottom))
    return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r


def score_level(time_s, hits, par):
    time_bonus = max(0, int(round((par - time_s) * TIME_BONUS_PER_SEC)))
    penalty = hits * HIT_PENALTY
    return time_bonus, penalty, max(0, COMPLETE_BONUS + time_bonus - penalty)


# --------------------------------------------------------------------------
# Sound (generated in code, no files needed)
# --------------------------------------------------------------------------
class Sounds:
    def __init__(self):
        self.ok = False
        self.bank = {}
        try:
            init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, fmt, self.channels = init
            if fmt != -16:
                return
            win = (self._tone(523, 523, 0.12, "square", 0.15)
                   + self._tone(659, 659, 0.12, "square", 0.15)
                   + self._tone(784, 784, 0.12, "square", 0.15)
                   + self._tone(1046, 1046, 0.35, "square", 0.15))
            self.bank = {
                "jump": self._sound(self._tone(320, 640, 0.10, "square", 0.12)),
                "hit": self._sound(self._noise(0.22, 0.5, 0.3)),
                "die": self._sound(self._tone(440, 50, 0.75, "saw", 0.25)),
                "slam": self._sound(self._noise(0.25, 0.45, 0.05)),
                "arrow": self._sound(self._tone(1400, 500, 0.07, "square", 0.06)),
                "tick": self._sound(self._tone(880, 880, 0.035, "square", 0.10)),
                "start": self._sound(self._tone(200, 800, 0.25, "square", 0.12)),
                "win": self._sound(win),
            }
            self.ok = True
        except Exception:
            self.ok = False

    def _tone(self, f0, f1, dur, wave, vol):
        n = int(self.rate * dur)
        out = []
        ph = 0.0
        for i in range(n):
            k = i / n
            ph = (ph + (f0 + (f1 - f0) * k) / self.rate) % 1.0
            if wave == "square":
                v = 1.0 if ph < 0.5 else -1.0
            elif wave == "saw":
                v = 2 * ph - 1
            else:
                v = math.sin(2 * math.pi * ph)
            env = min(1.0, i / (self.rate * 0.005)) * (1 - k)
            out.append(v * env * vol)
        return out

    def _noise(self, dur, vol, smooth):
        rng = random.Random(7)
        n = int(self.rate * dur)
        raw = []
        y = 0.0
        for _ in range(n):
            y += (rng.uniform(-1, 1) - y) * smooth
            raw.append(y)
        peak = max(abs(v) for v in raw) or 1.0
        return [v / peak * vol * (1 - i / n) for i, v in enumerate(raw)]

    def _sound(self, samples):
        buf = array("h")
        for v in samples:
            s = int(max(-1.0, min(1.0, v)) * 32767)
            buf.append(s)
            if self.channels == 2:
                buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.ok:
            self.bank[name].play()


# --------------------------------------------------------------------------
# Hazards and level objects
# --------------------------------------------------------------------------
class Spike:
    layer = "front"

    def __init__(self, c, r, down):
        self.tx, self.ty, self.down = c * T, r * T, down
        self.x0 = self.tx + T / 2
        if down:
            self.box = pygame.Rect(self.tx + 5, self.ty, T - 10, 20)
        else:
            self.box = pygame.Rect(self.tx + 5, self.ty + T - 18, T - 10, 18)

    def update(self, level):
        pass

    def hit(self, rect):
        return rect.colliderect(self.box)

    def center(self):
        return self.box.center

    def draw(self, surf, cam, level):
        x = self.tx - cam
        for i in range(2):
            bx = x + i * 20
            if self.down:
                b = self.ty
                pts = [(bx + 1, b), (bx + 10, b + 26), (bx + 19, b)]
                tip = [(bx + 7, b + 18), (bx + 10, b + 26), (bx + 13, b + 18)]
            else:
                b = self.ty + T
                pts = [(bx + 1, b), (bx + 10, b - 26), (bx + 19, b)]
                tip = [(bx + 7, b - 18), (bx + 10, b - 26), (bx + 13, b - 18)]
            pygame.draw.polygon(surf, (175, 175, 190), pts)
            pygame.draw.polygon(surf, (90, 90, 105), pts, 1)
            pygame.draw.polygon(surf, (190, 20, 30), tip)


class Axe:
    layer = "front"
    SHAPE = [(-5, -10), (-22, -18), (-27, 0), (-22, 18), (-5, 10),
             (5, 10), (22, 18), (27, 0), (22, -18), (5, -10)]

    def __init__(self, c, r, phase, mult):
        self.px = c * T + T / 2
        self.py = r * T + T / 2
        self.x0 = self.px
        self.length = 3 * T
        self.amp = math.radians(65)
        self.speed = 2 * math.pi / 140 * mult
        self.phase = phase
        self.angle = 0.0

    def update(self, level):
        self.angle = self.amp * math.sin(level.t * self.speed + self.phase)

    def blade(self):
        return (self.px + math.sin(self.angle) * self.length,
                self.py + math.cos(self.angle) * self.length)

    def hit(self, rect):
        bx, by = self.blade()
        return circle_rect(bx, by, 22, rect)

    def center(self):
        return self.blade()

    def draw(self, surf, cam, level):
        px, py = self.px - cam, self.py
        bx, by = self.blade()
        bx -= cam
        pygame.draw.line(surf, (40, 36, 46), (px, 0), (px, py), 6)
        pygame.draw.line(surf, (125, 90, 55), (px, py), (bx, by), 6)
        pygame.draw.circle(surf, (110, 105, 120), (int(px), int(py)), 8)
        sa, ca = math.sin(self.angle), math.cos(self.angle)
        pts = [(bx + ca * u + sa * v, by - sa * u + ca * v) for u, v in self.SHAPE]
        pygame.draw.polygon(surf, (205, 205, 220), pts)
        pygame.draw.polygon(surf, (70, 70, 85), pts, 2)
        pygame.draw.circle(surf, (150, 20, 30), (int(bx), int(by)), 5)


class Saw:
    layer = "back"      # drawn behind the ground so it looks half-buried

    def __init__(self, c, r, vertical, phase, mult):
        self.cx = c * T + T / 2
        self.cy = (r + 1) * T
        self.x0 = self.cx
        self.vertical = vertical
        self.phase = phase
        self.range = 4 * T if vertical else 2.5 * T
        self.speed = (0.045 if vertical else 0.035) * mult
        self.r = 22
        self.rot = 0.0
        self.x, self.y = self.cx, self.cy

    def update(self, level):
        s = level.t * self.speed + self.phase
        if self.vertical:
            self.y = self.cy - (1 - math.cos(s)) / 2 * self.range
        else:
            self.x = self.cx + math.sin(s) * self.range
        self.rot += 0.35

    def hit(self, rect):
        return circle_rect(self.x, self.y, self.r - 3, rect)

    def center(self):
        return (self.x, self.y)

    def draw(self, surf, cam, level):
        if self.vertical:
            x = self.cx - cam
            pygame.draw.line(surf, (30, 26, 34), (x, self.cy), (x, self.cy - self.range), 6)
            pygame.draw.circle(surf, (30, 26, 34), (int(x), int(self.cy - self.range)), 6)
        x, y = self.x - cam, self.y
        pts = []
        teeth = 12
        for i in range(teeth * 2):
            a = self.rot + i * math.pi / teeth
            rr = self.r if i % 2 == 0 else self.r - 7
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(surf, (195, 195, 205), pts)
        pygame.draw.circle(surf, (125, 125, 135), (int(x), int(y)), self.r - 9)
        pygame.draw.circle(surf, (160, 25, 35), (int(x), int(y)), 5)


class Flame:
    layer = "front"

    def __init__(self, c, r, offset, mult):
        self.tx, self.ty = c * T, r * T
        self.x0 = self.tx + T / 2
        self.period = int(150 / mult)
        self.warn = 30
        self.on = 55
        self.offset = offset
        self.phase_t = 0
        self.box = pygame.Rect(self.tx + 8, self.ty - 3 * T + 8, T - 16, 3 * T - 8)

    def update(self, level):
        self.phase_t = (level.t + self.offset) % self.period

    def state(self):
        if self.phase_t < self.warn:
            return "warn"
        if self.phase_t < self.warn + self.on:
            return "on"
        return "off"

    def hit(self, rect):
        return self.state() == "on" and rect.colliderect(self.box)

    def center(self):
        return (self.tx + T / 2, self.ty)

    def draw(self, surf, cam, level):
        x = self.tx - cam
        cx = x + T / 2
        pygame.draw.rect(surf, (45, 42, 48), (x + 4, self.ty - 6, T - 8, 8))
        for i in range(4):
            pygame.draw.line(surf, (20, 18, 22), (x + 9 + i * 7, self.ty - 5), (x + 9 + i * 7, self.ty), 2)
        st = self.state()
        if st == "warn":
            for _ in range(2):
                pygame.draw.circle(surf, (255, random.randint(80, 160), 0),
                                   (int(cx + random.uniform(-10, 10)),
                                    int(self.ty - random.uniform(4, 20))), 2)
        elif st == "on":
            t_on = self.phase_t - self.warn
            grow = min(1.0, t_on / 6)
            full = 3 * T * grow
            layers = [((255, 70, 0), 1.0, 1.0), ((255, 160, 0), 0.65, 0.85),
                      ((255, 240, 160), 0.32, 0.65)]
            for col, ws, hs in layers:
                w = (T - 8) * ws
                h = full * hs * random.uniform(0.9, 1.0)
                j = random.uniform(-4, 4)
                pts = [(cx - w / 2, self.ty), (cx - w * 0.42 + j, self.ty - h * 0.4),
                       (cx - w * 0.2 + j, self.ty - h * 0.75), (cx + j, self.ty - h),
                       (cx + w * 0.2 + j, self.ty - h * 0.7), (cx + w * 0.42 + j, self.ty - h * 0.35),
                       (cx + w / 2, self.ty)]
                pygame.draw.polygon(surf, col, pts)


class Crusher:
    layer = "front"

    def __init__(self, c, r, level, offset, mult):
        self.x = c * T + 2
        self.w = 2 * T - 4
        self.h = T + 8
        self.x0 = self.x + self.w / 2
        self.top = r * T
        floor_row = ROWS
        for row in range(r + 1, ROWS):
            if level.solid[row][c]:
                floor_row = row
                break
        self.bottom = floor_row * T - self.h
        self.y = float(self.top)
        self.vy = 0.0
        self.mult = mult
        self.state = "wait"
        self.timer = 30 + offset % 90

    def update(self, level):
        if self.state == "wait":
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "shake", 24
        elif self.state == "shake":
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.vy = "fall", 0.0
        elif self.state == "fall":
            self.vy += 1.0 * self.mult
            self.y += self.vy
            if self.y >= self.bottom:
                self.y = self.bottom
                self.state, self.timer = "slam", 35
                level.events.append(("slam", self.x0))
        elif self.state == "slam":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "rise"
        elif self.state == "rise":
            self.y -= 2 * self.mult
            if self.y <= self.top:
                self.y = self.top
                self.state, self.timer = "wait", int(70 / self.mult)

    def rect(self):
        return pygame.Rect(self.x, int(self.y), self.w, self.h)

    def hit(self, rect):
        return rect.colliderect(self.rect())

    def center(self):
        return self.rect().center

    def draw(self, surf, cam, level):
        shake = random.randint(-2, 2) if self.state == "shake" else 0
        x = self.x - cam + shake
        y = int(self.y)
        cx = x + self.w // 2
        for ly in range(0, y, 12):
            pygame.draw.rect(surf, (70, 65, 75), (cx - 3, ly, 6, 9), 2)
        pygame.draw.rect(surf, (75, 72, 82), (x, y, self.w, self.h - 10))
        pygame.draw.rect(surf, (40, 38, 46), (x, y, self.w, self.h - 10), 3)
        for i in range(6):
            tx = x + 2 + i * (self.w - 4) / 6
            tw = (self.w - 4) / 6
            pygame.draw.polygon(surf, (160, 160, 175),
                                [(tx, y + self.h - 10), (tx + tw / 2, y + self.h), (tx + tw, y + self.h - 10)])
        eye = (255, 40, 40) if self.state in ("shake", "fall") else (150, 30, 30)
        pygame.draw.polygon(surf, eye, [(cx - 22, y + 10), (cx - 6, y + 16), (cx - 20, y + 20)])
        pygame.draw.polygon(surf, eye, [(cx + 22, y + 10), (cx + 6, y + 16), (cx + 20, y + 20)])
        for bx in (x + 6, x + self.w - 6):
            pygame.draw.circle(surf, (120, 115, 130), (bx, y + 6), 3)


class Arrow:
    LENGTH = 26

    def __init__(self, x, y, vx):
        self.x, self.y, self.vx = float(x), y, vx
        self.dist = 0.0
        self.alive = True

    def update(self, level):
        self.x += self.vx
        self.dist += abs(self.vx)
        tip = self.x if self.vx < 0 else self.x + self.LENGTH
        if self.dist > 14 * T or level.solid_at(int(tip // T), int(self.y // T)):
            self.alive = False

    def rect(self):
        return pygame.Rect(int(self.x), self.y - 3, self.LENGTH, 6)

    def draw(self, surf, cam):
        x = self.x - cam
        y = self.y
        pygame.draw.line(surf, (140, 100, 60), (x + 4, y), (x + self.LENGTH, y), 3)
        pygame.draw.polygon(surf, (210, 210, 220), [(x, y), (x + 8, y - 5), (x + 8, y + 5)])
        pygame.draw.line(surf, (200, 40, 40), (x + self.LENGTH - 6, y), (x + self.LENGTH, y - 5), 2)
        pygame.draw.line(surf, (200, 40, 40), (x + self.LENGTH - 6, y), (x + self.LENGTH, y + 5), 2)


class Launcher:
    layer = "front"

    def __init__(self, c, r, offset, mult):
        self.rect = pygame.Rect(c * T, r * T, T, T)
        self.x0 = self.rect.centerx
        self.period = int(110 / mult)
        self.timer = offset % self.period

    def update(self, level):
        self.timer += 1
        if self.timer >= self.period:
            self.timer = 0
            level.arrows.append(Arrow(self.rect.left - Arrow.LENGTH, self.rect.centery, -7))
            level.events.append(("arrow", self.x0))

    def hit(self, rect):
        return False

    def center(self):
        return self.rect.center

    def draw(self, surf, cam, level):
        r = self.rect.move(-cam, 0)
        pygame.draw.rect(surf, (70, 66, 74), r)
        pygame.draw.rect(surf, (35, 32, 40), r, 3)
        charge = self.timer / self.period
        glow = (int(80 + 175 * charge ** 3), 20, 20)
        pygame.draw.rect(surf, (20, 15, 20), (r.left, r.centery - 5, 16, 10))
        pygame.draw.rect(surf, glow, (r.left + 2, r.centery - 3, 12, 6))
        pygame.draw.circle(surf, (210, 200, 190), (r.centerx + 6, r.top + 12), 7)
        pygame.draw.circle(surf, (20, 15, 20), (r.centerx + 3, r.top + 11), 2)
        pygame.draw.circle(surf, (20, 15, 20), (r.centerx + 9, r.top + 11), 2)


class MovingPlatform:
    def __init__(self, c, r, phase, mult):
        self.cx = c * T
        self.w = 2 * T
        self.top = r * T + 4
        self.amp = 3 * T
        self.speed = 0.02 * mult
        self.phase = phase
        self.x = self.cx + self.amp * math.sin(phase)
        self.dx = 0.0

    def update(self, level):
        nx = self.cx + self.amp * math.sin(level.t * self.speed + self.phase)
        self.dx = nx - self.x
        self.x = nx

    def rect(self):
        return pygame.Rect(round(self.x), self.top, self.w, 16)

    def draw(self, surf, cam, theme):
        r = self.rect().move(-cam, 0)
        pygame.draw.rect(surf, theme["plate"], r, border_radius=3)
        pygame.draw.rect(surf, (30, 28, 34), r, 2, border_radius=3)
        for bx in (r.left + 8, r.centerx, r.right - 8):
            pygame.draw.circle(surf, (40, 38, 44), (bx, r.centery), 3)


class Exit:
    def __init__(self, c, r):
        self.pole_x = c * T + T // 2
        self.ground = (r + 1) * T
        self.rect = pygame.Rect(c * T, self.ground - 4 * T, T, 4 * T)

    def draw(self, surf, cam, t):
        x = self.pole_x - cam
        top = self.ground - 4 * T
        pygame.draw.line(surf, (200, 200, 210), (x, self.ground), (x, top), 5)
        pygame.draw.circle(surf, (240, 200, 60), (x, top), 7)
        pts = []
        for i in range(9):
            fx = x + 3 + i * 7
            pts.append((fx, top + 8 + math.sin(t * 0.15 + i * 0.7) * 3 * i / 8))
        bottom = [(px, py + 30) for px, py in reversed(pts)]
        pygame.draw.polygon(surf, (200, 25, 35), pts + bottom)
        mx, my = x + 30, top + 23 + math.sin(t * 0.15 + 2.8) * 1.5
        pygame.draw.circle(surf, (240, 235, 225), (int(mx), int(my)), 8)
        pygame.draw.rect(surf, (240, 235, 225), (mx - 5, my + 4, 10, 6))
        pygame.draw.circle(surf, (200, 25, 35), (int(mx - 3), int(my)), 2)
        pygame.draw.circle(surf, (200, 25, 35), (int(mx + 3), int(my)), 2)


# --------------------------------------------------------------------------
# Level
# --------------------------------------------------------------------------
class Level:
    def __init__(self, index):
        data = LEVELS[index]
        self.index = index
        self.name = data["name"]
        self.par = data["par"]
        self.theme = THEMES[data["theme"]]
        mult = data["speed"]
        self.grid = build_grid(data["chunks"])
        self.cols = len(self.grid[0])
        self.width = self.cols * T
        self.solid = [[ch in SOLID for ch in row] for row in self.grid]
        self.hazards = []
        self.platforms = []
        self.arrows = []
        self.events = []
        self.start = (T, T)
        self.exit = None
        self.t = 0
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                phase = ((c * 73 + r * 31) % 360) * math.pi / 180
                offset = (c * 37 + r * 11) % 150
                if ch == "^":
                    self.hazards.append(Spike(c, r, False))
                elif ch == "v":
                    self.hazards.append(Spike(c, r, True))
                elif ch == "A":
                    self.hazards.append(Axe(c, r, phase, mult))
                elif ch == "S":
                    self.hazards.append(Saw(c, r, False, phase, mult))
                elif ch == "s":
                    self.hazards.append(Saw(c, r, True, phase, mult))
                elif ch == "F":
                    self.hazards.append(Flame(c, r, offset, mult))
                elif ch == "C":
                    self.hazards.append(Crusher(c, r, self, offset, mult))
                elif ch == "R":
                    self.hazards.append(Launcher(c, r, offset, mult))
                elif ch == "M":
                    self.platforms.append(MovingPlatform(c, r, phase, mult))
                elif ch == "P":
                    self.start = (c * T + (T - Player.W) / 2, (r + 1) * T - Player.H)
                elif ch == "E":
                    self.exit = Exit(c, r)

    def solid_at(self, c, r):
        if r < 0 or r >= ROWS or c < 0 or c >= self.cols:
            return False
        return self.solid[r][c]

    def solid_rects(self, rect):
        out = []
        for r in range(rect.top // T, (rect.bottom - 1) // T + 1):
            for c in range(rect.left // T, (rect.right - 1) // T + 1):
                if self.solid_at(c, r):
                    out.append(pygame.Rect(c * T, r * T, T, T))
        return out

    def update(self):
        self.t += 1
        for h in self.hazards:
            h.update(self)
        for p in self.platforms:
            p.update(self)
        for a in self.arrows:
            a.update(self)
        self.arrows = [a for a in self.arrows if a.alive]


# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------
class Player:
    W, H = 26, 44

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0
        self.buffer = 0
        self.jumping = False
        self.invuln = 0
        self.lock = 0
        self.riding = None
        self.run_phase = 0.0

    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.W, self.H)

    def update(self, game, level, inp):
        move = 0
        if self.lock > 0:
            self.lock -= 1
        else:
            move = inp["right"] - inp["left"]

        if move:
            accel = ACCEL if self.on_ground else AIR_ACCEL
            self.vx += max(-accel, min(accel, move * RUN_SPEED - self.vx))
            self.facing = move
        elif self.lock == 0:
            self.vx *= FRICTION if self.on_ground else 0.95
            if abs(self.vx) < 0.1:
                self.vx = 0.0

        self.coyote = COYOTE_FRAMES if self.on_ground else self.coyote - 1
        if self.buffer > 0:
            self.buffer -= 1
            if self.coyote > 0:
                self.vy = JUMP_VEL
                self.buffer = self.coyote = 0
                self.jumping = True
                self.on_ground = False
                game.sfx.play("jump")
                game.dust(self.x + self.W / 2, self.y + self.H)
        if self.jumping and not inp["jump"] and self.vy < JUMP_CUT:
            self.vy = JUMP_CUT

        self.vy = min(self.vy + GRAVITY, MAX_FALL)

        if self.riding is not None:
            self.move_x(level, self.riding.dx)
        self.move_x(level, self.vx)
        self.move_y(level, self.vy)

        if self.invuln > 0:
            self.invuln -= 1
        if self.on_ground and abs(self.vx) > 0.5:
            self.run_phase += abs(self.vx) * 0.07

    def move_x(self, level, dx):
        self.x += dx
        r = self.rect()
        for t in level.solid_rects(r):
            if r.colliderect(t):
                if dx > 0:
                    self.x = t.left - self.W
                elif dx < 0:
                    self.x = t.right
                self.vx = 0.0
                r = self.rect()
        self.x = max(0.0, min(self.x, level.width - self.W))

    def move_y(self, level, dy):
        prev_bottom = self.y + self.H
        self.y += dy
        self.on_ground = False
        self.riding = None
        r = self.rect()
        for t in level.solid_rects(r):
            if r.colliderect(t):
                if dy > 0:
                    self.y = t.top - self.H
                    self.on_ground = True
                elif dy < 0:
                    self.y = t.bottom
                self.vy = 0.0
                r = self.rect()
        if dy >= 0:
            for p in level.platforms:
                pr = p.rect()
                if (prev_bottom <= pr.top + 2 and self.y + self.H >= pr.top
                        and r.right > pr.left and r.left < pr.right):
                    self.y = pr.top - self.H
                    self.vy = 0.0
                    self.on_ground = True
                    self.riding = p
                    r = self.rect()
        if self.on_ground:
            self.jumping = False

    def draw(self, surf, cam, t):
        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return
        x = round(self.x - cam)
        y = round(self.y)
        f = self.facing
        # scarf
        nx, ny = x + self.W // 2 - f * 6, y + 20
        pts = [(nx, ny)]
        for i in range(1, 6):
            pts.append((nx - f * i * 5, ny + math.sin(t * 0.35 + i) * 2.5 + i * (1.6 - min(abs(self.vx), 5) * 0.25)))
        pygame.draw.lines(surf, (210, 30, 40), False, pts, 4)
        # legs
        if self.on_ground:
            l = math.sin(self.run_phase) * 6 if abs(self.vx) > 0.5 else 0
            pygame.draw.rect(surf, (40, 34, 50), (x + 5 + l, y + self.H - 12, 7, 12))
            pygame.draw.rect(surf, (40, 34, 50), (x + self.W - 12 - l, y + self.H - 12, 7, 12))
        else:
            pygame.draw.rect(surf, (40, 34, 50), (x + 4, y + self.H - 14, 7, 10))
            pygame.draw.rect(surf, (40, 34, 50), (x + self.W - 11, y + self.H - 10, 7, 10))
        # body + hood
        pygame.draw.rect(surf, (70, 58, 95), (x, y + 2, self.W, self.H - 12), border_radius=9)
        pygame.draw.rect(surf, (235, 225, 210), (x + 4 + max(0, f) * 4, y + 9, self.W - 12, 13), border_radius=4)
        ex = x + self.W // 2 + f * 4
        pygame.draw.rect(surf, (15, 10, 20), (ex - 5, y + 12, 3, 6))
        pygame.draw.rect(surf, (15, 10, 20), (ex + 2, y + 12, 3, 6))
        pygame.draw.line(surf, (40, 30, 55), (x + 3, y + self.H - 18), (x + self.W - 3, y + self.H - 18), 2)


# --------------------------------------------------------------------------
# Visuals
# --------------------------------------------------------------------------
class Backdrop:
    LAYER_W = 1920

    def __init__(self, theme, seed):
        rng = random.Random(seed)
        self.theme = theme
        self.sky = pygame.Surface((W, H))
        for y in range(H):
            k = y / H
            col = [int(a + (b - a) * k) for a, b in zip(theme["sky_top"], theme["sky_bot"])]
            pygame.draw.line(self.sky, col, (0, y), (W, y))
        mx, my = rng.randint(550, 850), rng.randint(70, 140)
        pygame.draw.circle(self.sky, theme["moon"], (mx, my), 46)
        pygame.draw.circle(self.sky, theme["sky_top"], (mx + 18, my - 10), 40)
        for _ in range(60):
            pygame.draw.circle(self.sky, (220, 200, 210),
                               (rng.randint(0, W), rng.randint(0, H // 2)), 1)
        self.layers = [(self._mountains(rng, theme["far"], 330, 170, 120), 0.2),
                       (self._mountains(rng, theme["near"], 420, 140, 70), 0.45)]
        self.fog = pygame.Surface((W, 160), pygame.SRCALPHA)
        for y in range(160):
            pygame.draw.line(self.fog, (0, 0, 0, int(230 * (y / 160) ** 1.5)), (0, y), (W, y))
        self.embers = [[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.3, 1.0)] for _ in range(40)]

    def _mountains(self, rng, color, base, amp, step):
        surf = pygame.Surface((self.LAYER_W, H), pygame.SRCALPHA)
        n = self.LAYER_W // step
        heights = [base - rng.uniform(0, amp) for _ in range(n)]
        pts = [(0, H)] + [(i * step, heights[i % n]) for i in range(n + 1)] + [(self.LAYER_W, H)]
        pygame.draw.polygon(surf, color, pts)
        return surf

    def draw(self, surf, cam):
        surf.blit(self.sky, (0, 0))
        for layer, factor in self.layers:
            off = -(cam * factor) % self.LAYER_W
            surf.blit(layer, (off - self.LAYER_W, 0))
            surf.blit(layer, (off, 0))
        for e in self.embers:
            e[1] -= e[2]
            e[0] += math.sin(e[1] * 0.02) * 0.3
            if e[1] < 0:
                e[1] = H
                e[0] = random.uniform(0, W)
            pygame.draw.circle(surf, (255, int(120 + 100 * e[2]), 40), (int(e[0]), int(e[1])), 1 + int(e[2] * 1.5))
        surf.blit(self.fog, (0, H - 160))


def make_tiles(theme):
    def block(top):
        s = pygame.Surface((T, T))
        s.fill(theme["block"])
        dark = theme["block_dark"]
        pygame.draw.line(s, dark, (0, T // 2), (T, T // 2), 2)
        pygame.draw.line(s, dark, (T // 2, 0), (T // 2, T // 2), 2)
        pygame.draw.line(s, dark, (6, T // 2), (6, T), 2)
        pygame.draw.rect(s, dark, (0, 0, T, T), 1)
        if top:
            pygame.draw.rect(s, theme["block_top"], (0, 0, T, 6))
            for dx, dh in ((5, 6), (17, 10), (29, 5), (35, 8)):
                pygame.draw.rect(s, theme["block_top"], (dx, 6, 3, dh))
        return s

    plate = pygame.Surface((T, T))
    plate.fill(theme["plate"])
    pygame.draw.rect(plate, (35, 32, 40), (0, 0, T, T), 2)
    pygame.draw.line(plate, (35, 32, 40), (0, 0), (T, T), 1)
    pygame.draw.line(plate, (35, 32, 40), (T, 0), (0, T), 1)
    for p in ((6, 6), (T - 6, 6), (6, T - 6), (T - 6, T - 6)):
        pygame.draw.circle(plate, (35, 32, 40), p, 3)
    return {"top": block(True), "inner": block(False), "plate": plate}


def draw_heart(surf, x, y, filled):
    col = (220, 30, 45) if filled else (60, 50, 60)
    pygame.draw.circle(surf, col, (x + 8, y + 8), 8)
    pygame.draw.circle(surf, col, (x + 20, y + 8), 8)
    pygame.draw.polygon(surf, col, [(x + 0, y + 11), (x + 28, y + 11), (x + 14, y + 26)])
    if filled:
        pygame.draw.circle(surf, (255, 150, 160), (x + 6, y + 6), 3)


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(GAME_TITLE)
        self.screen = pygame.display.set_mode((W, H))
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font_huge = pygame.font.SysFont("impact,arialblack,arial", 96)
        self.font_big = pygame.font.SysFont("impact,arialblack,arial", 56)
        self.font_med = pygame.font.SysFont("impact,arialblack,arial", 30)
        self.font_small = pygame.font.SysFont("consolas,couriernew,monospace", 20, bold=True)
        self.sfx = Sounds()
        self.highscore = self.load_highscore()
        self.new_highscore = False
        self.state = "title"
        self.title_backdrop = Backdrop(THEMES[0], 99)
        self.title_cam = 0.0
        self.global_t = 0
        self.level = None
        self.player = None
        self.particles = []
        self.shake = 0
        self.level_index = 0
        self.total_score = 0
        self.level_results = []

    # ---- persistence ---------------------------------------------------
    def load_highscore(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                return int(json.load(f).get("highscore", 0))
        except Exception:
            return 0

    def save_highscore(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                json.dump({"highscore": self.highscore}, f)
        except Exception:
            pass

    # ---- flow ------------------------------------------------------------
    def start_run(self):
        self.level_index = 0
        self.total_score = 0
        self.level_results = []
        self.new_highscore = False
        self.sfx.play("start")
        self.load_level(0)

    def load_level(self, index):
        self.level_index = index
        self.deaths = 0
        self.backdrop = Backdrop(THEMES[LEVELS[index]["theme"]], index)
        self.tiles = make_tiles(THEMES[LEVELS[index]["theme"]])
        self.reset_attempt()

    def reset_attempt(self):
        self.level = Level(self.level_index)
        self.player = Player(*self.level.start)
        self.hits = 0
        self.frames = 0
        self.particles = []
        self.shake = 0
        self.cam = 0.0
        self.state = "playing"
        self.banner_t = 120

    def take_hit(self, source):
        p = self.player
        self.hits += 1
        self.shake = 10
        self.sfx.play("hit")
        self.burst(p.x + p.W / 2, p.y + p.H / 2, (230, 30, 40), 14)
        if self.hits >= MAX_HITS:
            self.die("hits")
            return
        p.invuln = INVULN_FRAMES
        hx = source[0]
        pc = p.x + p.W / 2
        direction = -p.facing if abs(hx - pc) < 4 else (-1 if hx > pc else 1)
        p.vx = direction * 6
        p.vy = -8
        p.lock = KNOCKBACK_LOCK
        p.jumping = False

    def die(self, kind):
        self.state = "dead"
        self.death_kind = kind
        self.dead_timer = 110
        self.deaths += 1
        self.shake = 14
        self.sfx.play("die")
        if kind == "hits":
            p = self.player
            self.burst(p.x + p.W / 2, p.y + p.H / 2, (70, 58, 95), 30)
            self.burst(p.x + p.W / 2, p.y + p.H / 2, (210, 30, 40), 20)

    def complete_level(self):
        t = self.frames / FPS
        bonus, penalty, score = score_level(t, self.hits, self.level.par)
        self.total_score += score
        self.result = {"name": self.level.name, "time": t, "hits": self.hits, "par": self.level.par,
                       "bonus": bonus, "penalty": penalty, "score": score, "deaths": self.deaths}
        self.level_results.append(self.result)
        self.state = "complete"
        self.tally_t = 0
        self.sfx.play("win")
        self.burst(self.level.exit.pole_x, self.level.exit.ground - 4 * T, (240, 200, 60), 30)

    def advance(self):
        if self.level_index + 1 < len(LEVELS):
            self.load_level(self.level_index + 1)
        else:
            self.state = "victory"
            if self.total_score > self.highscore:
                self.highscore = self.total_score
                self.new_highscore = True
                self.save_highscore()

    # ---- particles ------------------------------------------------------
    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(1.5, 6)
            life = random.randint(25, 50)
            self.particles.append([x, y, math.cos(a) * sp, math.sin(a) * sp - 2, life, life, color,
                                   random.randint(2, 5)])

    def dust(self, x, y):
        for _ in range(6):
            life = random.randint(12, 22)
            self.particles.append([x + random.uniform(-10, 10), y, random.uniform(-1.5, 1.5),
                                   random.uniform(-1.5, -0.3), life, life, (190, 170, 160), 3])

    def update_particles(self):
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.25
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    # ---- per-frame update ---------------------------------------------
    def read_input(self):
        keys = pygame.key.get_pressed()
        return {
            "left": int(keys[pygame.K_LEFT] or keys[pygame.K_a]),
            "right": int(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
            "jump": any(keys[k] for k in JUMP_KEYS),
        }

    def update_world(self):
        lvl = self.level
        lvl.update()
        for kind, x in lvl.events:
            if abs(x - (self.cam + W / 2)) < W * 0.6:
                if kind == "slam":
                    self.sfx.play("slam")
                    self.shake = max(self.shake, 6)
                elif kind == "arrow":
                    self.sfx.play("arrow")
        lvl.events.clear()
        self.update_particles()
        if self.shake > 0:
            self.shake -= 1

    def update_playing(self, inp):
        self.update_world()
        p = self.player
        p.update(self, self.level, inp)
        self.frames += 1
        if self.banner_t > 0:
            self.banner_t -= 1

        target = p.x + p.W / 2 - W * 0.4
        self.cam += (target - self.cam) * 0.15
        self.cam = max(0.0, min(self.cam, self.level.width - W))

        if p.rect().colliderect(self.level.exit.rect):
            self.complete_level()
            return
        if p.y > H + 60:
            self.die("pit")
            return
        if p.invuln == 0:
            hurt = p.rect().inflate(-6, -4)
            for h in self.level.hazards:
                if h.hit(hurt):
                    self.take_hit(h.center())
                    return
            for a in self.level.arrows:
                if a.rect().colliderect(hurt):
                    a.alive = False
                    self.take_hit((a.x, a.y))
                    return

    def update(self, inp):
        self.global_t += 1
        if self.state == "title":
            self.title_cam += 1.5
        elif self.state == "playing":
            self.update_playing(inp)
        elif self.state == "dead":
            self.update_world()
            self.dead_timer -= 1
            if self.dead_timer <= 0:
                self.reset_attempt()
        elif self.state == "complete":
            self.update_world()
            self.tally_t += 1
            if self.tally_t < 6 * 25 and self.tally_t % 25 == 0:
                self.sfx.play("tick")

    def handle_key(self, key):
        if self.state == "title":
            if key in CONFIRM_KEYS:
                self.start_run()
            elif key == pygame.K_ESCAPE:
                return False
        elif self.state == "playing":
            if key in JUMP_KEYS:
                self.player.buffer = BUFFER_FRAMES
            elif key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = "paused"
            elif key == pygame.K_r:
                self.reset_attempt()
        elif self.state == "paused":
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = "playing"
            elif key == pygame.K_q:
                self.state = "title"
        elif self.state == "dead":
            if key in CONFIRM_KEYS and self.dead_timer < 80:
                self.reset_attempt()
        elif self.state == "complete":
            if key in CONFIRM_KEYS and self.tally_t > 20:
                if self.tally_t < 7 * 25:
                    self.tally_t = 7 * 25
                else:
                    self.advance()
        elif self.state == "victory":
            if key in CONFIRM_KEYS:
                self.state = "title"
        return True

    # ---- drawing --------------------------------------------------------
    def text(self, surf, font, msg, color, center=None, topleft=None, topright=None, shadow=True):
        img = font.render(msg, True, color)
        r = img.get_rect()
        if center:
            r.center = center
        elif topleft:
            r.topleft = topleft
        elif topright:
            r.topright = topright
        if shadow:
            surf.blit(font.render(msg, True, (0, 0, 0)), r.move(3, 3))
        surf.blit(img, r)
        return r

    def draw_world(self, surf):
        lvl = self.level
        cam = int(self.cam)
        self.backdrop.draw(surf, cam)

        def visible(h):
            return abs(h.x0 - cam - W / 2) < W / 2 + 200

        for h in lvl.hazards:
            if h.layer == "back" and visible(h):
                h.draw(surf, cam, lvl)
        c0 = max(0, cam // T)
        c1 = min(lvl.cols - 1, (cam + W) // T + 1)
        for r in range(ROWS):
            row = lvl.grid[r]
            for c in range(c0, c1 + 1):
                ch = row[c]
                if ch in SOLID:
                    if ch == "=":
                        img = self.tiles["plate"]
                    elif r > 0 and lvl.solid[r - 1][c]:
                        img = self.tiles["inner"]
                    else:
                        img = self.tiles["top"]
                    surf.blit(img, (c * T - cam, r * T))
        for h in lvl.hazards:
            if h.layer == "front" and visible(h):
                h.draw(surf, cam, lvl)
        for p in lvl.platforms:
            p.draw(surf, cam, lvl.theme)
        lvl.exit.draw(surf, cam, lvl.t)
        for a in lvl.arrows:
            a.draw(surf, cam)
        if self.state in ("playing", "paused", "complete"):
            self.player.draw(surf, cam, lvl.t)
        for p in self.particles:
            size = max(1, int(p[7] * p[4] / p[5]))
            pygame.draw.rect(surf, p[6], (int(p[0] - cam), int(p[1]), size, size))

    def draw_hud(self, surf):
        for i in range(MAX_HITS):
            draw_heart(surf, 18 + i * 34, 14, i < MAX_HITS - self.hits)
        self.text(surf, self.font_small, f"TIME {self.frames / FPS:6.1f}", (240, 230, 220), topright=(W - 18, 16))
        self.text(surf, self.font_small, f"PAR {self.level.par}s", (200, 180, 170), topright=(W - 18, 40))
        self.text(surf, self.font_small, f"LEVEL {self.level_index + 1}: {self.level.name.upper()}",
                  (240, 230, 220), center=(W // 2, 22))
        bar = pygame.Rect(W // 2 - 120, 40, 240, 8)
        pygame.draw.rect(surf, (30, 25, 35), bar)
        prog = max(0.0, min(1.0, self.player.x / max(1, self.level.exit.pole_x)))
        pygame.draw.rect(surf, (210, 40, 50), (bar.left, bar.top, int(bar.width * prog), bar.height))
        pygame.draw.rect(surf, (240, 230, 220), bar, 1)
        if self.deaths:
            self.text(surf, self.font_small, f"DEATHS {self.deaths}", (200, 180, 170), topleft=(18, 46))

    def overlay(self, surf, alpha):
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, alpha))
        surf.blit(shade, (0, 0))

    def draw_title(self, surf):
        self.title_backdrop.draw(surf, int(self.title_cam))
        word = "DOOMSCROLLER!"
        widths = [self.font_huge.size(ch)[0] for ch in word]
        x = W // 2 - sum(widths) // 2
        rng = random.Random(self.global_t // 6)
        for ch, w in zip(word, widths):
            jx, jy = rng.randint(-2, 2), rng.randint(-3, 3)
            surf.blit(self.font_huge.render(ch, True, (0, 0, 0)), (x + jx + 5, 120 + jy + 5))
            surf.blit(self.font_huge.render(ch, True, (220, 30, 40)), (x + jx, 120 + jy))
            x += w
        self.text(surf, self.font_med, "Run. Jump. Try not to die.", (240, 220, 200), center=(W // 2, 260))
        lines = ["ARROWS / A D  run", "SPACE / UP / W  jump (hold = higher)",
                 "P / ESC  pause      R  restart level"]
        for i, line in enumerate(lines):
            self.text(surf, self.font_small, line, (220, 210, 200), center=(W // 2, 320 + i * 28))
        if (self.global_t // 30) % 2 == 0:
            self.text(surf, self.font_med, "PRESS ENTER TO START", (255, 210, 80), center=(W // 2, 440))
        self.text(surf, self.font_small, f"BEST TOTAL: {self.highscore}", (200, 180, 170), center=(W // 2, 500))

    def draw_complete(self, surf):
        self.overlay(surf, 160)
        r = self.result
        self.text(surf, self.font_big, f"LEVEL {self.level_index + 1} CLEARED!", (255, 210, 80), center=(W // 2, 80))
        verdict = "FLAWLESS!" if r["hits"] == 0 else ("BARELY ALIVE" if r["hits"] == MAX_HITS - 1 else "BRUISED")
        self.text(surf, self.font_med, verdict, (230, 60, 60), center=(W // 2, 135))
        rows = [
            ("Time", f"{r['time']:.1f}s  (par {r['par']}s)"),
            ("Hits taken", f"{r['hits']}"),
            ("Level cleared", f"+{COMPLETE_BONUS}"),
            ("Time bonus", f"+{r['bonus']}"),
            ("Hit penalty", f"-{r['penalty']}"),
            ("LEVEL SCORE", f"{r['score']}"),
        ]
        shown = min(len(rows), self.tally_t // 25)
        for i in range(shown):
            label, val = rows[i]
            y = 185 + i * 40
            col = (255, 210, 80) if i == len(rows) - 1 else (235, 225, 215)
            self.text(surf, self.font_med, label, col, topleft=(W // 2 - 260, y))
            self.text(surf, self.font_med, val, col, topright=(W // 2 + 260, y))
        if self.tally_t >= 7 * 25:
            self.text(surf, self.font_med, f"RUN TOTAL: {self.total_score}", (255, 255, 255), center=(W // 2, 450))
            nxt = "next level" if self.level_index + 1 < len(LEVELS) else "final results"
            if (self.global_t // 30) % 2 == 0:
                self.text(surf, self.font_small, f"PRESS ENTER FOR {nxt.upper()}", (255, 210, 80),
                          center=(W // 2, 500))

    def draw_victory(self, surf):
        self.backdrop.draw(surf, int(self.global_t * 1.5))
        self.overlay(surf, 120)
        self.text(surf, self.font_big, "YOU SURVIVED THE DOOMSCROLL", (255, 210, 80), center=(W // 2, 80))
        for i, r in enumerate(self.level_results):
            y = 160 + i * 44
            self.text(surf, self.font_med, f"{i + 1}. {r['name']}", (235, 225, 215), topleft=(W // 2 - 300, y))
            hits = f"{r['hits']} hit" + ("" if r["hits"] == 1 else "s")
            self.text(surf, self.font_small, f"{r['time']:.1f}s  {hits}",
                      (200, 180, 170), topleft=(W // 2 + 10, y + 8))
            self.text(surf, self.font_med, f"{r['score']}", (235, 225, 215), topright=(W // 2 + 300, y))
        self.text(surf, self.font_big, f"TOTAL: {self.total_score}", (255, 255, 255), center=(W // 2, 340))
        if self.new_highscore:
            self.text(surf, self.font_med, "NEW HIGH SCORE!", (230, 60, 60), center=(W // 2, 400))
        else:
            self.text(surf, self.font_small, f"BEST: {self.highscore}", (200, 180, 170), center=(W // 2, 400))
        if (self.global_t // 30) % 2 == 0:
            self.text(surf, self.font_small, "PRESS ENTER TO RETURN TO TITLE", (255, 210, 80), center=(W // 2, 480))

    def draw(self):
        screen = self.screen
        if self.state == "title":
            self.draw_title(screen)
        elif self.state == "victory":
            self.draw_victory(screen)
        else:
            self.draw_world(self.canvas)
            ox = oy = 0
            if self.shake > 0:
                ox, oy = random.randint(-self.shake, self.shake) // 2, random.randint(-self.shake, self.shake) // 2
            screen.fill((0, 0, 0))
            screen.blit(self.canvas, (ox, oy))
            self.draw_hud(screen)
            if self.state == "playing" and self.banner_t > 0:
                self.text(screen, self.font_big, f"LEVEL {self.level_index + 1}", (255, 210, 80),
                          center=(W // 2, H // 2 - 50))
                self.text(screen, self.font_med, self.level.name, (240, 220, 200), center=(W // 2, H // 2 + 5))
            elif self.state == "paused":
                self.overlay(screen, 150)
                self.text(screen, self.font_big, "PAUSED", (255, 210, 80), center=(W // 2, H // 2 - 30))
                self.text(screen, self.font_small, "P / ESC resume     Q quit to title",
                          (230, 220, 210), center=(W // 2, H // 2 + 30))
            elif self.state == "dead":
                msg = "YOU FELL INTO THE ABYSS" if self.death_kind == "pit" else "YOU DIED"
                self.text(screen, self.font_huge if self.death_kind != "pit" else self.font_big, msg,
                          (220, 30, 40), center=(W // 2, H // 2 - 20))
                self.text(screen, self.font_small, "Restarting level...", (230, 220, 210),
                          center=(W // 2, H // 2 + 50))
            elif self.state == "complete":
                self.draw_complete(screen)
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if not self.handle_key(event.key):
                        running = False
            self.update(self.read_input())
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    Game().run()
    sys.exit()
