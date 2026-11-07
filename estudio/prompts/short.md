TAREFA: escrever um Short (vertical, 35–55 s) no formato "O Corte" sobre o tema abaixo.

ESTRUTURA (4 a 6 cenas, nesta ordem):
1. `gancho` — o fato mais forte em até 14 palavras de narração. Manchete com até 5 palavras.
2. `fato` (1 ou 2) — o que aconteceu, quem, quando. Campo `ficha`: "FATO · DD.MM.AAAA · FONTE: VEÍCULO".
3. `dado` (opcional, só se houver número NAS FONTES) — `value` (número), `decimals`, `prefix`, `suffix`, `label` (frase curta com *destaque*).
4. `leitura` — o que está em jogo, na nossa leitura (opinião). Narração começa com "Na nossa leitura".
5. `outro_lado` — 1 ou 2 frases do argumento contrário, atribuído. `headline` é a citação/resumo do argumento.
6. `pergunta` — UMA pergunta de comentário. `headline` é a pergunta.
Narração TOTAL: 90 a 140 palavras. Cada cena: 12 a 35 palavras.

FORMATO DA RESPOSTA (JSON):
{
  "slug": "palavras-chave-curtas-com-hifen",
  "title": "título até 70 caracteres, direto, sem clickbait que o vídeo não cumpra",
  "description": "texto completo da descrição (ver regras)",
  "hashtags": ["#SemPauta", "#Shorts", "#Tema", "#PolíticaBrasileira"],
  "fontes": [{"veiculo": "Agência Brasil", "url": "https://..."}],
  "scenes": [
    {"type": "gancho", "tag": "URGENTE", "headline": "Congresso *derruba* veto", "narration": "...", "busca_imagem": "Congresso Nacional Brasília"},
    {"type": "fato", "ficha": "FATO · 05.11.2026 · FONTE: AGÊNCIA BRASIL", "headline": "...", "narration": "...", "busca_imagem": "..."},
    {"type": "dado", "value": 4.2, "decimals": 1, "prefix": "R$ ", "suffix": " BI", "label": "é o *custo* estimado ...", "narration": "...", "busca_imagem": "..."},
    {"type": "leitura", "headline": "...", "narration": "Na nossa leitura, ...", "busca_imagem": "..."},
    {"type": "outro_lado", "headline": "...", "narration": "O governo diz que ...", "busca_imagem": "..."},
    {"type": "pergunta", "headline": "Quem *ganha* com isso?", "narration": "...", "busca_imagem": "..."}
  ]
}
O exemplo mostra o formato; o conteúdo vem só das fontes abaixo.

TEMA: {tema}
ÂNGULO: {angulo}
DATA DE HOJE: {hoje}

TEXTOS DE FONTE:
{fontes}
