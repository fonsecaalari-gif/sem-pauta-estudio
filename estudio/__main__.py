"""Sem Pauta Estúdio — gera roteiros com a Mistral e renderiza os vídeos com o kit.

  python -m estudio hoje                        # produção do dia (Shorts + longo do quadro + tutorial no domingo + produto)
  python -m estudio shorts [--quantos 3] [--tema "…"]
  python -m estudio longo [--quadro siga_o_dinheiro] [--tema "…"]
  python -m estudio tutorial [--tema "…"]
  python -m estudio produto --viral-url URL [--viral-print arquivo.png]

Opções comuns: --sem-render (só roteiros), --tts edge|espeak, --data AAAA-MM-DD.
Precisa da variável MISTRAL_API_KEY. Para testar sem gastar a API: ESTUDIO_LLM_FALSO=1.
"""
import argparse, sys
from datetime import date
from .produzir import Producao


def main(argv=None):
    ap = argparse.ArgumentParser(prog="estudio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["hoje", "shorts", "longo", "tutorial", "produto"])
    ap.add_argument("--tema"); ap.add_argument("--quadro"); ap.add_argument("--quantos", type=int)
    ap.add_argument("--viral-url"); ap.add_argument("--viral-print")
    ap.add_argument("--sem-render", action="store_true"); ap.add_argument("--tts", default="edge", choices=["edge", "espeak"])
    ap.add_argument("--data")
    a = ap.parse_args(argv)
    p = Producao(date.fromisoformat(a.data) if a.data else None, a.tts, not a.sem_render)
    if a.acao == "hoje": p.hoje(a.viral_url)
    elif a.acao == "shorts": p.shorts(a.quantos, a.tema)
    elif a.acao == "longo": p.longo(a.quadro, a.tema)
    elif a.acao == "tutorial": p.tutorial(a.tema)
    elif a.acao == "produto": p.produto(a.viral_url, a.viral_print)
    prontos = p.relatorio()
    if p.render and prontos == 0 and p.videos:
        sys.exit(1)


if __name__ == "__main__":
    main()
