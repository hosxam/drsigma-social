"""DrSigma reel studio: shared drawing, animation and audio helpers."""
import math, subprocess, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
TEAL = (4, 211, 185)
TEAL_D = (5, 92, 80)
BG = (9, 11, 12)
WHITE = (245, 247, 246)
GREY = (150, 160, 158)
RED = (255, 86, 86)
CARD = (22, 27, 29)
FD = "/usr/share/fonts/opentype/inter/"

_fc = {}
def font(size, w="Black"):
    k = (size, w)
    if k not in _fc:
        name = {"Black": "InterDisplay-Black.otf", "XB": "InterDisplay-ExtraBold.otf",
                "Bold": "InterDisplay-Bold.otf", "Semi": "Inter-SemiBold.otf",
                "Med": "InterDisplay-Medium.otf"}[w]
        _fc[k] = ImageFont.truetype(FD + name, size)
    return _fc[k]

# ---------- easing ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, start, dur): return clamp((t - start) / dur)
def ease_out(x): return 1 - (1 - x) ** 3
def ease_back(x, s=1.7):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1
def ease_in_out(x): return 3 * x * x - 2 * x * x * x

# ---------- background ----------
_bg_cache = {}
def background(t, accent=TEAL):
    key = accent
    if key not in _bg_cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        base = np.zeros((H, W, 3), np.float32)
        base[:] = BG
        # vertical subtle gradient
        base *= (1.0 - 0.25 * (yy / H))[..., None]
        # grid
        grid = ((xx % 90 < 1.5) | (yy % 90 < 1.5)).astype(np.float32) * 7
        base += grid[..., None]
        _bg_cache[key] = (base, xx, yy)
    base, xx, yy = _bg_cache[key]
    # moving glow blobs (computed at quarter res for speed)
    cx1 = W * (0.25 + 0.15 * math.sin(t * 0.6)); cy1 = H * (0.22 + 0.05 * math.cos(t * 0.5))
    cx2 = W * (0.8 + 0.1 * math.cos(t * 0.4)); cy2 = H * (0.78 + 0.05 * math.sin(t * 0.7))
    sx, sy = xx[::4, ::4], yy[::4, ::4]
    g = np.exp(-((sx - cx1) ** 2 + (sy - cy1) ** 2) / (2 * 380 ** 2)) * 0.55 + \
        np.exp(-((sx - cx2) ** 2 + (sy - cy2) ** 2) / (2 * 420 ** 2)) * 0.35
    g = np.repeat(np.repeat(g, 4, 0), 4, 1)[:H, :W]
    img = base + g[..., None] * np.array(accent, np.float32)[None, None] * 0.28
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

# ---------- logo ----------
_logo = None
def logo(size):
    global _logo
    if _logo is None:
        im = Image.open(os.path.join(os.path.dirname(__file__), "..", "assets", "logo.jpg")).convert("RGB")
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).ellipse((6, 6, im.size[0] - 6, im.size[1] - 6), fill=255)
        im.putalpha(m)
        _logo = im
    return _logo.resize((size, size), Image.LANCZOS)

def header(img, tag, t=1.0):
    """top brand bar: logo + handle, series tag pill"""
    d = ImageDraw.Draw(img)
    a = ease_out(prog(t, 0, 0.4))
    y = int(110 - 40 * (1 - a))
    img.paste(logo(78), (70, y), logo(78))
    d.text((165, y + 10), "DrSigma", font=font(34, "Black"), fill=WHITE)
    d.text((165, y + 48), "@drsigma.emree", font=font(24, "Semi"), fill=GREY)
    if tag:
        f = font(30, "XB")
        tw = d.textlength(tag, font=f)
        x2 = W - 70; x1 = x2 - tw - 52
        d.rounded_rectangle((x1, y + 14, x2, y + 66), 26, fill=TEAL)
        d.text((x1 + 26, y + 22), tag, font=f, fill=BG)

# ---------- text ----------
def wrap(d, text, f, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            test = (cur + " " + w).strip()
            if d.textlength(test, font=f) <= maxw: cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        lines.append(cur)
    return lines

def text_block(img, text, y, size, weight="Black", fill=WHITE, maxw=920, align="center",
               lh=1.12, hl=None, x=None, alpha=1.0, scale=1.0, anchor_cy=False):
    """draw wrapped text. hl: dict word->color for highlights. returns bottom y"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(size, weight)
    lines = wrap(d, text, f, maxw)
    lhpx = int(size * lh)
    total = lhpx * len(lines)
    if anchor_cy: y = y - total // 2
    for i, ln in enumerate(lines):
        lw = d.textlength(ln, font=f)
        lx = (W - lw) / 2 if align == "center" else (x if x is not None else 80)
        ly = y + i * lhpx
        if hl:
            cx = lx
            for wd in ln.split(" "):
                col = hl.get(wd.strip(".,?!:"), fill)
                d.text((cx, ly), wd, font=f, fill=col)
                cx += d.textlength(wd + " ", font=f)
        else:
            d.text((lx, ly), ln, font=f, fill=fill)
    if alpha <= 0:
        return y + total
    if scale != 1.0 or alpha < 1.0:
        cy = y + total / 2
        if scale != 1.0:
            sw, sh = int(W * scale), int(H * scale)
            big = layer.resize((sw, sh), Image.BICUBIC)
            nl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ox = int((W - sw) / 2); oy = int(cy - cy * scale)
            nl.paste(big, (ox, oy))
            layer = nl
        if alpha < 1.0:
            r, g, b, a = layer.split()
            a = a.point(lambda v: int(v * alpha))
            layer = Image.merge("RGBA", (r, g, b, a))
    img.paste(layer, (0, 0), layer)
    return y + total

def pop(t, start, dur=0.35):
    p = prog(t, start, dur)
    if p <= 0: return 0.0, 0.0
    return min(1.0, p * 2.5), 0.6 + 0.4 * ease_back(p)

# ---------- cards ----------
def option_card(img, y, letter, text, state="idle", appear=1.0, h=128, fade=1.0):
    """state: idle / correct / wrong"""
    if appear <= 0: return
    a = ease_out(appear)
    x_off = int((1 - a) * 260)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x1, x2 = 70 + x_off, W - 70 + x_off
    if state == "correct":
        d.rounded_rectangle((x1 - 6, y - 6, x2 + 6, y + h + 6), 30, fill=TEAL + (90,))
        d.rounded_rectangle((x1, y, x2, y + h), 26, fill=(10, 60, 54, 255), outline=TEAL, width=5)
        lc, tc, bc = BG, WHITE, TEAL
    elif state == "wrong":
        d.rounded_rectangle((x1, y, x2, y + h), 26, fill=(16, 19, 20, 255), outline=(40, 44, 46), width=3)
        lc, tc, bc = (90, 95, 95), (95, 100, 100), (40, 44, 46)
    else:
        d.rounded_rectangle((x1, y, x2, y + h), 26, fill=CARD + (255,), outline=(52, 60, 62), width=3)
        lc, tc, bc = BG, WHITE, WHITE
    d.ellipse((x1 + 24, y + h / 2 - 38, x1 + 100, y + h / 2 + 38), fill=bc)
    lf = font(44, "Black")
    lw = d.textlength(letter, font=lf)
    d.text((x1 + 62 - lw / 2, y + h / 2 - 28), letter, font=lf, fill=lc)
    f = font(48, "Bold")
    lines = wrap(d, text, f, x2 - x1 - 150 - (70 if state == "correct" else 0))
    if len(lines) > 1:
        f = font(42, "Bold"); lines = wrap(d, text, f, x2 - x1 - 150 - (70 if state == "correct" else 0))
    lh = 50 if len(lines) > 1 else 56
    ty = y + h / 2 - len(lines) * lh / 2 - 4
    for i, ln in enumerate(lines):
        d.text((x1 + 128, ty + i * lh), ln, font=f, fill=tc)
    if state == "correct":
        d.text((x2 - 82, y + h / 2 - 38), "✓", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64), fill=TEAL)
    a = a * fade
    if a <= 0: return
    if a < 1:
        r, g, b, al = layer.split(); al = al.point(lambda v: int(v * a)); layer = Image.merge("RGBA", (r, g, b, al))
    img.paste(layer, (0, 0), layer)

def timer_ring(img, cx, cy, r, frac, label):
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(45, 52, 54), width=12)
    if frac > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * frac, fill=TEAL if frac > 0.3 else RED, width=12)
    f = font(int(r * 0.95), "Black")
    lw = d.textlength(label, font=f)
    d.text((cx - lw / 2, cy - r * 0.62), label, font=f, fill=WHITE)

def pill(img, text, cy, fill=TEAL, tc=BG, size=34, alpha=1.0, scale=1.0):
    if alpha <= 0 or scale <= 0: return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    f = font(int(size * scale), "Black")
    tw = d.textlength(text, font=f); ph = int(size * scale * 1.9)
    x1 = (W - tw) / 2 - 34 * scale
    d.rounded_rectangle((x1, cy - ph / 2, W - x1, cy + ph / 2), ph / 2, fill=fill + (int(255 * alpha),))
    d.text(((W - tw) / 2, cy - size * scale * 0.62), text, font=f, fill=tc + (int(255 * alpha),))
    img.paste(layer, (0, 0), layer)

def shake(img, t, start, amp=14, dur=0.25):
    p = prog(t, start, dur)
    if p <= 0 or p >= 1: return img
    k = (1 - p) * amp
    dx = int(math.sin(t * 90) * k); dy = int(math.cos(t * 77) * k)
    out = Image.new("RGB", (W, H), BG); out.paste(img, (dx, dy)); return out

def zoom(img, s):
    if abs(s - 1) < 1e-3: return img
    sw, sh = int(W * s), int(H * s)
    big = img.resize((sw, sh), Image.BICUBIC)
    return big.crop(((sw - W) // 2, (sh - H) // 2, (sw - W) // 2 + W, (sh - H) // 2 + H))

def flash(img, t, start, dur=0.18, color=(255, 255, 255), strength=0.55):
    p = prog(t, start, dur)
    if p <= 0 or p >= 1: return img
    return Image.blend(img, Image.new("RGB", (W, H), color), strength * (1 - p))

# ---------- audio ----------
SR = 44100
def _env(n, a=0.005, r=0.1):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)

def sfx(kind):
    rng = np.random.default_rng(len(kind))
    if kind == "pop":
        n = int(SR * 0.12); t = np.arange(n) / SR
        f = 900 * np.exp(-t * 18) + 300
        return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.04)
    if kind == "tick":
        n = int(SR * 0.05); t = np.arange(n) / SR
        return 0.35 * np.sin(2 * np.pi * 2400 * t) * _env(n, 0.0005, 0.008)
    if kind == "whoosh":
        n = int(SR * 0.45); noise = rng.standard_normal(n)
        t = np.arange(n) / SR
        out = np.zeros(n); y = 0
        for i in range(n):  # one-pole lowpass with sweeping cutoff
            c = 0.02 + 0.25 * math.sin(math.pi * i / n)
            y += c * (noise[i] - y); out[i] = y
        return 0.9 * out * np.sin(np.pi * t / t[-1]) ** 2
    if kind == "hit":
        n = int(SR * 0.6); t = np.arange(n) / SR
        f = 120 * np.exp(-t * 9) + 45
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.25)
        click = rng.standard_normal(n) * _env(n, 0.0005, 0.01) * 0.4
        return 0.9 * body + click
    if kind == "ding":
        n = int(SR * 1.2); t = np.arange(n) / SR
        a = np.sin(2 * np.pi * 1318.5 * t) * _env(n, 0.002, 0.35)
        b = np.zeros(n); k = int(0.11 * SR)
        b[k:] = np.sin(2 * np.pi * 1760 * t[:n - k]) * _env(n - k, 0.002, 0.45)
        return 0.32 * (a + b) + 0.08 * np.sin(2 * np.pi * 2637 * t) * _env(n, 0.002, 0.2)
    if kind == "buzz":
        n = int(SR * 0.35); t = np.arange(n) / SR
        return 0.25 * np.sign(np.sin(2 * np.pi * 110 * t)) * _env(n, 0.003, 0.15)
    if kind == "riser":
        n = int(SR * 1.0); t = np.arange(n) / SR
        f = 200 + 1400 * (t / t[-1]) ** 2
        return 0.12 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / t[-1]) ** 2
    raise ValueError(kind)

def bed(dur, bpm=96):
    """quiet pulse bed so the reel isn't silent; users can swap trending audio in-app"""
    n = int(dur * SR); out = np.zeros(n); beat = 60 / bpm
    kick = sfx("hit") * 0.35; hat = sfx("tick") * 0.25
    t = 0.0
    i = 0
    while t < dur:
        s = int(t * SR)
        src = kick if i % 2 == 0 else hat
        e = min(n, s + len(src)); out[s:e] += src[:e - s]
        t += beat / 2; i += 1
    # soft pad
    tt = np.arange(n) / SR
    pad = 0.035 * (np.sin(2 * np.pi * 110 * tt) + 0.6 * np.sin(2 * np.pi * 164.8 * tt) + 0.4 * np.sin(2 * np.pi * 220 * tt))
    pad *= np.minimum(1, tt / 1.0) * np.minimum(1, (dur - tt) / 0.6)
    return out + pad

def mix(dur, events, with_bed=True, path="a.wav"):
    n = int(dur * SR); out = np.zeros(n)
    if with_bed: out += bed(dur) * 0.6
    for (t, kind, *g) in events:
        s = sfx(kind) * (g[0] if g else 1.0); i = int(t * SR); e = min(n, i + len(s))
        if i < n: out[i:e] += s[:e - i]
    out = np.tanh(out * 1.2) * 0.85
    pcm = (out * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
    return path

def render(draw, dur, events, out, with_bed=True):
    tmp = out[:-4] + ".tmp.mp4"
    vtmp = out[:-4] + ".v.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "18", "-pix_fmt", "yuv420p", vtmp], stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)):
        im = draw(i / FPS).convert("RGB")
        p.stdin.write(im.tobytes())
    p.stdin.close(); assert p.wait() == 0
    wav = mix(dur, events, with_bed, out[:-4] + ".wav")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vtmp, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-shortest", "-movflags", "+faststart", tmp])
    assert r.returncode == 0
    os.replace(tmp, out); os.remove(vtmp); os.remove(wav)
    return out
