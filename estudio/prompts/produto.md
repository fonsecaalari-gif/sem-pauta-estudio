TAREFA: escrever um Short da série **Sem Pauta Útil** no formato "Viral + Solução".

O vídeo parte de um post viral e entrega uma solução útil de verdade, mesmo para quem não comprar nada.
O produto aparece SÓ numa frase-ponte no fim da última narração: "E se quiser ir além, deixei na descrição {tipo_material} que eu uso pra isso."
Nada de preço, "compre", urgência, nome do produto no título ou na tela. Nada de política.
Só afirme sobre o produto o que está em "Pode afirmar" da FICHA. Fale do viral com respeito (comente a ideia, não a pessoa).

ESTRUTURA (4 cenas):
1. `viral` — "Esse vídeo viralizou essa semana: ..." + a pergunta que todo mundo fez. Campo "ficha": "PLATAFORMA · @PERFIL".
2. `fato` com "tag": "O PROBLEMA" — por que aquilo acontece / por que a ideia do viral falha ou funciona só em parte.
3. `fato` com "tag": "A SOLUÇÃO" — 2 ou 3 passos práticos que a pessoa faz hoje.
4. `pergunta` — pergunta de comentário ligada ao viral + a frase-ponte.
Narração total: 90 a 130 palavras.

DESCRIÇÃO, nesta ordem: (1) {linha_identificacao} (2) "👉 {frase do material}: {link}" (3) "O vídeo que viralizou: {viral_url} (@perfil, plataforma). Print usado como citação."
(4) resumo em 1 frase (5) a pergunta (6) "Siga o Sem Pauta: https://youtube.com/@somos.sempauta".
Título: a pergunta sobre o viral (ex.: "O desafio X viralizou. Funciona?"), nunca o nome do produto.

FORMATO (JSON): {"slug", "title", "description", "hashtags": ["#SemPautaÚtil", "#Shorts", ...], "fontes": [...],
 "scenes": [{"type": "viral", "tag": "VIRALIZOU", "ficha": "...", "narration": "..."},
            {"type": "fato", "tag": "O PROBLEMA", "ficha": "...", "headline": "...", "narration": "...", "busca_imagem": "..."},
            {"type": "fato", "tag": "A SOLUÇÃO", "ficha": "FAÇA HOJE", "headline": "...", "narration": "...", "busca_imagem": "..."},
            {"type": "pergunta", "headline": "...", "narration": "...", "busca_imagem": "..."}]}

FICHA DO PRODUTO:
{ficha}

O VIRAL:
{viral}
