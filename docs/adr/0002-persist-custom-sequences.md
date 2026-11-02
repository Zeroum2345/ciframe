# Persistir o catálogo de sequências de acordes em SQLite dentro do container único

O catálogo de sequências sempre viveu no código: seis chaves num dicionário em
`main.py`, e uma cópia menor (quatro) hardcoded no JavaScript da página
`#/porsequencia`. Não havia banco, schema, migração nem volume — a única massa de
dados persistida era `data/top/dataset_final.csv`, lido em memória a cada start. Isso
funcionava enquanto o catálogo fosse imutável, mas a feature de sequências
customizadas permite que qualquer visitante cadastre uma sequência, e cadastro sem
persistência se perde no primeiro restart. O enunciado também exige explicitamente um
banco de dados, restrito ao catálogo de sequências: músicas e gêneros continuam vindo
do CSV.

Decidimos introduzir **SQLite** (`sqlite3` da stdlib) como o único banco da aplicação,
guardando apenas o catálogo de sequências. O arquivo fica em `var/deciframe.db`, com
`VOLUME /app/var` no `Dockerfile` e volume nomeado no `docker run`
(`-v deciframe-data:/app/var`). O caminho é deliberadamente separado de `data/`,
porque montar um volume sobre `data/` sombrearia o CSV que o app lê. O banco tem duas
tabelas: `sequences` (id, nome opcional, chave canônica dos acordes em JSON, chave
legada e data de criação) e `sequence_chords` (acorde + posição, com chave primária
composta), o que preserva a ordem — que é semântica nesta feature — e permite
deduplicar pela lista canônica. As seis originais são semeadas de forma idempotente
com IDs explícitos 0–5, mantendo a compatibilidade com o que já existe no backend.

SQLite foi escolhido porque é a única opção que satisfaz "banco de dados" sem violar o
container único e local do ADR 0001: não é um serviço externo, não adiciona dependência
nem processo, oferece transações, constraints e chave única, e é mais que suficiente
para um catálogo que hoje tem seis registros. CSV/JSON foi descartado por não ter
constraints nem escrita atômica e por provavelmente não atender à letra do requisito;
TinyDB e DuckDB adicionariam dependência sem ganho nesse volume; `shelve`/`dbm` não
dariam unicidade nem consultas relacionais.

A decisão também muda o matching. Como sequências novas não têm tag pré-computada, a
busca passou a ser calculada em tempo real sobre `musica.cifra`, com a mesma regra que
gerou a coluna `SEQ_FAMOSA`: ocorrência contígua e nenhum acorde fora da sequência.
Escolhemos replicar exatamente essa regra, com comparação exata de tokens, porque ela
é a única que reproduz as tags atuais (0 divergências em 67.585 músicas) e assim as
seis originais continuam com os mesmos resultados sem regerar o CSV. A coluna 7
permanece no arquivo e continua sendo carregada, mas deixa de ser consultada pela
busca por sequência — é dado legado, não fonte de verdade.

As consequências são assumidas. A aplicação passa a ter duas fontes de dados: o CSV,
somente leitura, e o banco, gravável. O startup passa a depender de um diretório
gravável; sem volume, os cadastros sobrevivem a `docker restart`, mas não a
`docker rm`/rebuild, e isso precisa estar documentado no README. O backup deixa de ser
"copiar um arquivo" trivial por causa do WAL, então o procedimento recomendado é
`.backup` do SQLite ou parar o container antes de copiar. A evolução do schema é
manual, via `PRAGMA user_version`, sem ferramenta de migração — aceitável para duas
tabelas. Cada busca por sequência passa a custar ~40 ms em vez dos ~7 ms do lookup na
tag, ainda assim cerca de cinco vezes mais barato que a busca por acordes que já
existia. Por fim, a regra estrita faz muitas sequências novas retornarem zero
músicas; a decisão foi mantê-la mesmo assim, expondo `total_musicas` no retorno do
cadastro para que o autor entenda o resultado em vez de achar que a busca quebrou.

O ADR 0001 continua válido: a aplicação segue rodando em um único container local via
gunicorn, sem serviço adicional. O que muda é que ela deixa de ser stateless — passa a
ter um estado gravável próprio, cuja durabilidade depende de um volume nomeado.
