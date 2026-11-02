# Proposta — Sequências de Acordes Customizadas

## Contexto e decisão

A abordagem escolhida é a **Proposta 1**: uma única regra de matching, calculada em
tempo real sobre `musica.cifra`, aplicada a todo o catálogo (as 6 originais e as
novas), com o catálogo de sequências persistido em **SQLite**.

O motivo principal é o critério de regressão: das quatro definições de matching
testadas na pesquisa, só "ocorrência contígua + todos os acordes da música
pertencerem à sequência" reproduz as tags atuais (0 divergências em 67.585 músicas,
contagens 199/296/4/5/7/3). Adotá-la para todo o catálogo elimina a necessidade de
tratamento especial para as 6 originais e mantém **uma única semântica** — o que a
alternativa híbrida não consegue.

Decisões fechadas nesta fase:

- comparação **exata** de tokens (caixa preservada), sem `lower()`;
- `nome` é opcional;
- `?sequencia=` aceita **string arbitrária**, não só as 6 chaves legadas;
- a regra estrita vale também para sequências novas;
- caminho padrão para o arquivo do banco, com volume nomeado no Docker;
- sequências com a mesma lista de acordes são deduplicadas (retorna a existente);
- teto de 500 sequências no catálogo.

## Abordagem escolhida

### Algoritmo de matching

Uma música `m` casa com a sequência `S = [a1..an]` se, e somente se:

1. `set(m.cifra) ⊆ set(S)` — a música não usa nenhum acorde fora da sequência; e
2. existe `i` tal que `m.cifra[i:i+n] == S` — a sequência ocorre como fatia
   contígua.

A comparação é token a token, exata: `AM7` e `Am7` são acordes diferentes, e não há
normalização de caixa, enharmônicos, barras ou parênteses. O dataset tem 151 grupos
de tokens que diferem só por caixa, vários com qualidades harmônicas distintas, então
`lower()` seria uma fonte de falso positivo (ver pesquisa, §1).

Ordem importa (a fatia é contígua) e repetição importa (a fatia exige a mesma
quantidade de ocorrências). Acorde extra na música desqualifica, mesmo que a sequência
apareça: é o que faz `EmG` casar com 4 músicas em vez de 3.110.

Pseudocódigo:

```python
def casa_sequencia(acordes_seq, musica):
    seq_set = set(acordes_seq)
    if not set(musica.acordes) <= seq_set:
        return False
    n, cifra = len(acordes_seq), musica.cifra
    return any(cifra[i:i+n] == acordes_seq for i in range(len(cifra) - n + 1))
```

Custo medido sobre as 67.585 músicas carregadas: **~40 ms por busca**. Isso é ~5×
mais lento que o lookup na tag (~7 ms) e ~5× mais rápido que a busca por acordes que
já existe em produção (183–231 ms). Não há necessidade de pré-computar tags nem de
índice invertido; se o custo virar problema, pré-computar `set(musica.acordes)` no
startup derruba para 3–8 ms, desde que **não** seja guardado como atributo de
`Musica` (o `/musicas` serializa `musica.__dict__` e `json.dumps` falharia com `set`).

### Banco de dados

**SQLite**, via `sqlite3` da stdlib. Sem dependência nova, sem serviço/container
adicional, arquivo único, transações e constraints — compatível com o Docker único e
local do ADR 0001. O volume de dados é minúsculo (6 registros hoje), então performance
não é critério; integridade e simplicidade são.

- Arquivo: `var/deciframe.db` (relativo ao CWD), com override por
  `DECIFRAME_DB_PATH`. Funciona igual no venv (`./var`) e no container (`/app/var`).
- Docker: `VOLUME ["/app/var"]` e `docker run -v deciframe-data:/app/var`. O volume
  **não** pode ser montado em `/app/data`, porque ali está o CSV que o app lê.
- `.gitignore` e `.dockerignore` passam a ignorar `var/`, para um banco de
  desenvolvimento não entrar na imagem via `COPY . .`.
- `journal_mode=WAL`, `foreign_keys=ON`, `timeout=5` e uma conexão por operação.
  O gunicorn roda com 1 worker (default), então não há concorrência de escrita real.
- Schema e seed são criados no startup, de forma idempotente. As 6 originais são
  inseridas com IDs explícitos 0–5, para preservar os IDs que já existem no backend.
- Migração: `PRAGMA user_version`, aplicada passo a passo no startup. O detalhamento
  fica para o plano.

Músicas e gêneros continuam no CSV em memória. A coluna 7 (`SEQ_FAMOSA`) continua
sendo carregada em `musica.seqs_famosas`, mas deixa de ser consultada pela busca por
sequência — é dado legado preservado para não alterar o contrato do CSV.

### Esquema de dados (alto nível)

| tabela | campos | papel |
|---|---|---|
| `sequences` | `id` (PK), `nome` (nullable), `chords_key` (único), `legacy_key` (único, nullable), `criada_em` | cabeçalho da sequência; `chords_key` é a lista canônica de acordes serializada em JSON |
| `sequence_chords` | `sequence_id` (FK), `posicao`, `acorde`; PK `(sequence_id, posicao)` | acordes na ordem, um por linha |

`chords_key` em JSON (`'["Bm","G","D","A"]'`) em vez de concatenação porque preserva
a ordem e evita a ambiguidade de listas como `['Am','G']` vs `['A','mG']`. É a chave
de unicidade, o que dá deduplicação sem código extra. `legacy_key` guarda `BmGDA`,
`CGAmF`, `EmG`, `CA7DmG7`, `GmF` e `CC7FFm` apenas nas 6 originais, para o parâmetro
antigo continuar funcionando.

A tabela filha, em vez de uma lista serializada, mantém a ordem explícita e
consultável — a ordem é semântica nesta feature.

### API

Todos os retornos continuam `json.dumps(...)`, nunca `jsonify`; o Content-Type segue
`text/html`, como no resto da aplicação.

**`GET /sequencias`** — array ordenado por `id`:

```json
[{"id": 0, "nome": null, "acordes": ["Bm", "G", "D", "A"]}]
```

**`POST /sequencias`** — body JSON `{"nome": "...", "acordes": [...]}`. `nome` é
opcional e `acordes` aceita lista ou string separada por vírgula/espaço.

| caso | status | corpo |
|---|---|---|
| criada | 201 | `{"id": 6, "nome": "...", "acordes": [...], "total_musicas": 28}` |
| já existe | 200 | o registro existente |
| inválida | 400 | `{"erro": "<motivo>"}` |

Validação: `acordes` obrigatório, 1–32 tokens, cada token de 1–24 caracteres, sem
caracteres de controle, `strip` e caixa preservada; `nome` opcional, `strip`, até 80
caracteres, vazio vira `NULL`; catálogo limitado a 500 sequências. Os limites são
folgados em relação ao dataset (maior token real: 17 caracteres) e servem também para
limitar abuso, já que o cadastro é anônimo.

`total_musicas` no retorno do POST existe porque a regra estrita faz muitas sequências
novas retornarem zero — o autor descobre isso na hora, em vez de concluir que a busca
quebrou.

**`GET /similares`** — precedência `acordes` > `id_unico_musica` > `sequencia_id` >
`sequencia`:

- `sequencia_id=<id>`: resolve no catálogo e aplica o matcher. ID desconhecido ou não
  numérico devolve `[]` com 200, igual ao contrato atual para sequência desconhecida.
- `sequencia=<string>`: se bater em `legacy_key`, usa os acordes do catálogo; senão,
  faz split em vírgula/espaço e aplica o matcher ad-hoc.
- Paginação (100) e filtro por gênero inalterados.

Impacto nos contratos existentes:

| request | hoje | depois |
|---|---:|---:|
| `?sequencia=BmGDA` | 199 | 199 |
| `?sequencia=Bm,G,D,A` | 199 | 199 |
| `?sequencia=CGAmF&pagina=3` | 96 | 96 |
| `?sequencia=bmgda` | 0 | 0 |
| `?sequencia=Bm G D A` | 0 | 199 (novo, intencional) |
| `?sequencia_id=0` | 0 | 199 (novo) |

A ordem dos resultados também se mantém: o matcher percorre a mesma coleção na mesma
ordem que o filtro por tag, então a regressão pode comparar a lista completa, não só o
conjunto de `id_unico_musica`.

### Frontend

Em `#/porsequencia`:

- a lista hardcoded de 4 sequências sai do controller e passa a vir de
  `GET /sequencias`; cada item vira `{id, nome, rotulo, acordes: [{acorde, cor}]}`,
  mantendo a diretiva `df-hex` intacta. `rotulo` é o nome quando existe, senão os
  acordes unidos por `" - "`;
- a busca passa a enviar `sequencia_id` em vez da string de acordes;
- um formulário (nome opcional + campo de acordes separados por vírgula/espaço) faz
  `POST /sequencias` e, no sucesso, insere a sequência no catálogo e já busca por ela;
- paginação: `pagina` + botão "carregar mais" concatenando páginas, resolvendo o
  truncamento em 100 de `BmGDA` (199) e `CGAmF` (296);
- remove-se `ng-hide="music.diferenca.length"`, que é sempre falso (resultado de
  sequência não tem `diferenca`).

O dropdown de gênero continua com a constante estática de 51 gêneros. Trocar por
`GET /generos` (52, incluindo `R&B;`) é uma correção real, mas independente desta
feature — fica fora do escopo.

## Alternativas consideradas e descartadas

**Híbrida (Proposta 2): manter a tag nas 6 originais e usar outra regra só nas novas.**
Preservaria a regressão sem calcular nada em tempo real e daria resultados mais úteis
para sequências novas (`EmG` novo casaria com 3.110 em vez de 4). Foi descartada por
criar duas semânticas para a mesma lista de acordes: quem cadastrasse `BmGDA` veria um
conjunto diferente do da original, e o teste passaria a precisar cobrir os dois
caminhos. O ganho de utilidade não compensa a inconsistência, e a regra estrita é
aceitável para o catálogo novo.

**Outras regras de matching** (só ocorrência contígua, subsequência ordenada, conjunto
de acordes): todas são mais permissivas e retornam 866 / 4.763 / 5.768 músicas para
`BmGDA`, contra 199 da tag. Só seriam compatíveis com o requisito de regressão se as 6
originais continuassem usando a tag — ou seja, cairiam na alternativa híbrida.

**CSV/JSON, TinyDB, `shelve`/`dbm` ou DuckDB no lugar do SQLite:** CSV/JSON não tem
constraints nem transações e provavelmente não atende à letra de "banco de dados";
TinyDB/DuckDB adicionam dependência sem ganho para 6 registros; `shelve`/`dbm` não tem
consultas relacionais nem chave única composta. SQLite é stdlib, transacional e
suficiente.

**`localStorage` ou JSON estático no frontend:** não é compartilhado entre visitantes
nem sobrevive a outro dispositivo, e o requisito é persistência no servidor.

## Escopo explícito

**Dentro do escopo:**

- regra de matching única em tempo real, aplicada às 6 originais e às novas;
- SQLite com `sequences` + `sequence_chords`, seed idempotente das 6 originais;
- `GET /sequencias`, `POST /sequencias`, `sequencia_id` em `/similares` e suporte a
  string arbitrária em `?sequencia=`;
- `#/porsequencia` com catálogo dinâmico, cadastro e paginação;
- volume nomeado, `.gitignore`/`.dockerignore` e atualização do comando no README;
- ADR 0002 e testes (matcher, store, API, regressão das 6, persistência).

**Fora do escopo (e por quê):**

- editar/excluir sequências: o requisito é cadastro e busca; exclusão anônima
  destruiria o catálogo sem autenticação;
- autenticação, moderação ou rate limiting: não há login no produto e o deploy é
  local; o teto de 500 e os limites de tamanho são a mitigação possível;
- trocar o dropdown de gêneros por `GET /generos`: correção independente;
- normalizar/equiparar acordes (enharmônicos, barras, parênteses): exigiria uma tabela
  de equivalências que não existe, e a comparação exata foi a decisão tomada;
- migrar músicas/gêneros para o banco: fixado pelo enunciado;
- alterar a coluna `SEQ_FAMOSA` do CSV: ela fica como está, apenas deixa de ser
  consultada.
