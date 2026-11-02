# Plano — Sequências de Acordes Customizadas

Contexto, decisões e design técnico: [03-design.md](03-design.md).

## Passos

1. [x] Criar `sequence_store.py` com schema, `PRAGMA user_version` e seed idempotente dos
      IDs 0–5 (`INSERT OR IGNORE` em pai e filhos, em transação).
2. [x] Implementar `listar`, `buscar`, `buscar_legado` e `criar` (dedupe por `chords_key`,
      retorno `(registro, criado)`).
3. [x] Implementar validação no store: 1–32 acordes, 1–24 chars por acorde, nome ≤ 80,
      teto de 500, `strip` e caixa preservada.
4. [x] Em `main.py`, instanciar o store no startup com `DECIFRAME_DB_PATH` (default
      `var/deciframe.db`) e chamar `init_db()`.
5. [x] Adicionar `casa_sequencia` e reescrever `get_similares_por_sequencia` para receber a
      lista de acordes.
6. [x] Em `/similares`, ler `sequencia_id` (precedência sobre `sequencia`), resolver
      `legacy_key` e tratar string arbitrária via split.
7. [x] Adicionar `GET /sequencias` (`json.dumps`, ordenado por `id`).
8. [x] Adicionar `POST /sequencias` com 201/200/400 e `total_musicas`.
9. [x] Em `sequencia.js`, remover as 4 sequências fixas e carregar `GET sequencias`,
      montando `{id, nome, rotulo, acordes:[{acorde, cor}]}`.
10. [x] Enviar `sequencia_id` na busca e implementar `pagina` + `carregarMais()`.
11. [x] Adicionar `criar()` (POST) e o formulário em `sequencia.html`, fora do `ng-repeat`;
      remover `ng-hide="music.diferenca.length"`.
12. [x] `Dockerfile`: `VOLUME ["/app/var"]`; `var/` em `.gitignore` e `.dockerignore`.
13. [x] Escrever `tests/` (matching, store, API, regressão) e rodar
      `python -m unittest discover -s tests`.
14. [x] Validar persistência (processo, `docker restart`, `docker rm` + volume) e atualizar
      `README.md`/`AGENTS.md`. Persistência entre processos validada; Docker não estava
      disponível no ambiente (ver `04-test-report.md`).

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `sequence_store.py` (novo) | schema, seed, validação e CRUD do catálogo |
| `main.py:40-45` | remover o dict `sequencias` (vira seed) |
| `main.py:170-201` | ler `sequencia_id`; tratar `sequencia` legado/arbitrário |
| `main.py:203-223` | trocar membership na tag pelo matcher sobre `musica.cifra` |
| `main.py` (novas rotas) | `GET /sequencias`, `POST /sequencias` |
| `static/assets/js/controllers/sequencia.js:2-37` | catálogo dinâmico |
| `static/assets/js/controllers/sequencia.js:63-90` | busca por `id`, paginação, `criar()` |
| `static/templates/sequencia.html:6-14` | lista dinâmica + formulário de cadastro |
| `static/templates/sequencia.html:40-58` | "carregar mais", remover `ng-hide` |
| `Dockerfile:8-12` | `VOLUME ["/app/var"]` |
| `.gitignore`, `.dockerignore` | ignorar `var/` |
| `README.md:13-17`, `AGENTS.md:11-13` | comando com `-v`, nota de banco/persistência |
| `tests/*.py` (novo) | matching, store, API, regressão |
| `musica.py`, `requirements.txt`, CSV | sem alteração |

## Riscos e mitigação

| Risco | Como detectar | Mitigação |
|---|---|---|
| Volume montado em `/app/data` sombreia o CSV | app sem músicas / `FileNotFoundError` no startup | usar `/app/var`; documentar no README |
| `json.dumps` falha com `set` em `musica.__dict__` | 500 em `/musicas` e `/musica/<id>` | não adicionar atributo `set` em `Musica`; usar lista paralela se otimizar |
| Banco de dev entra na imagem | seed conflitante/registros inesperados no primeiro start | `var/` no `.dockerignore` |
| `sqlite3` indisponível no `python:3.9-slim` | `ImportError` no build | verificar com `docker run --rm python:3.9-slim python -c "import sqlite3"` |
| Ordem dos resultados muda | teste de regressão comparando listas | matcher percorre a mesma coleção de hoje |
| Regra estrita confunde quem cadastra | sequência nova com 0 resultados | `total_musicas` no POST + texto explicativo na UI |
| POST anônimo polui o catálogo | catálogo crescendo sem controle | limites de tamanho + teto de 500 |
| Diretório do banco não gravável | `sqlite3.OperationalError` no startup | criar o diretório e falhar com mensagem clara |
| Backup copia `.db` sem WAL | banco restaurado incompleto | usar `.backup` do SQLite ou parar o container antes de copiar |

## Definição de pronto

- [x] Cadastro de sequência funciona pela UI e via `POST /sequencias` (201).
- [x] A sequência cadastrada aparece em `GET /sequencias` e a busca por ela retorna
      músicas conforme a regra (inclusive o caso de 0 resultados).
- [x] As 6 originais retornam listas de `id_unico_musica` idênticas às de hoje
      (199/296/4/5/7/3), incluindo a ordem.
- [x] `?sequencia=BmGDA`, `?sequencia=Bm,G,D,A` e `?sequencia=CGAmF&pagina=3` mantêm os
      mesmos resultados; `?sequencia_id=0` funciona.
- [ ] Catálogo sobrevive a restart do processo e a `docker rm` quando há volume nomeado.
      Restart do processo validado; `docker rm` não foi verificado porque o daemon não
      estava disponível (ver `04-test-report.md`).
- [x] Endpoints novos e alterados usam `json.dumps` (Content-Type `text/html`).
- [x] `#/porsequencia` não tem sequências hardcoded, permite cadastrar e paginar.
- [x] Nenhuma dependência nova em `requirements.txt`.
- [x] `04-test-report.md` preenchido com a cobertura e o resultado da regressão.
