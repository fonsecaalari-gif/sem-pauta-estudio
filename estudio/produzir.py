"""Orquestra a produção: pauta → fontes → roteiro (Mistral) → fotos → render (kit) → relatório."""
import json, os, re, shutil, subprocess, sys, unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from . import fontes as F, imagens as I, roteiro as R
from .llm import ErroLLM, buscar_na_web

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "kit"
CFG = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
QUADROS = {
    "1_segunda_pauta_da_semana": "A PAUTA DA SEMANA — o que o Congresso, o STF e o governo vão decidir nesta semana e o que muda na vida das pessoas.",
    "2_terca_siga_o_dinheiro": "SIGA O DINHEIRO — um gasto público destrinchado: de onde vem, para onde vai, quem decide.",
    "3_quarta_sem_pauta_explica": "SEM PAUTA EXPLICA — explica um tema de política/economia que está no noticiário, de forma didática e atemporal.",
    "4_quinta_checagem_da_semana": "CHECAGEM DA SEMANA — 5 afirmações que circularam na semana, checadas com fonte.",
    "5_sexta_quem_votou": "QUEM VOTOU — uma votação importante da semana: o que estava em jogo, o placar e o que muda.",
    "6_sabado_linha_do_tempo": "LINHA DO TEMPO — a história completa de um caso que está no noticiário.",
    "7_domingo_resumo_da_semana": "RESUMO DA SEMANA — os 7 fatos mais importantes da semana.",
}


def slugify(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:50] or "video"


class Producao:
    def __init__(self, dia=None, tts="edge", render=True):
        self.dia = dia or date.today()
        self.tts, self.render = tts, render
        self.saida = RAIZ / "saida" / self.dia.isoformat(); self.saida.mkdir(parents=True, exist_ok=True)
        self.imgs = KIT / "imgs" / self.dia.isoformat(); self.imgs.mkdir(parents=True, exist_ok=True)
        self.avisos_gerais, self.videos = [], []
        self.modelo = os.environ.get("MISTRAL_MODEL") or CFG["modelo"]
        self.falso = os.environ.get("ESTUDIO_LLM_FALSO") == "1"
        self._manchetes = {}
        self.log(f"Sem Pauta Estúdio — {self.dia:%d/%m/%Y} — modelo {self.modelo}{' (MODO TESTE)' if self.falso else ''}")

    # ------------------------------------------------------------ utilidades
    def log(self, *a):
        print(*a, flush=True)

    def historico(self):
        p = KIT / "history.json"
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return {"publicados": []}

    def registrar(self, item):
        h = self.historico(); h.setdefault("publicados", []).append(item)
        (KIT / "history.json").write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")

    def historico_texto(self, dias=14, formato=None):
        lim = (self.dia - timedelta(days=dias)).isoformat()
        it = [p for p in self.historico().get("publicados", []) if p.get("data", "") >= lim and (not formato or p.get("formato") == formato)]
        return "\n".join(f"- {p['data']} [{p.get('formato', '')}] {p.get('tema', '')} — {p.get('angulo', '')}" for p in it[-40:])

    def manchetes(self, horas=36):
        if horas not in self._manchetes:
            if self.falso:
                self._manchetes[horas] = json.loads((RAIZ / "testes" / "manchetes.json").read_text(encoding="utf-8"))
            else:
                self._manchetes[horas] = F.ler_feeds(CFG["feeds"], horas, self.avisos_gerais)
            self.log(f"  {len(self._manchetes[horas])} manchetes coletadas ({horas} h)")
        return self._manchetes[horas]

    def pesquisar(self, tema, ids=(), horas=36, consultas=None):
        """Junta as matérias da pauta (feeds) e os resultados da busca na web, baixa o texto completo de cada uma.

        Devolve (fontes, texto). Menos de 2 fontes com texto = tema sem base suficiente.
        """
        if self.falso:
            ms = {m["id"]: m for m in self.manchetes(horas)}
            fontes = [{"n": k, "url": ms[i]["link"], "veiculo": ms[i]["fonte"], "titulo": ms[i]["titulo"], "texto": ms[i]["resumo"]}
                      for k, i in enumerate(ids, 1) if i in ms] or [{"n": 1, "url": "https://exemplo.invalid/1", "veiculo": "Teste", "titulo": tema, "texto": tema}]
            return fontes, "\n\n".join(f"[{f['n']}] {f['veiculo']} — {f['titulo']}\nURL: {f['url']}\n{f['texto']}" for f in fontes)
        ms = {m["id"]: m for m in self.manchetes(horas)}
        cand = [{"url": ms[i]["link"], "titulo": ms[i]["titulo"], "fonte": ms[i]["fonte"]} for i in ids if i in ms]
        for q in (consultas or [f"{tema} notícia"]):
            cand += buscar_na_web(q, self.modelo)
        fontes, texto = F.montar_fontes(cand, max_fontes=6 if horas <= 72 else 8)
        self.log(f"  {len(fontes)} fonte(s) com texto completo: " + ", ".join(F.dominio(f["url"]) for f in fontes))
        return fontes, texto

    def roteirizar(self, usuario, validador, rotulo, fontes_texto, max_tokens=8000):
        """Roteiro + checagem de fatos. Devolve (spec, erros_de_formato, afirmacoes_sem_fonte)."""
        spec, erros = R.pedir(usuario, validador, self.modelo, rotulo, max_tokens=max_tokens, log=self.log)
        if self.falso: return spec, erros, []
        for rodada in range(3):
            graves, ressalvas = R.verificar(spec, fontes_texto, self.modelo)
            self.log(f"  checagem {rodada + 1}: {len(graves)} grave(s), {len(ressalvas)} ressalva(s)")
            spec["_ressalvas"] = ressalvas
            if not graves or rodada == 2: return spec, erros, graves
            spec, erros = R.corrigir(spec, graves, usuario, validador, self.modelo, rotulo, max_tokens)
        return spec, erros, graves

    def salvar_fontes(self, nome, fontes):
        p = self.saida / f"{nome}_FONTES.md"
        p.write_text("\n\n".join(f"## [{f['n']}] {f['veiculo']} — {f['titulo']}\n{f['url']}\n\n{f['texto']}" for f in fontes), encoding="utf-8")

    # ------------------------------------------------------------ fotos
    def fotos(self, spec, prefixo, avisos):
        cache, ultimo = {}, None
        for i, s in enumerate(spec["scenes"]):
            if s.get("type") in ("vinheta", "capitulo", "tela_final", "checklist", "alerta", "passo", "viral"): continue
            if s.get("type") == "documento":
                self.documento(s, prefixo, i, avisos); continue
            termos = (s.pop("busca_imagem", "") or "").strip()
            if self.falso:
                demo = ["demo_city", "demo_papers", "demo_desk", "demo_h1", "demo_h2"][i % 5]
                s["image"], s["credit"] = f"imgs/{demo}.jpg", "Imagem demonstrativa (teste)"; ultimo = (s["image"], s["credit"]); continue
            if termos and termos in cache: achado = cache[termos]
            elif termos:
                p, cred = I.buscar_foto(termos, self.imgs, f"{prefixo}_{i:02d}", CFG["licencas_aceitas"])
                achado = (str(p.relative_to(KIT)), cred) if p else None
                if not p: avisos.append(f"bloco {i + 1}: {cred}")
                cache[termos] = achado
            else: achado = None
            if achado: s["image"], s["credit"] = achado; ultimo = achado
            elif ultimo: s["image"], s["credit"] = ultimo; avisos.append(f"bloco {i + 1}: reaproveitou a foto anterior")
        # cenas antes da 1ª foto achada recebem a 1ª foto
        primeira = next(((s["image"], s["credit"]) for s in spec["scenes"] if s.get("image")), None)
        for s in spec["scenes"]:
            if s.get("type") not in ("vinheta", "capitulo", "tela_final", "checklist", "alerta", "passo", "viral") and not s.get("image") and primeira:
                s["image"], s["credit"] = primeira
        th = spec.get("thumb")
        if isinstance(th, dict):
            termos = th.pop("busca_imagem", "")
            if termos and not self.falso:
                p, cred = I.buscar_foto(termos, self.imgs, f"{prefixo}_thumb", CFG["licencas_aceitas"])
                if p: th["image"] = str(p.relative_to(KIT))
            th.setdefault("image", primeira[0] if primeira else None)
        return primeira is not None

    def bloquear(self, spec, sem_fonte, fontes, formato, tema, avisos):
        """Guarda as fontes; se sobrou afirmação sem fonte, não renderiza e explica no relatório."""
        spec["_fontes"] = fontes
        spec["fontes"] = [{"veiculo": f["veiculo"], "url": f["url"]} for f in fontes]   # as matérias realmente entregues
        avisos += [f"ressalva bloco {p.get('bloco')}: \"{str(p.get('trecho', ''))[:140]}\" — {str(p.get('motivo', ''))[:220]}"
                   for p in spec.get("_ressalvas", [])[:8]]
        if not sem_fonte: return False
        avisos.append(f"BLOQUEADO: {len(sem_fonte)} afirmação(ões) sem fonte depois de 2 correções — não renderizado:")
        avisos += [f"  bloco {p.get('bloco')}: \"{str(p.get('trecho', ''))[:160]}\" — {str(p.get('motivo', ''))[:160]}" for p in sem_fonte[:12]]
        slug = f"{self.dia.isoformat()}_bloqueado_{slugify(spec.get('slug') or tema)}"
        (self.saida / f"{slug}.json").write_text(json.dumps({k: v for k, v in spec.items() if not k.startswith("_")}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.salvar_fontes(slug, fontes)
        self.videos.append({"slug": slug, "formato": formato, "spec": spec, "mp4": None, "avisos": avisos, "tema": tema})
        return True

    def documento(self, s, prefixo, i, avisos):
        url = s.pop("url_documento", ""); s.pop("busca_imagem", None)
        destino = self.imgs / f"{prefixo}_doc{i:02d}.png"
        if url and not self.falso and I.print_de_pagina(url, destino, 1100, 1300):
            s["image"] = str(destino.relative_to(KIT)); s["credit"] = f"Reprodução: {url.split('/')[2]}"
            s.setdefault("fonte", url.split("/")[2]); s.pop("destaque", None)
        else:
            avisos.append(f"bloco {i + 1}: sem print do documento ({url or 'sem URL'}); virou bloco 'fato'")
            s["type"] = "fato"; s["ficha"] = ("DOCUMENTO · FONTE: " + (s.get("fonte") or "ver descrição")).upper()[:60]
            s.pop("destaque", None)

    # ------------------------------------------------------------ descrição e render
    def completar_descricao(self, spec):
        creditos = sorted({s["credit"] for s in spec["scenes"] if s.get("credit")})
        linha = "Fotos: " + "; ".join(creditos) if creditos else ""
        d = spec.get("description", "")
        if "Fotos:" in d: d = re.sub(r"Fotos:.*", linha, d)
        elif linha: d += "\n" + linha
        spec["description"] = d

    def renderizar(self, spec_path, script, out):
        if not self.render: return None
        cmd = [sys.executable, f"scripts/{script}", str(spec_path.relative_to(KIT)), "--tts", self.tts, "--out", str(out)]
        self.log("  renderizando:", " ".join(cmd[1:]))
        r = subprocess.run(cmd, cwd=KIT, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("falha no render:\n" + (r.stderr or r.stdout)[-1500:])
        for linha in (r.stderr or "").splitlines():
            if linha.startswith("AVISO"): self.log("  " + linha)
        return out

    def guardar(self, spec, pasta_spec, script, formato, tema, angulo, avisos):
        slug = f"{self.dia.isoformat()}_{spec['_n']:02d}_{slugify(spec.get('slug') or tema)}"
        spec["slug"] = slug
        spec_path = KIT / pasta_spec / f"{slug}.json"; spec_path.parent.mkdir(parents=True, exist_ok=True)
        limpo = {k: v for k, v in spec.items() if not k.startswith("_")}
        spec_path.write_text(json.dumps(limpo, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copy(spec_path, self.saida / spec_path.name)
        if spec.get("_fontes"): self.salvar_fontes(slug, spec["_fontes"])
        mp4 = None
        try:
            mp4 = self.renderizar(spec_path, script, self.saida / f"{slug}.mp4")
        except RuntimeError as e:
            avisos.append(str(e)[:800]); self.log("  ERRO", str(e)[:400])
        self.videos.append({"slug": slug, "formato": formato, "spec": limpo, "mp4": mp4, "avisos": avisos, "tema": tema})
        if mp4 or not self.render:
            self.registrar({"data": self.dia.isoformat(), "formato": formato, "slug": slug, "tema": tema, "angulo": angulo,
                            "fontes": [f.get("url") for f in spec.get("fontes", []) if isinstance(f, dict)]})

    # ------------------------------------------------------------ formatos
    def shorts(self, n=None, tema=None):
        n = n or CFG["shorts_por_dia"]
        if tema:
            ms = self.manchetes(); palav = [w for w in slugify(tema).split("-") if len(w) > 3]
            ids = [m["id"] for m in ms if any(w in slugify(m["titulo"]) for w in palav)][:6]
            temas = [{"tema": tema, "angulo": "", "ids": ids}]
        else:
            self.log("Escolhendo a pauta dos Shorts…")
            temas = R.escolher_pauta(self.manchetes(), self.historico_texto(7), n, self.modelo)
        for k, t in enumerate(temas, 1):
            t["tema"] = t.get("tema", "").replace("*", "")
            self.log(f"Short {k}/{len(temas)}: {t['tema']}")
            fontes, ftexto = self.pesquisar(t["tema"], t.get("ids", []))
            if len(fontes) < 2 and not self.falso:
                self.avisos_gerais.append(f"Short '{t['tema']}': só {len(fontes)} fonte(s) com texto completo — tema descartado (regra: ≥ 2 fontes)."); continue
            urls = {f["url"] for f in fontes}
            usuario = R.prompt("short", tema=t["tema"], angulo=t.get("angulo", ""), hoje=f"{self.dia:%d/%m/%Y}", fontes=ftexto)
            try:
                spec, erros, sem_fonte = self.roteirizar(usuario, lambda x: R.validar_short(x, urls_validas=urls), "short", ftexto)
            except ErroLLM as e:
                self.avisos_gerais.append(f"Short '{t['tema']}': {e}"); self.log(f"  ERRO: {e}"); continue
            avisos = [f"validação: {x}" for x in erros]
            if self.bloquear(spec, sem_fonte, fontes, "short", t["tema"], avisos): continue
            spec["_n"] = k
            if not self.fotos(spec, f"s{k}", avisos):
                avisos.append("NENHUMA foto licenciada encontrada — vídeo não renderizado (regra do canal)")
                self.videos.append({"slug": spec.get("slug"), "formato": "short", "spec": spec, "mp4": None, "avisos": avisos, "tema": t["tema"]}); continue
            self.completar_descricao(spec)
            spec.update({"music": CFG["trilha"], "vinheta": True})
            self.guardar(spec, "specs", "render_short.py", "short", t["tema"], t.get("angulo", ""), avisos)

    def longo(self, quadro=None, tema=None):
        quadro = quadro or CFG["grade_longo"][str(self.dia.weekday())]
        if not quadro.startswith(tuple("1234567")):
            quadro = next(q for q in QUADROS if quadro.lower() in q)
        molde = json.loads((KIT / "longos" / "modelos" / f"{quadro}.json").read_text(encoding="utf-8"))
        semanal = quadro.startswith(("1_", "4_", "5_", "7_"))
        horas = 7 * 24 if semanal else 72
        extra_prompt, ids = "", []
        self.log(f"Vídeo longo: {QUADROS[quadro].split(' — ')[0]}")
        votacoes = F.votacoes_plenario(7) if quadro.startswith("5_") and not self.falso else []
        if not tema:
            ms = self.manchetes(horas)
            pedido = (f"Escolha 1 tema para o quadro {QUADROS[quadro]}"
                      + (f"\nVOTAÇÕES DO PLENÁRIO (escolha uma e devolva também \"votacao_id\"):\n" + "\n".join(f"{v['id']} · {v['data']} · {v['descricao']}" for v in votacoes) if votacoes else ""))
            linhas = "\n".join(f"{m['id']} · {m['fonte']} · {m['data']} · {m['titulo']}" for m in ms)
            usuario = R.prompt("pauta", n=1, historico=self.historico_texto(21, "longo") or "(vazio)", manchetes=linhas) + "\n\n" + pedido + \
                "\nResponda: {\"temas\": [{\"tema\", \"angulo\", \"ids\": [...], \"votacao_id\": \"opcional\"}]}"
            from .llm import conversar_json
            esc = conversar_json(R.sistema(), usuario, self.modelo, 0.3, 2000, rotulo="pauta_longo").get("temas", [{}])[0]
            tema, ids = esc.get("tema", "tema do dia").replace("*", ""), esc.get("ids", [])
            vid = esc.get("votacao_id")
            if vid and votacoes: extra_prompt = self.injetar_placar(molde, vid)
        self.log(f"  tema: {tema}")
        if not extra_prompt:   # sem placar oficial: o bloco placar vira um fato comum
            for b in molde["scenes"]:
                if b.get("type") == "placar":
                    b.clear(); b.update({"type": "fato", "busca_imagem": "TODO", "ficha": "FATO · FONTE: TODO", "headline": "TODO", "narration": "TODO ~70 palavras: mais um fato do caso, com fonte"})
        consultas = [f"{tema} notícia", f"{tema} histórico cronologia" if quadro.startswith("6_") else f"{tema} dados oficiais",
                     f"{tema} o que diz o governo e a oposição"]
        fontes, ftexto = self.pesquisar(tema, ids, horas, consultas)
        if len(fontes) < 3 and not self.falso:
            self.avisos_gerais.append(f"Longo '{tema}': só {len(fontes)} fonte(s) com texto completo — não gerado (mínimo 3)."); return
        urls = {f["url"] for f in fontes}
        usuario = R.prompt("longo", quadro=QUADROS[quadro], tema=tema, hoje=f"{self.dia:%d/%m/%Y}", extra=extra_prompt,
                           molde=json.dumps(molde, ensure_ascii=False, indent=1), fontes=ftexto)
        try:
            spec, erros, sem_fonte = self.roteirizar(usuario, lambda x: R.validar_longo(x, urls_validas=urls), "longo", ftexto, 16000)
        except ErroLLM as e:
            self.avisos_gerais.append(f"Longo: {e}"); self.log(f"  ERRO: {e}"); return
        avisos = [f"validação: {x}" for x in erros] + ["confira todos os números (dado, gráfico, placar) na fonte antes de postar"]
        if self.bloquear(spec, sem_fonte, fontes, "longo", tema, avisos): return
        spec["_n"] = 10
        self.fotos(spec, "l", avisos); self.completar_descricao(spec)
        spec.update({"music": CFG["trilha"], "quadro": molde.get("quadro"), "legendas_na_tela": False})
        self.guardar(spec, "longos", "render_longo.py", "longo", tema, quadro, avisos)

    def injetar_placar(self, molde, vid):
        r = subprocess.run([sys.executable, "scripts/dados_publicos.py", "placar", str(vid)], cwd=KIT, capture_output=True, text=True)
        try:
            bloco = json.loads(r.stdout)
        except json.JSONDecodeError:
            self.avisos_gerais.append(f"placar da votação {vid} indisponível"); return ""
        for s in molde["scenes"]:
            if s.get("type") == "placar":
                for k in ("sim", "nao", "abst", "resultado", "partidos", "fonte"): s[k] = bloco.get(k, s.get(k))
        return f"PLACAR OFICIAL (Câmara, votação {vid}) já inserido no molde: {json.dumps({k: bloco.get(k) for k in ('headline', 'sim', 'nao', 'abst', 'resultado')}, ensure_ascii=False)}"

    def tutorial(self, tema=None):
        if not tema:
            usados = self.historico_texto(180, "tutorial")
            temas = [l[2:].strip() for l in (KIT / "templates" / "temas_tutorial.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
            tema = next((t for t in temas if t[:40] not in usados), temas[0])
        self.log(f"Tutorial de domingo: {tema}")
        fontes, ftexto = self.pesquisar(tema, (), 72, [f"{tema} passo a passo site oficial gov.br", f"{tema} como fazer"])
        if len(fontes) < 2 and not self.falso:
            self.avisos_gerais.append(f"Tutorial '{tema}': só {len(fontes)} fonte(s) com texto — não gerado."); return
        urls = {f["url"] for f in fontes}
        molde = json.loads((KIT / "longos" / "modelos" / "8_domingo_tutorial.json").read_text(encoding="utf-8"))
        usuario = R.prompt("tutorial", tema=tema, molde=json.dumps(molde, ensure_ascii=False, indent=1), fontes=ftexto)
        try:
            spec, erros, sem_fonte = self.roteirizar(usuario, lambda x: R.validar_longo(x, urls_validas=urls), "tutorial", ftexto, 16000)
        except ErroLLM as e:
            self.avisos_gerais.append(f"Tutorial: {e}"); return
        avisos = [f"validação: {x}" for x in erros]
        if self.bloquear(spec, sem_fonte, fontes, "tutorial", tema, avisos): return
        pend = 0
        for i, s in enumerate(spec["scenes"]):
            if s.get("type") != "passo": continue
            url = s.pop("url_print", ""); destino = self.imgs / f"t_passo{i:02d}.png"
            for k in ("destaque", "borrar"): s.pop(k, None)
            if self.falso:
                s["image"] = "imgs/tutorial_exemplo_computador.png"; continue
            if url and I.print_de_pagina(url, destino, celular=s.get("tela") == "celular"):
                s["image"] = str(destino.relative_to(KIT)); s["endereco"] = url
            else:
                pend += 1; avisos.append(f"PENDENTE bloco {i + 1}: tirar print da tela ({url or 'tela com login'}) e salvar como imgs/…; depois rode de novo o render")
        spec["_n"] = 20
        self.fotos(spec, "t", avisos); self.completar_descricao(spec)
        spec.update({"music": CFG["trilha"], "quadro": "TUTORIAL DE DOMINGO", "legendas_na_tela": False})
        if pend:
            avisos.append(f"{pend} print(s) pendente(s): o vídeo não foi renderizado. Coloque os prints e rode: python3 scripts/render_longo.py longos/<arquivo>.json --tts edge")
            render = self.render; self.render = False
            self.guardar(spec, "longos", "render_longo.py", "tutorial", tema, "tutorial", avisos); self.render = render
        else:
            self.guardar(spec, "longos", "render_longo.py", "tutorial", tema, "tutorial", avisos)

    def produto(self, viral_url=None, viral_print=None):
        ficha_p = KIT / "produtos" / "produto.md"; ficha = ficha_p.read_text(encoding="utf-8")
        if "TODO" in ficha:
            self.avisos_gerais.append("Sem Pauta Útil: preencha kit/produtos/produto.md (ainda tem TODO). Vídeo de produto não gerado."); return
        hist = [p for p in self.historico().get("publicados", []) if p.get("formato") == "produto"]
        if hist and hist[-1]["data"] == (self.dia - timedelta(days=1)).isoformat():
            self.log("Sem Pauta Útil: ontem teve vídeo de produto; hoje não (dia sim, dia não)."); return
        if not viral_url:
            self.avisos_gerais.append("Sem Pauta Útil: informe o link do post viral (campo viral_url) para gerar o vídeo de produto."); return
        destino = self.imgs / "viral_print.png"
        if viral_print: shutil.copy(viral_print, destino); ok = True
        else: ok = I.print_de_pagina(viral_url, destino, celular=True)
        if not ok:
            self.avisos_gerais.append("Sem Pauta Útil: não consegui o print do post viral (redes costumam bloquear robôs). Envie o print (viral_print)."); return
        m = re.search(r"Linha de identificação.*?`([^`]+)`", ficha, re.S)
        usuario = R.prompt("produto", ficha=ficha, viral=f"URL: {viral_url}", viral_url=viral_url,
                           tipo_material="o material", linha_identificacao=(m.group(1) if m else "linha de identificação da ficha"))
        try:
            spec, erros = R.pedir(usuario, lambda s: R.validar_short(s, produto=True), self.modelo, "produto", log=self.log)
        except ErroLLM as e:
            self.avisos_gerais.append(f"Sem Pauta Útil: {e}"); return
        avisos = [f"validação: {x}" for x in erros] + ["marque 'Inclui promoção paga' no YouTube Studio ao postar"]
        for s in spec["scenes"]:
            if s.get("type") == "viral":
                s["image"] = str(destino.relative_to(KIT)); s["credit"] = f"Print: {viral_url.split('/')[2]} — citação"
        spec["_n"] = 30
        self.fotos(spec, "p", avisos); self.completar_descricao(spec)
        spec.update({"music": CFG["trilha"], "vinheta": True})
        self.guardar(spec, "specs", "render_short.py", "produto", spec.get("title", "produto"), "viral+solução", avisos)

    def hoje(self, viral_url=None):
        self.shorts()
        self.longo()
        if self.dia.weekday() == 6: self.tutorial()
        self.produto(viral_url)

    # ------------------------------------------------------------ relatório
    def relatorio(self):
        L = [f"# Sem Pauta — produção de {self.dia:%d/%m/%Y}", ""]
        prontos = [v for v in self.videos if v["mp4"]]
        L.append(f"**{len(prontos)} vídeo(s) pronto(s)** de {len(self.videos)} roteiro(s). Modelo: {self.modelo}.")
        if self.falso: L.append("\n> MODO TESTE: roteiros e imagens são de exemplo. Não publique.")
        if self.avisos_gerais: L += ["", "## Avisos gerais"] + [f"- {a}" for a in self.avisos_gerais]
        for v in self.videos:
            s = v["spec"]; L += ["", "---", f"## {s.get('title', v['slug'])}",
                                 f"Formato: {v['formato']} · Arquivo: `{Path(v['mp4']).name if v['mp4'] else 'NÃO RENDERIZADO'}`"]
            if v["formato"] in ("longo", "tutorial") and v["mp4"]:
                L.append(f"Legenda: `{v['slug']}.srt` · Thumbnail: `{v['slug']}_thumb.jpg`")
            txt = self.saida / f"{v['slug']}.txt"
            desc = txt.read_text(encoding="utf-8").split("\n\n", 1)[1].rsplit("\n\n", 1)[0] if txt.exists() else s.get("description", "")
            L += ["", "**Título**", "```", s.get("title", ""), "```", "**Descrição**", "```", desc.strip(), "```",
                  "**Hashtags**", "```", " ".join(s.get("hashtags", [])), "```"]
            fts = [f"{f.get('veiculo', '')} {f.get('url', '')}".strip() for f in s.get("fontes", []) if isinstance(f, dict)]
            if fts: L += ["**Fontes**"] + [f"- {f}" for f in fts]
            if (self.saida / f"{v['slug']}_FONTES.md").exists(): L.append(f"Textos completos das fontes usadas: `{v['slug']}_FONTES.md`")
            if v["avisos"]: L += ["", "**Conferir antes de postar**"] + [f"- {a}" for a in v["avisos"]]
        L += ["", "---", "Lembretes: confira os números nas fontes; suba o .srt dos longos; configure a tela final; "
              "no vídeo de produto marque 'Inclui promoção paga'."]
        p = self.saida / f"RELATORIO_{datetime.now():%H%M%S}.md"; p.write_text("\n".join(L), encoding="utf-8")
        shutil.copy(p, self.saida / "RELATORIO.md")   # o mais recente
        self.log(f"\nRelatório: {p}")
        return len(prontos)
