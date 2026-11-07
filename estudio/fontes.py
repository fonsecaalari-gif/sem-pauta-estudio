"""Coleta de pauta: feeds RSS, texto completo das matérias e votações da Câmara.

Tudo é tolerante a falhas: um feed fora do ar vira um aviso no relatório, não um erro.
"""
import html, json, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0 (compatible; SemPautaEstudio/1.0; +https://youtube.com/@somos.sempauta)",
      "Accept-Language": "pt-BR,pt;q=0.9"}


def baixar(url, timeout=30, binario=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dados = r.read()
        return dados if binario else dados.decode(r.headers.get_content_charset() or "utf-8", errors="replace")


def _limpa(t):
    t = re.sub(r"<[^>]+>", " ", html.unescape(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def ler_feeds(feeds, horas=36, avisos=None):
    """Lista de manchetes recentes: {id, titulo, resumo, link, fonte, data}."""
    itens, vistos = [], set()
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    for f in feeds:
        try:
            raiz = ET.fromstring(baixar(f["url"]))
        except Exception as e:
            if avisos is not None: avisos.append(f"feed indisponível: {f['nome']} ({e.__class__.__name__})")
            continue
        for it in raiz.iter("item"):
            titulo = _limpa(it.findtext("title"))
            chave = titulo.lower()[:80]
            if not titulo or chave in vistos: continue
            try:
                data = parsedate_to_datetime(it.findtext("pubDate") or "")
                if data.tzinfo is None: data = data.replace(tzinfo=timezone.utc)
            except Exception:
                data = datetime.now(timezone.utc)
            if data < limite: continue
            vistos.add(chave)
            fonte = _limpa(it.findtext("source")) or f["nome"]
            itens.append({"id": len(itens), "titulo": titulo, "resumo": _limpa(it.findtext("description"))[:400],
                          "link": (it.findtext("link") or "").strip(), "fonte": fonte, "data": data.strftime("%d/%m %H:%M")})
    return itens


class _Paragrafos(HTMLParser):
    def __init__(self):
        super().__init__(); self.dentro = 0; self.ignora = 0; self.atual = []; self.pars = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header", "aside"): self.ignora += 1
        if tag == "p": self.dentro += 1; self.atual = []
    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header", "aside") and self.ignora: self.ignora -= 1
        if tag == "p" and self.dentro:
            self.dentro -= 1; t = re.sub(r"\s+", " ", "".join(self.atual)).strip()
            if len(t) > 60: self.pars.append(t)
    def handle_data(self, d):
        if self.dentro and not self.ignora: self.atual.append(d)


def texto_da_materia(url, limite=6000):
    """Texto corrido de uma matéria (parágrafos <p>). Vazio se não conseguir."""
    try:
        p = _Paragrafos(); p.feed(baixar(url, timeout=25)); return "\n".join(p.pars)[:limite]
    except Exception:
        return ""


# ------------------------------------------------------------------ Câmara dos Deputados
CAMARA = "https://dadosabertos.camara.leg.br/api/v2"

def votacoes_plenario(dias=7):
    """Votações nominais do Plenário nos últimos dias: [{id, data, descricao}]."""
    fim = datetime.now().date(); ini = fim - timedelta(days=dias)
    url = f"{CAMARA}/votacoes?dataInicio={ini}&dataFim={fim}&itens=200&ordem=DESC&ordenarPor=dataHoraRegistro"
    try:
        js = json.loads(baixar(url, timeout=40))
    except Exception:
        return []
    out = []
    for v in js.get("dados", []):
        if v.get("siglaOrgao") == "PLEN" and v.get("descricao"):
            out.append({"id": v["id"], "data": (v.get("dataHoraRegistro") or "")[:10], "descricao": v["descricao"][:240]})
    return out[:40]


# ------------------------------------------------------------------ pesquisa com fontes completas
PREFERIDOS = ("agenciabrasil.ebc.com.br", ".gov.br", ".leg.br", ".jus.br", ".mp.br", "ibge.gov.br", "g1.globo.com",
              "oglobo.globo.com", "valor.globo.com", "folha.uol.com.br", "uol.com.br", "estadao.com.br", "cnnbrasil.com.br",
              "bbc.com", "poder360.com.br", "cartacapital.com.br", "brasildefato.com.br", "revistaforum.com.br",
              "metropoles.com", "apublica.org", "intercept.com.br", "jota.info", "conjur.com.br", "nexojornal.com.br",
              "correiobraziliense.com.br", "terra.com.br", "dw.com", "elpais.com", "infomoney.com.br", "exame.com",
              "veja.abril.com.br", "istoe.com.br", "otempo.com.br", "gazetadopovo.com.br", "jornaldebrasilia.com.br")
BLOQUEADOS = ("bet", "aposta", "livescore", "casino", "cassino")           # palavras no domínio
REDES = ("youtube.com", "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com", "wikipedia.org",
         "news.google.com", "msn.com", "kwai.com", "threads.net")       # não são fonte jornalística


def dominio(url):
    try: return url.split("/")[2].lower().removeprefix("www.")
    except IndexError: return ""


def confiavel(url):
    d = dominio(url)
    return any(d == p.lstrip(".") or d.endswith(p if p.startswith(".") else "." + p) or d == p for p in PREFERIDOS)


def bloqueado(url):
    d = dominio(url)
    return any(b in d for b in BLOQUEADOS) or any(d == r or d.endswith("." + r) for r in REDES)


def montar_fontes(candidatos, max_fontes=6, min_texto=700):
    """candidatos: [{url, titulo, descricao/resumo, trechos?, fonte?}]. Baixa o texto completo, prioriza veículos confiáveis.

    Devolve (lista_de_fontes, texto_para_a_mistral). Cada fonte: {n, url, veiculo, titulo, texto}.
    """
    vistos, ordem = set(), []
    for c in candidatos:
        u = c.get("url") or c.get("link")
        if not u or u in vistos or bloqueado(u): continue
        vistos.add(u); ordem.append(c)
    ordem.sort(key=lambda c: 0 if confiavel(c.get("url") or c.get("link")) else 1)
    fontes = []
    for c in ordem:
        if len(fontes) >= max_fontes: break
        u = c.get("url") or c.get("link")
        texto = texto_da_materia(u)
        if len(texto) < min_texto: continue
        fontes.append({"n": len(fontes) + 1, "url": u, "veiculo": c.get("fonte") or dominio(u),
                       "titulo": c.get("titulo", ""), "texto": texto})
    bloco = "\n\n".join(f"[{f['n']}] {f['veiculo']} — {f['titulo']}\nURL: {f['url']}\n{f['texto']}" for f in fontes)
    return fontes, bloco
