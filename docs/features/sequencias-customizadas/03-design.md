# Sequências de Acordes Customizadas — Design Document

Checklist de execução: [03-plan.md](03-plan.md).

## Contexto Atual

- O backend é um único `main.py` que carrega `data/top/dataset_final.csv` em memória no
  import (`main.py:49-98`): 67.585 músicas, 52 gêneros, 6.653 acordes distintos. Não há
  banco, ORM, schema, migração nem volume.
- A busca por sequência (`GET /similares?sequencia=`) faz lookup exato em um dicionário
  de 6 chaves (`main.py:40-45`) e filtra por `str(id_seq) in musica.seqs_famosas`, a
  coluna 7 do CSV (`main.py:203-223`). Nada é comparado com `musica.cifra` em tempo de
  requisição.
- A tag da coluna 7 foi gerada por `get_famosas` (`scripts/generate_data_set.py:7-24`)
  com a regra "ocorrência contígua + todos os acordes da música pertencem à sequência".
  Reaplicada sobre os dados atuais, reproduz as tags com 0 divergências
  (199/296/4/5/7/3 músicas).
- O frontend `#/porsequencia` tem 4 sequências hardcoded em JS (`sequencia.js:2-37`) e
  envia a lista de acordes como string; faltam as IDs 2 e 3, não há cadastro, catálogo,
  POST nem paginação (só os 100 primeiros resultados).
- Lacuna a resolver: qualquer visitante precisa poder cadastrar uma sequência e buscá-la,
  com o catálogo persistido, sem quebrar os resultados das 6 originais.

## Requisitos

### Funcionais

- Cadastro anônimo de sequência (lista ordenada de acordes), sem login.
- Busca por qualquer sequência do catálogo, com os mesmos resultados de hoje para as 6
  originais.
- Catálogo persistido em banco e sobrevivente a reinício do container.
- `#/porsequencia` lê o catálogo do backend (não hardcoded) e permite cadastrar.
- Cadastro por clique: a sequência é montada clicando nos mesmos botões hexagonais de
  `#/poracordes`; não há campo de texto para acordes (o nome segue opcional).
- Compatibilidade: `?sequencia=BmGDA` continua funcionando; `?sequencia=` passa a aceitar
  string arbitrária; `?sequencia_id=` é o novo seletor estável.
- Endpoints continuam retornando `json.dumps(...)`, não `jsonify`.

### Não Funcionais

- Container único e local (ADR 0001), sem serviço externo; `requirements.txt` sem
  dependência nova.
- Custo da busca por sequência na mesma ordem de grandeza da busca por acordes existente
  (medido: ~40 ms contra 183–231 ms).
- Python 3.9 (`Dockerfile:1`): apenas stdlib.
- Banco pequeno (6 registros hoje, teto de 500) e um único escritor (gunicorn com 1
  worker).
- Nenhuma mudança na coluna `SEQ_FAMOSA` do CSV.

## Decisões de Design

### 1. Regra de matching única, calculada em tempo real

Uma música casa com a sequência `S` se `set(musica.cifra) ⊆ set(S)` **e** `S` ocorre como
fatia contígua de `musica.cifra`; comparação exata de tokens, sem `lower()`.

- É a única das regras testadas que reproduz as tags atuais (0 divergências), então as 6
  originais passam na regressão sem tratamento especial.
- Elimina a necessidade de pré-computar tag para sequências novas.
- Ordem e repetição são semânticas; `AM7` ≠ `Am7` (151 grupos de tokens diferem só por
  caixa no dataset).
- Trade-off aceito: a regra é restritiva (`EmG` casa com 4 músicas, não 3.110). Mitigado
  expondo `total_musicas` no cadastro.
- Alternativa descartada: manter a tag nas 6 e usar regra mais permissiva nas novas
  (duas semânticas para a mesma lista de acordes).

### 2. SQLite embarcado

`sqlite3` da stdlib, arquivo único em `var/deciframe.db`.

- Não é serviço externo, não adiciona dependência nem processo; respeita o container
  único do ADR 0001.
- Transações, constraints e chave única — o que CSV/JSON não oferece.
- Trade-offs: schema evoluído à mão via `PRAGMA user_version`; um escritor por vez (sem
  impacto com 1 worker); backup precisa considerar o WAL.
- Alternativas descartadas: CSV/JSON (sem constraints/atomicidade), TinyDB e DuckDB
  (dependência sem ganho), `shelve`/`dbm` (sem unicidade nem consultas).

### 3. Duas tabelas, com chave canônica em JSON

`sequences` + `sequence_chords` (acorde por linha, com posição).

- A ordem é semântica, então precisa ser explícita e consultável.
- `chords_key` = JSON da lista (`'["Bm","G","D","A"]'`) preserva ordem e evita a
  ambiguidade de concatenação (`['Am','G']` vs `['A','mG']`); como é `UNIQUE`, a
  deduplicação sai de graça.
- IDs 0–5 são semeados explicitamente para preservar a identidade já usada no backend;
  `AUTOINCREMENT` segue em 6.

### 4. Persistência fora de `data/`

Arquivo em `var/deciframe.db`, `VOLUME /app/var` e volume nomeado no `docker run`.

- Montar sobre `/app/data` sombrearia o CSV que o app lê — o caminho é separado de
  propósito.
- `var/` entra em `.gitignore` e `.dockerignore` para um banco de dev não ir para a
  imagem via `COPY . .`.
- Trade-off: sem volume, os dados sobrevivem a `docker restart` mas não a `docker rm` ou
  rebuild; precisa estar documentado no README.

### 5. API com ID estável, string arbitrária e deduplicação

- `GET /sequencias` (catálogo), `POST /sequencias` (cadastro), `sequencia_id` em
  `/similares`; `?sequencia=` mantém as 6 chaves legadas via `legacy_key` e, para
  qualquer outro valor, aplica o matcher ad-hoc.
- Duplicata (mesma lista de acordes) retorna **200** com o registro existente em vez de
  criar outro; 201 só na criação.
- Mudança intencional: `?sequencia=Bm G D A` passa de 0 para 199 resultados.

### 6. Cadastro por paleta de acordes (revisão)

A primeira versão do formulário pedia os acordes em um campo de texto
(`"Acordes, ex.: C, A7, Dm, G7"`). Isso destoava do resto da aplicação: em
`#/poracordes` e no catálogo de sequências, acorde é um botão hexagonal clicável. O
texto livre também abria espaço para erro de digitação e para tokens sem
correspondência visual (inclusive `["C,G"]`, que vira um único acorde e nunca casa).

O cadastro passa a ser feito por **clique**, com a mesma paleta de `#/poracordes`:
36 acordes em 7 grupos (C, D, E, F, G, A, B), cobrindo maiores, menores e sétimas nas
12 raízes (com sustenidos), com as mesmas cores. A paleta sai de `acordes.js` e vira a
constante `PALETA_ACORDES` em `app.js`, ao lado de `GENEROS`, consumida pelos dois
controllers — uma fonte só, sem duplicar os 36 acordes.

Regras de interação:

- clicar na paleta **acrescenta** o acorde ao fim da sequência; ordem e repetição são
  semânticas, então o clique não alterna como em `#/poracordes`;
- a sequência em construção aparece como uma fileira de hexágonos na ordem escolhida;
  clicar em um hexágono dessa fileira remove aquela ocorrência;
- a fileira usa `ng-repeat` com `track by $index`, porque a mesma lista pode conter o
  mesmo acorde mais de uma vez;
- `Limpar` zera a seleção e o contador mostra `n/32` (limite do store); com 32
  acordes, novos cliques são ignorados com aviso;
- `Cadastrar` fica desabilitado com zero acordes ou durante o envio;
- `nome` continua um campo de texto opcional (é metadado, não a sequência).

O formulário passa a enviar `acordes` como **lista** (`["C","G","Am"]`), que é o
formato nativo do store; a API continua aceitando string para compatibilidade. Não há
mudança de backend, schema ou contrato de resposta.

Layout: a lista de sequências salvas ganha rolagem própria (`max-height` +
`overflow-y:auto`) para a paleta continuar alcançável quando o catálogo se aproxima do
teto de 500; o bloco de cadastro permanece abaixo dela, na mesma coluna.

Trade-offs aceitos:

- a paleta é curada: só maiores, menores e sétimas nas 12 raízes. Sequências com
  `Am7`, `9`, `sus`, acordes com barra etc. não são montáveis na UI; a API e
  `?sequencia=` continuam aceitando qualquer token (escape hatch documentado);
- não há inserção no meio: para corrigir a ordem, remova a ocorrência e recrie a cauda;
- `#/poracordes` não muda de comportamento — só a origem dos dados da paleta.

Alternativas descartadas: manter o texto livre (inconsistente e sujeito a erro); montar
a paleta a partir de `GET /acordes` (6.653 tokens, inviável como grade e visualmente
diferente); paleta + campo de acorde avulso (reintroduz o texto que esta revisão
remove).

## Design Técnico

### 1. Componentes Principais

```python
# sequence_store.py (novo)
from typing import Any, Dict, List, Optional, Tuple

class SequenceStore:
    def __init__(self, path: str) -> None: ...
    def init_db(self) -> None: ...                    # schema + seed idempotente
    def listar(self) -> List[Dict[str, Any]]: ...     # ordenado por id
    def buscar(self, seq_id: int) -> Optional[Dict[str, Any]]: ...
    def buscar_legado(self, key: str) -> Optional[Dict[str, Any]]: ...
    def criar(self, nome: Optional[str],
              acordes: List[str]) -> Tuple[Dict[str, Any], bool]: ...

# main.py
def casa_sequencia(acordes_seq: List[str], musica: "Musica") -> bool: ...
def parse_acordes(valor: str) -> List[str]: ...       # split em "," e espaço
def get_similares_por_sequencia(acordes_seq: List[str],
                                generos_key: List[str]) -> List[Dict[str, Any]]: ...
```

`casa_sequencia` replica a regra da decisão 1; `get_similares_por_sequencia` percorre a
mesma coleção de hoje (`apply_filtro(musicas.values(), generos_key)`), preservando ordem
e filtro de gênero.

### 2. Modelos de Dados

```sql
PRAGMA user_version = 1;
PRAGMA journal_mode = WAL;

CREATE TABLE sequences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT,                     -- NULL quando omitido
    chords_key TEXT NOT NULL UNIQUE,     -- JSON: '["Bm","G","D","A"]'
    legacy_key TEXT UNIQUE,              -- 'BmGDA' etc.; só nas 6 originais
    criada_em  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE sequence_chords (
    sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    posicao     INTEGER NOT NULL,
    acorde      TEXT NOT NULL,
    PRIMARY KEY (sequence_id, posicao)
);
```

Contratos JSON:

```json
GET /sequencias  ->  [{"id": 0, "nome": null, "acordes": ["Bm","G","D","A"]}]
POST /sequencias ->  {"nome": "Pop", "acordes": ["C","G","Am"]}
                     -> 201 {"id": 6, "nome": "Pop", "acordes": [...], "total_musicas": 28}
                     -> 200 (duplicata) | 400 {"erro": "<motivo>"}
```

### 3. Pontos de Integração

| endpoint | entrada | saída |
|---|---|---|
| `GET /sequencias` | — | catálogo ordenado por `id` |
| `POST /sequencias` | JSON `{nome?, acordes}`; lista ou string | 201/200/400 |
| `GET /similares` | `sequencia_id`, `sequencia`, `generos`, `pagina` | músicas paginadas (100) |
| `sequencia_store` | caminho do arquivo | conexão por operação, WAL, `timeout=5` |

Fluxo do cadastro: cliques na paleta montam uma lista ordenada → `POST` com `acordes`
como lista → `strip`/validação (1–32 acordes, 1–24 chars cada, nome ≤ 80) → `chords_key`
→ `INSERT` ou retorno do existente → `total_musicas` via matcher → resposta.

Fluxo da busca: parâmetro → acordes (catálogo, legado ou ad-hoc) → `apply_filtro` por
gênero → `casa_sequencia` → `get_pagina`.

### 4. Arquivos Alterados

Criados:

- `sequence_store.py`
- `tests/test_matching.py`, `tests/test_store.py`, `tests/test_api.py`,
  `tests/test_regression.py`

Modificados:

- `main.py`
- `static/assets/js/app.js` (constante `PALETA_ACORDES` compartilhada)
- `static/assets/js/controllers/acordes.js` (passa a consumir a constante)
- `static/assets/js/controllers/sequencia.js`
- `static/templates/sequencia.html`
- `static/assets/css/app.css` (rolagem da lista de sequências salvas)
- `Dockerfile`, `.gitignore`, `.dockerignore`
- `README.md`, `AGENTS.md`

Sem alteração: `musica.py`, `requirements.txt`, `data/top/dataset_final.csv`.

## Plano de Implementação

Estimativas de esforço (não há datas neste projeto). Total ≈ 8–11 h (inclui a revisão do
cadastro por paleta). O checklist executável está em [03-plan.md](03-plan.md).

1. **Fase 1 — Persistência e matching (≈ 3 h)**
   - Entrega: `sequence_store.py` (schema, seed, CRUD, validação) e matching por acordes
     em `main.py`, com o store inicializado no startup.
   - Saída da fase: as 6 originais retornam as mesmas listas de hoje.

2. **Fase 2 — API e frontend (≈ 3 h)**
   - Entrega: `GET/POST /sequencias`, `sequencia_id` em `/similares` e `#/porsequencia`
     lendo o catálogo, cadastrando e paginando.
   - Saída da fase: cadastro pela UI aparece no catálogo e a busca funciona.

2b. **Fase 2b — cadastro por paleta (revisão, ≈ 1–2 h)**
   - Entrega: `PALETA_ACORDES` compartilhada em `app.js`, formulário sem campo de texto
     de acordes, seleção por clique com remoção/limpeza e lista de salvas com rolagem.
   - Saída da fase: sequência montada só por cliques, `POST` em lista e `#/poracordes`
     inalterado.

3. **Fase 3 — Deploy, testes e documentação (≈ 2 h)**
   - Entrega: volume no Docker, `.gitignore`/`.dockerignore`, testes e README/AGENTS.
   - Saída da fase: `04-test-report.md` preenchido (fase 5 do enunciado).

## Estratégia de Testes

### Unitários

- Matcher: casa exato; rejeita acorde extra; rejeita ordem trocada; rejeita cifra vazia;
  respeita repetição (`A A B`); caixa diferente não casa.
- Store (DB em diretório temporário): `init_db` duas vezes → 6 linhas; criar → 7;
  duplicata → mesmo `id`; ordem dos acordes preservada; validação de vazio/tamanho/teto.
- Sem mocks: o store usa SQLite real em `tmp`; o matcher usa objetos `Musica` reais.

### Integração

- Regressão: para as 6 chaves, comparar a **lista completa** de `id_unico_musica` (todas
  as páginas) com o esperado derivado de `musica.seqs_famosas` em tempo de teste; assert
  também em 199/296/4/5/7/3.
- API: `GET /sequencias`, POST válido/duplicado/inválido, `sequencia_id` inexistente →
  `[]`, paginação, Content-Type `text/html`.
- Persistência: gravar, reiniciar o processo, reler.
- Docker: `import sqlite3` na imagem base; `docker restart` mantém; `docker rm` + volume
  mantém; sem volume perde (comportamento esperado e documentado).
- Manual (sem infra de teste JS): catálogo dinâmico, cadastro **por cliques na paleta**
  (montar, remover, limpar, limite de 32), duplicata, "carregar mais", filtro de gênero,
  além da regressão visual de `#/poracordes` — mais o gif entregável.

Runner: `python -m unittest discover -s tests` (stdlib, sem dependência nova).

## Observabilidade

Não se aplica: a aplicação não tem logging, métricas ou tracing hoje, e esta mudança não
introduz nenhum. Falhas aparecem como status HTTP (400/500) e erro no startup se o
diretório do banco não for gravável.

## Considerações Futuras

### Melhorias Potenciais

- Editar/excluir sequência (exige autenticação ou moderação).
- Índice invertido acorde → músicas, se o catálogo ou o custo por busca crescerem.
- Trocar o dropdown de gêneros por `GET /generos` (hoje 51 hardcoded vs 52 no backend).

### Limitações Conhecidas

- Regra estrita: muitas sequências novas retornam zero músicas.
- Busca O(n) sobre 3,5 milhões de tokens por requisição (~40 ms).
- Sem normalização de acordes (enharmônicos, barras, parênteses).
- A paleta da UI expõe 36 acordes curados (maiores, menores e sétimas nas 12 raízes com
  sustenidos); tokens como `Am7`, `9`, `sus` e acordes com barra só entram via API ou
  `?sequencia=`.
- A sequência é montada só no fim: não há inserção no meio (remova a ocorrência e
  recrie a cauda).
- Um escritor por vez; schema evoluído manualmente.

## Dependências

### Desenvolvimento

- Nenhuma dependência nova em runtime: `sqlite3` é stdlib.
- `unittest` (stdlib) para os testes; sem build step no frontend.
- Docker apenas para o teste de volume.

## Segurança

- Cadastro anônimo, sem autenticação, sessão ou CSRF — decisão do produto; o deploy é
  local (ADR 0001), o que limita a exposição.
- `Access-Control-Allow-Origin: *` (`main.py:343-345`) permite POST de qualquer origem;
  o impacto é poluição do catálogo, não vazamento de dados.
- Mitigações: validação server-side, limites de tamanho, teto de 500 sequências e SQL
  sempre parametrizado.
- Nenhum dado pessoal é coletado; o banco guarda apenas nome opcional e acordes.

## Rollout

1. Desenvolvimento local (venv) com o CSV atual e banco em `var/`.
2. Regressão das 6 sequências e testes de API antes de qualquer mudança de deploy.
3. Docker com volume nomeado; validar `docker restart` e `docker rm` + volume.
4. Atualizar o comando documentado no README (com `-v`); não há staging nem produção —
   o alvo é local-only por decisão registrada no ADR 0001.
5. Comunicar no README que o banco pode ser perdido sem volume e como fazer backup.

## Referências

- `docs/features/sequencias-customizadas/00-enunciado.md`
- `docs/features/sequencias-customizadas/01-research.md`
- `docs/features/sequencias-customizadas/02-proposal.md`
- `docs/adr/0001-local-only-docker-deploy.md`, `docs/adr/0002-persist-custom-sequences.md`
