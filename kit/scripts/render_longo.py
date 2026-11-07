#!/usr/bin/env python3
"""
Sem Pauta v3 — renderizador de VÍDEO LONGO (1920x1080, 30 fps, 8–15 min).

  python3 scripts/render_longo.py longos/<slug>.json [--tts edge|espeak] [--voice pt-BR-AntonioNeural]
                                  [--align whisperx] [--preview 5,60,120] [--jobs 4]

Saídas em output/: <slug>.mp4 · <slug>.srt (legenda para subir no YouTube) · <slug>_thumb.jpg (1280x720)
                  · <slug>.txt (título, descrição com CAPÍTULOS automáticos, hashtags)

Blocos ("type"):
  abertura        gancho frio: foto + manchete gigante (antes da vinheta)
  vinheta         vinheta 3D horizontal (1,8 s) — coloque logo após a abertura
  capitulo        cartão de capítulo (papel pautado + corte); vira marcador de capítulo no YouTube
  fato            foto + ficha (FATO · data · fonte) + manchete; opcional "pontos" (lista que aparece com a fala)
  documento       documento/manchete em recorte + marca-texto animado sobre "destaque" [x,y,w,h] (0–1)
  dado            número gigante com contagem
  grafico         barras ou linha animadas: "grafico": {"tipo": "barras"|"linha", "rotulos", "valores", "unidade", "destaque"}
  placar          votação: "sim", "nao", "abst", "resultado", "partidos": [{"sigla","sim","nao"}]
  checagem        afirmação + carimbo VERDADEIRO / FALSO / ENGANOSO / FALTA CONTEXTO + explicação
  linha_do_tempo  "eventos": [{"ano","texto"}] com câmera que percorre a linha
  leitura         NOSSA LEITURA · OPINIÃO (fundo papel) — opcional "pontos"
  outro_lado      O OUTRO LADO DIZ: citação atribuída
  encerramento    pergunta final + "amanhã no Sem Pauta"
  passo           tutorial: "PASSO 03 DE 07" + instrução + print da tela (celular/computador) com destaque de onde clicar
                  campos: headline, instrucao, image (print), tela ("celular"|"computador"), destaque [x,y,w,h], t_destaque, endereco,
                  borrar [[x,y,w,h], …] (borra dados pessoais no print)
  checklist       "Você vai precisar": "itens" que recebem um check em sequência com a fala
  alerta          faixa de atenção + ícone: golpes, prazos, erros comuns ("headline" + "pontos")
  tela_final      12–20 s com espaço para os elementos de tela final do YouTube (vídeo sugerido + inscrever)

Cada bloco narrado tem "narration" (+ "audio" opcional, recomendado: SUA VOZ gravada bloco a bloco).
Blocos sem narração usam "duracao" (s). Áudio, trilha, ducking e loudnorm iguais aos Shorts.
"""
import argparse, json, math, os, re, subprocess, sys, tempfile, glob
import multiprocessing as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from brand import C, T, ROOT, font, spring, ease_out, ease_in_out, clamp
import render_short as RS
from render_short import (dur, tts_edge, tts_espeak, align_whisperx, map_words, read_wav_mono, write_wav, beat_grid,
                          kb_frame, load_cover, line_images, place_lines, label, wipe_in, with_alpha, wrap_tokens, split_marked, rgba)

W, H, FPS = 1920, 1080, 30
MX, MY = 96, 64                      # margens seguras (5% / 6%)
MAXW = W - 2 * MX
PAD_END = 0.35
CUT_F = 10
K14 = math.tan(math.radians(14))
SR = RS.SR
MIN_TOTAL = 8 * 60

# ================================================================= camadas
def hgrad(strength=0.92, until=0.62):
    x = np.arange(W, dtype=np.float32) / W
    a = np.clip(1 - x / until, 0, 1) ** 1.3 * strength
    y = np.arange(H, dtype=np.float32) / H
    b = np.clip((y - 0.55) / 0.45, 0, 1) ** 1.4 * 0.85
    t = np.clip(1 - y / 0.18, 0, 1) ** 1.5 * 0.6
    al = np.maximum(a[None, :], np.maximum(b, t)[:, None])
    g = np.zeros((H, W, 4), np.uint8); g[..., :3] = C["carvao"]; g[..., 3] = (al * 255).astype(np.uint8)
    return Image.fromarray(g, "RGBA")

def ruled(color, alpha, step=72, y0=150):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for y in range(y0, H, step): d.line([(0, y), (W, y)], fill=rgba(color, alpha), width=2)
    return L

def text_block(text, f, maxw, fg, hl=None, lead=1.2):
    """Parágrafo (sem caixa-alta) com *destaques* em outra cor. Retorna imagem RGBA."""
    lines, lh = line_images(text, f, maxw, fg, hl or fg, None, False, lead, 12)
    im = Image.new("RGBA", (maxw + 20, lh * len(lines)), (0, 0, 0, 0))
    for i, l in enumerate(lines): im.alpha_composite(l, (0, i * lh))
    return im

def fmt_num(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def ts(t):  # 00:00
    t = int(t); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"

# ================================================================= preparação
TAGS = {"abertura": "AGORA", "fato": "FATO", "documento": "DOCUMENTO", "dado": "O NÚMERO", "grafico": "OS DADOS",
        "placar": "A VOTAÇÃO", "checagem": "CHECAGEM", "linha_do_tempo": "LINHA DO TEMPO", "leitura": "NOSSA LEITURA · OPINIÃO",
        "outro_lado": "O OUTRO LADO DIZ", "encerramento": "E VOCÊ?", "passo": "PASSO A PASSO", "checklist": "VOCÊ VAI PRECISAR",
        "alerta": "ATENÇÃO"}
VEREDITO = {"VERDADEIRO": C["papel"], "FALSO": C["corte"], "ENGANOSO": C["ambar"], "FALTA CONTEXTO": C["ambar"], "EXAGERADO": C["ambar"]}

def prep(s, G):
    tp = s["type"]
    img = os.path.join(ROOT, s["image"]) if s.get("image") else None
    if img and not os.path.exists(img):
        print(f"AVISO: imagem não encontrada ({s['image']}) no bloco {tp} — usando fundo liso", file=sys.stderr); img = None
    if tp not in ("capitulo", "vinheta", "tela_final", "passo", "checklist", "alerta"):
        s["_base"] = load_cover(img, W, H) if img else Image.new("RGB", (W, H), C["grafite"])
    s["_tag"] = label((s.get("tag") or TAGS.get(tp, "")).upper(), font("ficha", 28), C["papel"], C["corte"], 16, 9)
    if s.get("credit"): s["_cred"] = label(s["credit"].upper(), font("ficha2", 18), C["nevoa"], C["carvao"], 10, 6)
    hl = s.get("headline", "")
    if tp == "abertura":
        s["_lines"], s["_lh"] = line_images(hl, font("display", 150), 1150, C["papel"], C["corte"], None, True, 0.88, 4)
    elif tp == "capitulo":
        s["_lines"], s["_lh"] = line_images(s["titulo"], font("display", 200), 1250, C["carvao"], C["corte"], None, True, 0.86, 3)
        s["_num"] = label(f"CAPÍTULO {s['_cap']:02d}", font("ficha", 40), C["corte"], None, 0, 0)
        if s.get("subtitulo"): s["_sub"] = text_block(s["subtitulo"], font("corpo", 44), 1200, C["grafite"])
    elif tp == "fato":
        s["_lines"], s["_lh"] = line_images(hl, font("display2", 78), 1100, C["carvao"], C["papel"], C["corte"], True, 1.0, 3)
        s["_ficha"] = label((s.get("ficha") or "FATO").upper(), font("ficha", 24), C["carvao"], C["papel"], 14, 8)
    elif tp == "documento":
        s["_doc"] = Image.open(img).convert("RGBA") if img else Image.new("RGBA", (800, 1000), rgba(C["papel"]))
        s["_doc"].thumbnail((820, 860), Image.LANCZOS)
        s["_base"] = s["_base"].filter(ImageFilter.GaussianBlur(40))
        s["_lines"], s["_lh"] = line_images(hl, font("display", 104), 720, C["papel"], C["ambar"], None, True, 0.9, 5)
        if s.get("fonte"): s["_fonte"] = label(("FONTE: " + s["fonte"]).upper(), font("ficha2", 22), C["nevoa"], None, 0, 0)
    elif tp == "dado":
        s["_base"] = s["_base"].filter(ImageFilter.GaussianBlur(30))
        s["_lbl"] = text_block(s.get("label", ""), font("titulo", 56), 1300, C["papel"], C["ambar"], 1.15)
        if s.get("fonte"): s["_fonte"] = label(("FONTE: " + s["fonte"]).upper(), font("ficha2", 22), C["nevoa"], None, 0, 0)
    elif tp in ("grafico", "placar"):
        s["_lines"], s["_lh"] = line_images(hl, font("display", 92), MAXW, C["papel"], C["ambar"], None, True, 0.92, 2)
        if s.get("fonte"): s["_fonte"] = label(("FONTE: " + s["fonte"]).upper(), font("ficha2", 22), C["nevoa"], None, 0, 0)
    elif tp == "checagem":
        s["_claim"] = text_block("“" + s["afirmacao"] + "”", font("titulo", 62), 1080, C["papel"], C["ambar"], 1.18)
        s["_autor"] = label(("— " + s.get("autor", "")).upper(), font("ficha2", 26), C["nevoa"], None, 0, 0) if s.get("autor") else None
        s["_expl"] = text_block(s.get("explicacao", ""), font("corpo", 40), 1500, C["papel"], C["ambar"], 1.3)
        v = s["veredito"].upper(); col = VEREDITO.get(v, C["ambar"]); f = font("display", 120 if len(v) < 11 else 92)
        d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); bb = d0.textbbox((0, 0), v, font=f)
        st = Image.new("RGBA", (bb[2] - bb[0] + 80, bb[3] - bb[1] + 70), (0, 0, 0, 0)); ds = ImageDraw.Draw(st)
        ds.rectangle([4, 4, st.width - 5, st.height - 5], outline=rgba(col), width=10)
        ds.text((40 - bb[0], 35 - bb[1]), v, font=f, fill=rgba(col))
        s["_stamp"] = st.rotate(8, expand=True, resample=Image.BICUBIC)
        if s.get("fonte"): s["_fonte"] = label(("FONTE: " + s["fonte"]).upper(), font("ficha2", 22), C["nevoa"], None, 0, 0)
    elif tp == "linha_do_tempo":
        s["_ev"] = []
        for e in s["eventos"]:
            a = label(str(e["ano"]).upper(), font("display", 110), C["papel"], None, 0, 0)
            ac = label(str(e["ano"]).upper(), font("display", 110), C["corte"], None, 0, 0)
            tx = text_block(e["texto"], font("corpo", 36), 500, C["papel"], C["ambar"], 1.25)
            s["_ev"].append((a, ac, tx))
    elif tp == "leitura":
        s["_lines"], s["_lh"] = line_images(hl, font("display", 118), 1000, C["carvao"], C["corte"], None, True, 0.88, 4)
        if img:
            ph = ImageOps.fit(Image.open(img).convert("L"), (640, 760), Image.LANCZOS, centering=s.get("focus", [.5, .4]))
            duo = ImageOps.colorize(ImageOps.autocontrast(ph, 1), C["carvao"], C["papel"]).convert("RGBA")
            card = Image.new("RGBA", (duo.width + 24, duo.height + 24), rgba(C["carvao"])); card.alpha_composite(duo, (12, 12))
            s["_card"] = card.rotate(3, expand=True, resample=Image.BICUBIC)
    elif tp == "outro_lado":
        s["_base"] = ImageOps.grayscale(s["_base"]).convert("RGB")
        s["_quote"] = text_block(hl, font("titulo", 66), 1350, C["papel"], C["ambar"], 1.18)
        s["_autor"] = label(("— " + s.get("autor", "")).upper(), font("ficha2", 26), C["nevoa"], None, 0, 0) if s.get("autor") else None
    elif tp == "passo":
        s["_num"] = label(f"PASSO {s['_pn']:02d} DE {s['_ptot']:02d}", font("ficha", 34), C["corte"], None, 0, 0)
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display", 96), 720, C["papel"], C["ambar"], None, True, 0.92, 3)
        s["_txt"] = text_block(s.get("instrucao", ""), font("corpo", 38), 720, C["papel"], C["ambar"], 1.28)
        shot = Image.open(img).convert("RGBA") if img else Image.new("RGBA", (1280, 800), rgba(C["grafite"]))
        for bx, by, bw, bh in s.get("borrar", []):   # esconde dados pessoais do print (CPF, nome, saldo…)
            box = tuple(int(v) for v in (bx * shot.width, by * shot.height, (bx + bw) * shot.width, (by + bh) * shot.height))
            shot.paste(shot.crop(box).filter(ImageFilter.GaussianBlur(18)), box[:2])
        tela = s.get("tela") or ("celular" if shot.height > shot.width else "computador")
        if tela == "celular":
            shot = ImageOps.contain(shot, (460, 880), Image.LANCZOS); bz = 18
            dev = Image.new("RGBA", (shot.width + 2 * bz, shot.height + 2 * bz), (0, 0, 0, 0))
            ImageDraw.Draw(dev).rounded_rectangle([0, 0, dev.width - 1, dev.height - 1], radius=54, fill=rgba(C["grafite"]), outline=rgba(C["nevoa"], 120), width=3)
            m = Image.new("L", shot.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], radius=36, fill=255)
            dev.paste(shot, (bz, bz), m); off = (bz, bz)
        else:
            shot = ImageOps.contain(shot, (980, 640), Image.LANCZOS); bar = 44
            dev = Image.new("RGBA", (shot.width, shot.height + bar), rgba(C["grafite"])); dd = ImageDraw.Draw(dev)
            for k, cx in enumerate((26, 54, 82)): dd.ellipse([cx - 8, bar / 2 - 8, cx + 8, bar / 2 + 8], fill=rgba(C["nevoa"], 200 - 50 * k))
            if s.get("endereco"): dd.text((120, 10), s["endereco"], font=font("ficha2", 20), fill=rgba(C["nevoa"]))
            dev.alpha_composite(shot, (0, bar)); off = (0, bar)
        s["_dev"], s["_off"], s["_ss"], s["_tela"] = dev, off, shot.size, tela
    elif tp == "checklist":
        s["_lines"], s["_lh"] = line_images(s.get("headline", "Antes de começar"), font("display", 110), MAXW, C["papel"], C["ambar"], None, True, 0.9, 2)
        s["_items"] = [text_block(it, font("corpo", 44), 1500, C["papel"], C["ambar"], 1.15) for it in s["itens"]]
    elif tp == "alerta":
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display", 116), 1300, C["papel"], C["ambar"], None, True, 0.9, 3)
        tape = Image.new("RGBA", (W + 200, 54), rgba(C["carvao"])); dt = ImageDraw.Draw(tape)
        for x in range(-60, W + 200, 70): dt.polygon([(x, 54), (x + 35, 54), (x + 89, 0), (x + 54, 0)], fill=rgba(C["ambar"]))
        s["_tape"] = tape
        ic = Image.new("RGBA", (150, 136), (0, 0, 0, 0)); di = ImageDraw.Draw(ic)
        di.polygon([(75, 4), (146, 132), (4, 132)], outline=rgba(C["ambar"]), width=10)
        di.text((60, 30), "!", font=font("display", 96), fill=rgba(C["ambar"])); s["_icon"] = ic
    elif tp == "encerramento":
        s["_base"] = s["_base"].filter(ImageFilter.GaussianBlur(12))
        s["_lines"], s["_lh"] = line_images(hl, font("display", 140), 1300, C["papel"], C["ambar"], None, True, 0.88, 3)
        s["_pill"] = label("COMENTA AQUI ↓", font("ficha", 36), C["papel"], C["corte"], 26, 16)
        if s.get("amanha"):
            s["_amanha"] = label("AMANHÃ NO SEM PAUTA: " + s["amanha"].upper(), font("ficha", 30), C["carvao"], C["papel"], 22, 14)
    if s.get("pontos"):
        s["_pontos"] = [text_block(p, font("corpo", 42), 760, C["carvao"] if tp == "leitura" else C["papel"], C["corte"] if tp == "leitura" else C["ambar"], 1.18) for p in s["pontos"]]

# ================================================================= desenho
def draw_pontos(fr, s, lt, x, y, light=False):
    n = len(s["_pontos"]); sp = s.get("_speech", 4)
    d = ImageDraw.Draw(fr)
    for i, im in enumerate(s["_pontos"]):
        t_in = 0.4 + sp * i / max(n, 1) * 0.85
        u = spring(lt - t_in, 220, 20)
        if u <= 0: continue
        dx = int((1 - min(u, 1)) * 60)
        d.rectangle([x + dx, y + 16, x + dx + 18, y + 34], fill=rgba(C["corte"]))
        fr.alpha_composite(with_alpha(im, clamp(u)), (x + 40 + dx, y)); y += im.height + 26
    return y

def draw_scene(s, lt, G):
    tp = s["type"]; u = clamp(lt / s["_dur"]); light = False
    if tp == "vinheta":
        i = int(clamp(lt / s["_dur"], 0, 0.9999) * len(G["vin"]))
        return Image.open(G["vin"][i]).convert("RGBA"), False
    if tp == "tela_final":
        fr = G["papel_ruled_dark"].copy(); d = ImageDraw.Draw(fr)
        fr.alpha_composite(G["sym"], (MX, MY + 10))
        d.text((MX + 110, MY + 22), "ASSISTA A SEGUIR", font=font("ficha", 34), fill=rgba(C["nevoa"]))
        a = clamp(lt / 0.5)
        for bx in (MX, MX + 900):   # áreas para "vídeo sugerido" (o YouTube coloca os elementos por cima)
            d.rectangle([bx, 300, bx + 820, 300 + 461], outline=rgba(C["nevoa"], int(120 * a)), width=3)
        d.ellipse([W - MX - 260, 820, W - MX - 60, 1020], outline=rgba(C["corte"], int(200 * a)), width=4)
        d.text((MX, 850), "Fora da pauta. Dentro do fato.", font=font("titulo", 52), fill=rgba(C["papel"]))
        return fr, False
    if tp == "capitulo":
        fr = G["papel_ruled"].copy(); light = True
        # faixa de corte vermelha diagonal entrando da direita
        e = ease_out((lt - 0.0) / 0.45); d = ImageDraw.Draw(fr)
        cx = W - 330 + (1 - e) * 600; bw = 120
        d.polygon([(cx - bw / 2 + 300 * K14 * 4, -10), (cx + bw / 2 + 300 * K14 * 4, -10), (cx + bw / 2 - 300 * K14 * 0.3, H + 10), (cx - bw / 2 - 300 * K14 * 0.3, H + 10)], fill=rgba(C["corte"]))
        wipe_in(fr, s["_num"], MX, 270, lt, 0.1, 0.3)
        end = place_lines(fr, s["_lines"], MX - 6, 340, s["_lh"], lt, 0.15, 0.08)
        if s.get("_sub") is not None: fr.alpha_composite(with_alpha(s["_sub"], clamp((lt - 0.6) / 0.4)), (MX, end + 30))
        return fr, light
    if tp == "passo":
        fr = G["papel_ruled_dark"].copy(); d = ImageDraw.Draw(fr)
        wipe_in(fr, s["_num"], MX, 180, lt, 0.0, 0.25)
        end = place_lines(fr, s["_lines"], MX, 236, s["_lh"], lt, 0.08)
        fr.alpha_composite(with_alpha(s["_txt"], clamp((lt - 0.4) / 0.4)), (MX, end + 28))
        for i in range(s["_ptot"]):   # bolinhas de progresso dos passos
            cx = MX + 12 + i * 36; cy = H - 150
            if i < s["_pn"]: d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=rgba(C["corte"]))
            else: d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=rgba(C["nevoa"]), width=3)
        dev = s["_dev"]; du = spring(lt - 0.1, 170, 18)
        dx = W - MX - dev.width - (180 if s["_tela"] == "celular" else 0); dy = (H - dev.height) // 2 + 10 + int((1 - min(du, 1)) * 320)
        if du > 0: fr.alpha_composite(with_alpha(dev, clamp(du * 1.5)), (dx, dy))
        if s.get("destaque") and du > 0.5:
            hx, hy, hw, hh = s["destaque"]; sw, sh = s["_ss"]; ox, oy = s["_off"]
            hu = spring(lt - s.get("t_destaque", 1.2), 200, 14)
            if hu > 0:
                x0 = dx + ox + hx * sw; y0 = dy + oy + hy * sh; x1 = x0 + hw * sw; y1 = y0 + hh * sh
                ov = Image.new("RGBA", dev.size, rgba(C["carvao"], int(140 * clamp(hu)))); ImageDraw.Draw(ov).rectangle(
                    [x0 - dx - 6, y0 - dy - 6, x1 - dx + 6, y1 - dy + 6], fill=(0, 0, 0, 0))
                fr.alpha_composite(ov, (dx, dy))
                z = 1.6 - 0.6 * min(hu, 1.05); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                hw2, hh2 = (x1 - x0) / 2 * z + 10, (y1 - y0) / 2 * z + 10
                wpx = 7 + int(2 * math.sin(max(0, lt - s.get("t_destaque", 1.2) - 0.6) * 2 * math.pi * 1.4))
                d.rounded_rectangle([cx - hw2, cy - hh2, cx + hw2, cy + hh2], radius=14, outline=rgba(C["ambar"]), width=wpx)
        return fr, False
    if tp == "checklist":
        fr = G["papel_ruled_dark"].copy(); d = ImageDraw.Draw(fr)
        wipe_in(fr, s["_tag"], MX, 160, lt, 0.0, 0.2)
        y = place_lines(fr, s["_lines"], MX, 220, s["_lh"], lt, 0.05) + 40
        n = len(s["_items"])
        for i, im in enumerate(s["_items"]):
            ti = 0.5 + s["_speech"] * i / max(n, 1) * 0.85
            a = clamp((lt - ti + 0.25) / 0.3)
            if a <= 0: y += im.height + 30; continue
            d.rounded_rectangle([MX, y + 4, MX + 48, y + 52], radius=8, outline=rgba(C["papel"], int(255 * a)), width=4)
            cu = ease_out((lt - ti) / 0.25)
            if cu > 0:   # o "check" é desenhado como um traço
                p1, p2, p3 = (MX + 10, y + 28), (MX + 21, y + 41), (MX + 42, y + 12)
                pts = [p1, (p1[0] + (p2[0] - p1[0]) * min(1, cu * 2), p1[1] + (p2[1] - p1[1]) * min(1, cu * 2))]
                if cu > 0.5: pts.append((p2[0] + (p3[0] - p2[0]) * (cu - 0.5) * 2, p2[1] + (p3[1] - p2[1]) * (cu - 0.5) * 2))
                d.line(pts, fill=rgba(C["corte"]), width=9, joint="curve")
            fr.alpha_composite(with_alpha(im, a), (MX + 80, y)); y += im.height + 30
        return fr, False
    if tp == "alerta":
        fr = G["papel_ruled_dark"].copy()
        off = int((lt * 60) % 70); fr.alpha_composite(s["_tape"].crop((off, 0, off + W, 54)), (0, 112))
        iu = spring(lt - 0.05, 260, 12)
        if iu > 0:
            ic = s["_icon"]; z = max(0.01, min(iu, 1.2)); ic2 = ic.resize((max(1, int(ic.width * z)), max(1, int(ic.height * z))), Image.BILINEAR)
            fr.alpha_composite(ic2, (MX + (ic.width - ic2.width) // 2, 230 + (ic.height - ic2.height) // 2))
        wipe_in(fr, s["_tag"], MX + 180, 250, lt, 0.1, 0.2)
        end = place_lines(fr, s["_lines"], MX, 400, s["_lh"], lt, 0.15)
        if s.get("_pontos"): draw_pontos(fr, s, lt, MX, end + 40)
        return fr, False
    if tp == "leitura":
        fr = G["papel_ruled"].copy(); light = True
        if s.get("_card") is not None:
            cu = spring(lt - 0.05, 160, 18)
            if cu > 0: fr.alpha_composite(with_alpha(s["_card"], clamp(cu)), (W - MX - s["_card"].width, 150 + int((1 - min(cu, 1)) * 100)))
        wipe_in(fr, s["_tag"], MX, 170, lt, 0.1)
        end = place_lines(fr, s["_lines"], MX, 240, s["_lh"], lt, 0.18)
        if s.get("_pontos"): draw_pontos(fr, s, lt, MX, end + 40, True)
        return fr, light

    ph = kb_frame(s["_base"], u, s.get("motion", "in"), s.get("focus", [0.5, 0.4]), W, H).convert("RGBA")
    fr = ph; d = ImageDraw.Draw(fr)
    if tp == "abertura":
        fr.alpha_composite(G["hgrad"])
        nl = len(s["_lines"]); y0 = (H - nl * s["_lh"]) // 2 + 20
        wipe_in(fr, s["_tag"], MX, y0 - 70, lt, 0.0, 0.2)
        place_lines(fr, s["_lines"], MX - 6, y0, s["_lh"], lt, 0.04, 0.07)
    elif tp == "fato":
        fr.alpha_composite(G["hgrad_soft"])
        if s.get("_pontos"):
            fr.alpha_composite(G["panel"], (0, 0)); wipe_in(fr, s["_ficha"], MX, 170, lt, 0.05); wipe_in(fr, s["_tag"], MX, 120, lt, 0.0, 0.2)
            draw_pontos(fr, s, lt, MX, 250)
        else:
            nl = len(s["_lines"]); y0 = 930 - nl * s["_lh"]
            bw = int(ease_out((lt - 0.08) / 0.3) * (max(im.width for im in s["_lines"]) + 46))
            if bw > 0:
                d.rectangle([MX, y0 - 8, MX + bw, y0 + nl * s["_lh"] + 4], fill=rgba(C["papel"]))
                d.rectangle([MX, y0 - 8, MX + 10, y0 + nl * s["_lh"] + 4], fill=rgba(C["corte"]))
            wipe_in(fr, s["_tag"], MX, y0 - 60, lt, 0.0, 0.2)
            wipe_in(fr, s["_ficha"], MX + s["_tag"].width + 10, y0 - 60 + (s["_tag"].height - s["_ficha"].height) // 2, lt, 0.1)
            place_lines(fr, s["_lines"], MX + 30, y0, s["_lh"], lt, 0.16)
    elif tp == "documento":
        fr.alpha_composite(G["dim"]); fr.alpha_composite(G["ruled_dark"])
        doc = s["_doc"]
        hu = ease_in_out((lt - 0.9) / 0.8)
        if s.get("destaque") and hu > 0:
            dx, dy, dw, dh = s["destaque"]; ov = Image.new("RGBA", doc.size, (0, 0, 0, 0)); md = ImageDraw.Draw(ov)
            x0 = dx * doc.width; y0 = dy * doc.height
            md.rectangle([x0, y0, x0 + dw * doc.width * hu, y0 + dh * doc.height], fill=rgba(C["ambar"], 120))
            doc = doc.copy(); doc.alpha_composite(ov)
        cu = spring(lt - 0.05, 170, 18)
        card = Image.new("RGBA", (doc.width + 20, doc.height + 20), rgba(C["papel"])); card.alpha_composite(doc, (10, 10))
        card = card.rotate(-2, expand=True, resample=Image.BICUBIC)
        sh = Image.new("RGBA", card.size, (0, 0, 0, 0)); sh.putalpha(card.getchannel("A").point(lambda v: v * 0.5))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        cx = MX + 10; cy = (H - card.height) // 2 + int((1 - min(cu, 1)) * 500)
        if cu > 0: fr.alpha_composite(sh, (cx + 16, cy + 22)); fr.alpha_composite(card, (cx, cy))
        rx = 1060
        wipe_in(fr, s["_tag"], rx, 200, lt, 0.2)
        end = place_lines(fr, s["_lines"], rx, 260, s["_lh"], lt, 0.3)
        if s.get("_fonte") is not None: wipe_in(fr, s["_fonte"], rx, end + 30, lt, 0.8)
    elif tp == "dado":
        fr.alpha_composite(G["dim"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], MX, 180, lt, 0.0, 0.2)
        cu = ease_out((lt - 0.1) / 1.2); dec = s.get("decimals", 0)
        txt = f"{s.get('prefix', '')}{fmt_num(s.get('value', 0) * cu, dec)}{s.get('suffix', '')}"
        f = font("display", s.get("size", 330)); bb = d.textbbox((0, 0), txt, font=f)
        while bb[2] - bb[0] > MAXW and f.size > 140: f = font("display", f.size - 20); bb = d.textbbox((0, 0), txt, font=f)
        sc = spring(lt - 0.05, 260, 14)
        if sc > 0:
            ti = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
            ImageDraw.Draw(ti).text((10 - bb[0], 10 - bb[1]), txt, font=f, fill=rgba(C["papel"]))
            z = 0.75 + 0.25 * sc; ti2 = ti.resize((max(1, int(ti.width * z)), max(1, int(ti.height * z))), Image.BILINEAR)
            fr.alpha_composite(with_alpha(ti2, clamp(sc * 1.5)), (MX, 260 + (ti.height - ti2.height) // 2))
        yb = 260 + bb[3] - bb[1] + 50
        lw = int(ease_out((lt - 1.0) / 0.4) * 760)
        if lw > 0: d.rectangle([MX, yb, MX + lw, yb + 14], fill=rgba(C["corte"]))
        fr.alpha_composite(with_alpha(s["_lbl"], clamp((lt - 0.6) / 0.4)), (MX, yb + 50))
        if s.get("_fonte") is not None: wipe_in(fr, s["_fonte"], MX, H - 150, lt, 1.0)
    elif tp == "grafico":
        fr.alpha_composite(G["dim_full"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], MX, 120, lt, 0.0, 0.2)
        place_lines(fr, s["_lines"], MX, 170, s["_lh"], lt, 0.05)
        draw_chart(fr, s, lt)
        if s.get("_fonte") is not None: wipe_in(fr, s["_fonte"], MX, H - 112, lt, 0.8)
    elif tp == "placar":
        fr.alpha_composite(G["dim_full"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], MX, 120, lt, 0.0, 0.2)
        place_lines(fr, s["_lines"], MX, 170, s["_lh"], lt, 0.05)
        draw_placar(fr, s, lt)
        if s.get("_fonte") is not None: wipe_in(fr, s["_fonte"], MX, H - 128, lt, 0.8)
    elif tp == "checagem":
        fr.alpha_composite(G["dim_full"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], MX, 150, lt, 0.0, 0.2)
        fr.alpha_composite(with_alpha(s["_claim"], clamp((lt - 0.1) / 0.35)), (MX, 220))
        yy = 220 + s["_claim"].height + 16
        if s.get("_autor") is not None: wipe_in(fr, s["_autor"], MX, yy, lt, 0.4); yy += s["_autor"].height + 20
        st = s["_stamp"]; t_st = s.get("t_carimbo", min(2.2, s["_speech"] * 0.35))
        su = spring(lt - t_st, 300, 15)
        if su > 0:
            z = 1 + 0.9 * (1 - min(su, 1)) if su < 1 else 1 + 0.9 * (1 - su)
            st2 = st.resize((max(1, int(st.width * z)), max(1, int(st.height * z))), Image.BILINEAR)
            fr.alpha_composite(with_alpha(st2, clamp(su * 2)), (W - MX - 30 - st.width // 2 - st2.width // 2, 240 + st.height // 2 - st2.height // 2))
        ea = clamp((lt - t_st - 0.7) / 0.4)
        if ea > 0: fr.alpha_composite(with_alpha(s["_expl"], ea), (MX, max(yy + 40, 600)))
        if s.get("_fonte") is not None: wipe_in(fr, s["_fonte"], MX, H - 128, lt, t_st + 0.8)
    elif tp == "linha_do_tempo":
        fr.alpha_composite(G["dim_full"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], MX, 150, lt, 0.0, 0.2)
        ev = s["_ev"]; n = len(ev); sp = s["_speech"]
        times = [e.get("t", 0.3 + sp * i / n) for i, e in enumerate(s["eventos"])]
        k = max([i for i, tt in enumerate(times) if tt <= lt] or [0])
        pos = k - 1 + ease_in_out((lt - times[k]) / 0.7) if k > 0 else 0.0
        GAP = 640; ax_y = 560; cx0 = 700
        d.line([(0, ax_y), (W, ax_y)], fill=rgba(C["nevoa"], 160), width=4)
        for i, (a, ac, tx) in enumerate(ev):
            x = int(cx0 + (i - pos) * GAP)
            if x < -700 or x > W + 100: continue
            shown = lt >= times[i] - 0.15
            act = i == k
            r = 16 if act else 10
            d.ellipse([x - r, ax_y - r, x + r, ax_y + r], fill=rgba(C["corte"] if act else C["papel"]))
            if not shown: continue
            al = clamp((lt - times[i] + 0.15) / 0.35) * (1 if act or i < k else 0.5)
            al *= 1 if i >= k else 0.4
            im = ac if act else a
            fr.alpha_composite(with_alpha(im, al), (x - 10, ax_y - 40 - im.height))
            fr.alpha_composite(with_alpha(tx, al), (x - 10, ax_y + 40))
    elif tp == "outro_lado":
        fr.alpha_composite(G["hgrad"]); fr.alpha_composite(G["dim_soft"]); fr.alpha_composite(G["dim_soft"])
        qa = clamp((lt - 0.05) / 0.25)
        if qa > 0: fr.alpha_composite(with_alpha(G["quote"], qa), (MX - 14, 200))
        wipe_in(fr, s["_tag"], MX, 140, lt, 0.0)
        fr.alpha_composite(with_alpha(s["_quote"], clamp((lt - 0.2) / 0.4)), (MX, 450))
        if s.get("_autor") is not None: wipe_in(fr, s["_autor"], MX, 450 + s["_quote"].height + 30, lt, 0.6)
    elif tp == "encerramento":
        fr.alpha_composite(G["hgrad"]); fr.alpha_composite(G["dim_soft"])
        nl = len(s["_lines"]); y0 = 470 - nl * s["_lh"] // 2
        wipe_in(fr, s["_tag"], MX, y0 - 70, lt, 0.0)
        end = place_lines(fr, s["_lines"], MX - 4, y0, s["_lh"], lt, 0.05)
        pu = spring(lt - 0.6, 200, 12)
        if pu > 0:
            pulse = 1 + 0.03 * math.sin(max(0, lt - 1.2) * 2 * math.pi * 1.5); z = min(pu, 1.1) * pulse; p = s["_pill"]
            p2 = p.resize((max(1, int(p.width * z)), max(1, int(p.height * z))), Image.BILINEAR)
            fr.alpha_composite(p2, (MX, end + 40 + (p.height - p2.height) // 2))
        if s.get("_amanha") is not None: wipe_in(fr, s["_amanha"], W - MX - s["_amanha"].width, 860, lt, 1.2, 0.4)
    return fr, light

def draw_chart(fr, s, lt):
    g = s["grafico"]; vals = [float(v) for v in g["valores"]]; labs = g.get("rotulos", [""] * len(vals))
    dec = g.get("decimals", 0); un = g.get("unidade", ""); hi = g.get("destaque", -1)
    d = ImageDraw.Draw(fr); x0, x1, yt, yb = MX + 70, W - MX, 330, 850
    vmax = max(vals) * 1.12 if max(vals) > 0 else 1; vmin = min(0, min(vals))
    if g.get("tipo", "barras") == "linha": vmin = min(vals) - (max(vals) - min(vals)) * 0.15; vmax = max(vals) + (max(vals) - min(vals)) * 0.2
    Y = lambda v: yb - (v - vmin) / (vmax - vmin) * (yb - yt)
    fa = clamp(lt / 0.4)
    for k in range(5):   # grade
        v = vmin + (vmax - vmin) * k / 4; y = Y(v)
        d.line([(x0, y), (x1, y)], fill=rgba(C["nevoa"], int(55 * fa)), width=2)
        d.text((MX - 10, y - 14), fmt_num(v, dec), font=font("ficha2", 20), fill=rgba(C["nevoa"], int(200 * fa)))
    n = len(vals)
    if g.get("tipo", "barras") == "barras":
        slot = (x1 - x0) / n; bw = min(170, slot * 0.6)
        for i, v in enumerate(vals):
            cx = x0 + slot * (i + 0.5); gu = spring(lt - 0.3 - i * 0.09, 120, 16)
            if gu <= 0: continue
            top = yb - (Y(0) - Y(v)) * gu if v >= 0 else Y(0)
            col = C["corte"] if i == hi else C["papel"]
            d.rectangle([cx - bw / 2, top, cx + bw / 2, Y(0)], fill=rgba(col, 255 if i == hi or hi < 0 else 215))
            vt = fmt_num(v * min(gu, 1), dec) + un; fv = font("display", 52)
            d.text((cx - d.textlength(vt, font=fv) / 2, top - 64), vt, font=fv, fill=rgba(C["ambar"] if i == hi else C["papel"], int(255 * clamp(gu))))
            fl = font("ficha", 24); lb = str(labs[i]).upper()
            for j, ln in enumerate(wrap_tokens([(w, False) for w in lb.split()], fl, slot - 16)):
                t = " ".join(w for w, _ in ln); d.text((cx - d.textlength(t, font=fl) / 2, yb + 18 + j * 30), t, font=fl, fill=rgba(C["papel"], int(230 * fa)))
    else:
        xs = [x0 + (x1 - x0) * i / max(n - 1, 1) for i in range(n)]; ys = [Y(v) for v in vals]
        p = ease_in_out((lt - 0.3) / max(1.6, min(4.0, s["_speech"] * 0.5))) * (n - 1)
        k = int(p); fr_ = p - k
        pts = [(xs[i], ys[i]) for i in range(k + 1)]
        if k < n - 1: pts.append((xs[k] + (xs[k + 1] - xs[k]) * fr_, ys[k] + (ys[k + 1] - ys[k]) * fr_))
        if len(pts) > 1: d.line(pts, fill=rgba(C["corte"]), width=8, joint="curve")
        fl = font("ficha", 22); step = max(1, n // 8)
        for i in range(n):
            if i % step == 0 or i == n - 1:
                t = str(labs[i]).upper(); d.text((xs[i] - d.textlength(t, font=fl) / 2, yb + 18), t, font=fl, fill=rgba(C["papel"], int(220 * fa)))
            if i <= p + 1e-6:
                r = 12 if i in (hi, n - 1) else 7
                d.ellipse([xs[i] - r, ys[i] - r, xs[i] + r, ys[i] + r], fill=rgba(C["papel"] if i not in (hi,) else C["ambar"]))
                if i in (0, n - 1, hi):
                    vt = fmt_num(vals[i], dec) + un; fv = font("display", 56)
                    d.text((xs[i] - d.textlength(vt, font=fv) / 2, ys[i] - 78), vt, font=fv, fill=rgba(C["ambar"] if i == hi else C["papel"]))

def draw_placar(fr, s, lt):
    d = ImageDraw.Draw(fr); tot = max(1, s.get("sim", 0) + s.get("nao", 0) + s.get("abst", 0))
    cu = ease_out((lt - 0.2) / 1.3)
    cols = [("SIM", s.get("sim", 0), C["papel"]), ("NÃO", s.get("nao", 0), C["corte"]), ("ABSTENÇÃO", s.get("abst", 0), C["nevoa"])]
    for i, (nm, v, col) in enumerate(cols):
        x = MX + i * 420
        d.text((x, 330), nm, font=font("ficha", 30), fill=rgba(col))
        d.text((x - 4, 360), fmt_num(v * cu), font=font("display", 170), fill=rgba(col))
    y = 590; x = MX; wbar = W - 2 * MX
    d.rectangle([x, y, x + wbar, y + 46], fill=rgba(C["grafite"]))
    acc = 0
    for nm, v, col in cols:
        w = wbar * v / tot * cu; d.rectangle([x + acc, y, x + acc + w, y + 46], fill=rgba(col)); acc += w
    if s.get("quorum"):  # linha do mínimo necessário
        qx = x + wbar * s["quorum"] / tot; d.line([(qx, y - 16), (qx, y + 62)], fill=rgba(C["ambar"]), width=4)
        d.text((qx + 8, y - 44), f"MÍNIMO: {s['quorum']}", font=font("ficha", 22), fill=rgba(C["ambar"]))
    if s.get("resultado"):
        su = spring(lt - 1.6, 300, 15)
        if su > 0:
            r = s["resultado"].upper(); f = font("display", 110); col = C["papel"] if r.startswith("APROV") else C["corte"]
            st = Image.new("RGBA", (int(d.textlength(r, font=f)) + 70, 150), (0, 0, 0, 0)); ds = ImageDraw.Draw(st)
            ds.rectangle([4, 4, st.width - 5, st.height - 5], outline=rgba(col), width=9); ds.text((35, 8), r, font=f, fill=rgba(col))
            st = st.rotate(6, expand=True, resample=Image.BICUBIC); z = 1 + 0.8 * max(0, 1 - su)
            st2 = st.resize((int(st.width * z), int(st.height * z)), Image.BILINEAR)
            fr.alpha_composite(with_alpha(st2, clamp(su * 2)), (W - MX - st.width // 2 - st2.width // 2, 330 + st.height // 2 - st2.height // 2))
    ps = s.get("partidos", [])[:8]
    for i, p in enumerate(ps):
        col_i, row = i % 2, i // 2; px = MX + col_i * 880; py = 700 + row * 62
        a = clamp((lt - 1.0 - i * 0.08) / 0.3)
        if a <= 0: continue
        d.text((px, py), p["sigla"].upper(), font=font("ficha", 28), fill=rgba(C["papel"], int(255 * a)))
        bx = px + 170; bw = 600; t2 = max(1, p.get("sim", 0) + p.get("nao", 0))
        d.rectangle([bx, py + 6, bx + bw, py + 32], fill=rgba(C["grafite"]))
        ws = bw * p.get("sim", 0) / t2 * a; d.rectangle([bx, py + 6, bx + ws, py + 32], fill=rgba(C["papel"]))
        d.rectangle([bx + ws, py + 6, bx + ws + bw * p.get("nao", 0) / t2 * a, py + 32], fill=rgba(C["corte"]))
        d.text((bx + bw + 14, py + 2), f"{p.get('sim', 0)}×{p.get('nao', 0)}", font=font("ficha2", 24), fill=rgba(C["nevoa"], int(255 * a)))

def loudnorm_2pass(path, au):
    """Normalização EBU R128 em duas passadas (mede, depois aplica linear) — alvo exato em vídeos longos."""
    tgt = f"I={au['lufs']}:TP={au['true_peak']}:LRA=11"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"loudnorm={tgt}:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    out = path.replace(".wav", "_norm.wav")
    af = (f"loudnorm={tgt}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-af", af, "-ar", str(SR), out])
    return out

# ================================================================= legendas (SRT e na tela)
def build_cues(scenes):
    cues = []
    for s in scenes:
        ws, wt = s.get("_words") or [], s.get("_wt") or []
        cur, start = [], None
        for i, w in enumerate(ws):
            if not cur: start = s["_t0"] + wt[i]
            cur.append(w)
            txt = " ".join(cur)
            if len(txt) >= 70 or re.search(r"[.!?…]$", w) or i == len(ws) - 1:
                end = s["_t0"] + (wt[i + 1] if i + 1 < len(wt) else s["_speech"])
                cues.append((start, max(end, start + 0.8), txt)); cur = []
    return cues

def srt_time(t):
    ms = int(round(t * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

def wrap2(txt, n=42):
    if len(txt) <= n: return txt
    mid = len(txt) // 2; i = txt.rfind(" ", 0, mid + 8); i = i if i > 0 else mid
    return txt[:i].strip() + "\n" + txt[i:].strip()

# ================================================================= thumbnail
def thumbnail(spec, out):
    th = spec.get("thumb", {}); TW, TH = 1280, 720
    img = th.get("image") or next((s["image"] for s in spec["scenes"] if s.get("image")), None)
    if img and not os.path.exists(os.path.join(ROOT, img)): print(f"AVISO: imagem da thumbnail não encontrada ({img})", file=sys.stderr); img = None
    bg = load_cover(os.path.join(ROOT, img), TW, TH).crop((0, 0, TW, TH)).convert("RGBA") if img else Image.new("RGBA", (TW, TH), rgba(C["grafite"]))
    x = np.arange(TW, dtype=np.float32) / TW; a = (np.clip(1 - (x - 0.42) / 0.38, 0, 1) ** 1.2 * 0.96 * 255).astype(np.uint8)
    g = np.zeros((TH, TW, 4), np.uint8); g[..., :3] = C["carvao"]; g[..., 3] = a[None, :]; bg.alpha_composite(Image.fromarray(g, "RGBA"))
    q = label(spec.get("quadro", "SEM PAUTA").upper(), font("ficha", 34), C["papel"], C["corte"], 18, 10); bg.alpha_composite(q, (48, 48))
    lines, lh = line_images(th.get("texto", spec.get("title", "")), font("display", th.get("tamanho", 150)), 820, C["papel"], C["ambar"], None, True, 0.86, 4)
    y = (TH - lh * len(lines)) // 2 + 30
    for l in lines: bg.alpha_composite(l, (44, y)); y += lh
    sym = Image.open(os.path.join(ROOT, "brand/logo/simbolo_1024.png")).convert("RGBA").resize((110, 110), Image.LANCZOS)
    bg.alpha_composite(sym, (TW - 110 - 40, TH - 110 - 40))
    bg.convert("RGB").save(out, quality=92)

# ================================================================= renderização paralela
_CTX = {}
def frame_at(t):
    scenes, G, bounds = _CTX["scenes"], _CTX["G"], _CTX["bounds"]
    idx = max([i for i, s in enumerate(scenes) if s["_t0"] <= t + 1e-9] or [0]); s = scenes[idx]
    fr, light = draw_scene(s, t - s["_t0"], G)
    for bi, b in bounds:
        fu = (t - b) * FPS + CUT_F / 2
        if 0 <= fu < CUT_F:
            prev, nxt = scenes[bi - 1], scenes[bi]
            A, _ = draw_scene(prev, t - prev["_t0"], G); B, light = draw_scene(nxt, max(t - nxt["_t0"], -0.2), G)
            e = ease_in_out(fu / (CUT_F - 1)); edge = -G["BAND"] + e * (G["DMAX"] + 2 * G["BAND"])
            a = np.asarray(A.convert("RGB")); bb = np.asarray(B.convert("RGB")); diag = G["diag"]
            out = np.where((diag < edge - G["BAND"] / 2)[..., None], bb, a).copy()
            out[(diag >= edge - G["BAND"] / 2) & (diag < edge + G["BAND"] / 2)] = C["corte"]
            fr = Image.fromarray(out).convert("RGBA"); s = nxt if fu >= CUT_F / 2 else prev
    if s["type"] not in ("vinheta", "tela_final"):
        d = ImageDraw.Draw(fr)
        fr.alpha_composite(G["chip"], (MX, 40))
        cap = _CTX["chap_at"](t)
        if cap and s["type"] != "capitulo":
            lb = G["caplabels"][cap]; fr.alpha_composite(lb, (W - MX - lb.width, 46))
        if s.get("_cred") is not None: fr.alpha_composite(s["_cred"], (MX, H - 62))
        if _CTX["legendas"] and s.get("_words"):
            cue = next((c for c in _CTX["cues"] if c[0] <= t < c[1]), None)
            if cue: draw_onscreen_caption(fr, cue[2])
        # barra de progresso por capítulo
        tot = _CTX["total"]; y = H - 14
        d.rectangle([0, y, W, H], fill=rgba(C["carvao"] if not light else C["papel"], 200))
        d.rectangle([0, y + 4, W * t / tot, H - 4], fill=rgba(C["corte"]))
        for c0 in _CTX["chap_t"]: d.rectangle([W * c0 / tot - 2, y, W * c0 / tot + 2, H], fill=rgba(C["papel"] if not light else C["carvao"]))
    return fr.convert("RGB")

_ocap = {}
def draw_onscreen_caption(fr, txt):
    if txt not in _ocap:
        f = font("corpo", 42); lines = wrap2(txt, 46).split("\n"); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        wmax = int(max(d0.textlength(l, font=f) for l in lines)) + 40
        im = Image.new("RGBA", (wmax, 58 * len(lines) + 24), rgba(C["carvao"], 200)); d = ImageDraw.Draw(im)
        for i, l in enumerate(lines): d.text(((wmax - d.textlength(l, font=f)) / 2, 10 + i * 58), l, font=f, fill=rgba(C["papel"]))
        _ocap[txt] = im
    im = _ocap[txt]; fr.alpha_composite(im, ((W - im.width) // 2, H - 110 - im.height))

def render_range(args):
    a, b, path = args
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-g", "60", path], stdin=subprocess.PIPE)
    for n in range(a, b): enc.stdin.write(frame_at(n / FPS).tobytes())
    enc.stdin.close(); enc.wait(); return path

# ================================================================= principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--tts", choices=["edge", "espeak"]); ap.add_argument("--voice", default="pt-BR-AntonioNeural")
    ap.add_argument("--align", choices=["whisperx"]); ap.add_argument("--preview"); ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8")); slug = spec["slug"]; tmp = tempfile.mkdtemp(prefix="spL_"); scenes = spec["scenes"]

    # 1) narração e tempos
    for i, s in enumerate(scenes):
        s.setdefault("type", "fato")
        if s["type"] == "vinheta": s["_speech"] = 1.8; s["_audio"] = None; continue
        if not s.get("narration"):
            s["_speech"] = float(s.get("duracao", 3.2 if s["type"] == "capitulo" else 15 if s["type"] == "tela_final" else 4)); s["_audio"] = None; continue
        p = os.path.join(ROOT, s["audio"]) if s.get("audio") else None; timed = None
        if not p or not os.path.exists(p):
            if a.tts == "edge": p = os.path.join(tmp, f"s{i}.mp3"); timed = tts_edge(s["narration"], p, a.voice)
            elif a.tts == "espeak": p = os.path.join(tmp, f"s{i}.wav"); tts_espeak(s["narration"], p)
            else: sys.exit(f"bloco {i + 1} ({s['type']}): sem áudio. Grave e informe 'audio', ou use --tts edge")
        if s.get("words_json"): timed = json.load(open(os.path.join(ROOT, s["words_json"])))
        elif timed is None and a.align == "whisperx": timed = align_whisperx(p)
        s["_audio"] = p; s["_speech"] = dur(p)
        s["_words"], s["_wt"] = map_words(s["narration"], timed, s["_speech"])

    music = os.path.join(ROOT, spec["music"]) if spec.get("music") else None
    beats = beat_grid(music) if music and os.path.exists(music) else None
    t0 = 0.0; cap_n = 0; chapters = []
    for s in scenes:
        s["_t0"] = t0
        if s["type"] == "capitulo":
            cap_n += 1; s["_cap"] = cap_n; chapters.append((t0, cap_n, s["titulo"]))
        end = t0 + s["_speech"] + (PAD_END if s.get("narration") else 0)
        if beats is not None and s["type"] in ("capitulo", "abertura"):
            nxt = beats[beats >= end - 0.05]
            if len(nxt) and nxt[0] - end < 0.5: end = float(nxt[0])
        s["_dur"] = end - t0; t0 = end
    total = t0
    if total < MIN_TOTAL: print(f"AVISO: {total / 60:.1f} min — abaixo do mínimo de 8 min. Aumente o roteiro.", file=sys.stderr)

    # 2) camadas globais
    G = {"hgrad": hgrad(), "hgrad_soft": hgrad(0.55, 0.45), "dim": Image.new("RGBA", (W, H), rgba(C["grafite"], 215)),
         "dim_full": Image.new("RGBA", (W, H), rgba(C["carvao"], 235)), "dim_soft": Image.new("RGBA", (W, H), rgba(C["carvao"], 80)),
         "ruled_dark": ruled(C["nevoa"], 30)}
    pr = Image.new("RGBA", (W, H), rgba(C["papel"])); pr.alpha_composite(ruled(C["nevoa"], 70)); G["papel_ruled"] = pr
    pd = Image.new("RGBA", (W, H), rgba(C["carvao"])); pd.alpha_composite(ruled(C["nevoa"], 26)); G["papel_ruled_dark"] = pd
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(panel).rectangle([0, 0, 980, H], fill=rgba(C["carvao"], 200)); G["panel"] = panel
    q = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); ImageDraw.Draw(q).text((0, -40), "“", font=font("display", 400), fill=rgba(C["corte"])); G["quote"] = q
    chip = Image.open(os.path.join(ROOT, "brand/logo/chip_sempauta.png")).convert("RGBA")
    G["chip"] = chip.resize((int(chip.width * .72), int(chip.height * .72)), Image.LANCZOS)
    G["sym"] = Image.open(os.path.join(ROOT, "brand/logo/simbolo_1024.png")).convert("RGBA").resize((86, 86), Image.LANCZOS)
    G["caplabels"] = {n: label(f"{n:02d} · {tit.replace('*', '')}".upper(), font("ficha", 22), C["papel"], C["carvao"], 12, 8) for _, n, tit in chapters}
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); G["diag"] = xx + (H - yy) * K14; G["DMAX"] = W + H * K14; G["BAND"] = 170
    vin = os.path.join(ROOT, "brand", "vinheta", "vinheta_1920x1080.mp4"); vdir = os.path.join(tmp, "vin"); os.makedirs(vdir)
    if any(s["type"] == "vinheta" for s in scenes):
        subprocess.check_call(["ffmpeg", "-loglevel", "error", "-i", vin, "-q:v", "2", os.path.join(vdir, "f_%04d.jpg")])
    G["vin"] = sorted(glob.glob(os.path.join(vdir, "*.jpg")))
    pss = [x for x in scenes if x["type"] == "passo"]
    for k, x in enumerate(pss, 1): x["_pn"], x["_ptot"] = k, len(pss)
    for s in scenes: prep(s, G)
    bounds = [(i, s["_t0"]) for i, s in enumerate(scenes) if i > 0 and s["type"] not in ("vinheta", "tela_final") and scenes[i - 1]["type"] != "vinheta"]
    chap_t = [c[0] for c in chapters]
    def chap_at(t):
        c = [n for t0_, n, _ in chapters if t0_ <= t]; return c[-1] if c else None
    cues = build_cues([s for s in scenes if s.get("_words")])
    _CTX.update(scenes=scenes, G=G, bounds=bounds, total=total, chap_t=chap_t, chap_at=chap_at, cues=cues, legendas=spec.get("legendas_na_tela", False))

    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True); os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    if a.preview:
        tlist = [sc["_t0"] + min(sc["_dur"] * 0.8, 5.5) for sc in scenes] if a.preview == "blocos" else [float(x) for x in a.preview.split(",")]
        for tt in tlist:
            p = os.path.join(ROOT, "preview", f"{slug}_{float(tt):06.1f}s.png"); frame_at(float(tt)).save(p); print("preview", p)
        thumbnail(spec, os.path.join(ROOT, "preview", f"{slug}_thumb.jpg")); return

    out = a.out or os.path.join(ROOT, "output", f"{slug}.mp4")
    # 3) vídeo em paralelo (pedaços de ~20 s) + concat
    nfr = int(round(total * FPS)); step = 600
    parts = [(i, min(i + step, nfr), os.path.join(tmp, f"part_{i:07d}.mp4")) for i in range(0, nfr, step)]
    print(f"renderizando {nfr} quadros ({total / 60:.1f} min) em {len(parts)} partes, {a.jobs} processos…", file=sys.stderr)
    with mp.get_context("fork").Pool(a.jobs) as pool:
        for k, _ in enumerate(pool.imap(render_range, parts)): print(f"  parte {k + 1}/{len(parts)}", file=sys.stderr)
    lst = os.path.join(tmp, "parts.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for _, _, p in parts))
    vid = os.path.join(tmp, "v.mp4"); subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid])

    # 4) áudio
    N = int((total + 1) * SR); narr = np.zeros(N, np.float32); sfx = np.zeros(N, np.float32)
    def put(buf, x, at, g=1.0):
        i = int(at * SR); j = min(N, i + len(x))
        if i < N: buf[i:j] += x[:j - i] * g
    S = {k: read_wav_mono(os.path.join(ROOT, "brand", "sfx", f"{k}.wav")) for k in ("corte", "impacto", "tique", "vinheta")}
    for s in scenes:
        if s.get("_audio"): put(narr, read_wav_mono(s["_audio"]), s["_t0"])
        if s["type"] == "vinheta": put(sfx, S["vinheta"], s["_t0"], 0.9)
        if s["type"] in ("abertura", "capitulo", "dado"): put(sfx, S["impacto"], s["_t0"] + 0.02, 0.4)
        if s["type"] == "dado":
            for k in range(8): put(sfx, S["tique"], s["_t0"] + 0.1 + 1.2 * (1 - (1 - k / 8) ** (1 / 3)), 0.28)
        if s["type"] == "checagem": put(sfx, S["impacto"], s["_t0"] + s.get("t_carimbo", min(2.2, s["_speech"] * 0.35)), 0.5)
        if s["type"] == "placar" and s.get("resultado"): put(sfx, S["impacto"], s["_t0"] + 1.6, 0.45)
        if s["type"] == "alerta": put(sfx, S["impacto"], s["_t0"] + 0.05, 0.4)
        if s["type"] == "passo" and s.get("destaque"): put(sfx, S["tique"], s["_t0"] + s.get("t_destaque", 1.2), 0.5)
        if s["type"] == "checklist":
            for i in range(len(s["itens"])): put(sfx, S["tique"], s["_t0"] + 0.5 + s["_speech"] * i / len(s["itens"]) * 0.85, 0.4)
    for _, b in bounds: put(sfx, S["corte"], b - 0.26, 0.45)
    nw, sw = os.path.join(tmp, "narr.wav"), os.path.join(tmp, "sfx.wav"); write_wav(nw, narr); write_wav(sw, sfx)
    au = T["audio"]; norm = f"loudnorm=I={au['lufs']}:TP={au['true_peak']}:LRA=11"
    if music and os.path.exists(music):
        fc = (f"[2:a]volume=-21dB,aformat=channel_layouts=mono[m];[0:a]asplit=2[n][sc];"
              "[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=500[duck];"
              f"[n][duck][1:a]amix=inputs=3:duration=first:normalize=0,atrim=0:{total:.3f}[a]")
        ins = ["-i", nw, "-i", sw, "-stream_loop", "-1", "-i", music]
    else:
        fc = f"[0:a][1:a]amix=inputs=2:duration=first:normalize=0,atrim=0:{total:.3f}[a]"; ins = ["-i", nw, "-i", sw]
    mixed = os.path.join(tmp, "mix.wav")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-map", "[a]", "-ar", str(SR), "-ac", "2", mixed])
    mixed = loudnorm_2pass(mixed, au)
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mixed, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])

    # 5) SRT, thumbnail, metadados com capítulos
    base = out[:-4]
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i, (c0, c1, txt) in enumerate(cues, 1): f.write(f"{i}\n{srt_time(c0)} --> {srt_time(c1)}\n{wrap2(txt)}\n\n")
    thumbnail(spec, base + "_thumb.jpg")
    caps = ["00:00 Abertura"] + [f"{ts(t0_)} {tit.replace('*', '')}" for t0_, n, tit in chapters if t0_ >= 10]
    desc = spec.get("description", "").replace("{CAPITULOS}", "\n".join(caps))
    if "{CAPITULOS}" not in spec.get("description", ""): desc += "\n\nCapítulos:\n" + "\n".join(caps)
    open(base + ".txt", "w", encoding="utf-8").write(f"{spec.get('title', '')}\n\n{desc}\n\n{' '.join(spec.get('hashtags', []))}\n")
    print(f"OK {out} ({total / 60:.1f} min) + .srt + _thumb.jpg + .txt")

if __name__ == "__main__":
    main()
