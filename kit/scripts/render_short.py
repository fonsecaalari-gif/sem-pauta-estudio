#!/usr/bin/env python3
"""
Sem Pauta v3 — renderizador do formato "O CORTE" (Shorts 1080x1920, 30 fps).

  python3 scripts/render_short.py specs/<slug>.json [--tts edge|espeak] [--voice pt-BR-AntonioNeural]
                                  [--align whisperx] [--preview 0,2.5,10]

Blocos (campo "type" de cada cena — ver templates/spec_exemplo.json):
  gancho      foto + manchete gigante condensada que sobe da máscara; batida grave
  fato        foto + ficha de dossiê (FATO · data · fonte) + manchete em tarja
  dado        número gigante com contagem + rótulo; fundo grafite pautado
  leitura     NOSSA LEITURA (opinião): fundo papel, foto em recorte — visualmente separado do fato
  outro_lado  O OUTRO LADO DIZ: foto em P&B, aspas, citação
  pergunta    pergunta final + selo COMENTA pulsando
Entre cenas: transição "corte" (faixa vermelha diagonal a 14°, igual ao símbolo) + som de lâmina.
Ao final: vinheta 3D de 1,8 s (brand/vinheta/vinheta_1080x1920.mp4), se "vinheta": true.

Tempo das palavras (legenda): edge-tts WordBoundary (exato) > WhisperX (--align whisperx) > proporcional.
Som: narração + trilha com ducking (sidechain) + efeitos; tudo normalizado a -14 LUFS.
Com "music", os cortes caem no tempo da trilha (beats detectados com librosa).
Requer: Pillow, numpy, ffmpeg. Opcional: edge-tts, librosa, whisperx.
"""
import argparse, asyncio, json, math, os, re, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from brand import C, T, ROOT, font, spring, ease_out, ease_in, ease_in_out, clamp

W, H, FPS = T["video"]["width"], T["video"]["height"], T["video"]["fps"]
SAFE = T["safe"]; L0 = SAFE["left"]; RMAX = W - SAFE["right"]; MAXW = RMAX - L0
PAD_END = 0.28
CUT_F = T["motion"]["corte_frames"]          # duração da transição em frames
K14 = math.tan(math.radians(14))
SR = 48000

def rgba(c, a=255): return tuple(c) + (a,)

# ================================================================= áudio
def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", path]).decode().strip())

def tts_edge(text, out, voice, rate="+5%"):
    """edge-tts com marcação de palavra (offsets em unidades de 100 ns)."""
    import edge_tts
    words = []
    async def run():
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        with open(out, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio": f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    words.append({"word": ch["text"], "start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7})
    asyncio.run(run())
    return words

def tts_espeak(text, out, voice="pt-br"):
    """Só para teste local (voz robótica). Em produção use edge-tts."""
    subprocess.check_call(["espeak-ng", "-v", voice, "-s", "168", "-w", out, text])
    return None

def align_whisperx(audio, lang="pt"):
    out = tempfile.mkdtemp(prefix="wx_")
    subprocess.check_call(["whisperx", audio, "--language", lang, "--model", "large-v3", "--output_format", "json",
                           "--output_dir", out, "--device", "cpu", "--compute_type", "int8"])
    js = json.load(open(os.path.join(out, os.path.splitext(os.path.basename(audio))[0] + ".json")))
    return [{"word": w["word"], "start": w["start"], "end": w["end"]} for s in js["segments"] for w in s.get("words", []) if "start" in w]

def map_words(narration, timed, speech):
    """Associa cada palavra do texto (com pontuação) ao tempo de início. Sem tempos: proporcional ao nº de letras."""
    words = narration.split()
    if timed:
        norm = lambda s: re.sub(r"[^\wÀ-ÿ]", "", s.lower())
        ts, j = [], 0
        for w in words:
            k = j
            while k < len(timed) and norm(timed[k]["word"]) != norm(w): k += 1
            if k < len(timed): ts.append(timed[k]["start"]); j = k + 1
            else: ts.append(ts[-1] + 0.25 if ts else 0.0)
        return words, ts
    n = sum(len(w) + 1 for w in words); acc, ts = 0, []
    for w in words: ts.append(speech * acc / n); acc += len(w) + 1
    return words, ts

def read_wav_mono(path):
    tmp = os.path.join(tempfile.mkdtemp(prefix="sp3a_"), "a.wav")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), tmp])
    with wave.open(tmp) as w: x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
    return x

def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes())

def beat_grid(music):
    try:
        import librosa
        y, sr = librosa.load(music, sr=22050)
        _, b = librosa.beat.beat_track(y=y, sr=sr)
        return librosa.frames_to_time(b, sr=sr)
    except Exception as e:
        print("aviso: sem librosa/beat —", e, file=sys.stderr); return None

# ================================================================= imagem
def load_cover(path, w=W, h=H, scale=1.0):
    im = Image.open(path).convert("RGB")
    s = max(w / im.width, h / im.height) * scale
    return im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)

def kb_frame(base, u, motion, focus, w=W, h=H):
    e = ease_in_out(u)
    z0, z1 = {"in": (1.0, 1.12), "out": (1.12, 1.0)}.get(motion, (1.05, 1.12))
    z = z0 + (z1 - z0) * e; vw, vh = w / z, h / z
    cx = focus[0] * base.width; cy = focus[1] * base.height
    if motion == "left": cx += (0.5 - e) * (base.width - vw) * 0.5
    if motion == "right": cx += (e - 0.5) * (base.width - vw) * 0.5
    x0 = min(max(cx - vw / 2, 0), base.width - vw); y0 = min(max(cy - vh / 2, 0), base.height - vh)
    return base.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + vw, y0 + vh))

def vgrad(top_a=0.75, top_h=460, bot_from=700, bot_a=0.95, color=C["carvao"]):
    y = np.arange(H, dtype=np.float32)
    top = np.clip(1 - y / top_h, 0, 1) ** 1.5 * top_a
    bot = np.clip((y - bot_from) / (H - bot_from - 250), 0, 1) ** 1.25 * bot_a
    a = (np.maximum(top, bot) * 255).astype(np.uint8)
    g = np.zeros((H, W, 4), np.uint8); g[..., :3] = color; g[..., 3] = a[:, None]
    return Image.fromarray(g, "RGBA")

def ruled_layer(color, alpha=40, step=86, y0=300):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for y in range(y0, H, step): d.line([(0, y), (W, y)], fill=rgba(color, alpha), width=3)
    return L

def with_alpha(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a))); return im

# ================================================================= tipografia
def split_marked(text):
    """'Quem *ganha* com isso' -> [('Quem',False),('ganha',True),...]"""
    out, hl = [], False
    for w in text.split():
        m = re.match(r"^(\*?)(.*?)(\*?)([.,:;!?…]*)$", w)
        if m.group(1): hl = True
        out.append((m.group(2) + m.group(4), hl))
        if m.group(3): hl = False
    return out

def wrap_tokens(toks, f, maxw, upper=False, d=ImageDraw.Draw(Image.new("RGB", (1, 1)))):
    lines, cur = [], []
    for w, hl in toks:
        s = w.upper() if upper else w
        cand = " ".join((x.upper() if upper else x) for x, _ in cur + [(w, hl)])
        if cur and d.textlength(cand, font=f) > maxw: lines.append(cur); cur = []
        cur.append((s, hl))
    if cur: lines.append(cur)
    return lines

def line_images(text, f, maxw, fg, hl_fg, hl_bg=None, upper=True, lead=1.0, max_lines=4):
    """Uma imagem RGBA por linha (para animar linha a linha). Destaque: cor do texto e/ou bloco atrás."""
    lines = wrap_tokens(split_marked(text), f, maxw, upper)[:max_lines]
    asc, desc = f.getmetrics(); lh = int((asc + desc) * lead)
    out = []
    for ln in lines:
        d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        wtot = int(sum(d0.textlength(w + " ", font=f) for w, _ in ln)) + 20
        im = Image.new("RGBA", (wtot, lh), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 0
        sp = d.textlength(" ", font=f)
        for w, hl in ln:
            tw = d.textlength(w, font=f)
            if hl and hl_bg is not None:
                d.rectangle([x - 8, int(lh * .10), x + tw + 8, int(lh * .94)], fill=rgba(hl_bg))
            d.text((x, int((lh - asc - desc) / 2)), w, font=f, fill=rgba(hl_fg if hl else fg))
            x += tw + sp
        out.append(im)
    return out, lh

def place_lines(fr, lines, x, y, lh, lt, start=0.0, stagger=0.07, rise=True):
    """Cada linha sobe de uma máscara (mola), com atraso escalonado."""
    for i, im in enumerate(lines):
        u = spring(lt - start - i * stagger, 200, 20)
        if u <= 0: continue
        yy = y + i * lh
        if rise:
            dy = int((1 - min(u, 1)) * lh)
            if dy >= lh: continue
            vis = im.crop((0, 0, im.width, lh - dy)) if dy > 0 else im
            fr.alpha_composite(vis, (int(x), int(yy + dy)))
        else:
            fr.alpha_composite(with_alpha(im, min(u, 1)), (int(x), int(yy)))
    return y + len(lines) * lh

def label(text, f, fg, bg, padx=18, pady=10):
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); bb = d0.textbbox((0, 0), text, font=f)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * padx, bb[3] - bb[1] + 2 * pady), rgba(bg) if bg else (0, 0, 0, 0))
    ImageDraw.Draw(im).text((padx - bb[0], pady - bb[1]), text, font=f, fill=rgba(fg)); return im

def wipe_in(fr, im, x, y, lt, start=0.0, dur=0.28):
    """Revela da esquerda para a direita (rótulos e fichas)."""
    u = ease_out((lt - start) / dur)
    if u <= 0: return
    w = max(1, int(im.width * u)); fr.alpha_composite(im.crop((0, 0, w, im.height)), (int(x), int(y)))

# ================================================================= legendas
def chunk_words(words, max_chars=16, max_words=3):
    chunks, cur = [], []
    for i, w in enumerate(words):
        cand = " ".join(words[j] for j in cur + [i])
        if cur and (len(cand) > max_chars or len(cur) >= max_words): chunks.append(cur); cur = []
        cur.append(i)
        if re.search(r"[.!?…:;]$", w): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return chunks

_cap = {}
def caption_img(words, chunk, active, light_bg=False):
    key = (id(words), tuple(chunk), active, light_bg)
    if key in _cap: return _cap[key]
    f = font("legenda", 74); d0 = ImageDraw.Draw(Image.new("RGB", (1, 1))); sp = d0.textlength(" ", font=f)
    toks = [(i, re.sub(r"[,;:]$", "", words[i]).upper()) for i in chunk]
    lines = [[]]
    for i, w in toks:
        trial = " ".join(x for _, x in lines[-1] + [(i, w)])
        if lines[-1] and d0.textlength(trial, font=f) > MAXW - 40: lines.append([])
        lines[-1].append((i, w))
    im = Image.new("RGBA", (W, 112 * len(lines) + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im); y = 10
    for ln in lines:
        tot = sum(d.textlength(w, font=f) for _, w in ln) + sp * (len(ln) - 1)
        x = L0 + (MAXW - tot) / 2
        for i, w in ln:
            tw = d.textlength(w, font=f)
            if i == active:
                bg = C["corte"] if light_bg else C["ambar"]; fg = C["papel"] if light_bg else C["carvao"]
                d.rectangle([x - 12, y + 8, x + tw + 12, y + 100], fill=rgba(bg))
                d.text((x, y), w, font=f, fill=rgba(fg))
            elif light_bg:
                d.text((x, y), w, font=f, fill=rgba(C["carvao"]))
            else:
                d.text((x, y), w, font=f, fill=rgba(C["papel"]), stroke_width=6, stroke_fill=rgba(C["carvao"]))
            x += tw + sp
        y += 112
    _cap[key] = im; return im

def draw_caption(fr, s, lt, light_bg=False, y=1150):
    ws, ts = s["_words"], s["_wt"]
    if lt < 0 or not ws: return
    wi = max([i for i, t in enumerate(ts) if t <= lt] or [0])
    ch = next(c for c in s["_chunks"] if c[0] <= wi <= c[-1])
    im = caption_img(ws, ch, wi, light_bg)
    u = spring(lt - ts[ch[0]], 320, 22)            # "pop" da entrada do bloco
    sc = 0.86 + 0.14 * min(u, 1.05)
    if abs(sc - 1) > 0.004:
        im2 = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
        fr.alpha_composite(with_alpha(im2, min(1, u * 1.6)), (int((W - im2.width) / 2), int(y + (im.height - im2.height) / 2)))
    else:
        fr.alpha_composite(im, (0, y))

# ================================================================= blocos (cenas)
TAGS = {"gancho": "URGENTE", "fato": "FATO", "dado": "O NÚMERO", "leitura": "NOSSA LEITURA · OPINIÃO",
        "outro_lado": "O OUTRO LADO DIZ", "pergunta": "E VOCÊ?", "viral": "VIRALIZOU"}

def prep_scene(s, spec):
    tp = s.setdefault("type", "fato")
    img = os.path.join(ROOT, s["image"]) if s.get("image") else None
    s["_base"] = load_cover(img) if img else Image.new("RGB", (W, H), C["grafite"])
    tag = (s.get("tag") or TAGS[tp]).upper()
    s["_tag"] = label(tag, font("ficha", 34), C["papel"], C["corte"])
    if s.get("credit"): s["_cred"] = label(s["credit"].upper(), font("ficha2", 22), C["nevoa"], C["carvao"], 12, 8)
    if tp == "gancho":
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display", 168), MAXW, C["papel"], C["corte"], None, True, 0.86, 4)
    elif tp == "fato":
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display2", 104), MAXW - 40, C["carvao"], C["papel"], C["corte"], True, 0.98, 3)
        ficha = s.get("ficha") or "FATO"
        s["_ficha"] = label(ficha.upper(), font("ficha", 28), C["carvao"], C["papel"], 16, 10)
    elif tp == "dado":
        blur = s["_base"].filter(ImageFilter.GaussianBlur(28)); s["_base"] = blur
        s["_lines"], s["_lh"] = line_images(s.get("label", ""), font("titulo", 58), MAXW, C["papel"], C["ambar"], None, False, 1.12, 3)
    elif tp == "leitura":
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display", 128), MAXW, C["carvao"], C["corte"], None, True, 0.88, 4)
        ph = ImageOps.fit(Image.open(img).convert("L"), (820, 470), Image.LANCZOS, centering=s.get("focus", [.5, .4])) if img else Image.new("L", (820, 470), 60)
        duo = ImageOps.colorize(ImageOps.autocontrast(ph, 1), C["carvao"], C["papel"]).convert("RGBA")
        card = Image.new("RGBA", (duo.width + 24, duo.height + 24), rgba(C["carvao"])); card.alpha_composite(duo, (12, 12))
        s["_card"] = card.rotate(-3, expand=True, resample=Image.BICUBIC)
    elif tp == "outro_lado":
        s["_base"] = ImageOps.grayscale(s["_base"]).convert("RGB")
        s["_lines"], s["_lh"] = line_images(s["headline"], font("titulo", 76), MAXW - 30, C["papel"], C["ambar"], None, False, 1.14, 5)
    elif tp == "viral":
        # print do post viral (citação): cartão em formato de celular sobre o próprio print desfocado
        s["_base"] = s["_base"].filter(ImageFilter.GaussianBlur(32))
        shot = Image.open(img).convert("RGBA") if img else Image.new("RGBA", (540, 960), rgba(C["grafite"]))
        shot = ImageOps.contain(shot, (580, 800), Image.LANCZOS)
        bz = 16; card = Image.new("RGBA", (shot.width + 2 * bz, shot.height + 2 * bz), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=44, fill=rgba(C["carvao"]))
        m = Image.new("L", shot.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], radius=30, fill=255)
        card.paste(shot, (bz, bz), m)
        s["_card"] = card.rotate(-2.5, expand=True, resample=Image.BICUBIC)
        s["_ficha"] = label((s.get("ficha") or "POST VIRAL").upper(), font("ficha", 26), C["carvao"], C["papel"], 14, 9)
    elif tp == "pergunta":
        s["_base"] = s["_base"].filter(ImageFilter.GaussianBlur(10))
        s["_lines"], s["_lh"] = line_images(s["headline"], font("display", 150), MAXW, C["papel"], C["ambar"], None, True, 0.88, 4)
        s["_pill"] = label("COMENTA AQUI ↓", font("ficha", 40), C["papel"], C["corte"], 30, 18)

def draw_scene(s, lt, G):
    """Retorna (frame RGBA, fundo_claro?) da cena s no tempo local lt (pode ser <0 durante o corte de entrada)."""
    tp = s["type"]; lt_c = max(lt, 0); u = clamp(lt / s["_dur"])
    light = False
    if tp == "leitura":
        fr = Image.new("RGBA", (W, H), rgba(C["papel"])); fr.alpha_composite(G["ruled_light"]); light = True
        cu = spring(lt - 0.05, 160, 18)
        cy = 300 + int((1 - min(cu, 1)) * 120)
        card = with_alpha(s["_card"], clamp(cu))
        if cu > 0: fr.alpha_composite(card, ((W - card.width) // 2 - 20, cy))
        wipe_in(fr, s["_tag"], L0, 230, lt, 0.1)
        hy = 300 + s["_card"].height + 40
        end = place_lines(fr, s["_lines"], L0, hy, s["_lh"], lt, 0.18)
        draw_caption(fr, s, lt, light_bg=True, y=max(1150, end + 20))
        return fr, light
    ph = kb_frame(s["_base"], u, s.get("motion", "in"), s.get("focus", [0.5, 0.38])).convert("RGBA")
    fr = ph
    if tp == "gancho":
        fr.alpha_composite(G["grad_strong"])
        nl = len(s["_lines"]); y0 = 1010 - nl * s["_lh"]
        wipe_in(fr, s["_tag"], L0, y0 - 80, lt, 0.0, 0.2)
        place_lines(fr, s["_lines"], L0 - 6, y0, s["_lh"], lt, 0.04, 0.06)
        draw_caption(fr, s, lt, y=1160)
    elif tp == "fato":
        fr.alpha_composite(G["grad"])
        wipe_in(fr, s["_ficha"], L0, 230, lt, 0.05)
        nl = len(s["_lines"]); y0 = 1040 - nl * s["_lh"]
        # tarja papel atrás das linhas, crescendo da esquerda
        bw = int(ease_out((lt - 0.08) / 0.3) * (max(im.width for im in s["_lines"]) + 50))
        if bw > 0: ImageDraw.Draw(fr).rectangle([L0, y0 - 10, L0 + bw, y0 + nl * s["_lh"] + 6], fill=rgba(C["papel"]))
        if bw > 0: ImageDraw.Draw(fr).rectangle([L0, y0 - 10, L0 + 12, y0 + nl * s["_lh"] + 6], fill=rgba(C["corte"]))
        wipe_in(fr, s["_tag"], L0, y0 - 74, lt, 0.0, 0.2)
        place_lines(fr, s["_lines"], L0 + 34, y0, s["_lh"], lt, 0.16)
        draw_caption(fr, s, lt, y=1160)
    elif tp == "dado":
        fr.alpha_composite(G["dim"]); fr.alpha_composite(G["ruled_dark"])
        wipe_in(fr, s["_tag"], L0, 260, lt, 0.0, 0.2)
        cu = ease_out((lt - 0.1) / 1.1)
        val = s.get("value", 0) * cu; dec = s.get("decimals", 0)
        num = f"{val:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        txt = f"{s.get('prefix', '')}{num}{s.get('suffix', '')}"
        f = font("display", s.get("size", 330)); d = ImageDraw.Draw(fr)
        bb = d.textbbox((0, 0), txt, font=f)
        while bb[2] - bb[0] > MAXW and f.size > 120: f = font("display", f.size - 20); bb = d.textbbox((0, 0), txt, font=f)
        sc = spring(lt - 0.05, 260, 14)
        if sc > 0:
            ti = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
            ImageDraw.Draw(ti).text((10 - bb[0], 10 - bb[1]), txt, font=f, fill=rgba(C["papel"]))
            z = 0.7 + 0.3 * sc; ti = ti.resize((max(1, int(ti.width * z)), max(1, int(ti.height * z))), Image.BILINEAR)
            fr.alpha_composite(with_alpha(ti, clamp(sc * 1.5)), (L0, int(560 + (bb[3] - bb[1]) * (1 - z) / 2)))
        lw = int(ease_out((lt - 0.9) / 0.35) * MAXW * 0.62)
        if lw > 0: d.rectangle([L0, 560 + (bb[3] - bb[1]) + 50, L0 + lw, 560 + (bb[3] - bb[1]) + 64], fill=rgba(C["corte"]))
        place_lines(fr, s["_lines"], L0, 560 + (bb[3] - bb[1]) + 100, s["_lh"], lt, 0.5, rise=False)
        draw_caption(fr, s, lt, y=1290)
    elif tp == "outro_lado":
        fr.alpha_composite(G["grad"]); fr.alpha_composite(G["dim_soft"])
        d = ImageDraw.Draw(fr)
        qa = clamp((lt - 0.05) / 0.25)
        if qa > 0: fr.alpha_composite(with_alpha(G["quote"], qa), (L0 - 10, 360))
        wipe_in(fr, s["_tag"], L0, 300, lt, 0.0)
        place_lines(fr, s["_lines"], L0 + 6, 600, s["_lh"], lt, 0.15, 0.05, rise=False)
        draw_caption(fr, s, lt, y=1210)
    elif tp == "viral":
        fr.alpha_composite(G["dim_soft"]); fr.alpha_composite(G["dim_soft"]); fr.alpha_composite(G["grad"])
        wipe_in(fr, s["_tag"], L0, 210, lt, 0.0, 0.2)
        cu = spring(lt - 0.05, 170, 16); card = s["_card"]
        if cu > 0:
            cx = (W - card.width) // 2 - 30; cy = 290 + int((1 - min(cu, 1.2)) * 260)
            fr.alpha_composite(with_alpha(card, clamp(cu * 1.5)), (cx, cy))
            wipe_in(fr, s["_ficha"], cx + 10, cy + card.height - s["_ficha"].height - 30, lt, 0.4)
        draw_caption(fr, s, lt, y=1180)
    elif tp == "pergunta":
        fr.alpha_composite(G["grad_strong"]); fr.alpha_composite(G["dim_soft"])
        nl = len(s["_lines"]); y0 = 1000 - nl * s["_lh"]
        wipe_in(fr, s["_tag"], L0, y0 - 80, lt, 0.0)
        place_lines(fr, s["_lines"], L0 - 4, y0, s["_lh"], lt, 0.05)
        pu = spring(lt - 0.6, 200, 12)
        if pu > 0:
            pulse = 1 + 0.035 * math.sin(max(0, lt - 1.2) * 2 * math.pi * 1.6)
            z = min(pu, 1.1) * pulse; p = s["_pill"]
            p2 = p.resize((max(1, int(p.width * z)), max(1, int(p.height * z))), Image.BILINEAR)
            fr.alpha_composite(p2, (L0, int(1040 + (p.height - p2.height) / 2)))
        draw_caption(fr, s, lt, y=1220)
    return fr, light

# ================================================================= principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--tts", choices=["edge", "espeak"], default=None)
    ap.add_argument("--voice", default="pt-BR-AntonioNeural"); ap.add_argument("--align", choices=["whisperx"], default=None)
    ap.add_argument("--out", default=None); ap.add_argument("--preview", default=None, help="tempos em s, ex.: 0.5,8,20 → PNGs em preview/")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8")); slug = spec["slug"]; tmp = tempfile.mkdtemp(prefix="sp3_")
    scenes = spec["scenes"]

    # 1) narração por cena + tempos de palavra
    for i, s in enumerate(scenes):
        p = os.path.join(ROOT, s["audio"]) if s.get("audio") else None; timed = None
        if not p or not os.path.exists(p):
            if a.tts == "edge": p = os.path.join(tmp, f"s{i}.mp3"); timed = tts_edge(s["narration"], p, a.voice)
            elif a.tts == "espeak": p = os.path.join(tmp, f"s{i}.wav"); tts_espeak(s["narration"], p)
            else: sys.exit(f"cena {i + 1}: sem áudio. Informe 'audio' ou use --tts edge")
        if s.get("words_json"): timed = json.load(open(os.path.join(ROOT, s["words_json"])))
        elif timed is None and a.align == "whisperx": timed = align_whisperx(p)
        s["_audio"] = p; s["_speech"] = dur(p)
        s["_words"], s["_wt"] = map_words(s["narration"], timed, s["_speech"])
        s["_chunks"] = chunk_words(s["_words"])

    # 2) duração das cenas; com trilha, cada corte cai num beat
    music = os.path.join(ROOT, spec["music"]) if spec.get("music") else None
    beats = beat_grid(music) if music and os.path.exists(music) else None
    t0 = 0.0
    for s in scenes:
        s["_t0"] = t0; end = t0 + s["_speech"] + PAD_END
        if beats is not None:
            nxt = beats[beats >= end - 0.05]
            if len(nxt) and nxt[0] - end < 0.45: end = float(nxt[0])
        s["_dur"] = end - t0; t0 = end
    total = t0
    if not 28 <= total <= 58: print(f"AVISO: duração {total:.1f}s fora de 28–58 s", file=sys.stderr)

    # 3) camadas globais
    G = {"grad": vgrad(), "grad_strong": vgrad(0.8, 520, 380, 0.97),
         "dim": Image.new("RGBA", (W, H), rgba(C["grafite"], 215)), "dim_soft": Image.new("RGBA", (W, H), rgba(C["carvao"], 90)),
         "ruled_dark": ruled_layer(C["nevoa"], 34), "ruled_light": ruled_layer(C["nevoa"], 60)}
    q = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); ImageDraw.Draw(q).text((0, -40), "“", font=font("display", 420), fill=rgba(C["corte"])); G["quote"] = q
    chip = Image.open(os.path.join(ROOT, "brand/logo/chip_sempauta.png")).convert("RGBA")
    chip = chip.resize((int(chip.width * 0.8), int(chip.height * 0.8)), Image.LANCZOS)
    for s in scenes: prep_scene(s, spec)
    bounds = [s["_t0"] for s in scenes[1:]]

    # máscara do corte diagonal: valor = x + (H-y)*tan14  (faixa inclinada igual ao símbolo)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); diag = xx + (H - yy) * K14; DMAX = W + H * K14
    BAND = 150

    def frame_at(t):
        idx = max(i for i, s in enumerate(scenes) if s["_t0"] <= t + 1e-9) if t >= 0 else 0
        idx = min(idx, len(scenes) - 1); s = scenes[idx]
        fr, light = draw_scene(s, t - s["_t0"], G)
        # transição "corte": de -4 a +5 frames em torno de cada fronteira
        for bi, b in enumerate(bounds):
            fu = (t - b) * FPS + 4
            if 0 <= fu < CUT_F:
                prev, nxt = scenes[bi], scenes[bi + 1]
                A, _ = draw_scene(prev, t - prev["_t0"], G); B, light = draw_scene(nxt, t - nxt["_t0"], G)
                e = ease_in_out(fu / (CUT_F - 1)); edge = -BAND + e * (DMAX + 2 * BAND)
                a = np.asarray(A.convert("RGB")); bimg = np.asarray(B.convert("RGB"))
                out = np.where((diag < edge - BAND / 2)[..., None], bimg, a)
                band = (diag >= edge - BAND / 2) & (diag < edge + BAND / 2)
                out = out.copy(); out[band] = C["corte"]
                fr = Image.fromarray(out).convert("RGBA")
        # persistentes: selo, crédito, barra segmentada
        fr.alpha_composite(chip, (L0, 120))
        if s.get("_cred") is not None: fr.alpha_composite(s["_cred"], (L0, H - SAFE["bottom"] + 6))
        d = ImageDraw.Draw(fr); gap = 8; n = len(scenes); segw = (W - 2 * L0 - gap * (n - 1)) / n; y = H - SAFE["bottom"] - 24
        for i, sc in enumerate(scenes):
            x0 = L0 + i * (segw + gap); pr = clamp((t - sc["_t0"]) / sc["_dur"])
            d.rectangle([x0, y, x0 + segw, y + 6], fill=rgba(C["carvao"] if light else C["papel"], 70))
            if pr > 0: d.rectangle([x0, y, x0 + segw * pr, y + 6], fill=rgba(C["corte"]))
        return fr.convert("RGB")

    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    if a.preview:
        for ts in a.preview.split(","):
            p = os.path.join(ROOT, "preview", f"{slug}_{float(ts):05.1f}s.png"); frame_at(float(ts)).save(p); print("preview", p)
        return

    # 4) vídeo
    out = a.out or os.path.join(ROOT, "output", f"{slug}.mp4"); os.makedirs(os.path.dirname(out), exist_ok=True)
    vid = os.path.join(tmp, "v.mp4"); nfr = int(round(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    for n in range(nfr):
        enc.stdin.write(frame_at(n / FPS).tobytes())
        if n % 150 == 0: print(f"  quadro {n}/{nfr}", file=sys.stderr)
    enc.stdin.close(); enc.wait()

    # 5) áudio: narração + efeitos (numpy) ; trilha com ducking (ffmpeg sidechain) ; loudnorm
    N = int((total + 0.5) * SR); narr = np.zeros(N, np.float32); sfx = np.zeros(N, np.float32)
    def put(buf, x, at, g=1.0):
        i = int(at * SR); j = min(N, i + len(x));
        if i < N: buf[i:j] += x[:j - i] * g
    S = {k: read_wav_mono(os.path.join(ROOT, "brand", "sfx", f"{k}.wav")) for k in ("corte", "impacto", "tique")}
    for i, s in enumerate(scenes):
        put(narr, read_wav_mono(s["_audio"]), s["_t0"])
        if s["type"] in ("gancho", "dado"): put(sfx, S["impacto"], s["_t0"] + 0.02, 0.45)
        if s["type"] == "dado":
            for k in range(8): put(sfx, S["tique"], s["_t0"] + 0.1 + 1.1 * (1 - (1 - k / 8) ** (1 / 3)), 0.30)
    for b in bounds: put(sfx, S["corte"], b - 0.26 - 4 / FPS + (CUT_F / 2) / FPS, 0.5)  # lâmina fecha no meio do corte
    nw, sw = os.path.join(tmp, "narr.wav"), os.path.join(tmp, "sfx.wav"); write_wav(nw, narr); write_wav(sw, sfx)
    mixed = os.path.join(tmp, "mix.wav")
    if music and os.path.exists(music):
        fc = ("[2:a]volume=-17dB,aformat=channel_layouts=mono[m];[0:a]asplit=2[n][sc];"
              "[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[duck];"
              "[n][duck][1:a]amix=inputs=3:duration=first:normalize=0[a]")
        ins = ["-i", nw, "-i", sw, "-stream_loop", "-1", "-i", music]
    else:
        fc = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]"; ins = ["-i", nw, "-i", sw]
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-map", "[a]", "-ar", str(SR), mixed])

    # 6) vinheta 3D no final + normalização -14 LUFS
    vin = os.path.join(ROOT, "brand", "vinheta", "vinheta_1080x1920.mp4")
    au = T["audio"]; norm = f"loudnorm=I={au['lufs']}:TP={au['true_peak']}:LRA=11"
    if spec.get("vinheta", True) and os.path.exists(vin):
        fc = ("[0:v]fps=30,settb=1/30,setpts=PTS-STARTPTS,format=yuv420p[v0];[2:v]fps=30,settb=1/30,setpts=PTS-STARTPTS,format=yuv420p[v1];"
              f"[v0][v1]xfade=transition=fade:duration=0.12:offset={total - 0.12:.3f}[v];"
              f"[1:a]atrim=0:{total:.3f},aformat=sample_rates={SR}:channel_layouts=stereo[a0];[2:a]aformat=sample_rates={SR}:channel_layouts=stereo[a1];"
              f"[a0][a1]acrossfade=d=0.12[am];[am]{norm}[a]")
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mixed, "-i", vin, "-filter_complex", fc,
                               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                               "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", out])
        total += 1.8 - 0.12
    else:
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mixed, "-map", "0:v", "-map", "1:a", "-af", norm,
                               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest", "-movflags", "+faststart", out])
    meta = f"{spec.get('title', '')}\n\n{spec.get('description', '')}\n\n{' '.join(spec.get('hashtags', []))}\n"
    open(out.replace(".mp4", ".txt"), "w", encoding="utf-8").write(meta)
    print(f"OK {out} ({total:.1f}s)")

if __name__ == "__main__":
    main()
