#!/usr/bin/env python3
"""
Coleta dados públicos e devolve BLOCOS prontos para colar no spec do vídeo longo.

  python3 scripts/dados_publicos.py votacoes-do-dia 2026-11-04          # lista votações da Câmara num dia (ids)
  python3 scripts/dados_publicos.py placar <id_votacao>                 # bloco "placar" (sim/não/abst + partidos)
  python3 scripts/dados_publicos.py agenda 2026-11-09 2026-11-13        # eventos da Câmara na semana (para "A Pauta da Semana")
  python3 scripts/dados_publicos.py ipca 12                             # bloco "grafico" linha com IPCA mensal (últimos N meses)
  python3 scripts/dados_publicos.py sidra "/t/1737/n1/all/v/63/p/last%2012" "Título"   # qualquer série do SIDRA/IBGE

APIs (gratuitas, sem chave): Dados Abertos da Câmara (dadosabertos.camara.leg.br/api/v2) e SIDRA/IBGE (apisidra.ibge.gov.br).
Portal da Transparência exige chave gratuita (api.portaldatransparencia.gov.br) — use TRANSPARENCIA_KEY no ambiente.
Sempre confira o número no site oficial antes de publicar e cite a fonte no bloco.
"""
import json, sys, urllib.request, urllib.parse
from collections import Counter, defaultdict

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
UA = {"User-Agent": "SemPauta/3.0 (jornalismo)", "Accept": "application/json"}

def get(url, params=None):
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.load(r)

def camara_all(path, params):
    out, url = [], f"{CAMARA}{path}?" + urllib.parse.urlencode(params)
    while url:
        js = get(url); out += js.get("dados", [])
        url = next((l["href"] for l in js.get("links", []) if l.get("rel") == "next"), None)
    return out

def votacoes_do_dia(dia):
    vs = camara_all("/votacoes", {"dataInicio": dia, "dataFim": dia, "itens": 100, "ordem": "DESC", "ordenarPor": "dataHoraRegistro"})
    for v in vs: print(f"{v['id']:<22} {v.get('siglaOrgao', ''):<8} {v.get('dataHoraRegistro', '')}  {v.get('descricao', '')[:110]}")

def placar(vid, max_partidos=8):
    info = get(f"{CAMARA}/votacoes/{vid}").get("dados", {})
    votos = camara_all(f"/votacoes/{vid}/votos", {})
    tipos = Counter(v.get("tipoVoto", "") for v in votos)
    por = defaultdict(Counter)
    for v in votos: por[v["deputado_"].get("siglaPartido", "?")][v.get("tipoVoto", "")] += 1
    partidos = sorted(por.items(), key=lambda kv: -sum(kv[1].values()))[:max_partidos]
    bloco = {
        "type": "placar", "image": "imgs/TODO.jpg",
        "headline": (info.get("descricao") or "TODO nome do projeto")[:90],
        "fonte": f"Câmara dos Deputados — votação {vid} ({(info.get('dataHoraRegistro') or info.get('data') or '')[:10]})",
        "sim": tipos.get("Sim", 0), "nao": tipos.get("Não", 0),
        "abst": tipos.get("Abstenção", 0) + tipos.get("Obstrução", 0),
        "quorum": 257, "resultado": "APROVADO" if info.get("aprovacao") == 1 else "REJEITADO" if info.get("aprovacao") == 0 else "",
        "partidos": [{"sigla": p, "sim": c.get("Sim", 0), "nao": c.get("Não", 0)} for p, c in partidos],
        "narration": "TODO narre o placar, o quórum exigido e como votaram os maiores partidos."
    }
    print(json.dumps(bloco, ensure_ascii=False, indent=2))
    print(f"\n# tipos de voto: {dict(tipos)} — confira se o quórum (257 = maioria absoluta) vale para essa matéria.", file=sys.stderr)

def agenda(ini, fim):
    evs = camara_all("/eventos", {"dataInicio": ini, "dataFim": fim, "itens": 100, "ordem": "ASC", "ordenarPor": "dataHoraInicio"})
    for e in evs:
        orgs = ", ".join(o.get("sigla", "") for o in e.get("orgaos", []))
        print(f"{e.get('dataHoraInicio', '')[:16]}  {orgs:<12} {e.get('descricaoTipo', ''):<28} {e.get('descricao', '')[:100].replace(chr(10), ' ')}")

def sidra(path, titulo, unidade="", decimals=2, rotulo=lambda p: p):
    rows = get("https://apisidra.ibge.gov.br/values" + path)
    head, data = rows[0], rows[1:]
    per_key = next(k for k, v in head.items() if "Mês" in v or "Trimestre" in v or "Ano" in v or "Período" in v)
    rot = [rotulo(r[per_key.replace("N", "C")] if per_key.replace("N", "C") in r else r[per_key]) for r in data]
    val = [float(r["V"]) for r in data if r["V"] not in ("...", "-", "X")]
    bloco = {"type": "grafico", "image": "imgs/TODO.jpg", "headline": titulo, "fonte": "IBGE/SIDRA " + path.split("/p/")[0],
             "grafico": {"tipo": "linha", "rotulos": rot[:len(val)], "valores": val, "unidade": unidade, "decimals": decimals, "destaque": len(val) - 1},
             "narration": "TODO conduza o olho pela série: início, virada, ponto atual."}
    print(json.dumps(bloco, ensure_ascii=False, indent=2))

MESES = "JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ".split()
def ipca(n):
    sidra(f"/t/1737/n1/all/v/63/p/last%20{int(n)}", "Inflação mês a mês (*IPCA*)", "%", 2,
          lambda p: f"{MESES[int(p[4:6]) - 1]}/{p[2:4]}" if len(p) == 6 and p.isdigit() else p)

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd = a[0]
    if cmd == "votacoes-do-dia": votacoes_do_dia(a[1])
    elif cmd == "placar": placar(a[1])
    elif cmd == "agenda": agenda(a[1], a[2])
    elif cmd == "ipca": ipca(a[1] if len(a) > 1 else 12)
    elif cmd == "sidra": sidra(a[1], a[2] if len(a) > 2 else "TODO título")
    else: sys.exit(__doc__)
