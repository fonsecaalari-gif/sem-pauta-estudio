import math
from PIL import Image, ImageDraw

BASE_W, BASE_H = 360, 540

SKINS = {"porteiro": (222, 184, 152), "morador": (216, 178, 148)}
HAIRS = {"porteiro": (40, 34, 30), "morador": (168, 168, 172)}
SHIRTS = {"porteiro": (36, 52, 92), "morador": (86, 66, 52)}
PANTS = {"porteiro": (28, 32, 48), "morador": (48, 48, 58)}


def draw(name="porteiro", scale=1.0, expr="neutro", mouth=0.05, blink=False,
         look=0.0, breath=0.0):
    img = Image.new("RGBA", (BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin = SKINS.get(name, (220, 180, 150))
    hair = HAIRS.get(name, (40, 34, 30))
    shirt = SHIRTS.get(name, (50, 60, 90))
    pants = PANTS.get(name, (40, 40, 55))

    bob = int(4 * math.sin(breath * 2.0))
    cx = BASE_W // 2
    head_cy = 128 + bob

    # corpo
    d.rounded_rectangle([cx - 92, 208 + bob, cx + 92, 430], radius=42, fill=shirt + (255,))
    d.rounded_rectangle([cx - 60, 400, cx - 24, 540], radius=14, fill=pants + (255,))
    d.rounded_rectangle([cx + 24, 400, cx + 60, 540], radius=14, fill=pants + (255,))
    d.rounded_rectangle([cx - 128, 224 + bob, cx - 100, 380], radius=16, fill=shirt + (255,))
    d.rounded_rectangle([cx + 100, 224 + bob, cx + 128, 380], radius=16, fill=shirt + (255,))
    if name == "porteiro":
        d.rectangle([cx - 92, 300, cx + 92, 316], fill=(24, 34, 64, 255))
        d.ellipse([cx - 14, 310, cx + 14, 338], fill=(216, 176, 90, 255))

    # cabeca
    d.ellipse([cx - 82, head_cy - 82, cx + 82, head_cy + 82], fill=skin + (255,))
    # cabelo / chapeu
    if name == "porteiro":
        d.ellipse([cx - 86, head_cy - 100, cx + 86, head_cy - 10], fill=(28, 34, 52, 255))
        d.rectangle([cx - 96, head_cy - 34, cx + 96, head_cy - 20], fill=(20, 26, 42, 255))
    else:
        d.ellipse([cx - 84, head_cy - 88, cx + 84, head_cy - 8], fill=hair + (255,))
        d.ellipse([cx - 78, head_cy - 70, cx + 78, head_cy + 6], fill=skin + (255,))

    # sobrancelhas
    brow_y = head_cy - 34 if expr == "surpresa" else head_cy - 26
    if expr == "brava":
        d.line([(cx - 52, head_cy - 40), (cx - 16, head_cy - 28)], fill=hair + (255,), width=9)
        d.line([(cx + 16, head_cy - 28), (cx + 52, head_cy - 40)], fill=hair + (255,), width=9)
    else:
        d.line([(cx - 50, brow_y), (cx - 18, brow_y)], fill=hair + (255,), width=8)
        d.line([(cx + 18, brow_y), (cx + 50, brow_y)], fill=hair + (255,), width=8)

    # olhos
    look_px = int(look * 14)
    eye_dy = -6 if expr == "surpresa" else 0
    for ex in (cx - 38, cx + 38):
        if blink:
            d.line([(ex - 16, head_cy + eye_dy), (ex + 16, head_cy + eye_dy)], fill=(30, 26, 24, 255), width=7)
        else:
            eh = 22 if expr == "surpresa" else 16
            d.ellipse([ex - 16, head_cy - eh + eye_dy, ex + 16, head_cy + eh + eye_dy], fill=(245, 243, 240, 255))
            d.ellipse([ex - 7 + look_px, head_cy - 7 + eye_dy, ex + 7 + look_px, head_cy + 7 + eye_dy], fill=(28, 26, 30, 255))

    # nariz e boca
    d.line([(cx, head_cy + 6), (cx - 6, head_cy + 22)], fill=(190, 150, 122, 255), width=5)
    mh = max(4, int(6 + mouth * 44))
    mw = 40 if expr != "surpresa" else 30
    d.ellipse([cx - mw // 2, head_cy + 34, cx + mw // 2, head_cy + 34 + mh], fill=(60, 32, 32, 255))
    if name == "porteiro":
        d.rectangle([cx - 26, head_cy + 30, cx + 26, head_cy + 42], fill=(70, 60, 55, 255))

    if scale != 1.0:
        img = img.resize((int(BASE_W * scale), int(BASE_H * scale)), Image.BILINEAR)
    return img
