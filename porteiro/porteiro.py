import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from kit import *
import char_simple

TOTAL = 134.0
T_CUT = 123.0
T_END = 127.0
SEED = 3171

CAPS = [
    (2.5, 6.5, "Era minha primeira semana no turno da madrugada."),
    (7.5, 11.5, "Prédio antigo, 16 andares. Quase ninguém saía depois da meia-noite."),
    (13.5, 17.5, "Às 02:40, o interfone da portaria tocou."),
    (18.5, 22.5, "Era o Sr. Alberto, do apartamento 1408."),
    (24.0, 28.5, "'Não deixe ninguém subir aqui hoje. Ninguém.'"),
    (29.5, 33.5, "A voz dele estava trêmula. Parecia apavorado."),
    (35.0, 39.0, "Perguntei se precisava de ajuda, mas ele desligou."),
    (41.5, 46.0, "Olhei as câmeras dos corredores. Tudo vazio."),
    (47.0, 51.0, "O silêncio da recepção chegava a dar sono."),
    (54.0, 58.5, "Até o relógio da mesa marcar *03:17*."),
    (59.5, 63.5, "O interfone da entrada externa chamou."),
    (65.0, 69.0, "'Boa noite. Esqueci a tag. Libera o 1408, por favor.'"),
    (70.5, 74.5, "Gelei na hora. Era exatamente a voz do Sr. Alberto."),
    (76.0, 80.5, "Olhei para o monitor da câmera do portão..."),
    (81.5, 86.0, "*Era o próprio Sr. Alberto parado lá fora.*"),
    (88.0, 92.5, "Interfonei para o apartamento 1408. Ele atendeu na hora."),
    (93.5, 98.0, "'Eu disse para não abrir! *Esse cara lá fora não sou eu!*'"),
    (99.5, 104.0, "Pelo portão, o homem olhou direto para a câmera:"),
    (105.0, 109.5, "'Ele está mentindo. *O que está lá em cima não é humano.*'"),
    (111.0, 115.0, "Um deles entrou pelo acesso de serviço e pegou o elevador."),
    (116.5, 122.0, "Abri a câmera da cabine... *e só um deles tinha reflexo no espelho.*"),
]

GLITCH = [13.5, 24.0, 54.0, 65.0, 81.5, 93.5, 105.0, 116.5, 122.8]
SHEET = [4.0, 15.0, 26.0, 44.0, 56.0, 67.0, 83.5, 95.5, 107.0, 119.0, 129.0]
post = make_post(GLITCH, T_CUT, 18.0, chaos=1.15)


def _scanlines(img, alpha=35):
    arr = np.array(img, dtype=np.int16)
    arr[::3, :, :] = np.clip(arr[::3, :, :] - alpha, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def _particles(draw, t, rng, n=28, color=(140, 165, 200)):
    for i in range(n):
        px = int((rng.random() * W + t * (8 + (i % 7) * 3)) % W)
        py = int((rng.random() * H - t * (12 + (i % 5) * 4)) % H)
        r = 1 + (i % 2)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=color)


def _cctv_hud(draw, cam_name, ts_str, rec_blink):
    f_hud = F("DejaVuSansMono-Bold.ttf", 28)
    tx(draw, 54, 52, cam_name, f_hud, (210, 225, 215), "lm")
    tx(draw, W - 54, 52, ts_str, f_hud, (210, 225, 215), "rm")
    if rec_blink:
        draw.ellipse([54, 92, 74, 112], fill=(220, 35, 35))
        tx(draw, 86, 102, "REC", f_hud, (220, 55, 55), "lm")
    m = 36
    L = 45
    c = (150, 175, 160)
    draw.line([(m, m), (m + L, m)], fill=c, width=3)
    draw.line([(m, m), (m, m + L)], fill=c, width=3)
    draw.line([(W - m, m), (W - m - L, m)], fill=c, width=3)
    draw.line([(W - m, m), (W - m, m + L)], fill=c, width=3)
    draw.line([(m, H - m), (m + L, H - m)], fill=c, width=3)
    draw.line([(m, H - m), (m, H - m - L)], fill=c, width=3)
    draw.line([(W - m, H - m), (W - m - L, H - m)], fill=c, width=3)
    draw.line([(W - m, H - m), (W - m, H - m - L)], fill=c, width=3)


def _scene_portaria(t, rng, tense=False):
    img = Image.new("RGB", (W, H), (10, 14, 24))
    draw = ImageDraw.Draw(img)

    for y in range(0, 1180, 8):
        v = int(14 + 12 * (1 - y / 1180))
        draw.rectangle([0, y, W, y + 8], fill=(v, v + 5, v + 16))

    draw.rectangle([90, 220, W - 90, 920], fill=(6, 9, 16), outline=(35, 45, 65), width=6)
    for px in (240, 540, 830):
        draw.ellipse([px - 45, 420, px + 45, 510], fill=(35, 32, 22))
        draw.ellipse([px - 14, 450, px + 14, 480], fill=(165, 140, 85))

    _particles(draw, t, rng, 24, (90, 115, 150))

    blink = (int(t * 2.3) % 7 == 0) and ((t * 2.3) % 1.0 < 0.18)
    expr = "surpresa" if tense else "neutro"
    mouth = 0.25 if (tense and int(t * 4) % 2 == 0) else 0.05
    look = -0.35 if tense else 0.15 * math.sin(t * 0.7)
    char = char_simple.draw("porteiro", scale=1.55, expr=expr, mouth=mouth, blink=blink, look=look, breath=t * 1.4)
    cx = W // 2 - char.width // 2 + int(8 * math.sin(t * 0.4))
    cy = 480
    img.paste(char, (cx, cy), char)

    draw.rectangle([0, 1160, W, H], fill=(18, 22, 32))
    draw.line([(0, 1160), (W, 1160)], fill=(55, 70, 95), width=5)

    draw.rectangle([70, 1020, 370, 1220], fill=(12, 18, 26), outline=(48, 62, 82), width=4)
    draw.rectangle([85, 1035, 355, 1205], fill=(20, 38, 46))
    tx(draw, 220, 1120, "CFTV-01", F("DejaVuSansMono-Bold.ttf", 24), (110, 210, 170), "mm")

    clock_txt = "03:17" if t >= 53.5 else "02:41"
    clock_col = (230, 55, 55) if t >= 53.5 else (110, 220, 150)
    draw.rectangle([740, 1090, 990, 1185], fill=(8, 10, 14), outline=(45, 50, 60), width=3)
    tx(draw, 865, 1138, clock_txt, F("DejaVuSansMono-Bold.ttf", 44), clock_col, "mm")

    return img


def _scene_interfone(t, rng, caller_label, status_label, alert=False):
    img = Image.new("RGB", (W, H), (12, 15, 22))
    draw = ImageDraw.Draw(img)

    for i in range(0, W, 40):
        draw.line([(i, 0), (i, H)], fill=(16, 20, 28), width=2)

    bx0, by0, bx1, by1 = 230, 310, 850, 1380
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=38, fill=(28, 33, 44), outline=(75, 88, 110), width=5)

    scr_bg = (55, 16, 20) if alert else (18, 38, 34)
    scr_fg = (255, 95, 95) if alert else (125, 240, 185)
    draw.rounded_rectangle([290, 380, 790, 620], radius=16, fill=scr_bg, outline=(90, 105, 125), width=3)

    tx(draw, 540, 445, caller_label, F("DejaVuSansMono-Bold.ttf", 42), scr_fg, "mm")
    pulse = int(180 + 75 * math.sin(t * 8.0))
    st_col = (pulse, 70, 70) if alert else (110, pulse, 170)
    tx(draw, 540, 535, status_label, F("DejaVuSansMono-Bold.ttf", 30), st_col, "mm")

    for k in range(18):
        ox = 325 + k * 25
        amp = int((18 + 26 * abs(math.sin(t * 11 + k * 0.6))) if (int(t * 3) % 2 == 0 or alert) else 6)
        draw.line([(ox, 585 - amp), (ox, 585 + amp)], fill=scr_fg, width=5)

    for gy in range(690, 960, 26):
        draw.line([(330, gy), (750, gy)], fill=(14, 17, 24), width=8)

    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
    f_key = F("DejaVuSans-Bold.ttf", 32)
    for idx, k in enumerate(keys):
        r, c = divmod(idx, 3)
        kx = 340 + c * 145
        ky = 1020 + r * 82
        fill_k = (140, 35, 35) if (alert and k in ("1", "4", "0", "8")) else (42, 49, 64)
        draw.rounded_rectangle([kx, ky, kx + 110, ky + 62], radius=12, fill=fill_k, outline=(95, 110, 130), width=2)
        tx(draw, kx + 55, ky + 31, k, f_key, (225, 232, 240), "mm")

    _particles(draw, t, rng, 18, (110, 130, 165))
    return img


def _scene_corredor_3d(t, rng):
    img = Image.new("RGB", (W, H), (8, 11, 18))
    draw = ImageDraw.Draw(img)

    for z in range(2, 26, 2):
        p1 = P(-2.2, -1.6, z)
        p2 = P(2.2, -1.6, z)
        p3 = P(2.2, 1.8, z)
        p4 = P(-2.2, 1.8, z)
        shade = max(12, 48 - z * 2)
        col = (shade, shade + 6, shade + 16)
        draw.polygon([p1, p2, p3, p4], outline=col)

    for z in (4, 10, 16, 22):
        l1 = P(-0.45, -1.55, z)
        l2 = P(0.45, -1.55, z + 1.2)
        flick = 40 if (z == 16 and int(t * 14) % 5 == 0) else 190
        ry0, ry1 = min(l1[1], l2[1] + 10), max(l1[1], l2[1] + 10)
        draw.rectangle([min(l1[0], l2[0]), ry0, max(l1[0], l2[0]), ry1], fill=(flick, flick + 10, min(255, flick + 25)))

    d1 = P(-0.65, -0.9, 18)
    d2 = P(0.65, 1.75, 18)
    draw.rectangle([min(d1[0], d2[0]), min(d1[1], d2[1]), max(d1[0], d2[0]), max(d1[1], d2[1])], fill=(26, 30, 40), outline=(70, 82, 105), width=3)
    tx(draw, (d1[0] + d2[0]) // 2, min(d1[1], d2[1]) + 45, "1408", F("DejaVuSans-Bold.ttf", 26), (170, 185, 205), "mm")

    _cctv_hud(draw, "CAM-04 | 14º ANDAR", "03:02:19", int(t * 2) % 2 == 0)
    img = _scanlines(img, 28)
    return img


def _scene_relogio(t, rng):
    img = Image.new("RGB", (W, H), (6, 8, 12))
    draw = ImageDraw.Draw(img)

    scale = 1.0 + 0.08 * ((t - 53.5) / 5.5)
    bw, bh = int(860 * scale), int(420 * scale)
    x0, y0 = W // 2 - bw // 2, H // 2 - bh // 2 - 60
    draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=34, fill=(14, 16, 22), outline=(65, 72, 85), width=6)
    draw.rounded_rectangle([x0 + 36, y0 + 36, x0 + bw - 36, y0 + bh - 36], radius=20, fill=(18, 8, 10))

    hora = "03:16" if t < 54.0 else "03:17"
    cor = (190, 60, 60) if t < 54.0 else (245, 42, 42)
    tx(draw, W // 2, y0 + bh // 2 - 12, hora, F("DejaVuSansMono-Bold.ttf", int(185 * scale)), cor, "mm")
    tx(draw, W // 2, y0 + bh - 72, "TERÇA-FEIRA  •  TURNO MADRUGADA", F("DejaVuSansMono-Bold.ttf", 24), (140, 95, 95), "mm")

    _particles(draw, t, rng, 30, (130, 70, 70))
    return img


def _scene_cam_portao(t, rng):
    img = Image.new("RGB", (W, H), (10, 16, 18))
    draw = ImageDraw.Draw(img)

    for y in range(0, H, 10):
        v = int(14 + 14 * (y / H))
        draw.rectangle([0, y, W, y + 10], fill=(v, v + 12, v + 14))

    for gx in range(80, W, 110):
        draw.rectangle([gx, 160, gx + 16, H - 140], fill=(22, 30, 32))

    blink = (int(t * 1.5) % 9 == 0) and ((t * 1.5) % 1.0 < 0.12)
    mouth = 0.35 if (99.5 <= t <= 109.5 and int(t * 5) % 2 == 0) else 0.02
    char = char_simple.draw("morador", scale=1.85, expr="neutro", mouth=mouth, blink=blink, look=0.0, breath=t * 0.6)

    r, g, b, a = char.split()
    char_ir = Image.merge("RGBA", (r.point(lambda p: int(p * 0.72)), g.point(lambda p: int(p * 0.92)), b.point(lambda p: int(p * 0.88)), a))

    cx = W // 2 - char_ir.width // 2
    cy = 430 + int(6 * math.sin(t * 0.8))
    img.paste(char_ir, (cx, cy), char_ir)

    _cctv_hud(draw, "CAM-01 | PORTÃO EXTERNO", "03:17:42", int(t * 2) % 2 == 0)
    img = _scanlines(img, 36)
    return img


def _scene_elevador_climax(t, rng):
    img = Image.new("RGB", (W, H), (10, 14, 20))
    draw = ImageDraw.Draw(img)

    draw.rectangle([80, 150, W - 80, H - 160], fill=(20, 26, 36), outline=(65, 78, 95), width=6)

    mx0, my0, mx1, my1 = 150, 230, W - 150, 1120
    draw.rectangle([mx0, my0, mx1, my1], fill=(14, 22, 32), outline=(95, 115, 140), width=5)

    ref = char_simple.draw("morador", scale=1.15, expr="brava", mouth=0.15, blink=False, look=0.2, breath=t)
    rr, rg, rb, ra = ref.split()
    ref_dim = Image.merge("RGBA", (
        rr.point(lambda p: int(p * 0.48)),
        rg.point(lambda p: int(p * 0.65)),
        rb.point(lambda p: int(p * 0.78)),
        ra.point(lambda p: int(p * 0.72))
    ))
    img.paste(ref_dim, (220, 420), ref_dim)

    draw.ellipse([170, 960, 490, 1650], fill=(12, 15, 22))
    draw.ellipse([245, 760, 415, 980], fill=(15, 19, 28))

    draw.ellipse([590, 960, 910, 1650], fill=(12, 15, 22))
    draw.ellipse([665, 760, 835, 980], fill=(15, 19, 28))

    if t > 117.5:
        draw.rectangle([560, 380, 870, 940], outline=(210, 45, 45), width=3)
        tx(draw, 715, 355, "SEM REFLEXO", F("DejaVuSansMono-Bold.ttf", 22), (225, 65, 65), "mm")

    _cctv_hud(draw, "CAM-09 | ELEVADOR SOCIAL", "03:19:08", True)
    img = _scanlines(img, 32)
    return img


def frame(t, rng):
    if t >= T_END:
        return endcard(
            "O interfone tocou de novo.",
            "Dessa vez era o reflexo pedindo para descer.",
            t - T_END
        )

    if t < 13.5:
        img = _scene_portaria(t, rng, tense=False)
    elif t < 39.5:
        img = _scene_interfone(t, rng, "APTO 1408 - SR. ALBERTO", "CHAMADA INTERNA ATIVA", alert=True)
    elif t < 53.5:
        img = _scene_corredor_3d(t, rng)
    elif t < 59.0:
        img = _scene_relogio(t, rng)
    elif t < 75.5:
        img = _scene_interfone(t, rng, "PORTÃO EXTERNO", "PEDIDO DE ACESSO: 1408", alert=False)
    elif t < 87.5:
        img = _scene_cam_portao(t, rng)
    elif t < 99.0:
        img = _scene_interfone(t, rng, "APTO 1408 - LINHA 1", "CONEXÃO SIMULTÂNEA", alert=True)
    elif t < 110.5:
        img = _scene_cam_portao(t, rng)
    else:
        img = _scene_elevador_climax(t, rng)

    z = 1.03 + 0.03 * math.sin(t * 0.35)
    nw, nh = int(W * z), int(H * z)
    img = img.resize((nw, nh), Image.BILINEAR)
    ox = min(max((nw - W) // 2 + int(6 * math.cos(t * 0.5)), 0), nw - W)
    oy = min(max((nh - H) // 2 + int(6 * math.sin(t * 0.4)), 0), nh - H)
    img = img.crop((ox, oy, ox + W, oy + H))

    captions(img, t, CAPS, y=1540)
    return img, "RGB"


def audio():
    A = Audio(TOTAL, SEED, T_CUT)
    A.bed()

    A.creak(5.0)
    A.step(10.0, 3)

    A.ding(13.5)
    A.static(13.5, 0.4)
    A.murmur(18.5, 4.0)
    A.murmur(24.0, 4.5)
    A.click(38.8)

    A.heart(42.0, 11.0, rate=68)
    A.hiss(48.0, 3.0)

    A.hit(54.0)
    A.static(54.0, 0.5)
    A.ding(59.5)
    A.murmur(65.0, 4.0)

    A.whoosh(81.0)
    A.hit(81.5)
    A.heart(82.0, 34.0, rate=112)

    A.ding(88.0)
    A.murmur(93.5, 4.5)
    A.static(99.5, 0.4)
    A.murmur(105.0, 4.5)

    A.whoosh(116.0)
    A.hit(116.5)
    A.tone(117.0, 5.5, freq=58)
    A.hit(122.5)

    A.cut(T_END)
    return A


if __name__ == "__main__":
    import kit, sys
    kit.main(sys.modules[__name__], "porteiro")
