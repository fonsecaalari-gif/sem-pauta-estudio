# INSTRUÇÃO PARA O MODELO — VÍDEO DE PRODUTO EM DIAS ALTERNADOS (Sem Pauta v3)

Além dos Shorts de notícia e do vídeo longo, produza **1 Short a mais em dias alternados (dia sim, dia não)** da série **"Sem Pauta Útil"**.

**É dia de vídeo de produto?** Leia `produtos/historico_produto.json` e veja a data do último vídeo:
- se foi **ontem** → hoje **não** tem vídeo de produto; entregue só os outros vídeos e não mencione o produto;
- se foi **anteontem ou antes**, ou se o histórico está vazio → hoje **tem** vídeo de produto.
Nunca faça dois dias seguidos nem pule dois dias seguidos (se pulou, faça hoje e siga alternando a partir daqui).
Objetivo: entregar algo **útil de verdade** sobre o tema do produto e deixar o produto como **o próximo passo natural**,
com o link na descrição. O vídeo **não tem cara de anúncio**: nada de "compre", "promoção", "corre", preço na tela ou cupom gritado.
Leia antes: `produtos/produto.md` (ficha do produto, preenchida pelo dono do canal) e `produtos/historico_produto.json`.

## 1. Regras que não se negociam
1. **Separação editorial.** O vídeo de produto nunca fala de política, governo, eleição ou de notícia que o canal cobre, e nenhum
   vídeo de notícia menciona o produto. Se o tema do produto encostar numa pauta do dia, escolha outro ângulo.
2. **Transparência mínima obrigatória** (CDC art. 36, Guia de Publicidade por Influenciadores do CONAR, política do YouTube):
   - 1ª linha da descrição: a linha de identificação definida em `produto.md` (ex.: "Link de afiliado: o canal recebe comissão se você comprar.").
   - Lembre o dono do canal de marcar **"Inclui promoção paga"** no YouTube Studio quando houver comissão, pagamento ou permuta.
   - Isso é discreto (fica na descrição e num aviso automático do YouTube) e protege o canal. **Nunca** omita, esconda no fim nem disfarce.
3. **Só afirme o que está em "Pode afirmar"** em `produto.md`. Nada de promessa de resultado, depoimento inventado, número sem fonte,
   escassez falsa ("últimas unidades") ou comparação com concorrente.
4. Saúde, dinheiro e direito: só informação geral com fonte oficial; nunca orientação individual.
5. Mesmas regras de imagem dos outros vídeos: foto licenciada ou imagem do próprio produto (fornecida em `produtos/imgs/`). Nada de rosto de pessoa real sem autorização, exceto no print do post viral usado como citação (seção 2).

## 2. O viral do dia (ponto de partida de todo vídeo)
Todo vídeo começa de **um post que está viralizando** e termina na **solução**. É isso que deixa o vídeo natural.
1. **Busca:** procure em TikTok, Reels, YouTube Shorts e X posts dos **últimos 7 dias** ligados aos *temas permitidos* de `produto.md`
   (um desafio, uma reclamação, um "hack", uma polêmica de consumo, um erro que todo mundo comete).
2. **Filtros (todos obrigatórios):**
   - tração real e visível (visualizações/curtidas altas para o nicho) — anote o número **como aparece no post**, sem inventar;
   - autor é perfil público ou criador de conteúdo; **nunca** pessoa comum exposta, menor de idade, vítima, ou alguém em situação vexatória;
   - nada de política, governo, eleição ou de pauta que o canal cobre;
   - o viral é verdadeiro (não é montagem, IA ou golpe) — se houver dúvida, descarte;
   - o problema do viral é resolvido, de verdade, pela solução que você vai ensinar.
3. **Uso do viral = citação, não cópia** (Lei 9.610, art. 46, III):
   - use **um print** de um quadro do post (com o @ visível) no bloco `viral`; salve em `produtos/imgs/AAAA-MM-DD_print.jpg`;
   - **nunca** baixe, reposte ou use o áudio/vídeo do post; nunca use a música dele;
   - cite `@perfil` e a plataforma no campo `credit` e o **link do post original** na descrição;
   - fale do viral com respeito: comente a ideia, não ridicularize a pessoa.
   - (Opcional, feito pelo dono do canal no app: se o viral for um Short do YouTube, dá para usar o recurso **Remixar** do próprio YouTube.)
4. Sem viral que passe nos filtros? Use o melhor post viral dos últimos 30 dias que ainda não foi usado; se nenhum servir, não produza o vídeo de produto hoje e avise.
Registre em `produtos/historico_produto.json`: `{"data": "AAAA-MM-DD", "viral": "link", "perfil": "@…", "tema": "…", "titulo": "…"}`.
Não repita viral nem tema dos últimos 30 dias.

## 3. Roteiro "Viral + Solução" (35–50 s, 90–130 palavras)
| # | Bloco | Tempo | O que dizer |
|---|---|---|---|
| 1 | `viral` | 0–6 s | "Esse vídeo viralizou essa semana: …" — descreva o post em 1 frase e faça a pergunta que todo mundo fez ("Funciona mesmo?"). |
| 2 | `fato` (tag `O PROBLEMA`) | 6–20 s | Por que aquilo acontece / por que a ideia do viral falha ou funciona só em parte. Fato verificável, com fonte se tiver número. |
| 3 | `fato` (tag `A SOLUÇÃO`) | 20–38 s | A solução prática, em 2–3 passos que a pessoa faz **hoje, mesmo sem o produto**. |
| 4 | `pergunta` | 38–50 s | Pergunta de comentário ligada ao viral + **uma única frase-ponte**: "E se quiser ir além, deixei na descrição o [tipo de material] que eu uso pra isso." |
- O produto **só** aparece na frase-ponte e na descrição. Nunca no título, na tela, no print ou nas manchetes.
- Opcional entre 2 e 3: um bloco `dado` com número oficial que dimensione o problema.
- **Não use** os blocos `leitura` nem `outro_lado`; este vídeo não é jornalismo opinativo.
- Título: a pergunta sobre o viral ("O desafio X viralizou. Funciona?"), nunca o nome do produto.

## 4. Produção
1. Copie `templates/spec_produto_exemplo.json` para `specs/AAAA-MM-DD_P_<slug>.json` e preencha.
2. Prévia: `python3 scripts/render_short.py specs/<arquivo>.json --tts edge --preview 1.5,12,28,42`; confira os PNGs em `preview/`.
3. Render: `python3 scripts/render_short.py specs/<arquivo>.json --tts edge`.
4. Checklist: `templates/checklist_qualidade.md` (parte técnica) + os itens da seção 1 acima.

## 5. Metadados
- **Título** (≤ 70 caracteres): o benefício ou a pergunta do conteúdo, nunca o nome do produto.
- **Descrição** (nesta ordem):
  1. linha de identificação de `produto.md`;
  2. `👉 <frase curta do material> : <link>` (o link de `produto.md`);
  3. `O vídeo que viralizou: <link do post original> (@perfil, plataforma). Print usado como citação.`
  4. resumo do vídeo em 1 frase; `Fontes:`; `Imagens:`; "Narração gerada por voz sintética." (se for o caso);
  5. pergunta do vídeo; link do canal.
- **Hashtags:** `#SemPautaÚtil #Shorts` + 2–3 do tema do produto (nunca hashtags políticas).
- Fixe um comentário com a pergunta do vídeo (não com o link).

## 6. Resposta final neste chat
Só nos dias de vídeo de produto: na mesma mensagem dos outros vídeos, em seção separada **"Vídeo extra — Sem Pauta Útil"**: MP4, título, descrição pronta
(com a identificação na 1ª linha e o link), hashtags e o lembrete: *marcar "Inclui promoção paga" no YouTube Studio*.
Se a ficha `produto.md` estiver incompleta (sem link, sem vínculo ou sem "Pode afirmar"), **não produza** o vídeo de produto e diga o que falta.
