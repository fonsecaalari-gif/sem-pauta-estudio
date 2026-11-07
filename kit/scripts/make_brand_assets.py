#!/usr/bin/env python3
"""
Gera os arquivos de identidade Sem Pauta v3 em brand/logo/ e brand/vinheta/.

  python3 scripts/make_brand_assets.py            # 2D (símbolo, avatar, chip, wordmarks, banner*)
  python3 scripts/make_brand_assets.py --vinheta  # também monta a vinheta MP4 a partir dos quadros 3D

* banner e vinheta usam os renders 3D de brand/3d/out/ (gere com: cd brand/3d && node render3d.mjs <modo>).
  Sem os renders, o banner sai em versão 2D.
"""
import argparse, glob, math, os, subprocess
from PIL import Image, ImageDraw, ImageFilter
from brand import C, T, ROOT, font, spring, ease_out, clamp

LOGO = os.path.join(ROOT, "brand", "logo"); OUT3D = os.path.join(ROOT, "brand", "3d", "out")
SLASH_DEG = 14  # inclinação do corte (igual à lâmina da cena 3D)

# ---------------------------------------------------------------- símbolo
def simbolo(size=1024, fundo=C["carvao"], linhas=C["papel"], ss=4):
    """Folha pautada riscada: 4 linhas de pauta, um corte vermelho diagonal; à direita do corte, sem pauta."""
    S = size * ss; im = Image.new("RGBA", (S, S), fundo + (255,) if fundo else (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    k = math.tan(math.radians(SLASH_DEG))
    m = S * 0.20; lw = S * 0.062; gap = (S - 2 * m - lw) / 3
    cx = S * 0.56
    for i in range(4):
        y = m + i * gap + lw / 2
        x_cut = cx + (S / 2 - y) * k            # x do corte nessa altura
        d.rounded_rectangle([m, y - lw / 2, x_cut - S * 0.035, y + lw / 2], radius=lw / 2, fill=linhas)
    # corte: faixa vermelha inclinada que atravessa o quadro
    bw = S * 0.115; top = (cx + (S / 2 + S * 0.05) * k, -S * 0.05); bot = (cx - (S / 2 + S * 0.05) * k, S * 1.05)
    d.polygon([(top[0] - bw / 2, top[1]), (top[0] + bw / 2, top[1]), (bot[0] + bw / 2, bot[1]), (bot[0] - bw / 2, bot[1])], fill=C["corte"])
    return im.resize((size, size), Image.LANCZOS)

def wordmark(height=220, cor=C["papel"], com_simbolo=True, fundo=None):
    f = font("display", int(height * 0.92))
    txt = "SEM PAUTA"
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bb = tmp.textbbox((0, 0), txt, font=f); tw = bb[2] - bb[0]; th = bb[3] - bb[1]
    sym = simbolo(height, fundo=C["carvao"] if cor == C["papel"] else C["carvao"]) if com_simbolo else None
    gap = int(height * 0.22) if sym else 0
    W = (height + gap if sym else 0) + tw + int(height * .06); H = height
    im = Image.new("RGBA", (W, H), (fundo + (255,)) if fundo else (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 0
    if sym: im.alpha_composite(sym, (0, 0)); x = height + gap
    d.text((x - bb[0], (H - th) / 2 - bb[1]), txt, font=f, fill=cor)
    return im

def chip(h=72):
    """Selo fixo do vídeo: símbolo + SEM PAUTA em tarja carvão."""
    sym = simbolo(h); f = font("display", int(h * .78))
    tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength("SEM PAUTA", font=f))
    im = Image.new("RGBA", (h + 18 + tw + 26, h), C["carvao"] + (235,)); d = ImageDraw.Draw(im)
    im.alpha_composite(sym, (0, 0))
    bb = d.textbbox((0, 0), "SEM PAUTA", font=f)
    d.text((h + 16, (h - (bb[3] - bb[1])) / 2 - bb[1]), "SEM PAUTA", font=f, fill=C["papel"])
    return im

def avatar(size=800):
    im = Image.new("RGBA", (size, size), C["carvao"] + (255,))
    s = simbolo(int(size * 0.86), fundo=None)
    im.alpha_composite(s, ((size - s.width) // 2, (size - s.height) // 2))
    return im

def cover(path, w, h):
    im = Image.open(path).convert("RGB"); s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = (im.width - w) // 2; y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h)).convert("RGBA")

def banner():
    W, H = 2560, 1440
    bg3d = os.path.join(OUT3D, "banner", "f_0000.png")
    if os.path.exists(bg3d): im = cover(bg3d, W, H)
    else:
        im = Image.new("RGBA", (W, H), C["carvao"] + (255,)); d = ImageDraw.Draw(im)
        for y in range(80, H, 56): d.line([(0, y), (W, y)], fill=C["grafite"], width=2)
    # escurece a área de texto à esquerda para leitura
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for x in range(W):
        a = int(250 * clamp(1 - (x - 1150) / 900) ** 1.2); ds.line([(x, 0), (x, H)], fill=C["carvao"] + (a,))
    im.alpha_composite(sh)
    # área segura do YouTube: 1546x423 centrada
    sx, sy = (W - 1546) // 2, (H - 423) // 2
    wm = wordmark(190); im.alpha_composite(wm, (sx, sy + 40))
    d = ImageDraw.Draw(im)
    d.text((sx + 4, sy + 270), "FORA DA PAUTA. DENTRO DO FATO.", font=font("ficha", 44), fill=C["ambar"])
    d.text((sx + 4, sy + 335), "Política e atualidades do Brasil em Shorts diários · fato separado de opinião", font=font("apoio", 34), fill=C["nevoa"])
    return im.convert("RGB")

# ---------------------------------------------------------------- vinheta (3D + tipografia)
def vinheta():
    frames = sorted(glob.glob(os.path.join(OUT3D, "sting", "f_*.png")))
    if not frames: raise SystemExit("faltam os quadros 3D: cd brand/3d && node render3d.mjs sting")
    W, H, FPS = 1080, 1920, 30
    tmp = os.path.join(ROOT, "brand", "vinheta", "_frames"); os.makedirs(tmp, exist_ok=True)
    wm = wordmark(170, com_simbolo=False)
    tag = Image.new("RGBA", (W, 80), (0, 0, 0, 0)); dt = ImageDraw.Draw(tag)
    ft = font("ficha", 38); txt = "FORA DA PAUTA. DENTRO DO FATO."
    dt.text(((W - dt.textlength(txt, font=ft)) / 2, 14), txt, font=ft, fill=C["ambar"])
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dg = ImageDraw.Draw(grad)
    for y in range(1100, H): dg.line([(0, y), (W, y)], fill=C["carvao"] + (int(245 * clamp((y - 1100) / 420) ** 1.2),))
    for i, p in enumerate(frames):
        fr = Image.open(p).convert("RGBA").resize((W, H)); fr.alpha_composite(grad)
        t = i / FPS
        # SEM PAUTA sobe de uma máscara a partir de 0,62 s (logo após o corte)
        u = spring(t - 0.62, 170, 18)
        box_y = 1390; dy = int((1 - min(u, 1)) * wm.height) if u < 1 else 0
        if u > 0:
            vis = wm.crop((0, 0, wm.width, wm.height - dy)) if dy > 0 else wm
            fr.alpha_composite(vis, ((W - wm.width) // 2, box_y + dy))
            # traço vermelho sob o nome
            lw = int(ease_out((t - 0.75) / 0.35) * 520)
            if lw > 0: ImageDraw.Draw(fr).rectangle([(W - 520) // 2, box_y + wm.height + 18, (W - 520) // 2 + lw, box_y + wm.height + 30], fill=C["corte"])
        a = clamp((t - 1.0) / 0.25)
        if a > 0:
            tg = tag.copy(); tg.putalpha(tg.getchannel("A").point(lambda v: int(v * a)))
            fr.alpha_composite(tg, (0, box_y + wm.height + 52))
        fr.convert("RGB").save(os.path.join(tmp, f"f_{i:04d}.png"))
    out = os.path.join(ROOT, "brand", "vinheta", "vinheta_1080x1920.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(tmp, "f_%04d.png"),
                           "-i", os.path.join(ROOT, "brand", "sfx", "vinheta.wav"), "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    print("ok", out)

def vinheta_h():
    """Vinheta horizontal 1920x1080 para vídeos longos (quadros 3D do modo sting_h)."""
    frames = sorted(glob.glob(os.path.join(OUT3D, "sting_h", "f_*.png")))
    if not frames: raise SystemExit("faltam os quadros 3D: cd brand/3d && node render3d.mjs sting_h")
    W, H, FPS = 1920, 1080, 30
    tmp = os.path.join(ROOT, "brand", "vinheta", "_frames_h"); os.makedirs(tmp, exist_ok=True)
    wm = wordmark(190, com_simbolo=False); x0 = 1060; y0 = 400
    ft = font("ficha", 36); txt = "FORA DA PAUTA. DENTRO DO FATO."
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for x in range(W): ds.line([(x, 0), (x, H)], fill=C["carvao"] + (int(238 * clamp((x - 860) / 220)),))
    for i, p in enumerate(frames):
        fr = Image.open(p).convert("RGBA"); t = i / FPS; fr.alpha_composite(sh)
        u = spring(t - 0.62, 170, 18)
        if u > 0:
            dy = int((1 - min(u, 1)) * wm.height) if u < 1 else 0
            if dy < wm.height:
                vis = wm.crop((0, 0, wm.width, wm.height - dy)) if dy > 0 else wm
                fr.alpha_composite(vis, (x0, y0 + dy))
            lw = int(ease_out((t - 0.75) / 0.35) * wm.width)
            if lw > 0: ImageDraw.Draw(fr).rectangle([x0, y0 + wm.height + 18, x0 + lw, y0 + wm.height + 30], fill=C["corte"])
        a = clamp((t - 1.0) / 0.25)
        if a > 0: ImageDraw.Draw(fr).text((x0 + 2, y0 + wm.height + 54), txt, font=ft, fill=C["ambar"] + (int(255 * a),))
        fr.convert("RGB").save(os.path.join(tmp, f"f_{i:04d}.png"))
    out = os.path.join(ROOT, "brand", "vinheta", "vinheta_1920x1080.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(tmp, "f_%04d.png"),
                           "-i", os.path.join(ROOT, "brand", "sfx", "vinheta.wav"), "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    import shutil; shutil.rmtree(tmp)
    print("ok", out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--vinheta", action="store_true"); ap.add_argument("--so-vinheta-h", action="store_true"); a = ap.parse_args()
    if a.so_vinheta_h: vinheta_h(); raise SystemExit
    os.makedirs(LOGO, exist_ok=True)
    simbolo(1024).save(os.path.join(LOGO, "simbolo_1024.png"))
    simbolo(1024, fundo=None).save(os.path.join(LOGO, "simbolo_transparente_1024.png"))
    avatar().convert("RGB").save(os.path.join(LOGO, "avatar_800.png"))
    chip().save(os.path.join(LOGO, "chip_sempauta.png"))
    wordmark(240).save(os.path.join(LOGO, "wordmark_fundo_escuro.png"))
    wordmark(240, cor=C["carvao"]).save(os.path.join(LOGO, "wordmark_fundo_claro.png"))
    banner().save(os.path.join(LOGO, "banner_youtube_2560x1440.png"))
    print("ok logos em", LOGO)
    if a.vinheta: vinheta(); vinheta_h()
