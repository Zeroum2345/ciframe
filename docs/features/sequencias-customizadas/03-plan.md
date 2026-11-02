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

## Revisão — cadastro por paleta de acordes

A primeira versão usava um campo de texto para os acordes; esta revisão troca por
clique nos botões, como em `#/poracordes`. Design: [03-design.md](03-design.md).

15. [x] Extrair a paleta de `acordes.js` para a constante `PALETA_ACORDES` em `app.js` e
      consumi-la em `AcordesController`, sem mudar o comportamento de `#/poracordes`.
16. [x] Em `SequenciaController`, trocar a string de `novaSequencia.acordes` por uma lista
      ordenada de `{acorde, cor}`; adicionar `adicionarAcorde`, `removerAcorde(index)`,
      `limparSequencia`, contador e limite de 32.
17. [x] Em `sequencia.html`, remover o input de acordes e renderizar a paleta e a sequência
      em construção com `df-hex` (`track by $index`); desabilitar `Cadastrar` com zero
      acordes; enviar `acordes` como lista no `POST`.
18. [x] Dar rolagem própria à lista de sequências salvas (`max-height` +
      `overflow-y:auto`) para a paleta continuar acessível com o catálogo cheio.
19. [x] Verificar `#/poracordes` (paleta, cores, toggle) e o fluxo de `#/porsequencia` no
      browser: montar `C, G, Am` por cliques → 201 (ou 200 se já existir) com
      `total_musicas=28`, remover/limpar, limite de 32 e `node --check`.
20. [x] Atualizar `04-test-report.md` e `02-proposal.md` (que ainda descrevem o campo de
      texto) para o cadastro por cliques.

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
| `static/assets/js/app.js` | constante `PALETA_ACORDES` compartilhada |
| `static/assets/js/controllers/acordes.js:2-53` | consome `PALETA_ACORDES` (sem mudança visual) |
| `static/templates/sequencia.html:6-14` | lista dinâmica + formulário de cadastro |
| `static/templates/sequencia.html:18-31` | paleta + sequência em construção no lugar do input |
| `static/templates/sequencia.html:40-58` | "carregar mais", remover `ng-hide` |
| `static/assets/css/app.css` | rolagem da lista de sequências salvas |
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
| Paleta não cobre todos os tokens (`m7`, `9`, `sus`, barra) | usuário não encontra o acorde desejado | manter API/`?sequencia=` como escape e documentar a limitação |
| Refatoração da paleta quebra `#/poracordes` | regressão visual na grade/toggle | consumir a mesma constante e verificar a página no browser |
| Paleta + catálogo deixam a coluna esquerda longa | cadastro inalcançável com 500 sequências | rolagem própria na lista de salvas |

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
- [x] O cadastro é feito só por cliques nos acordes, sem campo de texto de acordes.
- [x] `#/poracordes` continua idêntico (paleta, cores e toggle) após extrair a constante.
- [x] `POST /sequencias` continua aceitando lista e string depois da mudança do formulário.
- [x] Nenhuma dependência nova em `requirements.txt`.
- [x] `04-test-report.md` preenchido com a cobertura e o resultado da regressão.
