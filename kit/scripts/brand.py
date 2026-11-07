"""Tokens da marca Sem Pauta v3 + utilidades de movimento (easing/spring) compartilhadas."""
import json, math, os
from functools import lru_cache
from PIL import ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(ROOT, "brand", "tokens.json"), encoding="utf-8"))

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
C = {k: hex2rgb(v) for k, v in T["colors"].items()}

@lru_cache(maxsize=None)
def font(role, size):
    return ImageFont.truetype(os.path.join(ROOT, T["fonts"][role]), size)

# ---------------------------------------------------------------- movimento
def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def ease_out(u): u = clamp(u); return 1 - (1 - u) ** 3
def ease_in(u): u = clamp(u); return u ** 3
def ease_in_out(u): u = clamp(u); return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2

def spring(t, stiffness=None, damping=None, mass=None):
    """Mola amortecida 0→1 (t em segundos, t<0 → 0). Mesmo modelo do spring() do Remotion."""
    sp = T["motion"]["spring"]
    k = stiffness or sp["stiffness"]; c = damping or sp["damping"]; m = mass or sp["mass"]
    if t <= 0: return 0.0
    w0 = math.sqrt(k / m); z = c / (2 * math.sqrt(k * m))
    if z < 1:
        wd = w0 * math.sqrt(1 - z * z)
        return 1 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))
    return 1 - math.exp(-w0 * t) * (1 + w0 * t)
