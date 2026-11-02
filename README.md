# deciframe

Descubra as músicas que você já sabe tocar (e ainda não faz ideia). Busque por
título/artista, gênero, pelos acordes que você já manja, ou por sequências de
acordes famosas — o deciframe cruza isso com uma base de cifras e sugere
músicas parecidas.

Stack: backend Flask (Python) servindo uma API JSON + um frontend AngularJS
estático. Músicas e gêneros vêm de um CSV carregado em memória; o catálogo de
sequências de acordes fica em um banco SQLite (`var/deciframe.db`).

## Rodando localmente

### Com Docker

```
docker build -t ciframe .
docker run -p 8080:8080 -v deciframe-data:/app/var ciframe
```

Acesse [http://localhost:8080](http://localhost:8080).

O volume `deciframe-data` guarda o catálogo de sequências. Sem ele, os cadastros
sobrevivem a `docker restart`, mas não a `docker rm` ou a um rebuild. Não monte o
volume sobre `/app/data`: ali está o CSV que o app lê. Para backup, use
`.backup` do SQLite ou pare o container antes de copiar o arquivo.

### Com virtualenv

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Acesse [http://localhost:5000](http://localhost:5000).

---

Para convenções de contribuição, veja [CONTRIB.md](CONTRIB.md). Licença: [LICENSE](LICENSE).
