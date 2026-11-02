# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

A suíte usa `unittest` da stdlib e não depende de serviço externo. São 30 testes,
todos passando.

**`tests/test_matching.py`** (10 testes) — a regra de matching isolada, com objetos
`Musica` reais:

- sequência exata casa;
- música com acorde fora da sequência é rejeitada;
- ordem trocada é rejeitada;
- cifra vazia e sequência vazia são rejeitadas;
- música menor que a sequência não casa;
- repetição é respeitada (`A A B` exige duas ocorrências contíguas de `A`);
- comparação é exata: `AM7` não casa com `Am7` (nem o contrário);
- `parse_acordes` aceita vírgula/espaço, ignora vazios e devolve lista vazia para
  string em branco.

**`tests/test_store.py`** (8 testes) — `SequenceStore` contra SQLite real em diretório
temporário:

- `init_db()` duas vezes continua com 6 sequências, IDs 0–5 e ordem dos acordes
  preservada;
- criação gera ID 6 e mantém a ordem informada;
- mesma lista de acordes devolve o registro existente (`criado=False`), inclusive
  depois de normalizar espaços, sem duplicar;
- nome vazio vira `NULL`;
- uma nova instância do store enxerga o que foi gravado (persistência no arquivo);
- matriz de validação: lista vazia, acorde vazio, mais de 32 acordes, acorde com
  mais de 24 caracteres, nome com mais de 80, caractere de controle, `acordes` como
  string, item não textual e nome não textual — todos `ValidacaoError`;
- teto de 500: após 500 sequências, cadastrar uma nova falha, mas uma duplicata
  continua retornando a existente.

**`tests/test_api.py`** (10 testes) — rotas com `app.test_client()` e um banco
temporário por teste:

- `GET /sequencias` devolve o catálogo semeado, ordenado por ID, com
  `Content-Type: text/html`;
- `POST /sequencias` válido devolve 201, ID 6, acordes normalizados e
  `total_musicas` (28 para `C, G, Am`);
- POST com acordes em string devolve o mesmo resultado;
- duplicata devolve 200, o mesmo ID e mantém o nome original;
- corpos inválidos devolvem 400 com `erro`;
- `sequencia_id` válido busca, desconhecido/não numérico devolve `[]`;
- sequência recém-cadastrada é buscável por `sequencia_id`;
- compatibilidade: `?sequencia=BmGDA`, `?sequencia=Bm,G,D,A`,
  `?sequencia=Bm G D A` e `CGAmF&pagina=3` (96) funcionam; `bmgda` devolve `[]`.

**`tests/test_regression.py`** (2 testes) — regressão e resolução de parâmetros:

- para cada uma das 6 originais, a lista completa de `id_unico_musica` produzida
  pelo matcher é comparada com a lista derivada de `musica.seqs_famosas`, usando a
  mesma coleção e a mesma ordem de `apply_filtro`;
- `acordes_da_sequencia` resolve tanto a chave legada (`BmGDA`) quanto o
  `sequencia_id` para os acordes do catálogo.

Além da suíte, o frontend foi verificado com `node --check` (sintaxe) e a API foi
exercitada com gunicorn real: `GET /sequencias`, `POST` 201, busca por
`sequencia_id`, paginação e reinício do processo com o registro preservado. O fluxo
de `#/porsequencia` também foi exercitado manualmente no browser: as 6 originais
aparecem com rótulo e acordes; `BmGDA` carrega 100 cartões e chega a 199 com
"Carregar mais"; depois da revisão do cadastro por paleta, montar `C, G, Am` por
cliques devolveu 201 e 28 músicas, repetir os mesmos acordes devolveu 200, o
catálogo não duplicou, remover/limpar a seleção funcionou e o 33º clique foi
bloqueado com o aviso de limite de 32. `#/poracordes` foi reconferido: 7 grupos, 36
acordes, mesmas cores e alternância (toggle) inalterada.

## Teste de regressão obrigatório

O teste compara a **lista completa e a ordem** dos resultados, não só o conjunto de
IDs. O esperado é montado em tempo de teste a partir da coluna `SEQ_FAMOSA`, com a
mesma coleção usada pela busca, e comparado ao resultado de `casa_sequencia`.

Resultado: **0 divergências**. As contagens continuam exatamente
**199 / 296 / 4 / 5 / 7 / 3** para `BmGDA`, `CGAmF`, `EmG`, `CA7DmG7`, `GmF` e
`CC7FFm`, na mesma ordem de antes.

Também foram conferidos os caminhos HTTP equivalentes: `?sequencia=BmGDA` e
`?sequencia=Bm,G,D,A` devolvem a mesma primeira página; `?sequencia=CGAmF&pagina=3`
devolve 96; `?sequencia_id=0` devolve a mesma sequência; `?sequencia=bmgda`
continua devolvendo `[]` (comparação exata de caixa).

Persistência: com `DECIFRAME_DB_PATH` apontando para um arquivo temporário, um POST
criou a sequência 6, o processo gunicorn foi encerrado e reiniciado, e
`GET /sequencias` continuou devolvendo 7 registros com a sequência criada.

Custo medido do matcher neste ambiente: ~42–48 ms por busca nas 67.585 músicas
(antes, o lookup na tag era ~7 ms; a busca por acordes existente é 183–231 ms).

## Como rodar

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
```

Sem ativar o virtualenv, o equivalente é
`.venv/bin/python -m unittest discover -s tests`. A suíte define um banco temporário
antes de importar `main`, então não toca em `var/deciframe.db`.

## O que ficou de fora

- **Docker/volume:** o daemon não estava disponível no ambiente, então não foi
  possível rodar `docker build`, `docker restart`, `docker rm` com volume nomeado
  nem confirmar `import sqlite3` na imagem `python:3.9-slim`. O `Dockerfile` declara
  `VOLUME ["/app/var"]`, `var/` está no `.gitignore` e no `.dockerignore`, e a
  persistência foi validada no nível de processo (reinício do gunicorn), não de
  container.
- **Frontend:** não há infraestrutura de teste JS no projeto (sem Karma/Jasmine nem
  build step). Catálogo dinâmico, cadastro por cliques na paleta, duplicata e
  "carregar mais" foram verificados manualmente no browser, por `node --check` e pela
  API que os alimenta, mas não por teste automatizado de browser.
- **Concorrência:** o gunicorn roda com 1 worker, então não há teste de escrita
  concorrente. O SQLite usa `timeout=5`, mas múltiplos workers não fazem parte do
  deploy atual.
- **Backup com WAL:** o procedimento com `.backup` está documentado, mas não foi
  testado.
- **Segurança/abuso:** limites de tamanho e teto de 500 são testados; não há teste
  de rate limiting, autenticação ou moderação, que estão fora do escopo.
