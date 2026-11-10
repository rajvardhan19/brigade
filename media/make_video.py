#!/usr/bin/env python3
"""Render the Brigade LinkedIn video (1080x1350, 30 fps, no audio) with Pillow + ffmpeg.

Usage: python3 media/make_video.py [out.mp4] [--frames t1,t2,...]   (--frames writes PNG stills instead)
"""
import math
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, SS, FPS = 1080, 1350, 2, 30  # SS = supersampling factor for smooth shapes

# Colors: dark chart surface and ink tokens, model identity hues and status colors
# from the validated dataviz palette (dark mode).
BG = (26, 26, 25)          # #1a1a19 surface
CARD = (36, 36, 34)        # raised card
RING = (58, 58, 56)        # hairline ring on cards
INK = (240, 239, 236)      # primary text
INK2 = (195, 194, 183)     # secondary text
MUTED = (137, 135, 129)    # muted text, de-emphasis fill
TRACK_GRAY = (56, 56, 53)  # #383835
OPUS = (57, 135, 229)      # slot 1 blue   #3987e5
SONNET = (217, 89, 38)     # slot 2 orange #d95926
HAIKU = (25, 158, 112)     # slot 3 aqua   #199e70
TRACK_BLUE = (16, 66, 129)  # blue ramp step 650, the meter track under the blue fill
GOOD = (12, 163, 12)       # status good, always with an icon + label

AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
FACES = {"bold": 0, "demi": 2, "medium": 5, "regular": 7, "heavy": 8}
MONO = "/System/Library/Fonts/SFNSMono.ttf"
SYMBOL = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
_fonts = {}


def font(size, face="medium"):
    key = (size, face)
    if key not in _fonts:
        if face == "mono":
            _fonts[key] = ImageFont.truetype(MONO, size * SS)
        elif face == "symbol":
            _fonts[key] = ImageFont.truetype(SYMBOL, size * SS)
        else:
            _fonts[key] = ImageFont.truetype(AVENIR, size * SS, index=FACES[face])
    return _fonts[key]


def clamp(x):
    return max(0.0, min(1.0, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def mix(c, a, under=BG):
    return tuple(int(round(under[i] + (c[i] - under[i]) * a)) for i in range(3))


class Canvas:
    def __init__(self, scene_alpha=1.0):
        self.img = Image.new("RGB", (W * SS, H * SS), BG)
        self.d = ImageDraw.Draw(self.img)
        self.sa = scene_alpha

    def text(self, xy, s, size, face="medium", color=INK, a=1.0, anchor="la", under=BG, dy=0.0):
        x, y = xy
        self.d.text((x * SS, (y + dy) * SS), s, font=font(size, face), fill=mix(color, a * self.sa, under), anchor=anchor)

    def width(self, s, size, face="medium"):
        return self.d.textlength(s, font=font(size, face)) / SS

    def rrect(self, box, r, fill=None, outline=None, a=1.0, width=2, under=BG):
        x0, y0, x1, y1 = box
        self.d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius=r * SS,
                                 fill=mix(fill, a * self.sa, under) if fill else None,
                                 outline=mix(outline, a * self.sa, under) if outline else None,
                                 width=int(width * SS))

    def line(self, pts, color, a=1.0, width=3):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=mix(color, a * self.sa), width=int(width * SS), joint="curve")

    def circle(self, cx, cy, r, color, a=1.0, under=BG):
        self.d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=mix(color, a * self.sa, under))

    def arrowhead(self, x, y, direction, color, a=1.0, size=11):
        dx, dy = {"down": (0, 1), "left": (-1, 0), "right": (1, 0), "up": (0, -1)}[direction]
        px, py = -dy, dx
        pts = [(x, y), (x - dx * size + px * size * 0.7, y - dy * size + py * size * 0.7),
               (x - dx * size - px * size * 0.7, y - dy * size - py * size * 0.7)]
        self.d.polygon([(u * SS, v * SS) for u, v in pts], fill=mix(color, a * self.sa))

    def check_icon(self, cx, cy, r, a=1.0):
        self.circle(cx, cy, r, GOOD, a)
        self.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], INK, a, width=r * 0.22)

    def done(self):
        return self.img.resize((W, H), Image.LANCZOS)


def path_point(pts, f):
    """Point at fraction f along a polyline, plus the polyline up to there."""
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    lens = [math.dist(p, q) for p, q in segs]
    target = sum(lens) * clamp(f)
    out = [pts[0]]
    for (p, q), length in zip(segs, lens):
        if target <= length:
            r = target / length if length else 0
            pt = (p[0] + (q[0] - p[0]) * r, p[1] + (q[1] - p[1]) * r)
            return pt, out + [pt]
        target -= length
        out.append(q)
    return pts[-1], out


def kicker(c, s="BRIGADE  ·  A CLAUDE CODE SKILL", a=1.0):
    c.text((90, 70), s, 22, "demi", MUTED, a)


# ---------------------------------------------------------------- scenes

def scene_title(c, t, dur):
    e = ease(t / 0.9)
    for i, col in enumerate((OPUS, SONNET, HAIKU)):
        c.circle(540 + (i - 1) * 46, 470, 13, col, ease((t - 0.2 - i * 0.12) / 0.5))
    c.text((540, 600), "Brigade", 150, "bold", INK, e, "mm", dy=(1 - e) * 30)
    e2 = ease((t - 0.6) / 0.8)
    c.text((540, 735), "Run big Claude Code projects", 46, "medium", INK2, e2, "mm", dy=(1 - e2) * 20)
    c.text((540, 795), "like a professional kitchen", 46, "medium", INK2, e2, "mm", dy=(1 - e2) * 20)
    e3 = ease((t - 1.4) / 0.8)
    c.text((540, 900), "An open-source skill for Claude Code", 30, "medium", MUTED, e3, "mm")


def scene_problem(c, t, dur):
    kicker(c)
    e = ease(t / 0.7)
    c.text((90, 250), "Long AI coding sessions", 64, "bold", INK, e, dy=(1 - e) * 20)
    c.text((90, 330), "drift.", 64, "bold", INK, e, dy=(1 - e) * 20)
    items = [["The context fills up"], ["Decisions get lost"], ["The session that wrote the code", "is the one checking it"]]
    y = 520
    for i, lines in enumerate(items):
        ei = ease((t - 0.9 - i * 0.7) / 0.6)
        c.rrect((90, y + 12, 98, y + 12 + 34 + 52 * (len(lines) - 1)), 4, MUTED, a=ei)
        for j, ln in enumerate(lines):
            c.text((126, y + j * 52), ln, 44, "medium", INK, ei, dy=(1 - ei) * 14)
        y += 70 + 52 * len(lines)
    ef = ease((t - 3.4) / 0.7)
    c.rrect((90, 1004, 98, 1050), 4, OPUS, a=ef)
    c.text((126, 1000), "Brigade fixes the structure.", 46, "demi", INK, ef)


# architecture layout (1x coordinates)
LX0, LX1 = 90, 790
CX = (LX0 + LX1) / 2
NODES = {
    "goal": (140, 220), "decide": (270, 380), "map": (430, 530),
    "plan": (580, 680), "stations": (730, 890), "progress": (940, 1040), "review": (1090, 1200),
}
ARCH_T = {"goal": 0.3, "decide": 1.2, "map": 2.2, "plan": 3.1, "stations": 4.0, "progress": 5.8, "loop": 6.6,
          "review": 7.6, "pulse": 8.8}


ORDER = ["goal", "decide", "map", "plan", "stations", "progress", "review"]


def glow_at(t, key):
    pt = t - ARCH_T["pulse"]
    if pt <= 0:
        return 0.0
    return clamp(1 - abs(pt - 0.35 * ORDER.index(key)) / 0.4)


def node(c, key, title, sub=None, sub_face="mono", t=0.0, highlight=None):
    y0, y1 = NODES[key]
    e = ease((t - ARCH_T[key]) / 0.55)
    if e <= 0:
        return
    dy = (1 - e) * 16
    g = glow_at(t, key)
    ring = mix(INK, 0.25 + 0.75 * g, CARD) if not highlight else highlight
    c.rrect((LX0, y0 + dy, LX1, y1 + dy), 18, CARD, ring if g > 0 else (highlight or RING), e, width=(3 if highlight else 2) + 1.5 * g)
    if sub:
        c.text((LX0 + 34, (y0 + y1) / 2 - 18 + dy), title, 34, "demi", INK, e, "lm", under=CARD)
        c.text((LX0 + 34, (y0 + y1) / 2 + 22 + dy), sub, 24 if sub_face == "mono" else 25, sub_face, INK2, e, "lm", under=CARD)
    else:
        c.text((LX0 + 34, (y0 + y1) / 2 + dy), title, 34, "demi", INK, e, "lm", under=CARD)


def down_arrow(c, frm, to, t, start):
    f = ease_io((t - start) / 0.45)
    if f <= 0:
        return
    y0, y1 = NODES[frm][1] + 6, NODES[to][0] - 6
    ye = y0 + (y1 - y0) * f
    c.line([(CX, y0), (CX, ye)], MUTED, 1, 3)
    if f > 0.9:
        c.arrowhead(CX, y1, "down", MUTED)


def scene_arch(c, t, dur):
    kicker(c, "HOW IT WORKS")
    node(c, "goal", "Your project goal or spec", t=t)
    down_arrow(c, "goal", "decide", t, ARCH_T["decide"] - 0.45)
    node(c, "decide", "Can one session do the whole job?", "Yes: it just does the work.  No: it splits the job.",
         "medium", t=t)
    down_arrow(c, "decide", "map", t, ARCH_T["map"] - 0.45)
    node(c, "map", "Map the project once", ".brigade/context.md", t=t)
    down_arrow(c, "map", "plan", t, ARCH_T["plan"] - 0.45)
    node(c, "plan", "Plan waves by file ownership", ".brigade/plan.md", t=t)
    down_arrow(c, "plan", "stations", t, ARCH_T["stations"] - 0.45)

    # three stations: fresh sessions, one model each
    y0, y1 = NODES["stations"]
    cw = (LX1 - LX0 - 2 * 20) / 3
    stations = [("Opus", OPUS, ["skeleton &", "interfaces"]), ("Sonnet", SONNET, ["a bounded", "module"]),
                ("Haiku", HAIKU, ["a mechanical", "piece"])]
    pulse_t = t - ARCH_T["pulse"]
    for i, (name, col, desc) in enumerate(stations):
        e = ease((t - ARCH_T["stations"] - i * 0.35) / 0.5)
        if e <= 0:
            continue
        x0 = LX0 + i * (cw + 20)
        dy = (1 - e) * 16
        glow = clamp(1 - abs(pulse_t - 0.35 * 4 - i * 0.12) / 0.4) if pulse_t > 0 else 0
        c.rrect((x0, y0 + dy, x0 + cw, y1 + dy), 16, CARD, mix(col, 0.35 + 0.65 * glow, CARD), e, width=2 + 2 * glow)
        c.circle(x0 + 30, y0 + 36 + dy, 9, col, e, under=CARD)
        c.text((x0 + 48, y0 + 36 + dy), name, 30, "demi", INK, e, "lm", under=CARD)
        for j, ln in enumerate(desc):
            c.text((x0 + 22, y0 + 78 + j * 30 + dy), ln, 24, "medium", INK2, e, "lm", under=CARD)
        c.text((x0 + 22, y1 - 24 + dy), "fresh session", 19, "demi", MUTED, e, "lm", under=CARD)

    down_arrow(c, "stations", "progress", t, ARCH_T["progress"] - 0.45)
    node(c, "progress", "Each session logs what it did", ".brigade/progress.md", t=t)

    # loop back: progress -> plan, for the next wave
    f = ease_io((t - ARCH_T["loop"]) / 0.8)
    if f > 0:
        py, ly = sum(NODES["progress"]) / 2, sum(NODES["plan"]) / 2
        pts = [(LX1 + 6, py), (850, py), (850, ly), (LX1 + 8, ly)]
        _, drawn = path_point(pts, f)
        c.line(drawn, OPUS, 1, 3)
        if f > 0.95:
            c.arrowhead(LX1 + 6, ly, "left", OPUS)
        el = ease((t - ARCH_T["loop"] - 0.5) / 0.5)
        c.text((866, (py + ly) / 2 - 34), "next", 26, "demi", INK, el, "lm")
        c.text((866, (py + ly) / 2 + 4), "wave", 26, "demi", INK, el, "lm")
        c.text((866, (py + ly) / 2 + 42), "/brigade next", 17, "mono", INK2, el, "lm")

    down_arrow(c, "progress", "review", t, ARCH_T["review"] - 0.45)
    node(c, "review", "Fresh-context review", "A session that never saw the code. Verdict + fix prompt.",
         "medium", t=t, highlight=OPUS)



def scene_risk(c, t, dur):
    kicker(c, "A MODEL FOR EACH PIECE")
    e = ease(t / 0.7)
    c.text((90, 200), "Chosen by risk,", 62, "bold", INK, e, dy=(1 - e) * 20)
    c.text((90, 278), "not by habit", 62, "bold", INK, e, dy=(1 - e) * 20)
    e2 = ease((t - 0.5) / 0.7)
    c.text((90, 400), "How bad would a mistake be?", 34, "medium", INK2, e2)
    c.text((90, 448), "Would a test catch it right away?", 34, "medium", INK2, e2)
    rows = [("Opus", OPUS, ["Auth, money, data, shared interfaces,", "or mistakes nobody would notice"]),
            ("Sonnet", SONNET, ["Bounded work with a clear spec", "and a test that catches mistakes"]),
            ("Haiku", HAIKU, ["Mechanical, fully specified work", ""])]
    y = 560
    for i, (name, col, desc) in enumerate(rows):
        ei = ease((t - 1.2 - i * 0.5) / 0.55)
        dy = (1 - ei) * 16
        c.rrect((90, y + dy, 990, y + 150 + dy), 18, CARD, RING, ei)
        c.circle(140, y + 75 + dy, 14, col, ei, under=CARD)
        c.text((172, y + 75 + dy), name, 40, "demi", INK, ei, "lm", under=CARD)
        for j, ln in enumerate([d for d in desc if d]):
            yy = y + 75 + dy + (j - (len([d for d in desc if d]) - 1) / 2) * 40
            c.text((380, yy), ln, 28, "medium", INK2, ei, "lm", under=CARD)
        y += 175
    ef = ease((t - 3.2) / 0.6)
    c.text((90, 1135), "Check fails? Rerun it one model up:", 32, "medium", INK, ef)
    x = 90
    for i, (name, col) in enumerate([("Haiku", HAIKU), ("Sonnet", SONNET), ("Opus", OPUS)]):
        c.circle(x + 10, 1206, 9, col, ef)
        c.text((x + 28, 1206), name, 32, "demi", INK, ef, "lm")
        x += 28 + c.width(name, 32, "demi") + 24
        if i < 2:
            c.line([(x + 6, 1208), (x + 34, 1208)], MUTED, ef, 3)
            c.arrowhead(x + 40, 1208, "right", MUTED, ef, 10)
            x += 64


def meter(c, x0, y, wd, n_on, color, track, progress, a):
    """Five discrete segments with 2px surface gaps; filled segments light up one by one."""
    gap, h = 6, 26
    seg = (wd - 4 * gap) / 5
    for i in range(5):
        sx = x0 + i * (seg + gap)
        on = i < n_on and progress * n_on > i
        c.rrect((sx, y, sx + seg, y + h), 6, color if on else track, a=a)


def scene_results(c, t, dur):
    kicker(c, "WHAT I MEASURED")
    e = ease(t / 0.7)
    c.text((90, 200), "Same 5-module build.", 58, "bold", INK, e, dy=(1 - e) * 20)
    c.text((90, 272), "Same brief.", 58, "bold", INK, e, dy=(1 - e) * 20)
    e1 = ease((t - 0.6) / 0.6)
    c.check_icon(112, 418, 20, e1)
    c.text((148, 418), "Both builds passed all 32 hidden tests", 36, "medium", INK, e1, "lm")
    e2 = ease((t - 1.7) / 0.6)
    c.text((90, 540), "But edge cases handled correctly:", 38, "demi", INK, e2)

    rows = [("A normal Claude Code session", 1, MUTED, TRACK_GRAY, 2.3), ("Brigade, after its fresh review", 5, OPUS, TRACK_BLUE, 3.4)]
    y = 640
    for name, n, col, track, start in rows:
        ea = ease((t - start + 0.3) / 0.4)
        c.text((90, y), name, 34, "medium", INK, ea)
        p = clamp((t - start) / (0.25 * n + 0.2))
        meter(c, 90, y + 62, 900, n, col, track, p, ea)
        ef = ease((t - start - 0.25 * n) / 0.4)
        c.text((990, y + 18), f"{n} of 5", 44, "bold", INK, ef, "rm")
        y += 190
    e3 = ease((t - 5.0) / 0.6)
    c.text((90, 1060), "The review caught crashes", 42, "demi", INK, e3)
    c.text((90, 1118), "the tests never touched.", 42, "demi", INK, e3)


def scene_stats(c, t, dur):
    kicker(c, "THE ARCHITECTURE HELD UP")
    stats = [("4 of 4", ["pieces handed to Sonnet passed", "on the first try"]),
             ("5 of 5", ["runs where it said “one session is enough”", "and just did the work"])]
    y = 230
    for i, (big, lines) in enumerate(stats):
        ei = ease((t - 0.2 - i * 1.0) / 0.6)
        c.text((90, y), big, 120, "bold", INK, ei, dy=(1 - ei) * 20)
        for j, ln in enumerate(lines):
            c.text((90, y + 165 + j * 50), ln, 38, "medium", INK2, ei)
        y += 360
    ef = ease((t - 2.4) / 0.7)
    c.rrect((90, 1020, 990, 1180), 18, CARD, RING, ef)
    c.text((122, 1072), "Small sample: 4 tasks, 11 runs.", 30, "medium", INK2, ef, "lm", under=CARD)
    c.text((122, 1124), "Benchmark, hidden tests and raw results are public.", 30, "medium", INK2, ef, "lm", under=CARD)


def scene_cta(c, t, dur):
    e = ease(t / 0.8)
    for i, col in enumerate((OPUS, SONNET, HAIKU)):
        c.circle(540 + (i - 1) * 46, 400, 13, col, ease((t - i * 0.1) / 0.5))
    c.text((540, 530), "Brigade", 130, "bold", INK, e, "mm", dy=(1 - e) * 24)
    e2 = ease((t - 0.5) / 0.7)
    c.text((540, 660), "Open source  ·  any Claude plan", 38, "medium", INK2, e2, "mm")
    c.text((540, 714), "Terminal and VS Code", 38, "medium", INK2, e2, "mm")
    e3 = ease((t - 1.1) / 0.7)
    url = "github.com/rajvardhan19/brigade"
    wd = c.width(url, 34, "mono") + 80
    c.rrect((540 - wd / 2, 820, 540 + wd / 2, 910), 20, CARD, OPUS, e3, width=3)
    c.text((540, 865), url, 34, "mono", INK, e3, "mm", under=CARD)


SCENES = [(scene_title, 4.0), (scene_problem, 5.5), (scene_arch, 12.5), (scene_risk, 6.0),
          (scene_results, 7.5), (scene_stats, 5.0), (scene_cta, 4.5)]
FADE = 0.35
TOTAL = sum(d for _, d in SCENES)


def frame_at(time):
    start = 0.0
    for i, (fn, dur) in enumerate(SCENES):
        if time < start + dur or i == len(SCENES) - 1:
            lt = time - start
            fade_out = clamp((dur - lt) / FADE) if i < len(SCENES) - 1 else 1.0
            c = Canvas(scene_alpha=fade_out)
            fn(c, lt, dur)
            img = c.done()
            # thin progress line along the bottom
            d = ImageDraw.Draw(img)
            d.rectangle([0, H - 6, int(W * time / TOTAL), H], fill=mix(OPUS, 0.8))
            return img
        start += dur


def main():
    args = sys.argv[1:]
    out = pathlib.Path(args[0] if args and not args[0].startswith("--") else "media/brigade-linkedin.mp4")
    if "--frames" in args:
        times = [float(x) for x in args[args.index("--frames") + 1].split(",")]
        for tm in times:
            p = out.parent / f"frame_{tm:05.1f}.png"
            frame_at(tm).save(p)
            print("wrote", p)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    n = int(TOTAL * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                          stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame_at(i / FPS).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", out, f"({TOTAL:.1f}s)")


if __name__ == "__main__":
    main()
