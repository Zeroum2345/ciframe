# Pesquisa — Sequências de Acordes Customizadas

## Registro das descobertas

### 1. Algoritmo de matching

Hoje o matching tem duas etapas: `GET /similares` lê `acordes`, `id_unico_musica`, `sequencia`, `pagina` e `generos`, com prioridade `acordes` > `id_unico_musica` > `sequencia` (`main.py:170-197`); no ramo de sequência, o backend remove as vírgulas, faz lookup exato no dicionário de seis chaves (`main.py:190-196`) e filtra músicas por `str(id_seq) in musica.seqs_famosas` (`main.py:203-223`). Ele **não compara** a sequência com `musica.cifra` ou `musica.acordes` em tempo de requisição. Os IDs 0-5 e as chaves estão em `main.py:40-45`; `data/mapeamento_sequencias_famosas.txt:1-6` é uma cópia legível, mas não é lida em runtime.

A tag foi gerada por `get_famosas` (`scripts/generate_data_set.py:7-24`): converte a cifra para minúsculas, exige a sequência como **substring contígua** e exige que **todos** os acordes da música pertençam ao vocabulário da sequência. Um acorde extra desqualifica, mesmo que a sequência apareça. Não é “a música inteira tem o tamanho da sequência”: `one-direction_taken` tem 176 acordes, mas só Bm/G/D/A, e recebe a tag 0. As 514 tags do CSV são IDs únicos de 0 a 5.

`musica.cifra` preserva ordem e repetição; `musica.acordes` é `list(set(cifra))`, sem ordem/repetição (`musica.py:16-18`). As seis sequências não repetem acorde, então os dados não definem o comportamento para uma sequência nova como `A A B`: fatia contígua e subsequência exigem duas ocorrências de A (adjacentes ou não); conjunto ignora a repetição.

No runtime, a única normalização da consulta é remover vírgulas; não há `strip`, `lower` nem correção de enharmônicos (`main.py:191`). O gerador aplica `lower()` (`scripts/generate_data_set.py:12`). Nos dados atuais isso não altera as seis sequências (0 músicas diferem), mas lowercase é inseguro em geral: há 151 grupos de tokens que diferem só por caixa, incluindo acordes de qualidades diferentes (`AM7` vs. `Am7`). Também não há normalização de barras (3.808 tokens) nem parênteses (2.287).

As definições possíveis para uma sequência nova, comparadas com a tag atual nos 67.585 registros carregados:

| ID | Chave | Tag atual | Só contígua | Subsequência | Conjunto (`seq ⊆ música`) | Contígua + vocabulário da música ⊆ sequência |
|---:|---|---:|---:|---:|---:|---:|
| 0 | `BmGDA` | 199 | 866 | 4.763 | 5.768 | 199 |
| 1 | `CGAmF` | 296 | 1.216 | 5.887 | 6.894 | 296 |
| 2 | `EmG` | 4 | 3.110 | 13.643 | 14.160 | 4 |
| 3 | `CA7DmG7` | 5 | 96 | 427 | 582 | 5 |
| 4 | `GmF` | 7 | 1.039 | 3.641 | 3.847 | 7 |
| 5 | `CC7FFm` | 3 | 132 | 280 | 365 | 3 |

A última coluna é a regra do gerador e, entre as comparadas, a única que reproduz a tag. “Só contígua” retorna 866 para `BmGDA`, não 199; 667 dessas músicas têm Bm-G-D-A contíguo, mas usam acordes fora da sequência. As demais são ainda mais permissivas. Para passar na regressão das seis, a regra precisa ser a última — ou as seis precisam continuar usando a tag (opção híbrida).

### 2. Validação da hipótese

Replay offline: li o CSV com a mesma rotina de `main.py`, montei `';'.join(cifra).lower()` e reapliquei `get_famosas` (`scripts/generate_data_set.py:7-24`). Resultado: **0 divergências** contra a coluna 7 em **67.585** músicas; **514** tags no total (199/296/4/5/7/3); nenhuma música com mais de uma tag; **8.141** músicas sem cifra, que não podem satisfazer ocorrência.

Endpoint: `BmGDA` retorna 100 + 99 (199), `CGAmF` 100 + 100 + 96 (296), `EmG` 4, `CA7DmG7` 5, `GmF` 7, `CC7FFm` 3. HTTP 200 e `Content-Type: text/html; charset=utf-8` (`json.dumps`); `POST /similares` retorna 405; `bmgda`, `Bm G D A` e vazio retornam `[]`; `Bm,G,D,A` retorna os mesmos 100 primeiros.

Conclusão: a hipótese se confirma **só** para “ocorrência contígua + todos os acordes da música na sequência”. Se a intenção fosse “só contígua”, ela é refutada: 866/1.216/3.110/96/1.039/132, não 199/296/4/5/7/3. O baseline tem 67.585 músicas, não 67.586, porque `main.py:50` descarta a primeira linha física do CSV (não há cabeçalho; `14-bis,a-qualquer-tempo` não entra). Não existe suíte de testes no repositório; o replay acima foi um script ad hoc.

### 3. Banco de dados

Hoje não há banco, ORM, schema, migração, driver nem configuração de conexão; `requirements.txt` só tem Flask e gunicorn (`requirements.txt:4-5`). O CSV é lido no import (`main.py:49-98`); o `Dockerfile` faz `COPY . .` e não declara `VOLUME` (`Dockerfile:1-12`); o `docker run` documentado não passa `-v` (`AGENTS.md:20-24`). O ADR 0001 fixa um Docker único e local, **não** “persistência só em arquivo”; um banco embarcado é compatível com a restrição (`docs/adr/0001-local-only-docker-deploy.md:9-16`, `00-enunciado.md:63-65`).

| Opção | Dependência | Implicação | Persistência |
|---|---|---|---|
| SQLite | `sqlite3` (stdlib) | arquivo único, SQL/transações/constraints; nenhuma dependência nova | sobrevive a `docker restart`; exige volume para `docker rm`/rebuild |
| CSV/JSON | stdlib | sem consulta/constraints; escrita atômica manual; pode não atender à letra de “banco de dados” | mesmo caso; volume necessário para recriação |
| TinyDB | `tinydb` (pip) | JSON e consultas simples; nova dependência | mesmo caso; concorrência/durabilidade menores |
| `shelve`/`dbm` | stdlib | chave-valor, sem SQL; formato dependente de plataforma | mesmo caso |
| DuckDB | `duckdb` (pip) | SQL em arquivo; dependência pesada para um catálogo pequeno | mesmo caso |

`docker restart` mantém a camada gravável do container; `docker rm` + novo `docker run` ou rebuild perde o arquivo. Para sobreviver à recriação é preciso volume nomeado (ex.: `-v deciframe-data:/app/data`) ou bind mount; `VOLUME` no `Dockerfile` cria volume anônimo. Se o volume cobrir o diretório de seed, o primeiro start precisa criar o schema e inserir as seis sequências de forma idempotente. O `CMD` do gunicorn não define `--workers` (`Dockerfile:12`), então o default é 1 worker. Só o catálogo de sequências vai para o banco; músicas e gêneros continuam no CSV (`00-enunciado.md:60-62`). Endpoints novos devem continuar com `json.dumps`, não `jsonify` (`00-enunciado.md:68`).

### 4. Frontend existente

`static/index.html:2` declara `ng-app="deciframeApp"`; AngularJS 1.4.9 e scripts são carregados em `static/index.html:129-147`. A rota `#/porsequencia` está em `static/assets/js/routes.js:17-21` e usa `templates/sequencia.html` com `SequenciaController` (`controllerAs: "Sequencia"`).

O catálogo é hardcoded (`sequencia.js:2-37`): `sequencia1` = ID 0, `sequencia2` = ID 1, `sequencia3` = ID 4, `sequencia4` = ID 5; faltam 2 (`EmG`) e 3 (`CA7DmG7`). Os objetos não têm o ID do backend.

Ao clicar, o controller copia a sequência para `vm.minhaSequencia`, junta os acordes com vírgulas (`sequencia.js:55-61`) e faz `GET similares?sequencia=<string>` com gênero opcional (`sequencia.js:72-77`). A URL é relativa; `RESTAPI` (`localhost:5003`) não é usada (`app.js:3-5`). Não há `pagina`, então o backend devolve no máximo 100 (`main.py:35`, `main.py:226-228`); `BmGDA` (199) e `CGAmF` (296) ficam truncados.

O template ordena só a página recebida por popularidade (`sequencia.html:41-58`); o backend monta a lista iterando gêneros, sem ordenação global. `ng-hide="music.diferenca.length"` (`sequencia.html:43`) é herança da busca por acordes — resultados de sequência não têm `diferenca` (`main.py:210-220`). O dropdown usa a constante de 51 gêneros (`app.js:6-58`), não `/generos`; o backend tem 52, incluindo `R&B;`.

Não existe GET de catálogo, formulário de cadastro, POST, validação no cliente, envio de ID, autenticação/sessão/CSRF nem paginação. Todas as chamadas atuais são GET; o único endpoint de sequência é `GET /similares?sequencia=...`, que devolve músicas.

## Trade-offs identificados

### 1. Algoritmo

- **A. Regra da tag em tempo real:** passa a regressão (0 divergências), mas é restritiva (`EmG` = 4, embora 3.110 tenham Em-G contíguo) e custa varrer ~3,5 milhões de tokens por requisição ou pré-computar.
- **B/C/D. Contígua, subsequência, conjunto:** 866/4.763/5.768 para `BmGDA` (e 1.216/5.887/6.894 etc.); mais permissivas, mas não reproduzem a tag.
- **E. Híbrida:** tag para as seis + outra regra para novas; preserva a regressão, mas cria duas semânticas.
- **Normalização/repetição:** token exato vs. `lower()` (mistura `AM7`/`Am7`) vs. canonicalização; fatia contígua vs. subsequência vs. conjunto.

### 2. Banco

- **SQLite:** stdlib, SQL/transações, adequado ao catálogo pequeno; schema manual e um escritor por vez.
- **CSV/JSON, TinyDB, `shelve`/`dbm`:** sem serviço externo; CSV/JSON não tem constraints, TinyDB adiciona dependência e `shelve`/`dbm` não tem consultas relacionais.
- **DuckDB:** SQL em arquivo, dependência pesada para o volume.
- **Persistência:** sem volume sobrevive só a `docker restart`; volume nomeado/bind mount sobrevive a recriação; schema + seed idempotente.

### 3. Frontend

- **Catálogo via GET + POST:** atende ao requisito; adiciona endpoint e estados de loading/erro. Hardcoded, JSON estático ou `localStorage` não refletem o catálogo compartilhado.
- **ID vs. string:** ID é estável e evita duplicatas; string é o formato atual.
- **Paginação:** enviar `pagina`/“carregar mais” ou retornar tudo; hoje só vêm 100.
- **Gêneros:** constante de 51 ou `/generos` (52, com `R&B;`).
- **Validação/duplicatas:** definir lista vazia, acorde inválido, sequência repetida e normalização; não há CSRF/sessão e o CORS é aberto (`main.py:274-277`).
- **Resposta:** `json.dumps`/`text/html`; o POST será a primeira rota não-GET.
