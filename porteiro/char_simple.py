import math
from PIL import Image, ImageDraw

BASE_W, BASE_H = 360, 540

CHARACTERS = {
    "vigia": {"skin": (157,151,132), "hair": (25,27,31), "shirt": (38,48,58), "pants": (25,29,38), "accent": (173,132,67)},
    "inquilina": {"skin": (191,171,153), "hair": (48,35,42), "shirt": (76,58,67), "pants": (43,42,53), "accent": (112,132,119)},
    "menino": {"skin": (183,157,139), "hair": (35,30,29), "shirt": (66,76,91), "pants": (39,43,55), "accent": (151,151,164)},
}
ALIASES = {"porteiro": "vigia", "morador": "inquilina"}


def draw(name="vigia", scale=1.0, expr="neutro", mouth=0.05, blink=False, look=0.0, breath=0.0):
    name = ALIASES.get(name, name)
    if name not in CHARACTERS:
        name = "vigia"
    c = CHARACTERS[name]
    skin, hair, shirt, pants, accent = c.values()
    img = Image.new("RGBA", (BASE_W, BASE_H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    bob = int(3 * math.sin(breath * 2))
    cx, hy = BASE_W // 2, 128 + bob

    d.rounded_rectangle([cx-62,402,cx-22,515], radius=13, fill=pants+(255,))
    d.rounded_rectangle([cx+22,402,cx+62,515], radius=13, fill=pants+(255,))
    d.rounded_rectangle([cx-72,500,cx-15,530], radius=10, fill=(19,20,25,255))
    d.rounded_rectangle([cx+15,500,cx+72,530], radius=10, fill=(19,20,25,255))
    d.rounded_rectangle([cx-91,205+bob,cx+91,430], radius=38, fill=shirt+(255,))
    d.rounded_rectangle([cx-126,224+bob,cx-96,382], radius=15, fill=shirt+(255,))
    d.rounded_rectangle([cx+96,224+bob,cx+126,382], radius=15, fill=shirt+(255,))
    d.ellipse([cx-130,365+bob,cx-94,402+bob], fill=skin+(255,))
    d.ellipse([cx+94,365+bob,cx+130,402+bob], fill=skin+(255,))

    if name == "vigia":
        d.rectangle([cx-90,292+bob,cx+90,307+bob], fill=(22,29,38,255))
        d.rounded_rectangle([cx+31,250+bob,cx+67,286+bob], radius=5, fill=accent+(255,))
        d.rounded_rectangle([cx-112,330+bob,cx-94,374+bob], radius=5, fill=(35,38,43,255))
        d.ellipse([cx-114,324+bob,cx-92,342+bob], fill=accent+(255,))
    elif name == "inquilina":
        d.polygon([(cx-90,218+bob),(cx-45,235+bob),(cx,340+bob),(cx+48,235+bob),(cx+90,218+bob),(cx+70,390),(cx-70,390)], fill=(48,39,48,255))
        d.ellipse([cx+37,263+bob,cx+61,287+bob], fill=accent+(255,))
    else:
        d.rounded_rectangle([cx-27,210+bob,cx+27,235+bob], radius=8, fill=accent+(255,))
        d.line([(cx,230+bob),(cx-18,263+bob),(cx,280+bob),(cx+18,263+bob),(cx,230+bob)], fill=(190,185,177,255), width=5)

    d.rectangle([cx-25,184+bob,cx+25,226+bob], fill=skin+(255,))
    d.ellipse([cx-82,hy-82,cx+82,hy+82], fill=skin+(255,))
    if name == "vigia":
        d.pieslice([cx-88,hy-102,cx+88,hy+25],180,360,fill=hair+(255,))
        d.rectangle([cx-91,hy-31,cx+91,hy-20], fill=(31,39,48,255))
    elif name == "inquilina":
        d.ellipse([cx-91,hy-99,cx+91,hy+76], fill=hair+(255,))
        d.ellipse([cx-73,hy-75,cx+73,hy+77], fill=skin+(255,))
        d.polygon([(cx-72,hy-45),(cx-50,hy-93),(cx+3,hy-78),(cx+66,hy-98),(cx+78,hy-34),(cx+47,hy-54),(cx-5,hy-36)], fill=hair+(255,))
        d.ellipse([cx-91,hy-10,cx-58,hy+91], fill=hair+(255,))
        d.ellipse([cx+58,hy-10,cx+91,hy+91], fill=hair+(255,))
    else:
        d.ellipse([cx-85,hy-96,cx+85,hy+15], fill=hair+(255,))
        d.polygon([(cx-82,hy-35),(cx-58,hy-93),(cx-12,hy-75),(cx+35,hy-97),(cx+83,hy-40),(cx+50,hy-56),(cx,hy-42)], fill=hair+(255,))

    brow_y = hy-34 if expr in ("surpresa","assustado") else hy-26
    if expr == "brava":
        d.line([(cx-52,hy-40),(cx-16,hy-28)], fill=hair+(255,), width=8)
        d.line([(cx+16,hy-28),(cx+52,hy-40)], fill=hair+(255,), width=8)
    else:
        d.line([(cx-50,brow_y),(cx-18,brow_y)], fill=hair+(255,), width=7)
        d.line([(cx+18,brow_y),(cx+50,brow_y)], fill=hair+(255,), width=7)
    for ex in (cx-38,cx+38):
        if blink:
            d.line([(ex-16,hy),(ex+16,hy)], fill=(30,26,24,255), width=6)
        else:
            eh = 22 if expr in ("surpresa","assustado") else 16
            d.ellipse([ex-16,hy-eh,ex+16,hy+eh], fill=(235,230,218,255))
            px = int(look*10)
            d.ellipse([ex-7+px,hy-7,ex+7+px,hy+7], fill=(22,22,25,255))
    d.line([(cx,hy+6),(cx-6,hy+22)], fill=(119,91,81,255), width=4)
    mh = max(4,min(25,int(6+mouth*35)))
    if expr in ("surpresa","assustado"):
        mh = max(mh,20)
    d.ellipse([cx-12,hy+34,cx+12,hy+34+mh], fill=(48,22,26,255))
    if name == "vigia":
        d.line([(cx+48,hy-8),(cx+58,hy+8),(cx+50,hy+20)], fill=(92,55,48,255), width=3)

    if scale != 1.0:
        img = img.resize((max(1,int(BASE_W*scale)),max(1,int(BASE_H*scale))), Image.Resampling.BILINEAR)
    return img


if __name__ == "__main__":
    for personagem in CHARACTERS:
        draw(personagem).save(f"{personagem}.png")
