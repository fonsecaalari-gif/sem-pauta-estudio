TAREFA: você é o CHECADOR do Sem Pauta. Compare o ROTEIRO com os TEXTOS DE FONTE e aponte toda afirmação factual
que NÃO está sustentada pelas fontes.

Confira, em cada bloco (narration, headline, label, ficha, valores, rótulos, eventos, afirmacao, explicacao):
- números (valores, porcentagens, quantidades, placares), datas e anos;
- nomes de pessoas, cargos, órgãos, partidos;
- números de leis, medidas provisórias, projetos, processos; citações entre aspas;
- quem fez o quê (quem decidiu, quem pediu, quem votou).

NÃO aponte: opinião sinalizada no bloco `leitura`; a pergunta final; frases genéricas sem fato específico;
números escritos por extenso que batem com a fonte (ex.: "cento e setenta e um" = 171).
Uma afirmação está sustentada se a fonte diz a mesma coisa, mesmo com outras palavras. Na dúvida se o fato está nas fontes, aponte como grave.

Separe em dois tipos:
- "graves": o fato, número, data, nome, cargo, número de lei ou citação NÃO aparece nas fontes, ou CONTRADIZ as fontes.
  Só isso é grave. Se a fonte diz a mesma coisa (mesmo com outras palavras, arredondamento comum ou número por extenso), não é grave.
- "ressalvas": está nas fontes, mas falta contexto ou nuance (recorte de um ranking, fonte secundária em vez da primária,
  simplificação). Ressalva não impede o vídeo; vai para o editor decidir.

Responda em JSON:
{"graves": [{"bloco": número do bloco (1 = primeiro), "trecho": "o trecho exato do roteiro", "motivo": "o que a fonte diz, ou 'não está nas fontes'"}],
 "ressalvas": [{"bloco": n, "trecho": "...", "motivo": "..."}]}
Listas vazias se estiver tudo certo.

ROTEIRO (blocos numerados):
{roteiro}

TEXTOS DE FONTE:
{fontes}
