"""2D side-view replay viewer (pygame). Reads the same replay JSON as the engine writes.

Boxers are drawn in profile with readable poses: gloves up at the chin in GUARD, arm cocked on WINDUP
then snapped out to the exact head/body target on the punch, head dropped on a DUCK / shifted on a SLIP.
Landed punches flash on the target. Side panels show a play-by-play of every punch + outcome and the
full reasoning for each fighter. A small top-down minimap shows ring position and circling.

  python -m render.renderer_2d replays/B2_LLM_vs_LLM_smoke_42.json

Controls: SPACE play/pause · LEFT/RIGHT scrub (hold) · +/- speed · R reasoning · Q/Esc quit
"""
import json
import sys

import pygame

W, H = 1280, 760
BG = (26, 26, 32)
FLOOR = (58, 54, 50)
CANVAS = (74, 70, 64)
ROPE = (200, 55, 55)
WHITE = (235, 235, 240)
DIM = (150, 150, 160)
HEADC = (245, 217, 190)

RED = {"torso": (210, 70, 70), "glove": (243, 160, 160), "ink": (255, 150, 150)}
BLUE = {"torso": (74, 120, 220), "glove": (166, 196, 255), "ink": (168, 198, 255)}
PUNCH = {"jab": (70, 160, 235), "cross": (245, 140, 40), "hook": (225, 60, 60), "uppercut": (240, 210, 60)}

FLOOR_Y = 560
CENTER_X = 540
PX_PER_FT = 42
RING_FT = 16.0


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class Viewer:
    def __init__(self, path):
        data = json.load(open(path, encoding="utf-8"))
        self.frames = data["frames"]
        self.footer = data["footer"]
        self.header = data["header"]
        self.dt = self.header["dt"]
        self.i = 0
        self.playing = True
        self.speed = 1.0
        self.acc = 0.0
        self.scrub_t = 0.1
        self.show_reason = True
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Glass Joe Minds - 2D")
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.SysFont("consolas", 22)
        self.f = pygame.font.SysFont("consolas", 16)
        self.f_sm = pygame.font.SysFont("consolas", 14)
        # precompute (t, text) event log
        self.log = []
        for fr in self.frames:
            for e in fr["events"]:
                self.log.append((fr["t"], self._fmt_event(e)))

    # ---------- helpers ----------
    @staticmethod
    def _fmt_event(e):
        k = e["kind"]
        if k == "land":
            q = e["quality"].upper()
            return (e["by"][0], f"{e['by']} {e['punch']}>{e['placement'].replace('_',' ')} {q} ({e['health_dmg']})")
        if k == "avoid":
            return (e["by"][0], f"{e['by']} {e['via'].replace('_',' ')} a {e['punch']}")
        if k == "whiff":
            return (e["by"][0], f"{e['by']} missed a {e['punch']}")
        return (e["by"][0] if "by" in e else "", f"{k}")

    def frame(self):
        return self.frames[max(0, min(self.i, len(self.frames) - 1))]

    # ---------- drawing ----------
    def draw_boxer(self, cx, facing, b, pal):
        s = self.screen
        Hh = 230
        hip_y = FLOOR_Y - int(0.45 * Hh)
        sh_y = FLOOR_Y - int(0.82 * Hh)
        head_y = FLOOR_Y - int(0.95 * Hh)
        head_r = int(0.12 * Hh)
        torso_w = int(0.34 * Hh)
        glove_r = int(0.085 * Hh)
        punching = b["left"]["state"] in ("windup", "recovery") or b["right"]["state"] in ("windup", "recovery")
        lean = facing * (10 if punching else 0)

        # legs
        for dx in (-0.10, 0.10):
            pygame.draw.line(s, pal["torso"], (cx + dx * Hh, hip_y), (cx + dx * Hh + facing * 8, FLOOR_Y), 12)
        # torso
        torso = pygame.Rect(0, 0, torso_w, hip_y - sh_y + 16)
        torso.center = (cx + lean * 0.4, (hip_y + sh_y) // 2)
        pygame.draw.rect(s, pal["torso"], torso, border_radius=10)
        # head (with defense)
        hx, hy = cx + lean, head_y
        d = b.get("defense")
        if d == "duck":
            hy += int(0.18 * Hh)
        elif d in ("slip_left", "slip_right"):
            hx -= facing * int(0.07 * Hh)
        pygame.draw.circle(s, HEADC, (int(hx), int(hy)), head_r)

        # arms / gloves (each hand by its own state)
        shoulder = (cx + facing * 6, sh_y + 6)
        for hand in (b["left"], b["right"]):
            st = hand["state"]
            pt = hand.get("punch_type", "")
            pl = hand.get("placement", "head_center")
            if st == "windup":
                g = (cx - facing * 0.07 * Hh, sh_y - 0.06 * Hh)          # cocked back
            elif st == "recovery":
                if pl.startswith("head"):
                    g = (cx + facing * 0.48 * Hh, head_y + 0.03 * Hh)    # extended to head
                else:
                    g = (cx + facing * 0.44 * Hh, hip_y - 0.10 * Hh)     # extended to body
            elif st == "guard":
                g = (cx + facing * 0.12 * Hh, sh_y - 0.02 * Hh)          # up at the chin
            else:  # free
                g = (cx + facing * 0.08 * Hh, hip_y + 0.02 * Hh)         # down
            gc = PUNCH.get(pt, pal["glove"]) if st in ("windup", "recovery") else pal["glove"]
            pygame.draw.line(s, pal["torso"], shoulder, g, 13)
            pygame.draw.circle(s, gc, (int(g[0]), int(g[1])), glove_r)
            pygame.draw.circle(s, (40, 40, 46), (int(g[0]), int(g[1])), glove_r, 2)

    def draw_impacts(self, fr, red_cx, blue_cx):
        for e in fr["events"]:
            if e["kind"] != "land":
                continue
            defender_cx = blue_cx if e["by"] == fr["red"]["name"] else red_cx
            facing = 1 if defender_cx == blue_cx else -1  # flash on the side the punch came from
            pl = e["placement"]
            y = FLOOR_Y - int(0.95 * 230) if pl.startswith("head") else FLOOR_Y - int(0.55 * 230)
            x = defender_cx - facing * 30
            blocked = e["quality"] == "blocked"
            col = (160, 170, 180) if blocked else (255, 230, 80)
            r = 14 if blocked else 26
            pygame.draw.circle(self.screen, col, (x, y), r)
            txt = "BLOCK" if blocked else f"-{e['health_dmg']}"
            self.screen.blit(self.f_sm.render(txt, True, (20, 20, 20)), (x - 18, y - 7))

    def bar(self, x, y, label, val, maxv, col):
        s = self.screen
        s.blit(self.f.render(label, True, WHITE), (x, y))
        bx = x + 52
        pygame.draw.rect(s, (60, 60, 68), (bx, y + 2, 240, 16))
        pygame.draw.rect(s, col, (bx, y + 2, int(240 * max(0, val) / maxv), 16))
        s.blit(self.f.render(f"{val:5.1f}", True, WHITE), (bx + 248, y))

    def draw_minimap(self, fr):
        s = self.screen
        mx, my, ms = 1108, 14, 150
        pygame.draw.rect(s, (45, 45, 52), (mx, my, ms, ms))
        pygame.draw.rect(s, (90, 90, 98), (mx, my, ms, ms), 2)
        for who, pal in (("red", RED), ("blue", BLUE)):
            p = fr[who]["pos"]
            px = mx + int(p[0] / RING_FT * ms)
            py = my + int(p[1] / RING_FT * ms)
            pygame.draw.circle(s, pal["torso"], (px, py), 8)
        s.blit(self.f_sm.render("ring (top-down)", True, DIM), (mx, my + ms + 2))

    def wrap(self, text, width):
        words, lines, cur = text.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 <= width:
                cur = (cur + " " + w).strip()
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
        return lines

    def last_reason(self, who):
        name = self.frames[0][who]["name"]
        for j in range(min(self.i, len(self.frames) - 1), -1, -1):
            dec = self.frames[j]["decisions"].get(name)
            if dec and dec.get("reasoning"):
                return dec["reasoning"]
        return ""

    def render(self):
        s = self.screen
        fr = self.frame()
        s.fill(BG)
        # floor / ring
        pygame.draw.rect(s, FLOOR, (0, FLOOR_Y, W, H - FLOOR_Y))
        pygame.draw.rect(s, CANVAS, (60, FLOOR_Y, 940, 8))
        for h in (60, 120, 180):
            pygame.draw.line(s, ROPE, (60, FLOOR_Y - h), (1000, FLOOR_Y - h), 4)
        for px in (60, 1000):
            pygame.draw.line(s, (150, 150, 156), (px, FLOOR_Y - 190), (px, FLOOR_Y), 6)

        # boxers, spaced by true range
        gap = max(120, min(620, _dist(fr["red"]["pos"], fr["blue"]["pos"]) * PX_PER_FT))
        red_cx = int(CENTER_X - gap / 2)
        blue_cx = int(CENTER_X + gap / 2)
        self.draw_boxer(red_cx, +1, fr["red"], RED)
        self.draw_boxer(blue_cx, -1, fr["blue"], BLUE)
        self.draw_impacts(fr, red_cx, blue_cx)

        # HUD
        s.blit(self.f_big.render(f"Round 1   t={fr['t']:5.2f}s   [{fr['phase']}]   x{self.speed:.1f}"
                                 f"   {'PLAYING' if self.playing else 'PAUSED'}", True, WHITE), (20, 10))
        self.bar(20, 40, fr["red"]["name"], fr["red"]["health"], 100, RED["torso"])
        self.bar(360, 40, "EN", fr["red"]["energy"], 100, (180, 150, 70))
        self.bar(20, 62, fr["blue"]["name"], fr["blue"]["health"], 100, BLUE["torso"])
        self.bar(360, 62, "EN", fr["blue"]["energy"], 100, (180, 150, 70))
        self.draw_minimap(fr)

        # play-by-play (events up to now, last 16)
        s.blit(self.f.render("PLAY-BY-PLAY", True, WHITE), (1020, 180))
        shown = [(t, who, txt) for (t, (who, txt)) in self.log if t <= fr["t"] + 1e-9][-16:]
        for k, (t, who, txt) in enumerate(shown):
            col = RED["ink"] if who == "R" else BLUE["ink"]
            s.blit(self.f_sm.render(f"{t:4.2f} {txt}"[:34], True, col), (1020, 206 + k * 18))

        # reasoning panels
        if self.show_reason:
            for who, pal, x in (("red", RED, 20), ("blue", BLUE, 660)):
                name = self.frames[0][who]["name"]
                pygame.draw.rect(s, (38, 38, 46), (x, 600, 600 if who == "red" else 540, 150), border_radius=8)
                s.blit(self.f.render(f"{name} thinking:", True, pal["ink"]), (x + 10, 608))
                for k, line in enumerate(self.wrap(self.last_reason(who), 64)[:5]):
                    s.blit(self.f_sm.render(line, True, WHITE), (x + 10, 632 + k * 20))

        # banner
        if fr["phase"] == "END" or self.i >= len(self.frames) - 1:
            b = self.f_big.render(self.footer["result"], True, (250, 220, 60))
            s.blit(b, (CENTER_X - b.get_width() // 2, 120))
        pygame.display.flip()

    # ---------- loop ----------
    def step_keys(self):
        keys = pygame.key.get_pressed()
        d = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
        if d:
            self.playing = False
            self.scrub_t += self.clock.get_time() / 1000.0
            if self.scrub_t >= 0.05:
                self.scrub_t = 0.0
                self.i = max(0, min(self.i + d, len(self.frames) - 1))
            return True
        self.scrub_t = 0.05
        return False

    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif ev.key == pygame.K_SPACE:
                        if self.i >= len(self.frames) - 1:
                            self.i = 0
                        self.playing = not self.playing
                    elif ev.key == pygame.K_r:
                        self.show_reason = not self.show_reason
                    elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.speed = min(8.0, self.speed * 1.5)
                    elif ev.key == pygame.K_MINUS:
                        self.speed = max(0.1, self.speed / 1.5)
            if not self.step_keys() and self.playing:
                self.acc += self.clock.get_time() / 1000.0 * self.speed
                while self.acc >= self.dt:
                    self.acc -= self.dt
                    if self.i < len(self.frames) - 1:
                        self.i += 1
                    else:
                        self.playing = False
            self.render()
            self.clock.tick(60)
        pygame.quit()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "replays/test_mock.json"
    Viewer(path).run()


if __name__ == "__main__":
    main()
