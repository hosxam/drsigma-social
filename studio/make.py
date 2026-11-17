"""Render one DrSigma post from a JSON spec.

Usage:
  python3 studio/make.py content/posts/2026-11-25.json            # renders into media/
  python3 studio/make.py content/posts/2026-11-25.json --frames   # preview stills into /tmp/preview/

Spec types (see content/posts/*.json for real examples):
  mcq:      tag, kicker, stem|null, question, options[4-5], correct "A".."E", explain, hook?, labs? [[name,value,unit],...]
  npc:      tag, stem, question, npc, npc_why, sigma, sigma_src
  pov:      lines [2 short lines], punch, sub
  promo:    (no fields; fixed product reel, edit studio/reels.py promo() if the offer changes)
  carousel: cover_title, cover_sub, slides [[situation, answer, why, source], ...] (max 8), cta_title, cta_sub
Every spec also has: date "YYYY-MM-DD", slug "series-nn_topic", caption, pinned_comment, sources [urls].
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from lib import *
import reels

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def build(spec):
    t = spec["type"]
    if t == "mcq":
        return reels.mcq(spec["tag"], spec["kicker"], spec.get("stem"), spec["question"], spec["options"],
                         spec["correct"], spec["explain"], labs=spec.get("labs"), hook=spec.get("hook"))
    if t == "npc":
        return reels.npc_vs_sigma(spec["tag"], spec["stem"], spec["question"], spec["npc"], spec["npc_why"],
                                  spec["sigma"], spec["sigma_src"])
    if t == "pov":
        return reels.pov_meme(spec["lines"], spec["punch"], spec["sub"])
    if t == "promo":
        return reels.promo()
    raise ValueError(t)

def carousel(spec, prefix):
    CW, CH = 1080, 1350
    def bg(): return background(0.0).crop((0, 200, CW, 200 + CH))
    def brand(img, page, total):
        d = ImageDraw.Draw(img)
        img.paste(logo(70), (70, 64), logo(70))
        d.text((156, 72), "DrSigma", font=font(32, "Black"), fill=WHITE)
        d.text((156, 108), "@drsigma.emree", font=font(22, "Semi"), fill=GREY)
        s = f"{page}/{total}"; f = font(30, "XB")
        d.text((CW - 70 - d.textlength(s, font=f), 86), s, font=f, fill=GREY)
    def tb(img, text, y, size, w="Black", fill=WHITE, maxw=920, hl=None, lh=1.15):
        d = ImageDraw.Draw(img); f = font(size, w); lines = wrap(d, text, f, maxw)
        for i, ln in enumerate(lines):
            cx = 80
            for wd in ln.split(" "):
                d.text((cx, y + i * int(size * lh)), wd, font=f, fill=(hl or {}).get(wd.strip(".,:"), fill))
                cx += d.textlength(wd + " ", font=f)
        return y + len(lines) * int(size * lh)
    slides = spec["slides"]; total = len(slides) + 2; out = []
    im = bg(); brand(im, 1, total); d = ImageDraw.Draw(im)
    d.rounded_rectangle((80, 260, 420, 326), 33, fill=RED); d.text((108, 270), "SAVE THIS", font=font(40, "Black"), fill=WHITE)
    y = tb(im, spec["cover_title"], 380, 100)
    tb(im, spec["cover_sub"], y + 50, 46, "Semi", fill=GREY)
    d.text((80, 1220), "Swipe  →", font=font(44, "XB"), fill=TEAL); out.append(im)
    for i, (sit, ans, why, src) in enumerate(slides):
        im = bg(); brand(im, i + 2, total); d = ImageDraw.Draw(im)
        d.text((80, 230), f"{i+1:02d}", font=font(200, "Black"), fill=(30, 70, 64))
        y = tb(im, sit, 470, 60, "XB", fill=TEAL); y = tb(im, ans, y + 30, 84, "Black")
        d.rounded_rectangle((80, y + 50, CW - 80, y + 54), 2, fill=TEAL_D)
        tb(im, why, y + 90, 46, "Semi", fill=(200, 210, 208))
        d.text((80, 1230), "Source: " + src, font=font(30, "Semi"), fill=GREY); out.append(im)
    im = bg(); brand(im, total, total); d = ImageDraw.Draw(im)
    im.paste(logo(220), ((CW - 220) // 2, 230), logo(220))
    y = tb(im, spec.get("cta_title", "4,900+ EMREE questions built around traps like these."), 520, 82, hl={"4,900+": TEAL})
    y = tb(im, spec.get("cta_sub", "Filter by exam year. Timed mocks in the EMREE blueprint mix. Every option explained."), y + 40, 44, "Semi", fill=GREY)
    d.rounded_rectangle((80, y + 70, CW - 80, y + 190), 60, fill=TEAL)
    s = "Try 10 pages free: drsigma.net"; f = font(48, "Black")
    d.text(((CW - d.textlength(s, font=f)) / 2, y + 100), s, font=f, fill=BG)
    d.text((80, 1220), "Save it. Send it to your batch.", font=font(40, "XB"), fill=WHITE); out.append(im)
    paths = []
    for i, im in enumerate(out):
        p = f"{prefix}_{i+1:02d}.png"; im.convert("RGB").save(p); paths.append(p)
    return paths

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    prefix = os.path.join(ROOT, "media", f'{spec["date"]}_{spec["slug"]}')
    if spec["type"] == "carousel":
        if "--frames" in sys.argv:
            os.makedirs("/tmp/preview", exist_ok=True); prefix = "/tmp/preview/" + spec["slug"]
        print("\n".join(carousel(spec, prefix)))
    else:
        draw, dur, ev = build(spec)
        if "--frames" in sys.argv:
            os.makedirs("/tmp/preview", exist_ok=True)
            for tt in [0.9, 2.5, 5.0, 9.4, dur - 0.3]:
                if tt < dur: draw(tt).convert("RGB").save(f"/tmp/preview/{spec['slug']}_{tt:.1f}.jpg", quality=85)
            print("/tmp/preview/")
        else:
            print(render(draw, dur, ev, prefix + ".mp4"))
