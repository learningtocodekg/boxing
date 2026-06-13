"""3D replay viewer (PRD §15). Primitive humanoid boxers — torso + head + arms with GLOVES that shoot
to the actual target (head/body, left/right) on a punch, so the action is readable — in a 16x16 ring,
with health/energy bars, the round clock, a KO banner, and a floating reasoning overlay per fighter.

  python -m render.renderer_ursina replays/B2_LLM_vs_LLM_smoke_42.json

Controls: SPACE play/pause · LEFT/RIGHT step · R reasoning · +/- speed
          1 side view · 2 corner/3-4 angle · 3 top · [ / ] zoom · Q/Esc quit
"""
import json
import sys

from ursina import Ursina, Entity, camera, color, Text, window, time, Vec3, held_keys

RING = 16.0
UP = Vec3(0, 1, 0)

RED_PALETTE = {"torso": "#d24646", "hips": "#a83636", "arm": "#bf4242", "glove": "#f3a0a0"}
BLUE_PALETTE = {"torso": "#4a78dc", "hips": "#37589f", "arm": "#4063c4", "glove": "#a6c4ff"}


def _w(pos):
    """Replay [x,z] in [0,16] -> world (x,0,z) centered on origin; feet on the floor (y=0)."""
    return Vec3(pos[0] - RING / 2, 0, pos[1] - RING / 2)


def _facing(base, opp):
    f = opp - base
    f.y = 0
    f = f.normalized()
    return f, Vec3(f.z, 0, -f.x)  # forward, right (xz-plane)


PUNCH_COLOR = {"jab": color.azure, "cross": color.orange, "hook": color.red, "uppercut": color.yellow}


def _limb(ent, p0, p1):
    """Stretch a thin cube from p0 to p1 (used for arms)."""
    ent.position = (p0 + p1) / 2
    ent.look_at(p1)
    ent.scale_z = max(0.12, (p1 - p0).length())


class Boxer:
    def __init__(self, palette):
        glove_c = color.hex(palette["glove"])
        arm_c = color.hex(palette["arm"])
        self.shadow = Entity(model="quad", scale=(1.5, 1.5, 1), rotation_x=90, color=color.black)
        self.shadow.alpha = 0.3
        self.hips = Entity(model="cube", color=color.hex(palette["hips"]), scale=(0.85, 0.8, 0.5))
        self.torso = Entity(model="cube", color=color.hex(palette["torso"]), scale=(0.95, 1.5, 0.55))
        self.head = Entity(model="sphere", color=color.peach, scale=0.62)
        self.larm = Entity(model="cube", color=arm_c, scale=(0.16, 0.16, 1))
        self.rarm = Entity(model="cube", color=arm_c, scale=(0.16, 0.16, 1))
        self.lglove = Entity(model="sphere", color=glove_c, scale=0.36)
        self.rglove = Entity(model="sphere", color=glove_c, scale=0.36)
        self.glove_c = glove_c
        self.label = Text(parent=camera.ui, text="", origin=(0, 0), scale=0.7, color=color.white)

    def update(self, bx, opp_pos):
        base = _w(bx["pos"])
        opp = _w(opp_pos)
        f, right = _facing(base, opp)
        punching = bx["left"]["state"] in ("windup", "recovery") or bx["right"]["state"] in ("windup", "recovery")
        lean = f * (0.25 if punching else 0.0)

        self.shadow.position = base + Vec3(0, 0.02, 0)
        self.hips.position = base + UP * 0.8
        self.hips.look_at(opp + UP * 0.8)
        self.torso.position = base + UP * 1.55 + lean
        self.torso.look_at(opp + UP * 1.55)

        head = base + UP * 2.2 + lean
        d = bx.get("defense")
        if d == "duck":
            head += UP * -0.6 + f * 0.25
        elif d == "slip_left":
            head += -right * 0.5
        elif d == "slip_right":
            head += right * 0.5
        self.head.position = head

        for glove, arm, hand, side in ((self.lglove, self.larm, bx["left"], 1),
                                       (self.rglove, self.rarm, bx["right"], -1)):
            shoulder = base + UP * 1.75 + right * (0.45 * side) + lean
            st = hand["state"]
            if st in ("windup", "recovery"):
                pl = hand.get("placement", "head_center")
                h = 2.1 if pl.startswith("head") else 1.25
                lat = 0.45 if pl.endswith("left") else (-0.45 if pl.endswith("right") else 0.0)
                reach = 1.7 if st == "windup" else 1.45
                target = base + f * reach + UP * h + right * lat
                glove.color = PUNCH_COLOR.get(hand.get("punch_type", ""), self.glove_c)
            elif st == "guard":
                target = base + UP * 2.0 + f * 0.3 + right * (0.22 * side)
                glove.color = self.glove_c
            else:  # free
                target = base + UP * 1.1 + right * (0.45 * side) + f * 0.1
                glove.color = self.glove_c
            glove.position = target
            _limb(arm, shoulder, target)


class Viewer:
    def __init__(self, path):
        data = json.load(open(path, encoding="utf-8"))
        self.frames = data["frames"]
        self.footer = data["footer"]
        self.header = data["header"]
        self.i = 0
        self.playing = True
        self.speed = 1.0
        self.acc = 0.0
        self.scrub_t = 0.06
        self.show_reason = True

        Entity(model="plane", scale=RING, color=color.hex("#3a3a44"))
        Entity(model="plane", scale=RING * 0.9, color=color.hex("#55504a"), y=0.01)  # canvas inset
        rope_c = color.hex("#cc3333")
        for s in (-1, 1):
            for h in (0.6, 1.2, 1.8):  # three ropes per side
                Entity(model="cube", color=rope_c, scale=(RING, 0.06, 0.06), position=(0, h, s * RING / 2))
                Entity(model="cube", color=rope_c, scale=(0.06, 0.06, RING), position=(s * RING / 2, h, 0))
            for c in (-1, 1):  # corner posts
                Entity(model="cube", color=color.gray, scale=(0.2, 2.0, 0.2), position=(s * RING / 2, 1.0, c * RING / 2))

        self.red = Boxer(RED_PALETTE)
        self.blue = Boxer(BLUE_PALETTE)
        for lbl in (self.red.label, self.blue.label):
            lbl.text = " "          # ensure raw_text exists before wordwrap setter reads it
            lbl.wordwrap = 40
        self.red.label.origin = (-0.5, 0.5); self.red.label.position = (-0.86, -0.34)
        self.red.label.color = color.hex("#ff9a9a")
        self.blue.label.origin = (0.5, 0.5); self.blue.label.position = (0.86, -0.34)
        self.blue.label.color = color.hex("#a8c6ff")

        self.hud = Text(parent=camera.ui, position=(-0.86, 0.46), scale=0.85, color=color.white)
        self.banner = Text(parent=camera.ui, origin=(0, 0), position=(0, 0.32), scale=2.4,
                           color=color.yellow, text="")

    def frame(self):
        return self.frames[max(0, min(self.i, len(self.frames) - 1))]

    def render(self):
        fr = self.frame()
        self.red.update(fr["red"], fr["blue"]["pos"])
        self.blue.update(fr["blue"], fr["red"]["pos"])

        def bar(b):
            hp = int(b["health"] / 5)
            en = int(b["energy"] / 5)
            return f"{b['name']:<5} HP {'#'*hp:<20} {b['health']:5.1f}   EN {'='*en:<20} {b['energy']:5.1f}"
        self.hud.text = (f"t={fr['t']:.2f}s  [{fr['phase']}]   round {self.header['round_seconds']}s   "
                         f"speed x{self.speed:.1f}\n{bar(fr['red'])}\n{bar(fr['blue'])}")

        self.red.label.text = self._last_reason("red") if self.show_reason else ""
        self.blue.label.text = self._last_reason("blue") if self.show_reason else ""

        self.banner.text = self.footer["result"] if (fr["phase"] == "END" or self.i >= len(self.frames) - 1) else ""

    def _last_reason(self, key):
        name = self.frames[0][key]["name"]
        for j in range(min(self.i, len(self.frames) - 1), -1, -1):
            dec = self.frames[j]["decisions"].get(name)
            if dec and dec.get("reasoning"):
                return f"{name}: {dec['reasoning']}"
        return ""


_V: Viewer | None = None
_APP = None

# Camera presets: side (ringside profile) / angle (3/4) / top
_CAMS = {
    "1": ((9.0, 3.8, 0), (0, 1.5, 0)),     # ringside side-on, close
    "2": ((7.5, 5.5, -7.5), (0, 1.4, 0)),  # 3/4 corner
    "3": ((0, 13, -6), (0, 0.5, 0)),       # high/top
}
_cam = {"pos": Vec3(9, 3.8, 0), "look": Vec3(0, 1.5, 0), "zoom": 1.0}


def _apply_cam():
    look = _cam["look"]
    camera.position = look + (_cam["pos"] - look) * _cam["zoom"]
    camera.look_at(look)


def _set_cam(key):
    pos, look = _CAMS[key]
    _cam.update(pos=Vec3(*pos), look=Vec3(*look), zoom=1.0)
    _apply_cam()


def _zoom(factor):
    _cam["zoom"] = max(0.3, min(2.5, _cam["zoom"] * factor))
    _apply_cam()


def update():
    if _V is None:
        return
    # Hold LEFT/RIGHT to scrub (works whether playing or paused). Tap = one frame; hold = ~16/sec.
    step = (1 if held_keys["right arrow"] else 0) - (1 if held_keys["left arrow"] else 0)
    if step:
        _V.playing = False
        _V.scrub_t += time.dt
        if _V.scrub_t >= 0.06:
            _V.scrub_t = 0.0
            _V.i = max(0, min(_V.i + step, len(_V.frames) - 1))
            _V.render()
        return
    _V.scrub_t = 0.06  # primed so the next tap steps immediately
    if not _V.playing:
        return
    _V.acc += time.dt * _V.speed
    while _V.acc >= _V.header["dt"]:
        _V.acc -= _V.header["dt"]
        if _V.i < len(_V.frames) - 1:
            _V.i += 1
        else:
            _V.playing = False  # stop at the end instead of spinning
    _V.render()


def input(key):
    if _V is None:
        return
    if key in ("q", "escape"):
        _APP.userExit()
    elif key == "space":
        if _V.i >= len(_V.frames) - 1:      # replay from start if at the end
            _V.i = 0
        _V.playing = not _V.playing
    elif key == "r":
        _V.show_reason = not _V.show_reason; _V.render()
    elif key in ("+", "="):
        _V.speed = min(8.0, _V.speed * 1.5); _V.render()
    elif key == "-":
        _V.speed = max(0.1, _V.speed / 1.5); _V.render()
    elif key in _CAMS:
        _set_cam(key)
    elif key == "]":
        _zoom(1 / 1.15)   # closer
    elif key == "[":
        _zoom(1.15)       # farther


def main():
    global _V, _APP
    path = sys.argv[1] if len(sys.argv) > 1 else "replays/test_mock.json"
    _APP = Ursina()
    window.title = "Glass Joe Minds"
    _V = Viewer(path)
    _set_cam("1")           # default: ringside side view
    _V.render()
    _APP.run()


if __name__ == "__main__":
    main()
