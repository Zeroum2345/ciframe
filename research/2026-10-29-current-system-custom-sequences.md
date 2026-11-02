# Research — deciframe as it exists today (custom chord sequences)

**Snapshot:** `HEAD` = `fb97001` (`Update 00-enunciado.md`, 2026-10-17).  
**Method:** read the application, data-prep, deploy, ADR, and feature-template files; replayed `main.py`'s CSV parser over `data/top/dataset_final.csv`; exercised the Flask app with its test client.  
**Scope:** this document records current behavior and current constraints only. It does not recommend an algorithm, database, or frontend change.

## High-level summary

deciframe is a Flask application that loads a 15 MB CSV into memory once at import time and serves both a JSON API and a static AngularJS 1.4.9 application from the same process. The six "famous sequence" definitions are hardcoded in two backend places (`main.py:40-45` and the offline generator `scripts/generate_data_set.py:8`), while each song's precomputed sequence membership is stored in column 7 of `data/top/dataset_final.csv`; the frontend contains a separate, four-entry hardcoded list (`static/assets/js/controllers/sequencia.js:2-37`). Sequence search does not inspect a song's chords at request time: it maps the concatenated query string to an integer ID and filters songs whose CSV-provided `seqs_famosas` list contains that ID. There is no database, no persistence layer, no create/update endpoint, no test suite, and no volume or database configuration in the single-container Docker setup. The backend's CSV-backed song catalog, the hardcoded sequence catalog, and the frontend's hardcoded subset are three independent sources that currently have to agree by construction.

**Map to the questions in `01-research.md`:** matching semantics → §4; validation against the six original sequences → §4.3; database/persistence state → §7 and §9.2; existing `#/porsequencia` behavior → §3.3 and §6.2. The template's own findings and trade-off sections are still placeholders (`docs/features/sequencias-customizadas/01-research.md:35-44`).

## 1. Runtime topology

- The container is a single `python:3.9-slim` image; `requirements.txt` installs Flask 3.1.3 and gunicorn 23.0.0 only (`Dockerfile:1-12`, `requirements.txt:1-5`).
- gunicorn serves `main:app` on port 8080 (`Dockerfile:10-12`).
- `main.py` creates one Flask app (`main.py:9`), sends `static/index.html` for `/` (`main.py:101-103`), and proxies every other static path through `send_static_file` (`main.py:109-112`).
- The browser application is AngularJS 1.4.9 with `ngRoute`, `ngAnimate`, `ngProgress`, and `ui.bootstrap` (`static/assets/js/app.js:1-5`), loaded from CDN with no build step (`static/index.html:125-147`). The main view is `ng-view` (`static/index.html:123`).
- All application routes are GET routes. There is no POST/PUT/DELETE route in `main.py`.
- There is no database driver, ORM, migration directory, schema file, connection string, or environment-variable configuration in the repository. `requirements.txt` contains only Flask and gunicorn (`requirements.txt:1-5`), and a repository grep finds no `sqlite`, `SQLAlchemy`, `psycopg`, `DATABASE`, `os.environ`, or `getenv` usage in application code.

## 2. Startup data load and in-memory model

### 2.1 CSV load

`main.py` opens `data/top/dataset_final.csv` at module import and keeps the parsed objects in module-level globals (`main.py:49-98`). The column positions are fixed constants (`main.py:25-35`):

| Index | Constant | Meaning |
|---|---|---|
| 0 | `ARTISTA_ID` | artist slug used in URLs and IDs |
| 1 | `MUSICA_ID` | song slug |
| 2 | `ARTISTA` | display artist name |
| 3 | `MUSICA` | display song name |
| 4 | `GENERO` | genre string |
| 5 | `POPULARIDADE` | popularity as text with `.` thousands separators |
| 6 | `TOM` | key |
| 7 | `SEQ_FAMOSA` | precomputed famous-sequence tag(s) |
| 8 | `CIFRA` | semicolon-separated chord sequence |

The load path is:

1. Open the file and unconditionally discard one line with `f.readline()` (`main.py:49-50`).
2. Remove all double quotes and all literal `NA` substrings, then remove the trailing newline (`main.py:52-53`).
3. Split on commas and convert popularity to `int` after removing dots (`main.py:55-56`).
4. If `CIFRA` is non-empty, split on `;` and pass through `limpa_cifra`; otherwise set it to `[]` (`main.py:58-61`).
5. Split `SEQ_FAMOSA` on `;` into `seqs_famosas` (`main.py:63`).
6. Build a `Musica` object and insert it into `musicas_dict` by `id_unico_musica` (`main.py:69-74`).
7. Accumulate the global `acordes` set and the `genero_musicas` map (`main.py:76-85`).
8. Sort all songs by popularity descending into the `musicas` `OrderedDict`, convert `generos` from a set to a list, and sort each genre's song list by popularity descending (`main.py:87-96`).

`limpa_cifra` (`main.py:11-23`) discards blank semicolon elements, treats any element containing `|` as a tablature line by taking the first pipe-separated token and then the first whitespace-separated token, and otherwise splits the element on whitespace into individual chords. The loaded `Musica` object stores the ordered, repeated chord list as `cifra`, a de-duplicated unordered list as `acordes`, and the raw sequence tags as `seqs_famosas` (`musica.py:3-22`).

### 2.2 In-memory indexes

- `musicas`: `OrderedDict` of `id_unico_musica -> Musica`, globally ordered by popularity descending (`main.py:87-89`).
- `musicas_dict`: insertion-order dictionary used to build `musicas` (`main.py:47`, `main.py:74`).
- `genero_musicas`: `genre -> [Musica]`, each list sorted by popularity descending (`main.py:82-85`, `main.py:95-96`).
- `generos`: list of unique genre strings from the CSV (`main.py:38`, `main.py:66`, `main.py:92`).
- `acordes`: set of every chord token in every song (`main.py:39`, `main.py:77-78`).
- `sequencias`: hardcoded `concatenated-chord-string -> integer id` map (`main.py:40-45`).

Measured on the current CSV with the current app:

| Metric | Value |
|---|---:|
| Physical CSV lines | 67,586 |
| Loaded songs (`len(musicas)`) | 67,585 |
| Distinct `id_unico_musica` values | 67,585 |
| Songs with empty `CIFRA` / `acordes` | 8,141 |
| Distinct chord tokens (`/acordes`) | 6,653 |
| Distinct genres (`/generos`) | 52 |
| Songs tagged with at least one of the 6 sequences | 514 |
| Songs with no sequence tag | 67,071 |
| Import time in a local Python 3.14 venv | ~1.17 s |

### 2.3 Observed parsing characteristics

- `data/top/dataset_final.csv` has no header row; its first physical line is the data row `14-bis,a-qualquer-tempo,...` (`data/top/dataset_final.csv:1`). Because `main.py:50` calls `readline()` before the loop, that song is not loaded. A live check of `'14-bis_a-qualquer-tempo' in musicas` returned `False`; the loaded data begins at the second physical row.
- `replace('NA','')` is a global substring replacement, not a field-level null conversion (`main.py:53`). It also alters names that contain uppercase `NA`, for example `ROTINA DE POBRE` becomes `ROTI DE POBRE`, `DNA` becomes `D`, `CABANA` becomes `CABA`, and `JULIANA` becomes `JULIA` (`data/top/dataset_final.csv:12965`, `:25631`, `:37719`, `:56713`).
- For untagged songs, `NA` becomes the empty string and `split(';')` produces `['']`, not an empty list (`main.py:53`, `main.py:63`). The per-song tag lists are therefore either `['']` or a single ID such as `['0']`.
- The current CSV contains only single tags: 67,071 songs with `NA`, and 514 songs with exactly one of `0` through `5`; no song has multiple tags in column 7.
- Six CSV lines contain `|` in the chord field and are handled by the tablature branch of `limpa_cifra` (`main.py:16-18`); sixteen lines contain chord tokens beginning with a lowercase letter, which are preserved as-is.
- The CSV contains 303 songs with genre `R&B;` (`data/top/dataset_final.csv:2167` is the first). That string is the literal genre value parsed from the CSV; the backend therefore exposes 52 genres while the frontend constant has 51 entries and no `R&B;` entry (`static/assets/js/app.js:6-58`).

## 3. The six-sequence catalog as it exists today

### 3.1 Backend definitions

The runtime catalog is the literal dictionary in `main.py:40-45`:

| Key sent as `?sequencia=` | ID | Chords in the key |
|---|---:|---|
| `BmGDA` | 0 | Bm, G, D, A |
| `CGAmF` | 1 | C, G, Am, F |
| `EmG` | 2 | Em, G |
| `CA7DmG7` | 3 | C, A7, Dm, G7 |
| `GmF` | 4 | Gm, F |
| `CC7FFm` | 5 | C, C7, F, Fm |

The same six sequences in the same order appear in the offline generator as lowercase semicolon strings (`scripts/generate_data_set.py:8`). A human-readable copy exists in `data/mapeamento_sequencias_famosas.txt:1-6`, which maps IDs 0-5 to display names and chord sequences; no application code reads that file.

### 3.2 Dataset tags

Column 7 contains the precomputed tag produced when `data/top/dataset_final.csv` was generated. The generator's `get_famosas` (`scripts/generate_data_set.py:7-24`) lowercases the song's full chord string and, for each of the six sequences:

1. Requires the sequence string (e.g. `bm;g;d;a`) to occur as a contiguous substring of the song's chord string.
2. Requires every chord in the song to be one of the sequence's chords.
3. Appends the sequence index as a string; multiple matches are appended to a list and concatenated with `''.join(...)` before being written (`scripts/generate_data_set.py:84-89`).

The current CSV contains only single IDs, so the concatenation path is not observable in the data. Replaying this generator rule over all 67,585 loaded songs produced exactly the same tag sets as the CSV column (0 mismatches).

### 3.3 Frontend definitions

The `#/porsequencia` page does not read the backend catalog. Its controller defines four objects (`static/assets/js/controllers/sequencia.js:2-37`):

| Controller variable | Chords | Matches backend ID | Backend key |
|---|---|---:|---|
| `sequencia1` | Bm, G, D, A | 0 | `BmGDA` |
| `sequencia2` | C, G, Am, F | 1 | `CGAmF` |
| `sequencia3` | Gm, F | 4 | `GmF` |
| `sequencia4` | C, C7, F, Fm | 5 | `CC7FFm` |

Backend IDs 2 (`EmG`) and 3 (`CA7DmG7`) have no frontend entry. All four frontend entries use the same color `#2E1C74` and the same `index: 1` (`static/assets/js/controllers/sequencia.js:2-31`). The page route is registered at `static/assets/js/routes.js:17-21`; the home-page link to it is at `static/templates/home.html:79-85`.

There is no API endpoint that returns the sequence catalog. The only sequence-related endpoint is `GET /similares?sequencia=...`, which returns songs, not sequence definitions.

## 4. Matching behavior

### 4.1 The sequence path uses precomputed tags only

`GET /similares` reads `acordes`, `id_unico_musica`, `sequencia`, `pagina`, and `generos` (`main.py:170-182`). Its branch order is:

1. If `acordes` is present, use it, ignoring the other selectors (`main.py:184-186`).
2. Else if `id_unico_musica` is present, look up that song and use its `acordes` (`main.py:187-189`).
3. Else if `sequencia` is present, remove every comma from the value and use the resulting string as a key into the hardcoded `sequencias` dictionary (`main.py:190-197`).

For the sequence branch, if the key exists, the endpoint calls `get_similares_por_sequencia(id_seq, generos_key)` and immediately returns its result (`main.py:194-197`). That function scans the genre-filtered song collection and keeps a song when `str(id_seq) in musica.seqs_famosas` (`main.py:203-223`). It does not inspect `musica.cifra` or `musica.acordes` at request time. If the key does not exist, the endpoint returns `[]` with HTTP 200 (`main.py:190-197`).

Consequences visible in the code and data:

- The query is case-sensitive. `bmgda` is not in `sequencias` and returns `[]`; `BmGDA` returns results.
- The query must be the exact comma-less concatenation of the chords. The frontend sends `Bm,G,D,A`; the backend removes the commas and matches `BmGDA` (`static/assets/js/controllers/sequencia.js:55-77`, `main.py:190-196`). A query with spaces, lowercase, enharmonic spellings, or a different chord order does not match a key.
- The current tag rule is not merely "the sequence occurs somewhere in the song": it also requires the entire song to use only the sequence's chord vocabulary. For example, `darvin_pensa-em-mim` contains a contiguous `Bm;G;D;A` and has five distinct chords, but is not tagged `0` because of the fifth chord.
- The sequence result objects do not include `diferenca` or `intersecao`; the generic chord result objects do (`main.py:210-220`, `main.py:246-258`).

### 4.2 The generic chord path uses set intersection

When the request uses `acordes` (or a song ID), `get_similares` scans the genre-filtered collection and, for every song other than the source song, computes:

- `inter = set(query_chords) & set(song.acordes)`
- `diff = set(song.acordes) - set(query_chords)`

A song is included if `len(inter) > 0`; it does not need to contain all query chords (`main.py:230-263`). Results are sorted by `(len(diferenca), -len(intersecao))`; popularity is not part of the sort key (`main.py:262-263`). `acordes` is a de-duplicated unordered list (`musica.py:17`), so this path ignores chord order and repetition.

### 4.3 Candidate rules compared against the current data

The table below replays four rules over the same 67,585 loaded songs. "Current tag" is the CSV-backed behavior used by `GET /similares?sequencia=...`. "Contiguous" means the exact chord list occurs in `musica.cifra`; "ordered subsequence" allows gaps but preserves order; "set inclusion" ignores order and repetition.

| ID | Key | Current tag | Contiguous occurrence | Ordered subsequence | Set inclusion | Contiguous + whole-song subset |
|---:|---|---:|---:|---:|---:|---:|
| 0 | `BmGDA` | 199 | 866 | 4,763 | 5,768 | 199 |
| 1 | `CGAmF` | 296 | 1,216 | 5,887 | 6,894 | 296 |
| 2 | `EmG` | 4 | 3,110 | 13,643 | 14,160 | 4 |
| 3 | `CA7DmG7` | 5 | 96 | 427 | 582 | 5 |
| 4 | `GmF` | 7 | 1,039 | 3,641 | 3,847 | 7 |
| 5 | `CC7FFm` | 3 | 132 | 280 | 365 | 3 |

For every one of the six sequences, all current-tag songs are contained in each of the alternative result sets (overlap equals the current count; no current match is missed by the alternatives). The "contiguous + whole-song subset" column reproduces the current tags exactly, which is the rule used by the dataset generator. The whole-song-subset condition alone (among the 59,444 songs with non-empty `cifra`) yields 873, 958, 24, 53, 18, and 57 songs for IDs 0-5 respectively; the 8,141 songs with no chords satisfy the subset test vacuously but cannot satisfy any occurrence test.

Additional observed counts for the same rules: with a two-chord sequence such as `C;G`, contiguous occurrence finds 11,877 songs, ordered subsequence 19,689, and set inclusion 20,290; `Em;G` finds 3,110 / 13,643 / 14,160. These counts are properties of the current data and the rules above, not of any endpoint implementation.

### 4.4 Pagination and ordering

`TAM_PAGINA` is 100 (`main.py:35`). `get_pagina` slices the result list with `(page - 1) * 100` (`main.py:226-228`). The sequence branch applies that slice after filtering (`main.py:196`). The frontend never sends a `pagina` parameter (`static/assets/js/controllers/sequencia.js:72-77`), so it only receives the first 100 results. Live checks: `BmGDA` returns 100 on the default page and 99 on `pagina=2` (199 total); `CGAmF` returns 100 on the default page (296 total); IDs 2-5 return 4, 5, 7, and 3 respectively.

Sequence results are built by iterating the genre-filtered collection (`main.py:203-223`). With no genre filter, `apply_filtro` iterates the `generos` list produced from a set (`main.py:92`, `main.py:265-272`); each genre's songs are popularity-sorted, but the combined sequence list is grouped by that genre iteration order rather than globally sorted. The frontend then applies `orderBy:'-popularidade'` to the page it received (`static/templates/sequencia.html:42`).

## 5. HTTP API behavior

### 5.1 Routes

| Route | Inputs | Output |
|---|---|---|
| `GET /` | none | `static/index.html` (`main.py:101-103`) |
| `GET /<path>` | static path | file from `static/` (`main.py:109-112`) |
| `GET /search` | `key` required; `generos` and `pagina` read | JSON list of matching songs (`main.py:114-142`) |
| `GET /musicas` | none | JSON list of every song's `__dict__` (`main.py:154-156`) |
| `GET /generos` | none | JSON list of 52 genre strings (`main.py:158-160`) |
| `GET /acordes` | none | JSON list of 6,653 chord strings (`main.py:162-164`) |
| `GET /musica/<m_id>/` | song ID | one song's `__dict__` (`main.py:166-168`) |
| `GET /similares` | `acordes`, `id_unico_musica`, `sequencia`, `pagina`, `generos` | JSON list of similar songs (`main.py:170-201`) |

### 5.2 Response format

Every JSON endpoint returns `json.dumps(...)` as a string rather than using `jsonify` (`main.py:142`, `:156`, `:160`, `:164`, `:168`, `:197`, `:201`). Live responses carried `Content-Type: text/html; charset=utf-8`. `after_request` adds `Access-Control-Allow-Origin: *` to every response (`main.py:274-277`).

Field sets:

- `/search` returns `id_unico_musica`, `id_artista`, `id_musica`, `nome_artista`, `nome_musica`, `genero`, `url` (`main.py:132-140`).
- Sequence results return `id_unico_musica`, `id_artista`, `id_musica`, `nome_artista`, `nome_musica`, `popularidade`, `acordes`, `genero`, `url` (`main.py:210-220`).
- Generic `/similares` results add `diferenca` and `intersecao` to the sequence fields (`main.py:246-258`).
- `/musicas` and `/musica/<id>/` return the object's `__dict__`, which includes `id_artista`, `nome_artista`, `id_musica`, `nome_musica`, `genero`, `popularidade`, `tom`, `cifra`, `acordes`, `seqs_famosas`, `id_unico_musica`, and `url` (`musica.py:7-22`).

### 5.3 Observed endpoint behavior

Live checks with the Flask test client:

| Request | Result |
|---|---:|
| `/similares?sequencia=BmGDA` | 100 items (199 total; page 2 gives 99) |
| `/similares?sequencia=CGAmF` | 100 items (296 total) |
| `/similares?sequencia=EmG` | 4 items |
| `/similares?sequencia=CA7DmG7` | 5 items |
| `/similares?sequencia=GmF` | 7 items |
| `/similares?sequencia=CC7FFm` | 3 items |
| `/similares?sequencia=Bm,G,D,A` | 100 items (commas removed) |
| `/similares?sequencia=bmgda` | 0 items |
| `/similares?sequencia=XYZ` | 0 items, HTTP 200 |
| `/similares?sequencia=BmGDA&generos=Rock` | 5 items |
| `/generos` | 52 items |
| `/musicas` | 67,585 items |
| `/acordes` | 6,653 items |

Other observed behavior:

- `/search` reads `generos` into `generos_key` (`main.py:116`, `main.py:121-123`) but never uses that variable in the matching loop (`main.py:128-141`), so the genre filter is not applied on this endpoint.
- `/musicas` is documented as paginated in its docstring (`main.py:149-153`) but returns the entire list with no `get_pagina` call (`main.py:154-156`).
- `/search` without `key` raises `AttributeError` because it calls `.lower()` on `None` (`main.py:118`); `/musica/unknown/` raises `KeyError` (`main.py:168`). The test client observed HTTP 500 for both.
- `/similares` with no selector produces `acordes = []`, so `get_similares` finds no intersection and returns `[]`; there is no error response.

## 6. Frontend

### 6.1 Boot and routing

`static/index.html` declares `ng-app="deciframeApp"` (`static/index.html:2`), includes the AngularJS/CDN libraries (`static/index.html:125-134`), and loads the application scripts in this order: `app.js`, `routes.js`, `main.js`, `home.js`, `about.js`, `acordes.js`, `musica.js`, `sequencia.js`, then the two directives (`static/index.html:138-147`). `static/assets/js/controllers/search.js` exists in the repository but is not included in `index.html`.

Routes are defined in `static/assets/js/routes.js:1-29`: `/`, `/poracordes`, `/pormusica`, `/porsequencia`, `/sobre`, with `otherwise` redirecting to `/`.

### 6.2 `#/porsequencia` page

`SequenciaController` (`static/assets/js/controllers/sequencia.js:1-105`) initializes:

- `vm.sequenciasFamosas`: the four hardcoded sequence objects (`static/assets/js/controllers/sequencia.js:2-37`).
- `vm.minhaSequencia = {}` (`static/assets/js/controllers/sequencia.js:38`).
- `vm.musics = []`, `vm.generos = GENEROS`, `vm.meuGenero = ""`, and a progress bar (`static/assets/js/controllers/sequencia.js:39-45`).

`vm.temAcorde(acorde)` checks whether a chord is in `vm.minhaSequencia.acordes` (`static/assets/js/controllers/sequencia.js:47-53`). `createChordsString` joins chord objects with commas (`static/assets/js/controllers/sequencia.js:55-61`). `vm.pesquisarPorSequencia` sets the selected sequence, starts the progress bar, and issues a relative `GET` request to `similares?sequencia=<comma-joined-chords>`; it appends `&generos=<selected>` when a genre is selected (`static/assets/js/controllers/sequencia.js:63-90`). The response is assigned directly to `vm.musics` on success (`static/assets/js/controllers/sequencia.js:78-84`). `vm.limparPesquisa` resets the selection and results (`static/assets/js/controllers/sequencia.js:92-95`). `vm.goToLirics` opens the song URL (`static/assets/js/controllers/sequencia.js:97-99`); `vm.goToResults` scrolls to the results panel (`static/assets/js/controllers/sequencia.js:101-104`).

`static/templates/sequencia.html` renders:

- The four hardcoded sequences with `ng-repeat` over `Sequencia.sequenciasFamosas` and a click handler that triggers the search (`static/templates/sequencia.html:5-8`).
- A "results found" button when results exist (`static/templates/sequencia.html:10-14`).
- A genre `<select>` bound to `Sequencia.meuGenero`, with options from `Sequencia.generos`, calling `Sequencia.pesquisarPorSequencia()` on change (`static/templates/sequencia.html:24-30`).
- The selected sequence's chords, with a click handler that clears the search (`static/templates/sequencia.html:34`).
- Result cards filtered with `ng-hide="music.diferenca.length"` and ordered by `-popularidade` (`static/templates/sequencia.html:40-59`). Sequence response objects do not contain `diferenca`, so the expression evaluates to `undefined` and the cards are not hidden.

There is no form, input, POST call, validation, or "add sequence" control on this page. The page only selects one of the four in-memory objects and performs a GET search.

### 6.3 Genre list and API base URL

The genre dropdown uses the `GENEROS` constant in `static/assets/js/app.js:6-58`, not the `/generos` endpoint. That constant has 51 entries; the backend's CSV-derived list has 52, the extra one being `R&B;` (`main.py:66`, `main.py:92`, `main.py:158-160`; first CSV occurrence at `data/top/dataset_final.csv:2167`).

The module also defines `RESTAPI.url = 'http://localhost:5003'` (`static/assets/js/app.js:3-5`), but no controller uses the `RESTAPI` constant. `AcordesController`, `MusicaController`, and `SequenciaController` each declare `var apiUrl = ""` and build relative URLs (`static/assets/js/controllers/acordes.js:91-96`, `static/assets/js/controllers/musica.js:12-16`, `static/assets/js/controllers/musica.js:52-56`, `static/assets/js/controllers/sequencia.js:72-77`). The browser therefore calls the same origin that served `index.html` (port 8080 under Docker, 5000 under `python main.py`).

### 6.4 Other search pages

For contrast, the two existing search flows are:

- `#/poracordes`: `AcordesController` keeps selected chords in `vm.meusAcordes`, builds `similares?acordes=...`, and renders songs with and without `diferenca` in two sections (`static/assets/js/controllers/acordes.js:63-115`, `static/templates/acordes.html:40-91`).
- `#/pormusica`: `MusicaController` uses a typeahead against `/search?key=...` and then calls `similares?id_unico_musica=...` for the selected song (`static/assets/js/controllers/musica.js:14-20`, `static/assets/js/controllers/musica.js:43-70`, `static/templates/musica.html:6-24`).

## 7. Persistence and deployment

- The only persisted application data is `data/top/dataset_final.csv`, read once at import (`main.py:49-98`). AGENTS.md records that editing this CSV requires a restart (`AGENTS.md:45`).
- `Dockerfile:8` copies the whole build context into `/app`; there is no `VOLUME`, no bind-mount instruction, and no data directory outside the image. The documented run command is `docker run -p 8080:8080 ciframe` with no mount (`README.md:15-20`, `AGENTS.md:22-25`).
- ADR 0001 records the current deploy decision: drop App Engine/Heroku config, use a single local-only Dockerfile, and leave the cloud target undecided (`docs/adr/0001-local-only-docker-deploy.md:1-16`).
- ADR 0002 is an unfilled assignment template: it contains instructions and `[seu texto aqui]`, not a decision about persistence (`docs/adr/0002-persist-custom-sequences.md:1-8`).
- ADR 0003 lifts the previous restriction on touching the legacy AngularJS frontend; the frontend remains AngularJS 1.4.9 + jQuery with no build step (`docs/adr/0003-lift-frontend-freeze.md:1-21`).
- The feature documentation directory contains a filled assignment statement and four unfilled templates. In particular, `01-research.md` lists the matching/database/frontend questions but its findings and trade-off sections are placeholders (`docs/features/sequencias-customizadas/01-research.md:7-44`), and `02-proposal.md`, `03-plan.md`, and `04-test-report.md` are also placeholders (`docs/features/sequencias-customizadas/02-proposal.md:7-49`, `03-plan.md:8-33`, `04-test-report.md:5-25`).
- No test directory, test file, or test runner configuration exists in `HEAD`; `requirements.txt` contains no test dependency. The only file matching "test" is the unfilled `04-test-report.md`.

## 8. Cross-component flows

### 8.1 Startup

`gunicorn` imports `main` → `main.py` opens `data/top/dataset_final.csv` (`main.py:49`) → constructs `Musica` objects (`main.py:69-74`, `musica.py:3-22`) → builds `musicas`, `genero_musicas`, `generos`, and `acordes` (`main.py:76-96`) → serves the static app and API from the same process (`main.py:101-112`).

### 8.2 Sequence search

`#/porsequencia` loads → `SequenciaController` creates four hardcoded sequence objects (`static/assets/js/controllers/sequencia.js:2-37`) → user clicks a sequence → controller joins its chords with commas and calls `similares?sequencia=Bm,G,D,A` (`static/assets/js/controllers/sequencia.js:63-77`) → Flask `get_similares` removes commas and looks up `BmGDA` in `sequencias` (`main.py:190-196`) → `get_similares_por_sequencia` filters `musicas` by genre (`main.py:203-205`) and keeps songs whose `seqs_famosas` list contains `'0'` (`main.py:207-221`) → `get_pagina` slices the first 100 (`main.py:196`, `main.py:226-228`) → `json.dumps` returns a string (`main.py:197`) → Angular assigns the parsed array to `vm.musics` (`static/assets/js/controllers/sequencia.js:78-84`) → template renders cards ordered by popularity (`static/templates/sequencia.html:40-59`).

### 8.3 Chord-set search

`#/poracordes` → selected chords joined with commas (`static/assets/js/controllers/acordes.js:76-82`) → `similares?acordes=C,G,Am` (`static/assets/js/controllers/acordes.js:91-96`) → `get_similares` computes intersection/difference against every genre-filtered song (`main.py:230-263`) → results include `diferenca`/`intersecao` (`main.py:246-258`) → template splits songs with no difference and songs requiring more chords (`static/templates/acordes.html:40-91`).

### 8.4 Song-title search

`#/pormusica` → typeahead calls `/search?key=...` after three characters (`static/templates/musica.html:8-18`, `static/assets/js/controllers/musica.js:14-20`) → `/search` lowercases and accent-strips the key, scans `musicas.values()`, and returns title/artist matches (`main.py:114-142`, `main.py:145-147`) → selecting a result calls `similares?id_unico_musica=<id>` (`static/assets/js/controllers/musica.js:52-56`) → generic chord matching returns similar songs (`main.py:187-189`, `main.py:230-263`).

## 9. Factual inputs to the algorithm/database/frontend trade-offs

This section records only what the current code and data establish. It does not select or recommend an option.

### 9.1 Matching algorithm

- There are two different existing matching semantics: sequence search uses the CSV tag (contiguous occurrence plus whole-song chord-vocabulary restriction); chord search uses any non-empty intersection and reports the difference (`main.py:203-223`, `main.py:230-263`).
- `musica.cifra` preserves order and repetition (`musica.py:16`); `musica.acordes` is a de-duplicated set converted to a list and loses order (`musica.py:17`). No runtime normalization of chord spelling, case, enharmonic equivalents, or slash-chord notation exists.
- The sequence key lookup is an exact dictionary lookup after comma removal (`main.py:190-196`). The six valid keys are the only accepted sequence values; anything else returns `[]` (`main.py:194-197`).
- The current CSV tags reproduce the generator's "contiguous + whole-song subset" rule exactly (0 mismatches over 67,585 songs). The alternative rules produce the counts in §4.3; all current-tagged songs are included in every alternative set.
- The sequence branch is limited to the first 100 results by default because the frontend never sends `pagina` (`main.py:35`, `main.py:226-228`, `static/assets/js/controllers/sequencia.js:72-77`).
- The sequence branch returns only `seqs_famosas` matches; it does not compare the requested sequence against `musica.acordes`, so a song with the same chords in a different order is not returned unless its CSV tag says otherwise.

### 9.2 Database

- There is no database today; the only persistence is the CSV file loaded at import (`main.py:49-98`, `requirements.txt:1-5`).
- The application runs as one process in one container with no volume or external service (`Dockerfile:1-12`, `README.md:15-20`, `docs/adr/0001-local-only-docker-deploy.md:9-16`).
- The song/genre catalog is rebuilt from the CSV on every process start; there is no incremental update path and no per-request CSV read (`main.py:49-98`, `AGENTS.md:45`).
- No database technology, schema, migration tool, connection configuration, or data-access module exists to extend; ADR 0002 is still an unfilled template (`docs/adr/0002-persist-custom-sequences.md:1-8`).
- The documented fixed constraints for the assignment state that only the sequence catalog should move to a database, while songs and genres stay on the CSV, and the app remains a single local Docker container (`docs/features/sequencias-customizadas/00-enunciado.md:57-68`).

### 9.3 Frontend

- `#/porsequencia` currently has four hardcoded sequences versus six backend sequences (`static/assets/js/controllers/sequencia.js:2-37`, `main.py:40-45`); IDs 2 and 3 have no UI entry.
- There is no create-sequence form, no POST call, no client-side validation, and no catalog-fetch endpoint to populate a dynamic list (`static/templates/sequencia.html:1-63`, `static/assets/js/controllers/sequencia.js:63-95`, `main.py:101-201`).
- The page sends only a chord list, not an ID or display name; the backend maps the comma-stripped list to its hardcoded dictionary (`static/assets/js/controllers/sequencia.js:55-77`, `main.py:190-196`).
- The genre dropdown is a static 51-entry constant, not `/generos` (`static/assets/js/app.js:6-58`, `main.py:158-160`).
- Requests are same-origin relative URLs; the `RESTAPI` constant pointing at port 5003 is unused (`static/assets/js/app.js:3-5`, `static/assets/js/controllers/sequencia.js:72-77`).
- All current frontend API calls are GETs; there is no authentication, session, user, or CSRF code in the application.
- The frontend uses `$http.success`/`.error` (`static/assets/js/controllers/sequencia.js:77-89`), AngularJS 1.4.9 from CDN (`static/index.html:129-134`), and no build step.

## Appendix — relevant files

| Path | Role |
|---|---|
| `main.py` | Flask app, CSV load, in-memory indexes, all endpoints, hardcoded 6-sequence map |
| `musica.py` | `Musica` object fields, `id_unico_musica`, `url`, `acordes`, `seqs_famosas` |
| `data/top/dataset_final.csv` | 67,586-line song catalog; column 7 is the precomputed sequence tag |
| `scripts/generate_data_set.py` | Offline generator that produced the CSV, including `get_famosas` |
| `data/mapeamento_sequencias_famosas.txt` | Human-readable ID-to-name mapping; not read at runtime |
| `static/index.html` | AngularJS boot and script includes |
| `static/assets/js/app.js` | Module, unused `RESTAPI` constant, 51-entry `GENEROS` constant |
| `static/assets/js/routes.js` | `#/porsequencia` route definition |
| `static/assets/js/controllers/sequencia.js` | Hardcoded 4-sequence list and sequence search request |
| `static/templates/sequencia.html` | Sequence page rendering and genre selector |
| `static/assets/js/controllers/acordes.js` | Chord-set search flow |
| `static/assets/js/controllers/musica.js` | Song title search and song-to-similar flow |
| `Dockerfile` | Single-container Python 3.9 + gunicorn deploy |
| `requirements.txt` | Flask and gunicorn only |
| `docs/adr/0001-local-only-docker-deploy.md` | Current deploy decision |
| `docs/adr/0002-persist-custom-sequences.md` | Unfilled persistence decision template |
| `docs/adr/0003-lift-frontend-freeze.md` | Frontend-touching restriction lifted |
| `docs/features/sequencias-customizadas/00-enunciado.md` | Feature assignment and fixed constraints |
| `docs/features/sequencias-customizadas/01-research.md` | Unfilled research questions/template |
