import sys
from lib import *

# ---------------- MCQ template ----------------
def mcq(tag, kicker, stem, question, options, correct, explain, labs=None, hook=None):
    T_OPT = 1.5; T_TIMER = 3.0; T_REVEAL = 8.0; T_END = 11.8; DUR = 13.4
    ci = "ABCDE".index(correct)

    def draw(t):
        img = background(t)
        header(img, tag, t)
        if hook:
            al, sc = pop(t, 0.05, 0.3)
            pill(img, hook, 300, fill=RED, tc=WHITE, size=40, alpha=al, scale=sc)
        y = 375
        al, sc = pop(t, 0.15)
        text_block(img, kicker, y, 44, "XB", fill=TEAL, alpha=al)
        y += 72
        if labs:
            d = ImageDraw.Draw(img)
            for i, (k, v, u) in enumerate(labs):
                a = ease_out(prog(t, 0.25 + i * 0.12, 0.3))
                if a <= 0: continue
                bx = 70 + i * 316; bw = 296
                d.rounded_rectangle((bx, y, bx + bw, y + 230), 30, fill=CARD, outline=TEAL_D, width=4)
                f1 = font(40, "Semi"); f2 = font(104, "Black"); f3 = font(32, "Semi")
                d.text((bx + bw / 2 - d.textlength(k, font=f1) / 2, y + 18), k, font=f1, fill=GREY)
                d.text((bx + bw / 2 - d.textlength(v, font=f2) / 2, y + 62), v, font=f2, fill=WHITE)
                d.text((bx + bw / 2 - d.textlength(u, font=f3) / 2, y + 180), u, font=f3, fill=GREY)
            y += 262
        if stem:
            al, sc = pop(t, 0.25)
            y = text_block(img, stem, y, 62, "Bold", alpha=al, scale=sc, maxw=950, lh=1.14) + 16
        al, sc = pop(t, 0.6)
        y = text_block(img, question, y, 88, "Black", fill=TEAL, alpha=al, scale=sc) + 26
        bar_y = y
        oy = bar_y + 46
        step = min(148, (1560 - oy) / len(options)); h = step - 20
        d = ImageDraw.Draw(img)
        if T_TIMER <= t < T_REVEAL:
            rem = T_REVEAL - t; fr = rem / 5.0
            d.rounded_rectangle((70, bar_y, W - 70, bar_y + 18), 9, fill=(40, 46, 48))
            d.rounded_rectangle((70, bar_y, 70 + max(18, (W - 140) * fr), bar_y + 18), 9, fill=TEAL if fr > 0.3 else RED)
            text_block(img, f"{int(math.ceil(rem))}s  -  comment your answer", oy + len(options) * step + 6, 38, "Bold", fill=GREY)
        rv = ease_in_out(prog(t, T_REVEAL + 0.15, 0.4))
        for i, o in enumerate(options):
            appear = prog(t, T_OPT + i * 0.12, 0.35)
            st = "idle"; fade = 1.0; yy = oy + i * step
            if t >= T_REVEAL:
                st = "correct" if i == ci else "wrong"
                if i == ci: yy = oy + (i * step) * (1 - rv)
                else: fade = 1 - rv
            option_card(img, int(yy), "ABCDE"[i], o, st, appear, h=int(h), fade=fade)
        if t >= T_REVEAL + 0.45:
            a = ease_out(prog(t, T_REVEAL + 0.45, 0.4))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
            yy = oy + step + 20 + int((1 - a) * 60)
            f = font(46, "Semi"); lines = wrap(dl, explain, f, 860)
            hgt = 56 + len(lines) * 60
            dl.rounded_rectangle((70, yy, W - 70, yy + hgt), 28, fill=(12, 40, 37, int(240 * a)), outline=TEAL + (int(255 * a),), width=4)
            for i, ln in enumerate(lines):
                dl.text((110, yy + 28 + i * 60), ln, font=f, fill=WHITE + (int(255 * a),))
            img.paste(layer, (0, 0), layer)
        img = flash(img, t, T_REVEAL, color=TEAL, strength=0.35)
        img = shake(img, t, T_REVEAL, 16)
        if t >= T_END:
            img = end_card(img, t - T_END)
        return img

    ev = [(0.05, "whoosh", .8), (0.15, "pop"), (0.6, "pop")]
    if labs: ev += [(0.25 + i * 0.12, "pop", .7) for i in range(len(labs))]
    ev += [(T_OPT + i * 0.12, "pop", .6) for i in range(len(options))]
    ev += [(T_TIMER + k, "tick") for k in range(5)]
    ev += [(T_REVEAL - 1.0, "riser"), (T_REVEAL, "hit"), (T_REVEAL + 0.05, "ding"), (T_REVEAL + 0.45, "whoosh", .5), (T_END, "whoosh", .7)]
    return draw, DUR, ev

def end_card(img, t):
    a = ease_out(clamp(t / 0.35))
    dark = Image.blend(img, Image.new("RGB", (W, H), BG), 0.88 * a)
    if a <= 0.05: return dark
    s = 0.85 + 0.15 * ease_back(clamp(t / 0.45))
    lg = logo(int(260 * s)); dark.paste(lg, ((W - lg.width) // 2, 560 - lg.height // 2), lg)
    text_block(dark, "1 EMREE question.\nEvery day.", 740, 96, "Black", alpha=a, hl={"Every": TEAL, "day.": TEAL})
    text_block(dark, "Follow @drsigma.emree", 1000, 50, "XB", fill=GREY, alpha=a)
    pill(dark, "4,900+ more at drsigma.net", 1160, size=44, alpha=a)
    return dark

# ---------------- NPC vs SIGMA ----------------
def npc_vs_sigma(tag, stem, question, npc, npc_why, sigma, sigma_src):
    DUR = 12.0; T_NPC = 1.6; T_X = 3.4; T_SIG = 4.8; T_OK = 6.3; T_END = 10.4

    def card(img, y, label, lab_col, body, sub, appear, state):
        if appear <= 0: return
        a = ease_out(appear)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        xo = int((1 - a) * (-300 if label.startswith("NPC") else 300))
        x1, x2 = 70 + xo, W - 70 + xo
        f = font(58, "XB"); lines = wrap(d, body, f, 860)
        fs = font(42, "Semi"); sl = wrap(d, sub, fs, 860) if sub else []
        hgt = 130 + len(lines) * 68 + (len(sl) * 52 + 24 if state else 0)
        outline = {"x": RED, "ok": TEAL}.get(state, (60, 66, 68))
        d.rounded_rectangle((x1, y, x2, y + hgt), 30, fill=CARD + (255,), outline=outline, width=5 if state else 3)
        fl = font(40, "Black"); lw = d.textlength(label, font=fl)
        d.rounded_rectangle((x1 + 30, y + 28, x1 + 78 + lw, y + 92), 32, fill=lab_col)
        d.text((x1 + 54, y + 37), label, font=fl, fill=BG if lab_col == TEAL else WHITE)
        for i, ln in enumerate(lines):
            d.text((x1 + 36, y + 116 + i * 68), ln, font=f, fill=WHITE)
        if state:
            for i, ln in enumerate(sl):
                d.text((x1 + 36, y + 130 + len(lines) * 68 + i * 52), ln, font=fs, fill=(255, 150, 150) if state == "x" else (150, 240, 228))
        if a < 1:
            r, g, b, al = layer.split(); al = al.point(lambda v: int(v * a)); layer = Image.merge("RGBA", (r, g, b, al))
        img.paste(layer, (0, 0), layer)
        return y + hgt

    def stamp(img, cx, cy, ch, col, t0, t):
        p = prog(t, t0, 0.25)
        if p <= 0: return
        s = 1.8 - 0.8 * ease_out(p)
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(130 * s))
        d = ImageDraw.Draw(img); w = d.textlength(ch, font=f)
        d.text((cx - w / 2, cy - 80 * s), ch, font=f, fill=col)

    def draw(t):
        img = background(t)
        header(img, tag, t)
        al, sc = pop(t, 0.1)
        y = text_block(img, stem, 340, 66, "Bold", alpha=al, scale=sc) + 16
        al, sc = pop(t, 0.6)
        y = text_block(img, question, y, 92, "Black", fill=TEAL, alpha=al, scale=sc) + 44
        st1 = "x" if t >= T_X else None
        y2 = card(img, y, "NPC INTERN", (120, 40, 40), npc, npc_why, prog(t, T_NPC, 0.4), st1)
        if t >= T_X: stamp(img, W - 150, y + 66, "✗", RED, T_X, t)
        ys = (y2 or y + 260) + 34
        st2 = "ok" if t >= T_OK else None
        card(img, ys, "SIGMA INTERN", TEAL, sigma, sigma_src, prog(t, T_SIG, 0.4), st2)
        if t >= T_OK: stamp(img, W - 150, ys + 66, "✓", TEAL, T_OK, t)
        img = shake(img, t, T_X, 18)
        img = flash(img, t, T_X, color=RED, strength=0.25)
        img = flash(img, t, T_OK, color=TEAL, strength=0.3)
        if t >= T_END: img = end_card(img, t - T_END)
        return img

    ev = [(0.05, "whoosh", .8), (0.1, "pop"), (0.6, "pop"), (T_NPC, "whoosh", .7), (T_X, "buzz"), (T_X, "hit", .6),
          (T_SIG, "whoosh", .7), (T_OK - 0.9, "riser"), (T_OK, "hit"), (T_OK + 0.05, "ding"), (T_END, "whoosh", .7)]
    return draw, DUR, ev

# ---------------- POV meme ----------------
def pov_meme(lines_, punch, sub):
    DUR = 9.0; T_P = 3.0; T_S = 5.6

    def draw(t):
        img = background(t, accent=(140, 60, 255) if t >= T_P else TEAL)
        header(img, "POV", t)
        y = 470
        for i, ln in enumerate(lines_):
            al, sc = pop(t, 0.15 + i * 0.7)
            y = text_block(img, ln, y, 100, "Black", alpha=al, scale=sc, hl={"3": TEAL, "weeks": TEAL, "cardio": TEAL}) + 26
        if t >= T_P:
            al, sc = pop(t, T_P, 0.3)
            text_block(img, punch, y + 50, 100, "Black", alpha=al, scale=sc * 1.05, fill=WHITE, hl={"HPV": (255, 205, 80), "schedule": (255, 205, 80), "Abu": (255, 205, 80), "Dhabi's": (255, 205, 80)})
        if t >= T_S:
            al, sc = pop(t, T_S, 0.35)
            pill(img, sub, 1480, size=42, alpha=al, scale=sc)
        z = 1.0 + (0.08 * ease_out(prog(t, T_P, 0.25)) if t >= T_P else 0)
        img = zoom(img, z + 0.01 * math.sin(t * 2))
        img = shake(img, t, T_P, 26, 0.35)
        img = flash(img, t, T_P, strength=0.6)
        return img

    ev = [(0.15, "pop"), (0.85, "pop"), (T_P - 0.8, "riser"), (T_P, "hit"), (T_P, "buzz", .5), (T_S, "pop")]
    return draw, DUR, ev

# ---------------- Promo kinetic ----------------
def promo():
    DUR = 12.0
    beats = [(0.0, "Stop doing random MCQs.", RED), (1.3, "The EMREE repeats patterns.", WHITE), (2.6, "Drill it by exam year.", TEAL)]
    chips = ["4,900+ EMREE questions", "Filter by exam year", "Timed mocks, blueprint mix", "Every option explained", "UAE guidance first"]
    T_C = 4.0; T_P = 7.2; T_END = 9.0

    def draw(t):
        img = background(t)
        header(img, "drsigma.net", t)
        if t < T_C:
            cur = [b for b in beats if t >= b[0]][-1]
            al, sc = pop(t, cur[0], 0.3)
            text_block(img, cur[1], 880, 120, "Black", fill=cur[2], alpha=al, scale=sc, anchor_cy=True, maxw=900)
        elif t < T_END:
            text_block(img, "Everything in one place:", 380, 64, "Black", fill=TEAL)
            d = ImageDraw.Draw(img)
            for i, c in enumerate(chips):
                a = ease_out(prog(t, T_C + 0.15 + i * 0.28, 0.3))
                if a <= 0: continue
                y = 500 + i * 158; xo = int((1 - a) * 400)
                d.rounded_rectangle((70 + xo, y, W - 70 + xo, y + 132), 66, fill=CARD, outline=TEAL_D, width=4)
                d.ellipse((100 + xo, y + 31, 170 + xo, y + 101), fill=TEAL)
                d.text((115 + xo, y + 30), "✓", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 54), fill=BG)
                d.text((200 + xo, y + 34), c, font=font(54, "XB"), fill=WHITE)
            if t >= T_P:
                al, sc = pop(t, T_P)
                text_block(img, "AED 400 · 90 days · no subscription", 1320, 52, "XB", fill=WHITE, alpha=al, scale=sc)
        else:
            tt = t - T_END
            al, sc = pop(t, T_END)
            lg = logo(240); img.paste(lg, ((W - 240) // 2, 420), lg)
            text_block(img, "See 10 real pages free", 720, 104, "Black", alpha=al, scale=sc, hl={"free": TEAL})
            pill(img, "drsigma.net/try", 1040, size=58, alpha=al, scale=sc)
            a2 = ease_out(prog(t, T_END + 0.6, 0.3))
            text_block(img, "Comment BANK and we'll DM you the link", 1200, 44, "Semi", fill=GREY, alpha=a2)
        img = shake(img, t, 0.0, 22, 0.3)
        img = flash(img, t, T_END, color=TEAL, strength=0.3)
        return img

    ev = [(0.0, "hit"), (1.3, "pop"), (2.6, "pop"), (3.6, "riser"), (T_C, "whoosh")]
    ev += [(T_C + 0.15 + i * 0.28, "pop", .7) for i in range(len(chips))]
    ev += [(T_P, "pop"), (T_END, "hit"), (T_END + 0.05, "ding")]
    return draw, DUR, ev

REELS = {
 "D1_hyperkalaemia": lambda: mcq("FIRST STEP? #01", "Emergency Medicine",
     "K+ 6.9 mmol/L. ECG: peaked T waves, widening QRS.", "What do you give FIRST?",
     ["IV insulin + dextrose", "IV calcium gluconate", "Salbutamol nebuliser", "Oral calcium resonium", "IV furosemide"], "B",
     "Calcium protects the heart within minutes but does NOT lower K+. Then shift it: insulin-dextrose ± salbutamol.",
     hook="Option A is the trap"),
 "D2_npc_vs_sigma_dka": lambda: npc_vs_sigma("NPC vs SIGMA #01",
     "DKA. pH 7.12.\nK+ 3.1 mmol/L.", "Next step?",
     "Start the insulin infusion right now.", "Insulin pushes K+ into cells. At 3.1 you just bought an arrhythmia.",
     "Fluids running. Hold insulin. Replace K+ first until it's at least 3.5.", "2024 international DKA consensus"),
 "D4_tension_pneumo": lambda: mcq("FIRST STEP? #02", "Trauma / ATLS",
     "RTA. BP 78/40, HR 132. Absent breath sounds on the left. Trachea deviated right.", "Next step?",
     ["Urgent chest X-ray", "Needle decompression", "CT chest", "Intubate and ventilate", "FAST scan"], "B",
     "Tension pneumothorax is a clinical diagnosis. Decompress now (4th/5th ICS, mid-axillary line), then chest drain. Imaging first kills.",
     hook="Don't order the X-ray"),
 "D5_pov_meme": lambda: pov_meme(["POV: you studied", "cardio for 3 weeks"],
     "and the EMREE asks about Abu Dhabi's HPV schedule", "Public Health = 1 of 7 specialties"),
 "D6_abg_normal_ph": lambda: mcq("ABG IN 10s #01", "Critically ill. 'Normal' pH?",
     None, "What's the disorder?",
     ["Normal ABG", "Fully compensated metabolic acidosis", "Metabolic acidosis + respiratory alkalosis", "Respiratory alkalosis only"], "C",
     "Winter's: expected PaCO2 = 1.5 × 15 + 8 = 30.5 ± 2. Actual 25 is too low = a second respiratory alkalosis. Think salicylate toxicity.",
     labs=[("pH", "7.40", "normal?"), ("PaCO2", "25", "mmHg"), ("HCO3-", "15", "mmol/L")], hook="Not as normal as it looks"),
 "D7_promo_bank": promo,
}

if __name__ == "__main__":
    import os
    os.makedirs("/home/claude/out", exist_ok=True)
    names = sys.argv[2:] or list(REELS)
    mode = sys.argv[1]
    for n in names:
        draw, dur, ev = REELS[n]()
        if mode == "frames":
            for tt in [0.8, 2.5, 5.0, 9.2, 10.6, 12.6]:
                if tt < dur: draw(tt).convert("RGB").save(f"/home/claude/out/f_{n}_{tt}.jpg", quality=85)
        else:
            render(draw, dur, ev, f"/home/claude/out/{n}.mp4")
            print("done", n)
