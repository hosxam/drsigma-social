"""DrSigma 2.0 "wild cut" skit finisher (batch 2). Same pipeline as skit.py, 2.0 look and extra edits.

usage: python3 studio/skit.py content/skits/specs/<date>.json [--frames]

Takes the raw AI clip (its own audio is DROPPED: no music ever), and adds:
top captions per beat, optional NPC/SIGMA labels, punch-in zooms, shakes,
flashes, freeze-frames, synthesized sound effects (no music, no bed), and the
DrSigma end card. Output: media/<date>_skit-<NN>_<slug>.mp4 (1080x1920, 30fps).
--frames writes a preview contact sheet to /tmp/skit_preview_<date>.png instead.
"""
import json, sys, os, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from lib import (W, H, FPS, SR, TEAL, WHITE, BG, GREY, font, wrap, sfx as base_sfx,
                 _env, clamp, ease_out, ease_back, shake, flash)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
END_DUR = 2.6


# ---------- extra sound effects (all synthesized, no music) ----------
def sfx(kind):
    rng = np.random.default_rng(len(kind) * 7)
    n_of = lambda s: int(SR * s)
    if kind == "boom":
        n = n_of(1.1); t = np.arange(n) / SR
        f = 70 * np.exp(-t * 4) + 32
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.45)
        return 0.95 * body + 0.25 * rng.standard_normal(n) * _env(n, 0.001, 0.03)
    if kind == "scratch":
        n = n_of(0.45); t = np.arange(n) / SR
        noise = rng.standard_normal(n)
        wob = np.sin(2 * np.pi * (9 + 18 * t) * t)
        car = np.sin(2 * np.pi * np.cumsum(500 + 900 * wob) / SR)
        return 0.35 * (car * 0.6 + noise * 0.4) * _env(n, 0.003, 0.18)
    if kind == "boing":
        n = n_of(0.6); t = np.arange(n) / SR
        f = 380 * np.exp(-t * 2.5) * (1 + 0.25 * np.sin(2 * np.pi * 14 * t)) + 120
        return 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.3)
    if kind == "glitch":
        n = n_of(0.3); out = np.zeros(n)
        for k in range(6):
            s = int(rng.integers(0, n - 2000)); L = int(rng.integers(600, 2000))
            fr = float(rng.choice([220, 440, 880, 1760]))
            tt = np.arange(L) / SR
            out[s:s + L] += 0.25 * np.sign(np.sin(2 * np.pi * fr * tt))
        return out
    if kind == "snore":
        n = n_of(1.4); t = np.arange(n) / SR
        noise = rng.standard_normal(n); y = 0; lp = np.zeros(n)
        for i in range(n):
            y += 0.04 * (noise[i] - y); lp[i] = y
        am = (0.5 + 0.5 * np.sin(2 * np.pi * 38 * t)) * np.sin(np.pi * t / t[-1]) ** 2
        return 2.2 * lp * am
    if kind == "cash":
        a = base_sfx("ding"); b = base_sfx("tick")
        out = np.zeros(len(a) + 4000); out[:len(b)] += b * 1.5; out[3000:3000 + len(a)] += a
        return out
    if kind == "slide":
        n = n_of(0.35); t = np.arange(n) / SR
        f = 300 + 1600 * (t / t[-1])
        return 0.2 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / t[-1])
    return base_sfx(kind)  # pop tick whoosh hit ding buzz riser


def mix(dur, events, path):
    n = int(dur * SR); out = np.zeros(n)
    for t, kind, *g in events:
        s = sfx(kind) * (g[0] if g else 1.0); i = int(t * SR); e = min(n, i + len(s))
        if 0 <= i < n: out[i:e] += s[:e - i]
    out = np.tanh(out * 1.3) * 0.9
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.stack([pcm, pcm], 1).tobytes())
    return path


# ---------- source reader with freeze support ----------
class Source:
    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf",
                                   f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.idx = -1; self.frame = Image.new("RGB", (W, H), BG)

    def get(self, i):
        while self.idx < i:
            buf = self.p.stdout.read(W * H * 3)
            if len(buf) < W * H * 3: break
            self.frame = Image.frombytes("RGB", (W, H), buf); self.idx += 1
        return self.frame


def src_time(t, freezes):
    """map output time -> source time, holding during freeze-frames"""
    held = 0.0
    for fz in sorted(freezes, key=lambda f: f["t"]):
        if t < fz["t"]: break
        held += min(fz["dur"], t - fz["t"])
    return t - held


# ---------- DrSigma 2.0 look ----------
NIGHT = (3, 22, 21); DEEP = (6, 47, 45); CYAN = (0, 202, 199); CYAN_S = (127, 227, 222)
CORAL = (242, 107, 102); GOLD = (231, 194, 106); CREAM = (250, 248, 242); MIST = (169, 189, 185)
COLS = {"gold": GOLD, "coral": CORAL, "cyan": CYAN, "cream": CREAM}
FDIR = os.path.join(ROOT, "assets/fonts")
_fc = {}
def dfont(size, wdth=75, wght=800):
    k = ("d", size, wdth, wght)
    if k not in _fc:
        f = ImageFont.truetype(os.path.join(FDIR, "Bricolage.ttf"), size)
        f.set_variation_by_axes([96, wght, wdth]); _fc[k] = f
    return _fc[k]
def sfont(size):
    k = ("s", size)
    if k not in _fc: _fc[k] = ImageFont.truetype(os.path.join(FDIR, "InstrumentSerif-Italic.ttf"), size)
    return _fc[k]
def mfont(size, wght=500):
    k = ("m", size, wght)
    if k not in _fc:
        f = ImageFont.truetype(os.path.join(FDIR, "JetBrainsMono.ttf"), size); f.set_variation_by_axes([wght]); _fc[k] = f
    return _fc[k]

def tw(d, s, f):
    b = d.textbbox((0, 0), s, font=f); return b[2] - b[0], b[3] - b[1], b[1]

def ecg_points(x0, x1, y, amp, phase=0.0):
    """one ECG-like polyline across [x0,x1]"""
    pts = []; n = 220
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n; u = ((i / n) * 3 + phase) % 1.0
        v = 0.0
        if 0.30 < u < 0.34: v = -0.15 * math.sin((u - 0.30) / 0.04 * math.pi)
        elif 0.40 < u < 0.42: v = 0.25
        elif 0.42 < u < 0.45: v = -1.0 + (u - 0.42) / 0.03 * 0.0
        elif 0.45 < u < 0.48: v = 0.45
        elif 0.58 < u < 0.68: v = -0.25 * math.sin((u - 0.58) / 0.10 * math.pi)
        pts.append((x, y + v * amp))
    return pts

def glow_line(im, pts, col, width=6, glow=18, alpha=255):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.line(pts, fill=col + (int(alpha * 0.45),), width=glow, joint="curve")
    lay = lay.filter(ImageFilter.GaussianBlur(glow / 2))
    d = ImageDraw.Draw(lay); d.line(pts, fill=col + (alpha,), width=width, joint="curve")
    im.alpha_composite(lay); return im

def caption_layer(text, k):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = dfont(78); lines = wrap(d, text.upper(), f, 900)[:3]
    lh = 80; bh = lh * len(lines) + 70
    widths = [tw(d, l, f)[0] for l in lines]
    bw = max(widths) + 84; x0 = (W - bw) / 2; y0 = 170
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 22, fill=NIGHT + (236,), outline=CYAN + (150,), width=3)
    tag = "● DRSIGMA 2.0"; mf = mfont(24, 600)
    d.text((x0 + 26, y0 + 14), tag, font=mf, fill=CYAN)
    for j, l in enumerate(lines):
        d.text(((W - widths[j]) / 2, y0 + 48 + j * lh), l, font=f, fill=CREAM)
    s = 0.55 + 0.45 * ease_back(clamp(k))
    if abs(s - 1) > 1e-3:
        part = im.crop((int(x0), y0, int(x0 + bw), int(y0 + bh)))
        pw, ph = max(1, int(part.width * s)), max(1, int(part.height * s))
        part = part.resize((pw, ph), Image.BILINEAR)
        cx, cy = W / 2, y0 + bh / 2
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.paste(part, (int(cx - pw / 2), int(cy - ph / 2)), part)
    return im

def label_layer(labels):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for lab, xf in labels:
        sig = "SIGMA" in lab.upper(); col = CYAN if sig else CORAL
        fl = mfont(44, 700); w, h, _ = tw(d, lab, fl); x = W * xf
        d.rounded_rectangle((x - w / 2 - 28, 1622, x + w / 2 + 28, 1706), 42, fill=NIGHT + (225,), outline=col + (255,), width=3)
        d.text((x - w / 2, 1640), lab, font=fl, fill=col)
    return im

# ----- fx layers -----
def stamp_layer(e, t):
    dt = t - e["t"]; dur = e.get("dur", 1.3)
    if dt < 0 or dt > dur: return None
    col = COLS.get(e.get("color", "gold"), GOLD)
    f = dfont(150, 75, 800); tmp = Image.new("RGBA", (W, 400), (0, 0, 0, 0)); d = ImageDraw.Draw(tmp)
    txt = e["text"].upper(); w, h, oy = tw(d, txt, f)
    if w > 960: f = dfont(int(150 * 960 / w)); w, h, oy = tw(d, txt, f)
    pad = 34; bx = (W - w) / 2 - pad; by = 200 - h / 2 - pad
    d.rounded_rectangle((bx + 12, by + 14, bx + w + 2 * pad + 12, by + h + 2 * pad + 14), 26, fill=(0, 0, 0, 150))
    d.rounded_rectangle((bx, by, bx + w + 2 * pad, by + h + 2 * pad), 26, fill=col + (255,), outline=NIGHT + (255,), width=8)
    d.text(((W - w) / 2, 200 - h / 2 - oy), txt, font=f, fill=NIGHT)
    k = ease_back(clamp(dt / 0.22), 2.2); s = 2.2 - 1.2 * k
    a = 1.0 if dt < dur - 0.2 else clamp((dur - dt) / 0.2)
    rot = e.get("rot", -7)
    tmp = tmp.rotate(rot, resample=Image.BICUBIC, expand=False)
    sw, sh = int(W * s), int(400 * s); tmp = tmp.resize((sw, sh), Image.BILINEAR)
    if a < 1: tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * a)))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0)); out.paste(tmp, ((W - sw) // 2, int(e.get("y", 900) - sh / 2)), tmp)
    return out

def xp_layer(e, t):
    dt = t - e["t"]
    if dt < 0 or dt > 1.6: return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    # bar
    bx0, by0, bx1 = 140, 1560, W - 140
    fill = 0.35 + 0.55 * ease_out(clamp(dt / 0.9))
    d.rounded_rectangle((bx0, by0, bx1, by0 + 22), 11, fill=NIGHT + (220,), outline=CYAN + (180,), width=2)
    d.rounded_rectangle((bx0 + 4, by0 + 4, bx0 + 4 + (bx1 - bx0 - 8) * fill, by0 + 18), 7, fill=CYAN + (255,))
    d.text((bx0, by0 - 40), "RANK · INTERN", font=mfont(26, 600), fill=CYAN_S)
    a = 1 - clamp((dt - 1.1) / 0.5)
    f = dfont(130); txt = e.get("text", "+10 XP"); w, h, oy = tw(d, txt, f)
    y = 820 - 220 * ease_out(clamp(dt / 1.2))
    d.text(((W - w) / 2 + 6, y + 6), txt, font=f, fill=(0, 0, 0, int(160 * a)))
    d.text(((W - w) / 2, y), txt, font=f, fill=GOLD + (int(255 * a),))
    return im

def combo_layer(e, t):
    dt = t - e["t"]
    if dt < 0 or dt > 1.8: return None
    n = e.get("n", 5); cur = max(1, int(round(1 + (n - 1) * ease_out(clamp(dt / 0.8)))))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    a = 1 - clamp((dt - 1.4) / 0.4)
    f = dfont(120); txt = f"x{cur}"; w, h, oy = tw(d, txt, f)
    x = W - 90 - w; y = 1240
    pulse = 1 + 0.12 * math.sin(dt * 30) * (1 - clamp(dt / 0.8))
    d.text((x + 5, y + 5), txt, font=f, fill=(0, 0, 0, int(150 * a)))
    d.text((x, y), txt, font=f, fill=GOLD + (int(255 * a),))
    d.text((x, y + 128), "COMBO", font=mfont(40, 800), fill=CREAM + (int(255 * a),))
    return im

def hp_layer(e, t):
    t0, t1 = e["t0"], e["t1"]
    if t < t0 or t > t1 + 0.6: return None
    u = clamp((t - t0) / (t1 - t0)); hp = 1 - (0.12 * clamp(u / 0.5) + 0.88 * clamp((u - 0.62) / 0.38) ** 0.7)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    bx0, by0, bx1 = 110, 112, W - 110
    d.text((bx0, by0 - 44), e.get("label", "BOSS"), font=mfont(32, 800), fill=CORAL)
    d.text((bx1 - 160, by0 - 44), f"{int(hp * 100):>3d}%", font=mfont(32, 800), fill=CREAM)
    d.rounded_rectangle((bx0, by0, bx1, by0 + 30), 8, fill=NIGHT + (230,), outline=CREAM + (200,), width=3)
    if hp > 0.005:
        d.rounded_rectangle((bx0 + 5, by0 + 5, bx0 + 5 + (bx1 - bx0 - 10) * hp, by0 + 25), 5, fill=CORAL + (255,))
    return im

def speed_layer(e, t):
    dt = t - e["t"]
    if dt < 0 or dt > e.get("dur", 2): return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rng = np.random.default_rng(int(t * 30)); cx, cy = W / 2, H / 2
    for _ in range(46):
        ang = rng.uniform(0, 2 * math.pi); r0 = rng.uniform(520, 700); r1 = r0 + rng.uniform(260, 700)
        wdt = int(rng.uniform(3, 10))
        d.line((cx + r0 * math.cos(ang), cy + r0 * 1.6 * math.sin(ang), cx + r1 * math.cos(ang), cy + r1 * 1.6 * math.sin(ang)),
               fill=CREAM + (int(rng.uniform(70, 170)),), width=wdt)
    return im

def ecg_layer(e, t):
    dt = t - e["t"]; dur = e.get("dur", 0.6)
    if dt < 0 or dt > dur + 0.35: return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    u = clamp(dt / dur); x1 = -40 + (W + 80) * ease_out(u)
    pts = [p for p in ecg_points(-40, W + 40, e.get("y", 960), 260) if p[0] <= x1]
    a = 1 - clamp((dt - dur) / 0.35)
    if len(pts) > 1: glow_line(im, pts, CYAN, 9, 34, int(255 * a))
    if u < 1 and pts:
        d = ImageDraw.Draw(im); x, y = pts[-1]; d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=CREAM + (255,))
    return im

def glitch(frame, t, e):
    dt = t - e["t"]
    if dt < 0 or dt > e.get("dur", 0.5): return frame
    a = np.asarray(frame).copy(); rng = np.random.default_rng(int(t * 60))
    off = int(rng.integers(12, 34))
    a[..., 0] = np.roll(a[..., 0], off, axis=1); a[..., 2] = np.roll(a[..., 2], -off, axis=1)
    for _ in range(7):
        y = int(rng.integers(0, H - 80)); h = int(rng.integers(12, 90)); s = int(rng.integers(-120, 120))
        a[y:y + h] = np.roll(a[y:y + h], s, axis=1)
    return Image.fromarray(a)

def whip(frame, t, e):
    dt = t - e["t"] + 0.12
    if dt < 0 or dt > 0.3: return frame
    k = math.sin(math.pi * dt / 0.3)
    out = frame; acc = None
    for i in range(5):
        s = 1 + 0.07 * i * k
        z = zoom_c(frame, s)
        acc = z if acc is None else Image.blend(acc, z, 1 / (i + 1))
    return Image.blend(frame, acc, 0.85 * k)

_logo = None
def end_card(t, lines, cta):
    global _logo
    if _logo is None:
        _logo = Image.open(os.path.join(ROOT, "assets/logo-m.webp")).convert("RGBA")
    im = Image.new("RGBA", (W, H), NIGHT + (255,)); d = ImageDraw.Draw(im)
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sl)
    for y in range(0, H, 6): ds.line((0, y, W, y), fill=(250, 248, 242, 7))
    im.alpha_composite(sl); d = ImageDraw.Draw(im)
    # ECG sweep
    u = clamp(t / 1.1); pts = [p for p in ecg_points(-20, W + 20, 1500, 120, phase=0.2) if p[0] <= -20 + (W + 40) * u]
    if len(pts) > 1: glow_line(im, pts, CYAN, 6, 26, 200)
    k = ease_back(clamp(t / 0.35)); lw = max(1, int(280 * k)); lh = max(1, int(lw * _logo.height / _logo.width))
    lg = _logo.resize((lw, lh)); im.alpha_composite(lg, ((W - lw) // 2, 520 - lh // 2))
    y = 820
    for j, line in enumerate(lines):
        a = clamp((t - 0.25 - 0.22 * j) / 0.2)
        if a <= 0: continue
        last = j == len(lines) - 1 and len(lines) > 1
        f = sfont(104) if last else dfont(104)
        txt = line if last else line.upper()
        for l in wrap(d, txt, f, 960):
            w, h, oy = tw(d, l, f)
            d.text(((W - w) / 2, y), l, font=f, fill=(CYAN_S if last else CREAM) + (int(255 * a),)); y += 108
        y += 14
    if t > 0.9:
        for i, c in enumerate(cta.split("|")):
            c = c.strip(); f = mfont(40 if i == 0 else 32, 700 if i == 0 else 500)
            w, h, oy = tw(d, c.upper(), f); d.text(((W - w) / 2, y + 70 + i * 62), c.upper(), font=f, fill=CYAN if i == 0 else MIST)
    return im.convert("RGB")


def punch_scale(t, fx):
    s = 1.0
    for e in fx:
        if e["kind"] != "punch": continue
        dt = t - e["t"]; dur = e.get("dur", 0.8); amt = e.get("amt", 0.16)
        if 0 <= dt < dur + 0.25:
            if dt < 0.1: s = max(s, 1 + amt * ease_out(dt / 0.1))
            elif dt < dur: s = max(s, 1 + amt)
            else: s = max(s, 1 + amt * (1 - ease_out((dt - dur) / 0.25)))
    return s


def zoom_c(img, s, cy=0.5):
    if s <= 1.0001: return img
    w, h = int(W / s), int(H / s); x = (W - w) // 2; y = int((H - h) * cy)
    return img.crop((x, y, x + w, y + h)).resize((W, H), Image.BILINEAR)


def build(spec):
    clip = os.path.join(ROOT, spec["raw"])
    base = float(spec.get("duration", 10))
    fx = spec.get("fx", [])
    freezes = [e for e in fx if e["kind"] == "freeze"]
    main = base + sum(f["dur"] for f in freezes)
    total = main + END_DUR
    beats = sorted(spec["beats"], key=lambda b: b["t"])
    labels = label_layer(spec.get("labels", [])) if spec.get("labels") else None
    cap_cache = {}
    src = Source(clip)

    def draw(t):
        if t >= main:
            return end_card(t - main, spec["end"], spec.get("cta", "drsigma.net | 7 days of everything · no card"))
        st = src_time(t, freezes)
        frame = src.get(min(int(st * FPS), int(base * FPS) - 1)).copy()
        frozen = any(f["t"] <= t < f["t"] + f["dur"] for f in freezes)
        if frozen:  # freeze-frame look: slight desat + zoom
            frame = Image.blend(frame, frame.convert("L").convert("RGB"), 0.5)
        frame = zoom_c(frame, punch_scale(t, fx) * (1.06 if frozen else 1.0))
        for e in fx:
            if e["kind"] == "shake": frame = shake(frame, t, e["t"], e.get("amp", 18), e.get("dur", 0.3))
            if e["kind"] == "flash": frame = flash(frame, t, e["t"], e.get("dur", 0.18))
            if e["kind"] == "glitch": frame = glitch(frame, t, e)
            if e["kind"] == "whip": frame = whip(frame, t, e)
        frame = frame.convert("RGBA")
        for e in fx:
            fn = {"speed": speed_layer, "ecg": ecg_layer, "hp": hp_layer, "xp": xp_layer, "combo": combo_layer, "stamp": stamp_layer}.get(e["kind"])
            if fn:
                lay = fn(e, t)
                if lay is not None: frame.alpha_composite(lay)
        if labels: frame.alpha_composite(labels)
        cur = None
        for b in beats:
            if b["t"] <= t: cur = b
        if cur and cur.get("text"):
            k = min(1.0, (t - cur["t"]) / 0.22)
            key = (cur["text"], round(k, 2) if k < 1 else 1)
            if key not in cap_cache: cap_cache[key] = caption_layer(cur["text"], k)
            frame.alpha_composite(cap_cache[key])
        for f in freezes:
            if f["t"] <= t < f["t"] + f["dur"] and f.get("text"):
                lay = stamp_layer({"t": f["t"], "dur": f["dur"], "text": f["text"], "color": f.get("color", "coral"), "rot": 0}, t)
                if lay is not None: frame.alpha_composite(lay)
        return frame.convert("RGB")

    # sound: spec events + automatic ones
    ev = [tuple(e) for e in spec.get("sfx", [])]
    for b in beats[1:]: ev.append((b["t"] - 0.05, "whoosh", 0.7))
    ev.append((beats[0]["t"], "pop", 0.8))
    for e in fx:
        if e["kind"] == "punch": ev.append((e["t"], "hit", 0.8))
        if e["kind"] == "freeze": ev.append((e["t"], "scratch", 1.0))
        if e["kind"] == "glitch": ev.append((e["t"], "glitch", 0.9))
        if e["kind"] == "whip": ev.append((e["t"] - 0.12, "whoosh", 1.0))
        if e["kind"] == "stamp": ev.append((e["t"], {"gold": "cash", "coral": "buzz"}.get(e.get("color"), "hit"), 0.9)); ev.append((e["t"], "hit", 0.6))
        if e["kind"] == "xp": ev.append((e["t"], "ding", 0.8))
        if e["kind"] == "combo":
            for i in range(6): ev.append((e["t"] + i * 0.13, "tick", 0.7))
        if e["kind"] == "ecg": ev.append((e["t"], "riser", 0.5)); ev.append((e["t"] + 0.45, "pop", 0.7))
        if e["kind"] == "speed": ev.append((e["t"], "whoosh", 0.8))
        if e["kind"] == "hp": ev.append((e["t1"] - 0.2, "boom", 0.8))
    ev += [(main - 0.6, "riser", 0.8), (main, "boom", 0.9), (main + 0.3, "pop"), (main + 0.95, "ding", 0.7)]
    return draw, total, ev


def main():
    spec_path = sys.argv[1]; spec = json.load(open(spec_path))
    draw, total, ev = build(spec)
    if "--frames" in sys.argv:
        ts = [b["t"] + 0.5 for b in spec["beats"]] + [e.get("t", e.get("t0", 0)) + 0.3 for e in spec.get("fx", []) if e["kind"] in ("freeze", "stamp", "combo", "xp", "ecg", "hp", "glitch", "speed")]
        ts = sorted(set(round(x, 2) for x in ts)) + [total - 0.3]
        # need sequential reads: rebuild per frame in order
        thumbs = []
        for t in ts:
            thumbs.append(draw(t).resize((360, 640)))
        cols = min(6, len(thumbs)); rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (360 * cols, 640 * rows))
        for i, th in enumerate(thumbs): sheet.paste(th, (360 * (i % cols), 640 * (i // cols)))
        out = f"/tmp/skit_preview_{spec['date']}.png"; sheet.save(out); print(out); return
    os.makedirs(os.path.join(ROOT, "media"), exist_ok=True)
    out = os.path.join(ROOT, "media", f"{spec['date']}_skit-{spec['n']:02d}_{spec['slug']}.mp4")
    vtmp = out[:-4] + ".v.mp4"; wav = out[:-4] + ".wav"
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                          "-pix_fmt", "yuv420p", vtmp], stdin=subprocess.PIPE)
    for i in range(int(total * FPS)):
        p.stdin.write(draw(i / FPS).tobytes())
    p.stdin.close(); assert p.wait() == 0
    mix(total, ev, wav)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", vtmp, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    assert r.returncode == 0
    os.remove(vtmp); os.remove(wav); print(out)


if __name__ == "__main__":
    main()
