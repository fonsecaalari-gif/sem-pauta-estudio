# Pedidos de produção

Enviar (commit + push) um arquivo `.json` nesta pasta dispara o workflow **Produzir vídeos**,
e os arquivos prontos são publicados numa release `producao-N` (pré-lançamento).

```json
{"acao": "hoje", "tema": "", "quadro": "", "quantos": 3, "viral_url": "", "somente_roteiro": false}
```
`acao`: hoje | shorts | longo | tutorial | produto. Os outros campos são opcionais.
