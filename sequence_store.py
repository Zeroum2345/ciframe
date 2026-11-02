# coding: utf-8
"""Persistência do catálogo de sequências de acordes em SQLite."""

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1
MAX_ACORDES = 32
MAX_CARACTERES_ACORDE = 24
MAX_CARACTERES_NOME = 80
MAX_SEQUENCIAS = 500

SEQUENCIAS_ORIGINAIS = [
    (0, 'BmGDA', ['Bm', 'G', 'D', 'A']),
    (1, 'CGAmF', ['C', 'G', 'Am', 'F']),
    (2, 'EmG', ['Em', 'G']),
    (3, 'CA7DmG7', ['C', 'A7', 'Dm', 'G7']),
    (4, 'GmF', ['Gm', 'F']),
    (5, 'CC7FFm', ['C', 'C7', 'F', 'Fm']),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sequences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT,
    chords_key TEXT NOT NULL UNIQUE,
    legacy_key TEXT UNIQUE,
    criada_em  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS sequence_chords (
    sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    posicao     INTEGER NOT NULL,
    acorde      TEXT NOT NULL,
    PRIMARY KEY (sequence_id, posicao)
);
"""


class ValidacaoError(ValueError):
    """Sequência inválida para cadastro."""


def chords_key(acordes: List[str]) -> str:
    """Serialização canônica da lista de acordes, usada como chave única."""
    return json.dumps(acordes, ensure_ascii=False, separators=(',', ':'))


def _tem_caractere_de_controle(valor: str) -> bool:
    return any(ord(caractere) < 32 or ord(caractere) == 127 for caractere in valor)


def validar_sequencia(nome: Optional[str],
                      acordes: List[str]) -> Tuple[Optional[str], List[str]]:
    """Normaliza e valida nome/acordes, devolvendo os valores prontos para gravar."""
    if not isinstance(acordes, (list, tuple)):
        raise ValidacaoError('acordes deve ser uma lista de acordes')

    normalizados = []
    for acorde in acordes:
        if not isinstance(acorde, str):
            raise ValidacaoError('cada acorde deve ser texto')
        acorde = acorde.strip()
        if not acorde:
            raise ValidacaoError('acorde vazio')
        if len(acorde) > MAX_CARACTERES_ACORDE:
            raise ValidacaoError('acorde com mais de %d caracteres' % MAX_CARACTERES_ACORDE)
        if _tem_caractere_de_controle(acorde):
            raise ValidacaoError('acorde com caractere de controle')
        normalizados.append(acorde)

    if not normalizados:
        raise ValidacaoError('informe pelo menos um acorde')
    if len(normalizados) > MAX_ACORDES:
        raise ValidacaoError('no máximo %d acordes por sequência' % MAX_ACORDES)

    if nome is not None:
        if not isinstance(nome, str):
            raise ValidacaoError('nome deve ser texto')
        nome = nome.strip()
        if not nome:
            nome = None
        elif len(nome) > MAX_CARACTERES_NOME:
            raise ValidacaoError('nome com mais de %d caracteres' % MAX_CARACTERES_NOME)
        elif _tem_caractere_de_controle(nome):
            raise ValidacaoError('nome com caractere de controle')

    return nome, normalizados


class SequenceStore:
    """Acesso ao catálogo de sequências, com uma conexão por operação."""

    def __init__(self, path: str) -> None:
        self.path = path

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.path, timeout=5)
        conexao.row_factory = sqlite3.Row
        conexao.execute('PRAGMA foreign_keys = ON')
        return conexao

    def init_db(self) -> None:
        """Cria schema e semeia as 6 sequências originais (idempotente)."""
        diretorio = os.path.dirname(os.path.abspath(self.path))
        try:
            os.makedirs(diretorio, exist_ok=True)
        except OSError as erro:
            raise RuntimeError(
                'Não foi possível criar o diretório do banco em %s: %s'
                % (diretorio, erro)
            )

        with self._conectar() as conexao:
            conexao.execute('PRAGMA journal_mode = WAL')
            versao = conexao.execute('PRAGMA user_version').fetchone()[0]
            if versao < SCHEMA_VERSION:
                conexao.executescript(SCHEMA)
                conexao.execute('PRAGMA user_version = %d' % SCHEMA_VERSION)
            self._semear(conexao)

    def _semear(self, conexao: sqlite3.Connection) -> None:
        for seq_id, legacy_key, acordes in SEQUENCIAS_ORIGINAIS:
            chave = chords_key(acordes)
            existente = conexao.execute(
                'SELECT chords_key FROM sequences WHERE id = ?', (seq_id,)
            ).fetchone()
            if existente is None:
                conexao.execute(
                    'INSERT INTO sequences (id, nome, chords_key, legacy_key) '
                    'VALUES (?, NULL, ?, ?)',
                    (seq_id, chave, legacy_key),
                )
            elif existente['chords_key'] != chave:
                # Banco com id divergente: não sobrescreve dado existente.
                continue

            for posicao, acorde in enumerate(acordes):
                conexao.execute(
                    'INSERT OR IGNORE INTO sequence_chords '
                    '(sequence_id, posicao, acorde) VALUES (?, ?, ?)',
                    (seq_id, posicao, acorde),
                )

    def _acordes_por_sequencia(
            self, conexao: sqlite3.Connection) -> Dict[int, List[str]]:
        resultado = {}  # type: Dict[int, List[str]]
        linhas = conexao.execute(
            'SELECT sequence_id, acorde FROM sequence_chords '
            'ORDER BY sequence_id, posicao'
        ).fetchall()
        for linha in linhas:
            resultado.setdefault(linha['sequence_id'], []).append(linha['acorde'])
        return resultado

    def _registro(self, conexao: sqlite3.Connection,
                  seq_id: int) -> Optional[Dict[str, Any]]:
        linha = conexao.execute(
            'SELECT id, nome FROM sequences WHERE id = ?', (seq_id,)
        ).fetchone()
        if linha is None:
            return None
        acordes = conexao.execute(
            'SELECT acorde FROM sequence_chords '
            'WHERE sequence_id = ? ORDER BY posicao',
            (seq_id,),
        ).fetchall()
        return {
            'id': linha['id'],
            'nome': linha['nome'],
            'acordes': [acorde['acorde'] for acorde in acordes],
        }

    def listar(self) -> List[Dict[str, Any]]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                'SELECT id, nome FROM sequences ORDER BY id'
            ).fetchall()
            acordes = self._acordes_por_sequencia(conexao)
        return [
            {
                'id': linha['id'],
                'nome': linha['nome'],
                'acordes': acordes.get(linha['id'], []),
            }
            for linha in linhas
        ]

    def buscar(self, seq_id: int) -> Optional[Dict[str, Any]]:
        with self._conectar() as conexao:
            return self._registro(conexao, seq_id)

    def buscar_legado(self, key: str) -> Optional[Dict[str, Any]]:
        with self._conectar() as conexao:
            linha = conexao.execute(
                'SELECT id FROM sequences WHERE legacy_key = ?', (key,)
            ).fetchone()
            if linha is None:
                return None
            return self._registro(conexao, linha['id'])

    def criar(self, nome: Optional[str],
              acordes: List[str]) -> Tuple[Dict[str, Any], bool]:
        """Cria a sequência ou devolve a existente com a mesma lista de acordes."""
        nome, acordes = validar_sequencia(nome, acordes)
        chave = chords_key(acordes)

        with self._conectar() as conexao:
            existente = conexao.execute(
                'SELECT id FROM sequences WHERE chords_key = ?', (chave,)
            ).fetchone()
            if existente is not None:
                return self._registro(conexao, existente['id']), False

            total = conexao.execute(
                'SELECT COUNT(*) FROM sequences'
            ).fetchone()[0]
            if total >= MAX_SEQUENCIAS:
                raise ValidacaoError(
                    'Catálogo cheio: limite de %d sequências atingido.'
                    % MAX_SEQUENCIAS
                )

            cursor = conexao.execute(
                'INSERT INTO sequences (nome, chords_key) VALUES (?, ?)',
                (nome, chave),
            )
            seq_id = cursor.lastrowid
            for posicao, acorde in enumerate(acordes):
                conexao.execute(
                    'INSERT INTO sequence_chords '
                    '(sequence_id, posicao, acorde) VALUES (?, ?, ?)',
                    (seq_id, posicao, acorde),
                )

            return self._registro(conexao, seq_id), True
