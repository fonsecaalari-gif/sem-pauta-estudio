"""Pedidos à Mistral (pauta, Short, longo, tutorial, produto) e validação das respostas."""
import json, re
from pathlib import Path
from . import llm

PROMPTS = Path(__file__).parent / "prompts"
TIPOS_SHORT = {"gancho", "fato", "dado", "leitura", "outro_lado", "pergunta", "viral"}
TIPOS_LONGO = {"abertura", "vinheta", "capitulo", "fato", "documento", "dado", "grafico", "placar", "checagem",
               "linha_do_tempo", "leitura", "outro_lado", "passo", "checklist", "alerta", "encerramento", "tela_final"}


def prompt(nome, **vals):
    txt = (PROMPTS / f"{nome}.md").read_text(encoding="utf-8")
    for k, v in vals.items():
        txt = txt.replace("{" + k + "}", str(v))
    return txt


def sistema():
    return prompt("regras")


def palavras(spec):
    return sum(len(s.get("narration", "").split()) for s in spec.get("scenes", []))


def _todo(obj):
    return "TODO" in json.dumps(obj, ensure_ascii=False)


# ------------------------------------------------------------------ validações
def validar_short(spec, produto=False):
    e = []
    sc = spec.get("scenes") or []
    if not 4 <= len(sc) <= 7: e.append(f"o Short precisa de 4 a 7 cenas (veio {len(sc)})")
    for i, s in enumerate(sc, 1):
        t = s.get("type")
        if t not in TIPOS_SHORT: e.append(f"cena {i}: tipo '{t}' não existe")
        if not s.get("narration"): e.append(f"cena {i}: falta narration")
        if t in ("gancho", "fato", "leitura", "outro_lado", "pergunta") and not s.get("headline"):
            e.append(f"cena {i} ({t}): falta headline")
        if t == "dado":
            if not isinstance(s.get("value"), (int, float)): e.append(f"cena {i} (dado): 'value' precisa ser número")
            if not s.get("label"): e.append(f"cena {i} (dado): falta label")
        if t not in ("viral",) and not s.get("busca_imagem"): e.append(f"cena {i}: falta busca_imagem")
        if s.get("headline", "").count("*") % 2: e.append(f"cena {i}: asteriscos desbalanceados na headline")
    if sc and sc[0].get("type") not in ("gancho", "viral"): e.append("a 1ª cena precisa ser gancho")
    if sc and sc[-1].get("type") != "pergunta": e.append("a última cena precisa ser pergunta")
    tipos = [s.get("type") for s in sc]
    if "leitura" in tipos and "outro_lado" not in tipos: e.append("vídeo com leitura (opinião) precisa de outro_lado")
    if "leitura" in tipos:
        lt = next(s for s in sc if s.get("type") == "leitura")
        if not lt.get("narration", "").lower().startswith("na nossa leitura"): e.append("narração da leitura deve começar com 'Na nossa leitura'")
    n = palavras(spec)
    if not 80 <= n <= 160: e.append(f"narração total com {n} palavras; precisa de 90 a 140")
    for k in ("title", "description", "slug"):
        if not spec.get(k): e.append(f"falta '{k}'")
    if len(spec.get("title", "")) > 100: e.append("título com mais de 100 caracteres")
    if not produto and not spec.get("fontes"): e.append("falta a lista 'fontes'")
    if _todo(spec): e.append("ainda há 'TODO' no texto")
    return e


def validar_longo(spec, minimo=1250):
    e = []
    sc = spec.get("scenes") or []
    for i, s in enumerate(sc, 1):
        t = s.get("type")
        if t not in TIPOS_LONGO: e.append(f"bloco {i}: tipo '{t}' não existe")
        if t not in ("vinheta", "capitulo", "tela_final") and not s.get("narration"): e.append(f"bloco {i} ({t}): falta narration")
        if t == "grafico":
            g = s.get("grafico") or {}
            if len(g.get("rotulos", [])) != len(g.get("valores", [])) or not g.get("valores"):
                e.append(f"bloco {i} (grafico): rotulos e valores precisam ter o mesmo tamanho")
            elif not all(isinstance(v, (int, float)) for v in g["valores"]): e.append(f"bloco {i} (grafico): valores precisam ser números")
        if t == "dado" and not isinstance(s.get("value"), (int, float)): e.append(f"bloco {i} (dado): value precisa ser número")
        if t == "checagem" and not s.get("veredito"): e.append(f"bloco {i} (checagem): falta veredito")
        if t == "linha_do_tempo" and len(s.get("eventos", [])) < 3: e.append(f"bloco {i}: linha do tempo com menos de 3 eventos")
    if sum(1 for s in sc if s.get("type") == "capitulo") < 3: e.append("precisa de pelo menos 3 capítulos")
    n = palavras(spec)
    if n < minimo: e.append(f"narração total com {n} palavras; precisa de pelo menos {minimo} para passar de 8 minutos — desenvolva mais cada bloco")
    if _todo(spec): e.append("ainda há 'TODO' no JSON — preencha todos")
    for k in ("title", "description", "slug"):
        if not spec.get(k): e.append(f"falta '{k}'")
    return e


# ------------------------------------------------------------------ chamadas
def pedir(usuario, validador, modelo, rotulo, max_tokens=8000, tentativas=3, log=print):
    """Pede o JSON e, se a validação falhar, devolve os erros para a Mistral corrigir."""
    sis = sistema(); msg = usuario; ultimo = None; erros = []
    for t in range(tentativas):
        spec = llm.conversar_json(sis, msg, modelo, max_tokens=max_tokens, rotulo=rotulo)
        erros = validador(spec)
        if not erros: return spec, []
        log(f"  tentativa {t + 1}: {len(erros)} problema(s): {'; '.join(erros[:4])}")
        ultimo = spec
        msg = (usuario + "\n\nSUA RESPOSTA ANTERIOR TINHA ESTES PROBLEMAS — corrija todos e devolva o JSON completo:\n- "
               + "\n- ".join(erros) + "\n\nRESPOSTA ANTERIOR:\n" + json.dumps(spec, ensure_ascii=False)[:30000])
    return ultimo, erros


def escolher_pauta(manchetes, historico, n, modelo):
    linhas = "\n".join(f"{m['id']} · {m['fonte']} · {m['data']} · {m['titulo']} — {m['resumo'][:200]}" for m in manchetes)
    usuario = prompt("pauta", n=n, historico=historico or "(vazio)", manchetes=linhas)
    js = llm.conversar_json(sistema(), usuario, modelo, temperatura=0.3, max_tokens=2000, rotulo="pauta")
    return js.get("temas", [])[:n]
