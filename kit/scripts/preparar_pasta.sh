#!/usr/bin/env bash
# Prepara (ou atualiza) a pasta de trabalho do Sem Pauta a partir da skill.
#   bash <skill>/scripts/preparar_pasta.sh [pasta_de_trabalho]     (padrão: ./sem-pauta)
# - Código, marca, moldes e referências são sempre atualizados a partir da skill.
# - O que é do canal NÃO é sobrescrito: history.json, specs/, longos/*.json, imgs/, audio/, output/,
#   produtos/produto.md e produtos/historico_produto.json.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-./sem-pauta}"
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
if [ "$SKILL" = "$DEST" ]; then echo "A pasta de trabalho é a própria skill; nada a copiar."; exit 0; fi

# 1) sempre atualizados
for d in scripts brand templates references longos/modelos; do
  mkdir -p "$DEST/$d"; cp -r "$SKILL/$d/." "$DEST/$d/"
done
# 2) só copiados se ainda não existirem (estado do canal)
for d in specs imgs audio output produtos longos; do
  mkdir -p "$DEST/$d"; cp -rn "$SKILL/$d/." "$DEST/$d/" 2>/dev/null || true
done
[ -f "$DEST/history.json" ] || cp "$SKILL/history.json" "$DEST/history.json"
mkdir -p "$DEST/preview"

# 3) dependências que faltam (só avisa)
for b in ffmpeg ffprobe; do command -v "$b" >/dev/null || echo "FALTA: $b (instale o ffmpeg)"; done
python3 - <<'E' || true
import importlib.util as u
falta = [m for m in ("PIL", "numpy", "edge_tts", "librosa") if u.find_spec(m) is None]
if falta: print("FALTA (pip install pillow numpy edge-tts librosa):", ", ".join(falta))
E
echo "OK pasta de trabalho: $DEST"
