#!/usr/bin/env python3
"""ドラゴンの「動くスタンプ」ジェネレーター.

武闘家 (martial_anim.py) の人形の仕組み (脚・腕・体の傾け方・RPG の数字・オチの一言・4 秒の 1 回再生)
をそのまま使い、ドラゴン用に上半身の絵・顔・翼・しっぽ・かぎ爪・炎を差し替える。
魔法や剣の表現は使わず、炎・煙・火の粉・羽ばたき・しっぽ・地響きなど、ドラゴンらしい表現だけで動かす。

使い方:
    python3 dragon_anim.py                     # dragon_stamps.json から生成
"""

import argparse
import copy
import math

import martial_anim as base
import wizard_anim as wz
from sprites import CHARACTERS, PALETTE

an = base.an
GROUND = base.GROUND
CH = CHARACTERS["dragon"]
MEMBRANE, BONE = "#5A7BD0", "#1F3266"
FIRE = ["#FFF3B0", "#FFD23C", "#FF9A2A", "#E8501E", "#B8281E"]
SMOKE = ["#C9C9D2", "#9A9AA8"]

# --- 武闘家の人形をドラゴン用に差し替える ------------------------------------
base.CH = CH
base.COLORS = {**PALETTE, **CH["colors"]}
base.BODY_H = len(CH["pixels"])
base.BODY_W = len(CH["pixels"][0])
base.BODY_CX = (base.BODY_W - 1) / 2
base.HEAD_ROWS = 13
base.PANTS, base.SHOE, base.SOLE = "#2F4A8A", "#1F3266", "#F2E6C8"
base.THIGH = base.SHIN = 4.0            # ドラゴンの脚は短くて太い
base.TRAIL_DARK, base.TRAIL_LIGHT = "#E8501E", "#FFD23C"   # 腕や足の軌跡は炎の色
base.IDLE = dict(base.IDLE, hip=7, lh=(-6, -11), rh=(6, -11), lf=(-4, 0), rf=(4, 0), wing=25, tail=0)

_EL, _ER = 6, 13
base.FACES = {
    "normal":    [(5, 6, "W"), (6, 6, "W"), (5, 7, "W"), (6, 7, "E"), (13, 6, "W"), (14, 6, "W"), (13, 7, "E"), (14, 7, "W")],
    "smile":     [(5, 6, "W"), (6, 6, "W"), (5, 7, "W"), (6, 7, "E"), (13, 6, "W"), (14, 6, "W"), (13, 7, "E"), (14, 7, "W"),
                  (9, 11, "R"), (10, 11, "R")],
    "calm":      [(5, 7, "W"), (6, 7, "W"), (13, 7, "W"), (14, 7, "W")],
    "sleep":     [(5, 7, "W"), (6, 7, "W"), (13, 7, "W"), (14, 7, "W")],
    "happy":     [(5, 7, "W"), (6, 6, "W"), (7, 7, "W"), (12, 7, "W"), (13, 6, "W"), (14, 7, "W"),
                  (8, 11, "R"), (9, 11, "R"), (10, 11, "R"), (11, 11, "R")],
    "wink":      [(5, 6, "W"), (6, 6, "W"), (5, 7, "W"), (6, 7, "E"), (13, 7, "W"), (14, 7, "W"), (9, 11, "R"), (10, 11, "R")],
    "surprised": [(5, 6, "W"), (6, 6, "W"), (5, 7, "W"), (6, 7, "W"), (13, 6, "W"), (14, 6, "W"), (13, 7, "W"), (14, 7, "W"),
                  (9, 11, "K"), (10, 11, "K")],
    "kira":      [(5, 6, "Y"), (6, 6, "Y"), (5, 7, "Y"), (6, 7, "Y"), (13, 6, "Y"), (14, 6, "Y"), (13, 7, "Y"), (14, 7, "Y"),
                  (9, 11, "R"), (10, 11, "R")],
    "sad":       [(5, 7, "W"), (6, 7, "E"), (13, 7, "E"), (14, 7, "W"), (_EL, 8, "L"), (_ER, 8, "L")],
    "angry":     [(5, 7, "W"), (6, 7, "W"), (6, 6, "E"), (13, 6, "E"), (13, 7, "W"), (14, 7, "W"), (7, 5, "K"), (12, 5, "K")],
    "roar":      [(5, 7, "W"), (6, 7, "W"), (6, 6, "E"), (13, 6, "E"), (13, 7, "W"), (14, 7, "W"), (7, 5, "K"), (12, 5, "K"),
                  (7, 11, "R"), (8, 11, "R"), (9, 11, "R"), (10, 11, "R"), (11, 11, "R"), (12, 11, "R")],
    "dizzy":     [(5, 6, "W"), (7, 8, "W"), (6, 7, "W"), (12, 8, "W"), (14, 6, "W"), (13, 7, "W")],
    "worry":     [(5, 7, "W"), (6, 7, "E"), (13, 7, "E"), (14, 7, "W"), (5, 5, "K"), (14, 5, "K")],
}


def col(c):
    return base.col(c)


def mouth(g, p):
    """口の位置 (炎や煙の出どころ)。体を傾けたときの頭のずれも合わせる。"""
    p = base.clamp(p)
    h = base.BODY_H * p["squash"]
    k = -math.tan(math.radians(p["tilt"]))
    hx, hy = g["hip"]
    return hx + k * (h - round(h * 0.58) / 2), hy - h + 1 + 11.5 * p["squash"] + p["bow"]


def draw_back(char, d, p, g):
    """翼 (左右) としっぽを体の後ろに描く。"""
    a = math.radians(p["wing"])
    for side, sh in zip((-1, 1), g["shoulders"]):
        sx = 1 if p["sx"] >= 0 else -1
        root = (sh[0] - side * sx * 1, sh[1] - 1)
        low = (root[0], root[1] + 7)
        tip = (root[0] + side * sx * math.cos(a) * 12, root[1] - math.sin(a) * 12)
        s1 = (tip[0] + (low[0] - tip[0]) * 0.35 - side * sx * 1, tip[1] + (low[1] - tip[1]) * 0.35 + 3)
        s2 = (tip[0] + (low[0] - tip[0]) * 0.7 - side * sx * 1, tip[1] + (low[1] - tip[1]) * 0.7 + 2)
        d.polygon([root, tip, s1, s2, low], fill=col(MEMBRANE), outline=col("K"))
        d.line([root, tip], fill=col(BONE), width=2)
        d.line([root, s1], fill=col(BONE))
        d.point((round(tip[0]), round(tip[1])), fill=col("Y"))
    # しっぽ: 腰の右後ろから外へ伸び、先が上に反る。tail で左右に振る
    hx, hy = g["hip"]
    sx = 1 if p["sx"] >= 0 else -1
    pts = [(0, 0), (4, 1), (8, 0), (11, -3), (12, -7)]
    tr = math.radians(p["tail"])
    world = [(hx + sx * (3 + x * math.cos(tr) - y * math.sin(tr)), hy - 1 + x * math.sin(tr) + y * math.cos(tr)) for x, y in pts]
    for i, w in enumerate((6, 5, 4, 3)):
        d.line([world[i], world[i + 1]], fill=col("K"), width=w + 1)
    for i, w in enumerate((4, 3, 2, 1)):
        d.line([world[i], world[i + 1]], fill=col("S"), width=w)
    tx, ty = world[-1]
    d.polygon([(tx - 2, ty), (tx + 2, ty), (tx, ty - 3)], fill=col("Y"), outline=col("K"))


def draw_claw(d, h):
    """かぎ爪の手: 紺色の手に白い爪 3 本。"""
    x, y = round(h[0]), round(h[1])
    d.rectangle([x - 2, y - 2, x + 3, y + 3], fill=col("K"))
    d.rectangle([x - 1, y - 1, x + 2, y + 2], fill=col("S"))
    d.point([(x - 1, y - 2), (x + 1, y - 2), (x + 3, y - 1)], fill=col("W"))


def draw_extra_fx(img, d, fx, g, phase, p):
    m = mouth(g, p)
    for e in fx:
        kind = e.get("type")
        if kind == "fire":  # 口から吐く炎: 口元は白っぽく、先へ行くほど赤く広がる
            ang, length, width = math.radians(e["ang"]), e["len"], e.get("width", 0.5)
            ux, uy = math.cos(ang), math.sin(ang)
            nx, ny = -uy, ux
            n = e.get("n", 22)
            for i in range(n):
                t = (i + 0.5) / n
                jit = ((i * 37 + phase * 13) % 11) / 10 * 2 - 1
                dist = length * t
                off = dist * width * jit
                x, y = m[0] + ux * dist + nx * off, m[1] + uy * dist + ny * off
                r = 1 + t * 2.2
                c = FIRE[min(len(FIRE) - 1, int(t * len(FIRE)))]
                d.ellipse([x - r, y - r, x + r, y + r], fill=col(c))
        elif kind == "smoke":  # 煙のかたまり
            for i, (x, y, r) in enumerate(e["pts"]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=col(SMOKE[i % 2]), outline=col("#6E6E7E"))
        elif kind == "nose":  # 鼻から出る小さな煙
            for i in range(2):
                o = (phase + i) % 3
                x, y = m[0] + (-3 if i == 0 else 3), m[1] - 1 - o * 2
                d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=col(SMOKE[i % 2]))
        elif kind == "embers":  # 火の粉
            for i in range(e.get("n", 8)):
                x = e.get("x", 24) - 14 + (i * 7) % 29
                y = 30 - ((phase * 4 + i * 6) % 28)
                d.point((round(x), round(y)), fill=col(FIRE[1 + i % 3]))
        elif kind == "roar":  # 咆哮の衝撃波 (口から広がる弧)
            for r in e.get("rs", (6, 10)):
                pts = [(m[0] + r * math.cos(math.radians(a)), m[1] + r * math.sin(math.radians(a)) * 0.8)
                       for a in range(-60, 241, 30)]
                for a0, a1 in zip(pts[::2], pts[1::2]):
                    d.line([a0, a1], fill=col("W"))
        elif kind == "ring":   # 煙の輪 / 火の輪
            x, y, r = e["x"], e["y"], e["r"]
            d.ellipse([x - r, y - r, x + r, y + r], outline=col(e.get("color", FIRE[2])), width=2)
        elif kind == "coins":  # 宝の山 (金貨)
            x0 = e["x"]
            for i in range(12):
                cx, cy = x0 - 12 + (i * 5) % 24, GROUND - 1 - (i % 3)
                d.ellipse([cx - 2, cy - 1, cx + 2, cy + 1], fill=col("Y"), outline=col("y"))


base.draw_back = draw_back
base.draw_fist = draw_claw
base.draw_extra_fx = draw_extra_fx

# --- エフェクトの部品 --------------------------------------------------------
spr, speed, puff, confetti, burst = wz.spr, wz.speed, base.puff, wz.confetti, wz.burst
num, status, impact, dust = base.num, base.status, base.impact, base.dust
DIZZY, NOSE = base.DIZZY, {"type": "nose"}


def fire(ang, length, width=0.45, n=22):
    return {"type": "fire", "ang": ang, "len": length, "width": width, "n": n}


def smoke(*pts):
    return {"type": "smoke", "pts": list(pts)}


def roar(*rs):
    return {"type": "roar", "rs": rs or (6, 10)}


EMBERS = {"type": "embers", "n": 9}
pose, lerp, tween, with_fx = base.pose, base.lerp, base.tween, base.with_fx


def stance(**kw):
    return pose(**{**dict(expr="normal"), **kw})


base.stance = stance


def flap(p, up):
    q = copy.deepcopy(p)
    q["wing"] = 70 if up else -15
    return q


def spin(base_p, sxs=(0.5, -0.5, -1.0, -0.5, 0.5)):
    out = []
    for sx in sxs:
        q = copy.deepcopy(base_p)
        q["sx"] = sx
        out.append(q)
    return out


# --- 動き (24 種) ------------------------------------------------------------
def m_thanks():   # ありがとう!: 翼を大きく広げてから、たたんで深くおじぎ
    final = stance(bow=5, squash=0.9, wing=-25, lh=(-2, -9), rh=(2, -9), expr="calm", fx=[spr("sparkle", 44, 6)])
    wide = stance(wing=75, lh=(-9, -14), rh=(9, -14), expr="smile", fx=[spr("sparkle", 44, 6)])
    return [final, stance(), wide, flap(wide, False), wide, lerp(wide, final, 0.5), final, final], [150] * 8, 1


def m_morning():  # おはよう!: 寝ぼけて煙をぷすっ → 翼を伸ばして炎を上へ。火力ゲージ 0 → 100
    def heat(v):
        return status("火力", v, 100, "#FF7A2A")
    final = stance(x=18, wing=80, squash=1.08, lh=(-8, -19), rh=(8, -19), expr="roar", fx=[fire(-90, 14, 0.35)],
                   panel=heat(100))
    yawn = stance(x=18, bow=2, wing=-15, expr="sleep", fx=[smoke((20, 12, 2), (23, 9, 3)), spr("zzz", 2, 6)], panel=heat(0))
    seq = [final, yawn, stance(x=18, expr="normal", fx=[NOSE], panel=heat(20)),
           stance(x=18, wing=50, expr="angry", fx=[NOSE], panel=heat(50)),
           stance(x=18, wing=80, squash=1.08, lh=(-8, -19), rh=(8, -19), expr="roar", fx=[fire(-90, 8, 0.3)], panel=heat(80)),
           final, final, final]
    return seq, [150] * len(seq), 1


def m_ok():       # OK!: かぎ爪で OK サインを作り、火の輪をぽっと吐く
    ringp = lambda r: {"type": "ring", "x": 38, "y": 14, "r": r}
    final = stance(wing=40, rh=(9, -18), lh=(-6, -11), expr="wink", fx=[ringp(6), spr("sparkle", 48, 2)])
    seq = [final, stance(), stance(rh=(9, -18), expr="smile", fx=[ringp(2)]), stance(rh=(9, -18), expr="smile", fx=[ringp(4)]),
           final, final]
    return seq, [150] * len(seq), 1


def m_roger():    # 了解!: 胸を張って吠え、真上に火柱!
    final = stance(wing=80, squash=1.08, lh=(-9, -14), rh=(9, -14), expr="roar", fx=[fire(-90, 20, 0.3), EMBERS])
    seq = [final, stance(squash=0.85, wing=-10, expr="angry"), stance(wing=60, expr="roar", fx=[fire(-90, 10, 0.3)]),
           final, with_fx(final, fire(-90, 22, 0.35), EMBERS, roar()), final, final]
    return seq, [150] * len(seq), 1


def m_sorry():    # ごめん!: 翼をしょんぼり下げて、何度も頭を下げる。鼻から煙
    final = stance(bow=6, squash=0.86, wing=-35, lh=(-2, -8), rh=(2, -8), expr="sad", fx=[NOSE, spr("sweats", 36, 6)])
    up = stance(wing=-25, lh=(-2, -9), rh=(2, -9), expr="sad", fx=[spr("sweat", 36, 8)])
    seq = [final] + tween(final, 2, up, 2, final)[1:]
    return seq, [200] * len(seq), 3


def m_otsukare():  # おつかれ!: どっかり座って、煙の輪をふーっ。EXP +100
    final = stance(hip=4, wing=-20, lf=(-7, 0), rf=(7, 0), lh=(-8, -6), rh=(8, -6), expr="calm",
                   fx=[{"type": "ring", "x": 34, "y": 10, "r": 4, "color": SMOKE[1]}, num("EXP +100", 48, 30, "heal")])
    seq = [final, stance(), stance(hip=4, wing=-20, lf=(-7, 0), rf=(7, 0), lh=(-8, -6), rh=(8, -6), expr="calm",
                                   fx=[smoke((28, 14, 2))]),
           stance(hip=4, wing=-20, lf=(-7, 0), rf=(7, 0), lh=(-8, -6), rh=(8, -6), expr="calm",
                  fx=[{"type": "ring", "x": 31, "y": 12, "r": 2, "color": SMOKE[1]}]),
           final, final, final]
    return seq, [150] * len(seq), 1


def m_congrats():  # おめでとう!: 空へ炎を吹き上げて花火、紙吹雪
    def fw(r, s):
        return [burst(46, 8, r, wz.PINK), burst(46, 8, r * 0.55, wz.GOLD, 6), burst(14, 8, r * 0.8, wz.CYAN), confetti(s)]
    final = stance(wing=80, squash=1.08, lh=(-9, -15), rh=(9, -15), expr="happy", fx=fw(7, 0))
    seq = [final, stance(squash=0.85, expr="smile"), stance(wing=70, expr="roar", fx=[fire(-90, 16, 0.25)]),
           stance(wing=80, expr="roar", fx=[fire(-90, 22, 0.25)]), with_fx(final, *fw(3, 1)), with_fx(final, *fw(5, 2)),
           final, final]
    return seq, [150] * len(seq), 1


def m_goodnight():  # おやすみ: 宝の山の上で丸くなって眠る。HP がだんだん回復
    def hp(v):
        return status("HP", v, 100, "#4CD964")
    final = stance(x=18, hip=3, bow=3, wing=-30, lf=(-8, 0), rf=(8, 0), lh=(-4, -6), rh=(4, -6), tail=-30, expr="sleep",
                   fx=[{"type": "coins", "x": 18}, spr("zzz", 2, 6)], panel=hp(100))
    seq = [final]
    for i, v in enumerate((10, 30, 50, 70, 90)):
        q = copy.deepcopy(final)
        q["panel"], q["bow"] = hp(v), (3 if i % 2 == 0 else 2)
        q["fx"] = [{"type": "coins", "x": 18}, spr("zzz", 2, 6 - i % 2), num("+20", 50, 33, "heal")]
        seq.append(q)
    seq += [with_fx(final, {"type": "coins", "x": 18}, spr("zzz", 2, 6), num("HP MAX", 49, 33, "heal")), final]
    return seq, [150] * len(seq), 1


def m_ittekimasu():  # いってきます!: 力強く羽ばたいて飛び立ち、画面の外へ
    final = stance(wing=75, rh=(9, -18), lh=(-6, -11), expr="happy", fx=[spr("note", 2, 6)])
    seq = [final, stance(squash=0.85, wing=-15, expr="smile")]
    for i in range(1, 8):
        seq.append(stance(x=24 + i * 5, y=-2 - min(i, 4), wing=70 if i % 2 else -15, lf=(-3, -2), rf=(3, -2), expr="happy",
                          fx=[speed(18 + i * 5, 18, n=3, length=6)] + ([dust(24, 10)] if i == 1 else [])))
    seq += [final]
    return seq, [150] * len(seq), 1


def m_tadaima():  # ただいま!: 飛んで帰ってきてズシン!と着地。震度3
    final = stance(squash=0.86, wing=60, lh=(-9, -12), rh=(9, -12), expr="happy",
                   fx=[dust(24, 8), {"type": "crack", "x": 24, "n": 3}, num("震度3", 42, 6, "crit")])
    seq = [final]
    for i, x in enumerate((-2, 6, 14, 20)):
        seq.append(stance(x=x, y=-4, wing=70 if i % 2 else -15, lf=(-3, -2), rf=(3, -2), expr="smile",
                          fx=[speed(x - 12, 18, n=3, length=6)]))
    shake = copy.deepcopy(final)
    shake["x"] = 25
    seq += [final, shake, final, final]
    return seq, [150] * len(seq), 1


def m_ganbare():  # がんばれ!: 炎を左右に振って、全力で応援
    l = stance(wing=70, tilt=12, expr="roar", lh=(-9, -16), rh=(9, -12), fx=[fire(-125, 16, 0.3)])
    r = stance(wing=-10, tilt=-12, expr="roar", lh=(-9, -12), rh=(9, -16), fx=[fire(-55, 16, 0.3)])
    return [r, lerp(r, l, 0.5), l, lerp(l, r, 0.5)], [150] * 4, 3


def m_sugoi():    # すごい!: 正面に特大の炎! CRITICAL! 9999
    big = stance(x=16, tilt=-10, wing=75, lh=(-8, -12), rh=(9, -12), expr="roar", fx=[fire(0, 30, 0.35, n=28), EMBERS])
    final = with_fx(big, fire(0, 30, 0.35, n=28), EMBERS, num("CRITICAL!", 30, 3, "crit"), num("9999", 50, 30, "damage", k=3))
    seq = [final, stance(x=16, squash=0.86, wing=-15, expr="angry", fx=[NOSE]), stance(x=16, wing=50, expr="angry", fx=[NOSE]),
           with_fx(big, fire(0, 14, 0.3)), big, final, final, final]
    return seq, [150] * len(seq), 1


def m_iine():     # いいね!: しっぽをぶんぶん振りながら、かぎ爪をぐっ
    a = stance(rh=(9, -18), wing=40, tail=25, expr="wink", fx=[spr("sparkle", 46, 4)])
    b = stance(rh=(9, -18), wing=40, tail=-25, expr="wink", fx=[spr("sparkle", 46, 6)])
    return [a, lerp(a, b, 0.5), b, lerp(b, a, 0.5)], [150] * 4, 3


def m_sorena():   # それな!: かぎ爪でこっちを指して、鼻から炎がボッ
    final = stance(x=22, tilt=-8, rh=(12, -16), wing=50, expr="kira", fx=[NOSE, spr("exclaim", 48, 2)])
    seq = [final, stance(), stance(x=21, tilt=6, rh=(2, -14), expr="angry"), with_fx(final, NOSE, fire(-60, 6, 0.4, n=10)),
           final, final]
    return seq, [150] * len(seq), 1


def m_wakaru():   # わかる〜: 腕を組んで深くうなずく。千年生きた Lv 999
    arms = dict(lh=(3, -11), rh=(-3, -11), wing=10)
    final = stance(bow=3, expr="calm", fx=[NOSE, num("Lv 999", 44, 6, "level")], **arms)
    up = stance(expr="calm", fx=[num("Lv 999", 44, 6, "level")], **arms)
    seq = [final] + tween(up, 2, final, 2, up, 2, final)[1:]
    return seq, [150] * len(seq), 1


def m_nandeyanen():  # なんでやねん!: くるっと回ってしっぽでツッコミ! ダメージ 1
    final = stance(x=20, tilt=10, tail=-50, wing=30, expr="angry",
                   fx=[impact(38, 22, 6), num("1", 44, 12, "damage"), speed(52, 18, left=False)])
    seq = [final, stance(expr="normal")] + spin(stance(expr="angry", tail=20), (0.5, -0.5, -1.0, -0.5)) + \
        [final, final, final]
    return seq, [130] * len(seq), 1


def m_muri():     # もうムリ…: HP がみるみる減って 0。煙を吐いてばったり
    def hp(v):
        return status("HP", v, 100, "#E8414F")
    final = stance(x=18, hip=3, bow=3, squash=0.85, wing=-35, lf=(-9, 0), rf=(9, 0), lh=(-9, -3), rh=(9, -3), expr="dizzy",
                   fx=[DIZZY, smoke((26, 16, 2), (28, 12, 3))], panel=hp(0))
    seq = [final, stance(x=18, panel=hp(100))]
    for v, tl in ((60, 12), (30, -12), (10, 10)):
        seq.append(stance(x=18, tilt=tl, wing=-25, expr="dizzy", fx=[DIZZY], panel=hp(v)))
    seq += [with_fx(final, DIZZY, puff(18)), final, final]
    return seq, [150] * len(seq), 1


def m_ureshii():  # うれしい!: 羽ばたいて舞い上がると LEVEL UP! (Lv 99 → 100)
    def fly(y, up, lv, lvl=False):
        fx = [num(f"Lv {lv}", 48, 30, "level")] + ([num("LEVEL UP!", 32, 3, "level")] if lvl else [])
        return stance(y=y, wing=70 if up else -15, lf=(-3, -2), rf=(3, -2), lh=(-8, -16), rh=(8, -16), expr="happy", fx=fx)
    final = fly(-5, True, 100, True)
    seq = [final, fly(0, False, 99), fly(-3, True, 99), fly(-5, False, 99), fly(-5, True, 100, True), fly(-3, False, 100, True),
           fly(-5, True, 100, True), final]
    return seq, [150] * len(seq), 1


def m_shock():    # ショック…: 何かが直撃して -9999。火がしゅんと消えて煙だけ
    def hp(v):
        return status("HP", v, 100, "#E8414F")
    final = stance(x=18, hip=4, bow=2, wing=-35, lf=(-7, 0), rf=(7, 0), lh=(-6, -5), rh=(6, -5), expr="sad",
                   fx=[smoke((26, 14, 2), (28, 10, 2))], panel=hp(12))
    hit_p = stance(x=16, tilt=20, wing=60, lh=(-11, -16), rh=(5, -18), expr="surprised",
                   fx=[impact(30, 14, 8), num("-9999", 16, 3, "crit")], panel=hp(100))
    seq = [final, stance(x=18, expr="normal", fx=[NOSE], panel=hp(100)), hit_p,
           with_fx(hit_p, num("-9999", 16, 2, "crit")), lerp(hit_p, final, 0.5), final, final]
    seq[3]["panel"], seq[4]["panel"] = hp(55), hp(20)
    return seq, [150] * len(seq), 1


def m_makasero():  # 任せろ!: 胸をドンと叩き、翼を広げて鼻から炎
    final = stance(wing=75, squash=1.06, lh=(-1, -13), rh=(10, -14), expr="kira", fx=[fire(-70, 8, 0.4, n=12), EMBERS])
    thump = stance(wing=20, lh=(-1, -13), rh=(1, -12), expr="angry", fx=[impact(24, 22, 4)])
    seq = [final, stance(), thump, stance(), thump, final, final, final]
    return seq, [150] * len(seq), 1


def m_kakattekoi():  # かかってこい!: 吠えながら手招き。まわりに火の粉
    a = stance(wing=75, rh=(11, -14), lh=(-8, -12), expr="roar", fx=[roar(6, 10), EMBERS])
    b = stance(wing=60, rh=(9, -18), lh=(-8, -12), expr="roar", fx=[roar(8), EMBERS])
    return [a, b, a, b], [200] * 4, 2


def m_yoroshiku():  # よろしく!: 翼を広げてから、かぎ爪を胸にていねいにおじぎ
    final = stance(bow=5, squash=0.9, wing=60, lh=(-2, -9), rh=(2, -9), expr="calm", fx=[spr("sparkle", 46, 4)])
    seq = [final, stance(), stance(wing=80, lh=(-9, -14), rh=(9, -14), expr="smile"), lerp(stance(wing=80), final, 0.5),
           final, final, final]
    return seq, [150] * len(seq), 1


def m_matte():    # ちょっと待って: 慌てて手をばたばた、翼もばたばた
    a = stance(wing=70, lh=(-10, -18), rh=(10, -12), tilt=6, expr="surprised", fx=[spr("sweats", 36, 4), speed(4, 12, n=2)])
    b = stance(wing=-15, lh=(-10, -12), rh=(10, -18), tilt=-6, expr="surprised", fx=[spr("sweats", 36, 6), speed(56, 12, n=2, left=False)])
    return [a, b, a, b], [150] * 4, 3


def m_gohan():    # ごはんどうする?: 首をかしげて、おなかがグゥ〜
    a = stance(tilt=10, lh=(-3, -8), rh=(3, -8), wing=10, expr="normal", fx=[spr("question", 48, 4), NOSE])
    b = stance(tilt=-10, lh=(-3, -8), rh=(3, -8), wing=10, expr="worry", fx=[spr("question", 48, 6), NOSE])
    return [a, lerp(a, b, 0.5), b, lerp(b, a, 0.5)], [200] * 4, 2


MOTIONS = {
    "thanks": m_thanks, "morning": m_morning, "ok": m_ok, "roger": m_roger, "sorry": m_sorry,
    "otsukare": m_otsukare, "congrats": m_congrats, "goodnight": m_goodnight, "ittekimasu": m_ittekimasu,
    "tadaima": m_tadaima, "ganbare": m_ganbare, "sugoi": m_sugoi, "iine": m_iine, "sorena": m_sorena,
    "wakaru": m_wakaru, "nandeyanen": m_nandeyanen, "muri": m_muri, "ureshii": m_ureshii, "shock": m_shock,
    "makasero": m_makasero, "kakattekoi": m_kakattekoi, "yoroshiku": m_yoroshiku, "matte": m_matte, "gohan": m_gohan,
}
base.MOTIONS = MOTIONS


def main():
    ap = argparse.ArgumentParser(description="ドラゴンの動くスタンプ")
    ap.add_argument("-c", "--config", default="dragon_stamps.json")
    base.build(ap.parse_args().config)


if __name__ == "__main__":
    main()
