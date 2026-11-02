import os
import shutil
import tempfile
import unittest

from sequence_store import (
    MAX_SEQUENCIAS,
    SequenceStore,
    ValidacaoError,
)


class SequenceStoreTest(unittest.TestCase):

    def setUp(self):
        self.diretorio = tempfile.mkdtemp(prefix='deciframe-store-')
        self.caminho = os.path.join(self.diretorio, 'deciframe.db')
        self.store = SequenceStore(self.caminho)

    def tearDown(self):
        shutil.rmtree(self.diretorio, ignore_errors=True)

    def test_init_db_e_idempotente_e_semeia_as_seis(self):
        self.store.init_db()
        self.store.init_db()

        sequencias = self.store.listar()
        self.assertEqual(6, len(sequencias))
        self.assertEqual([0, 1, 2, 3, 4, 5], [s['id'] for s in sequencias])
        self.assertEqual(['Bm', 'G', 'D', 'A'], sequencias[0]['acordes'])
        self.assertIsNone(sequencias[0]['nome'])
        self.assertEqual(['C', 'A7', 'Dm', 'G7'], self.store.buscar_legado('CA7DmG7')['acordes'])

    def test_criar_preserva_ordem_e_gera_id(self):
        self.store.init_db()
        registro, criado = self.store.criar('Samba', ['C', 'G', 'Am'])

        self.assertTrue(criado)
        self.assertEqual(6, registro['id'])
        self.assertEqual('Samba', registro['nome'])
        self.assertEqual(['C', 'G', 'Am'], registro['acordes'])
        self.assertEqual(7, len(self.store.listar()))

    def test_deduplica_pela_lista_de_acordes(self):
        self.store.init_db()
        primeiro, _ = self.store.criar('Samba', ['C', 'G', 'Am'])
        duplicado, criado = self.store.criar('Outro nome', ['C', 'G', 'Am'])

        self.assertFalse(criado)
        self.assertEqual(primeiro['id'], duplicado['id'])
        self.assertEqual('Samba', duplicado['nome'])
        self.assertEqual(7, len(self.store.listar()))

    def test_deduplica_apos_normalizar_espacos(self):
        self.store.init_db()
        primeiro, _ = self.store.criar(None, ['C', 'A7'])
        duplicado, criado = self.store.criar(None, [' C ', 'A7'])

        self.assertFalse(criado)
        self.assertEqual(primeiro['id'], duplicado['id'])

    def test_nome_vazio_vira_nulo(self):
        self.store.init_db()
        registro, _ = self.store.criar('   ', ['C'])
        self.assertIsNone(registro['nome'])

    def test_persiste_entre_instancias(self):
        self.store.init_db()
        self.store.criar('Persistente', ['G', 'Em', 'C', 'D'])

        outro = SequenceStore(self.caminho)
        outro.init_db()
        registro = outro.buscar_legado('BmGDA')
        self.assertIsNotNone(registro)
        self.assertEqual(7, len(outro.listar()))

    def test_validacao(self):
        self.store.init_db()
        invalidas = [
            (None, []),
            (None, ['']),
            (None, [''] * 1),
            (None, ['A'] * 33),
            (None, ['X' * 25]),
            ('a' * 81, ['C']),
            (None, ['A\x01']),
            (None, 'C'),
            (None, [1]),
            (1, ['C']),
        ]
        for nome, acordes in invalidas:
            with self.subTest(nome=nome, acordes=acordes):
                with self.assertRaises(ValidacaoError):
                    self.store.criar(nome, acordes)

    def test_limite_do_catalogo(self):
        self.store.init_db()
        for i in range(MAX_SEQUENCIAS - 6):
            self.store.criar(None, ['X%d' % i])

        self.assertEqual(MAX_SEQUENCIAS, len(self.store.listar()))
        with self.assertRaises(ValidacaoError):
            self.store.criar(None, ['Y'])

        # Duplicata continua devolvendo o registro existente, mesmo no limite.
        registro, criado = self.store.criar(None, ['X0'])
        self.assertFalse(criado)
        self.assertIsNotNone(registro)


if __name__ == '__main__':
    unittest.main()
