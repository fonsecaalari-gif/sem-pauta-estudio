"""Imagens: fotos licenciadas do Wikimedia Commons e prints de páginas públicas.

O Commons reúne milhares de fotos da Agência Brasil, Câmara e Senado com licença livre (CC BY etc.).
Cada foto vem com autor e licença, que viram o crédito na tela e na descrição.
"""
import json, re, urllib.parse
from pathlib import Path
from .fontes import baixar

API = "https://commons.wikimedia.org/w/api.php"


def _texto(meta, campo):
    return re.sub(r"<[^>]+>", "", (meta.get(campo) or {}).get("value", "")).strip()


_VAZIAS = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "file", "jpg", "jpeg", "png", "foto", "the", "of"}


def _palavras(texto):
    import unicodedata
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2 and w not in _VAZIAS}


def buscar_foto(termos, pasta, nome, licencas, largura=1920):
    """Procura no Commons e baixa a 1ª foto com licença aceita. Devolve (caminho_relativo, crédito) ou (None, motivo)."""
    q = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
         "gsrsearch": f"{termos} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|size",
         "iiurlwidth": largura}
    try:
        js = json.loads(baixar(API + "?" + urllib.parse.urlencode(q), timeout=30))
    except Exception as e:
        return None, f"Commons indisponível ({e.__class__.__name__})"
    paginas = sorted(js.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    aceitas = [l.lower() for l in licencas]
    chaves = _palavras(termos)
    for p in paginas:
        ii = (p.get("imageinfo") or [{}])[0]; meta = ii.get("extmetadata", {})
        # a foto precisa ser do que foi pedido: palavras da busca no título/descrição do arquivo
        rotulo = _palavras(" ".join([p.get("title", ""), _texto(meta, "ImageDescription"), _texto(meta, "ObjectName")]))
        if chaves and len(chaves & rotulo) < max(1, (len(chaves) + 1) // 2): continue
        lic = _texto(meta, "LicenseShortName")
        if not lic or not any(lic.lower().startswith(a) for a in aceitas): continue
        if ii.get("width", 0) < 900: continue
        url = ii.get("thumburl") or ii.get("url")
        try:
            dados = baixar(url, timeout=60, binario=True)
        except Exception:
            continue
        ext = ".png" if url.lower().endswith(".png") else ".jpg"
        destino = Path(pasta) / f"{nome}{ext}"; destino.write_bytes(dados)
        autor = _texto(meta, "Artist")[:60] or "autor não informado"
        credito = f"Foto: {autor} / Wikimedia Commons ({lic})"
        return destino, credito
    return None, f"nenhuma foto com licença aceita para '{termos}'"


def print_de_pagina(url, destino, largura=1440, altura=900, celular=False):
    """Captura a parte de cima de uma página pública com o Chromium do Playwright. Devolve True/False."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            ctx = nav.new_context(viewport={"width": 430 if celular else largura, "height": 900 if celular else altura},
                                  device_scale_factor=2 if celular else 1, locale="pt-BR")
            pg = ctx.new_page(); pg.goto(url, wait_until="networkidle", timeout=45000)
            pg.screenshot(path=str(destino)); nav.close()
        return True
    except Exception:
        return False
