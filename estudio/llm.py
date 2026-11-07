"""Cliente mínimo da API da Mistral (sem dependências externas).

A chave vem de MISTRAL_API_KEY (variável de ambiente ou segredo do GitHub). Nunca escreva a chave no código.
ESTUDIO_LLM_FALSO=1 usa respostas prontas de testes/respostas/ — para testar o fluxo sem gastar a API.
"""
import json, os, re, time, urllib.error, urllib.request
from pathlib import Path

API = "https://api.mistral.ai/v1"
AQUI = Path(__file__).parent


class ErroLLM(RuntimeError):
    pass


def _post(caminho, corpo, tentativas=4):
    chave = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not chave:
        raise ErroLLM("Falta a variável MISTRAL_API_KEY (no GitHub: Settings → Secrets and variables → Actions).")
    req = urllib.request.Request(f"{API}{caminho}", data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    espera = 4
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and i < tentativas - 1:
                time.sleep(espera); espera *= 2; continue
            if e.code == 401:
                raise ErroLLM("A Mistral recusou a chave (401). Confira o segredo MISTRAL_API_KEY.") from None
            raise ErroLLM(f"Mistral respondeu {e.code}: {msg}") from None
        except urllib.error.URLError as e:
            if i < tentativas - 1:
                time.sleep(espera); espera *= 2; continue
            raise ErroLLM(f"Sem conexão com a Mistral: {e.reason}") from None


def _extrair_json(texto):
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if m: texto = m.group(1)
    i = min([p for p in (texto.find("{"), texto.find("[")) if p >= 0], default=0)
    return json.loads(texto[i:])


def conversar_json(sistema, usuario, modelo, temperatura=0.4, max_tokens=8000, rotulo="geral"):
    """Pede uma resposta em JSON e devolve o objeto Python."""
    if os.environ.get("ESTUDIO_LLM_FALSO") == "1":
        return _resposta_falsa(rotulo)
    corpo = {"model": modelo, "temperature": temperatura, "max_tokens": max_tokens,
             "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
    js = _post("/chat/completions", corpo)
    conteudo = js["choices"][0]["message"]["content"]
    if isinstance(conteudo, list):  # alguns modelos devolvem pedaços
        conteudo = "".join(c.get("text", "") for c in conteudo if isinstance(c, dict))
    try:
        return _extrair_json(conteudo)
    except json.JSONDecodeError as e:
        raise ErroLLM(f"A Mistral não devolveu JSON válido ({e}). Início: {conteudo[:200]}") from None


def buscar_na_web(pergunta, modelo="mistral-large-latest"):
    """Busca na web com a ferramenta web_search da Mistral (API de Conversations).

    Devolve a lista de resultados da busca [{url, titulo, descricao, trechos}]. Lista vazia se falhar.
    """
    if os.environ.get("ESTUDIO_LLM_FALSO") == "1":
        return []
    try:
        js = _post("/conversations", {"model": modelo, "inputs": pergunta, "tools": [{"type": "web_search"}]}, tentativas=2)
    except ErroLLM as e:
        print(f"aviso: busca na web da Mistral indisponível ({e})")
        return []
    achados, vistos = [], set()
    for saida in js.get("outputs", []):
        info = saida.get("info") if saida.get("type") == "tool.execution" else None
        res = info.get("result") if isinstance(info, dict) else None
        if isinstance(res, str):
            try: res = json.loads(res)
            except json.JSONDecodeError: res = None
        if not isinstance(res, dict): continue
        for r in res.values():
            url = (r or {}).get("url")
            if not url or url in vistos: continue
            vistos.add(url)
            limpa = lambda t: re.sub(r"<[^>]+>", "", t or "")
            achados.append({"url": url, "titulo": limpa(r.get("title")), "descricao": limpa(r.get("description")),
                            "trechos": [limpa(x) for x in r.get("snippets", [])][:4]})
    return achados


def _resposta_falsa(rotulo):
    p = AQUI.parent / "testes" / "respostas" / f"{rotulo}.json"
    if not p.exists():
        raise ErroLLM(f"modo falso: falta {p}")
    return json.loads(p.read_text(encoding="utf-8"))
