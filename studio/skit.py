"""Finish a Higgsfield skit clip into a DrSigma reel.

usage: python3 studio/skit.py content/skits/specs/<date>.json [--frames]

Takes the raw AI clip (its own audio is DROPPED: no music ever), and adds:
top captions per beat, optional NPC/SIGMA labels, punch-in zooms, shakes,
flashes, freeze-frames, synthesized sound effects (no music, no bed), and the
DrSigma end card. Output: media/<date>_skit-<NN>_<slug>.mp4 (1080x1920, 30fps).
--frames writes a preview contact sheet to /tmp/skit_preview_<date>.png instead.
"""
import json, sys, os, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw

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


# ---------- drawing ----------
def caption_layer(text, k):
    """k: 0..1 pop-in progress"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = font(62); lines = wrap(d, text, f, 920)[:2]
    lh = 76; bh = lh * len(lines) + 44
    widths = [d.textbbox((0, 0), l, font=f)[2] for l in lines]
    bw = max(widths) + 72; x0 = (W - bw) / 2; y0 = 150
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 30, fill=(9, 11, 12, 230))
    for j, l in enumerate(lines):
        d.text(((W - widths[j]) / 2, y0 + 20 + j * lh), l, font=f, fill=WHITE)
    s = 0.6 + 0.4 * ease_back(clamp(k))
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
        col = TEAL if "SIGMA" in lab.upper() else (205, 210, 209)
        fl = font(52); b = d.textbbox((0, 0), lab, font=fl); lw = b[2] - b[0]; x = W * xf
        d.rounded_rectangle((x - lw / 2 - 30, 1620, x + lw / 2 + 30, 1708), 24, fill=(9, 11, 12, 225))
        d.text((x - lw / 2, 1632), lab, font=fl, fill=col)
    return im


_logo = None
def end_card(t, lines, cta):
    global _logo
    if _logo is None:
        lg = Image.open(os.path.join(ROOT, "assets/logo.jpg")).convert("RGB"); lg.thumbnail((340, 340)); _logo = lg
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    k = ease_back(clamp(t / 0.35)); lw = max(1, int(_logo.width * k))
    lg = _logo.resize((lw, lw)); im.paste(lg, ((W - lw) // 2, 640 - lw // 2))
    y = 920
    for j, line in enumerate(lines):
        a = clamp((t - 0.25 - 0.2 * j) / 0.2)
        if a <= 0: continue
        col = TEAL if j == len(lines) - 1 and len(lines) > 1 else WHITE
        for l in wrap(d, line, font(68), 960):
            b = d.textbbox((0, 0), l, font=font(68)); d.text(((W - b[2]) / 2, y), l, font=font(68), fill=col); y += 84
        y += 10
    if t > 0.9:
        b = d.textbbox((0, 0), cta, font=font(46, "Bold")); d.text(((W - b[2]) / 2, y + 90), cta, font=font(46, "Bold"), fill=GREY)
    return im


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
            return end_card(t - main, spec["end"], spec.get("cta", "10 free pages: drsigma.net/try"))
        st = src_time(t, freezes)
        frame = src.get(min(int(st * FPS), int(base * FPS) - 1)).copy()
        frozen = any(f["t"] <= t < f["t"] + f["dur"] for f in freezes)
        if frozen:  # freeze-frame look: slight desat + zoom
            frame = Image.blend(frame, frame.convert("L").convert("RGB"), 0.5)
        frame = zoom_c(frame, punch_scale(t, fx) * (1.06 if frozen else 1.0))
        for e in fx:
            if e["kind"] == "shake": frame = shake(frame, t, e["t"], e.get("amp", 18), e.get("dur", 0.3))
            if e["kind"] == "flash": frame = flash(frame, t, e["t"], e.get("dur", 0.18))
        frame = frame.convert("RGBA")
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
                d = ImageDraw.Draw(frame); fl = font(84); b = d.textbbox((0, 0), f["text"], font=fl)
                d.rounded_rectangle(((W - b[2]) / 2 - 30, 880, (W + b[2]) / 2 + 30, 990), 26, fill=(4, 211, 185, 240))
                d.text(((W - b[2]) / 2, 888), f["text"], font=fl, fill=BG)
        return frame.convert("RGB")

    # sound: spec events + automatic ones
    ev = [tuple(e) for e in spec.get("sfx", [])]
    for b in beats[1:]: ev.append((b["t"] - 0.05, "whoosh", 0.7))
    ev.append((beats[0]["t"], "pop", 0.8))
    for e in fx:
        if e["kind"] == "punch": ev.append((e["t"], "hit", 0.8))
        if e["kind"] == "freeze": ev.append((e["t"], "scratch", 1.0))
    ev += [(main - 0.6, "riser", 0.8), (main, "boom", 0.9), (main + 0.3, "pop"), (main + 0.95, "ding", 0.7)]
    return draw, total, ev


def main():
    spec_path = sys.argv[1]; spec = json.load(open(spec_path))
    draw, total, ev = build(spec)
    if "--frames" in sys.argv:
        ts = [b["t"] + 0.5 for b in spec["beats"]] + [e["t"] + 0.15 for e in spec.get("fx", []) if e["kind"] == "freeze"]
        ts = sorted(set(round(x, 2) for x in ts)) + [total - 0.3]
        # need sequential reads: rebuild per frame in order
        thumbs = []
        for t in ts:
            thumbs.append(draw(t).resize((360, 640)))
        sheet = Image.new("RGB", (360 * len(thumbs), 640))
        for i, th in enumerate(thumbs): sheet.paste(th, (360 * i, 0))
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
