import support  # noqa: F401
import json
import os
import shutil
import tempfile
import unittest

import main
from sequence_store import SequenceStore


class ApiTest(unittest.TestCase):

    def setUp(self):
        self.diretorio = tempfile.mkdtemp(prefix='deciframe-api-')
        self.store = SequenceStore(os.path.join(self.diretorio, 'deciframe.db'))
        self.store.init_db()
        self.store_original = main.sequence_store
        main.sequence_store = self.store
        self.client = main.app.test_client()

    def tearDown(self):
        main.sequence_store = self.store_original
        shutil.rmtree(self.diretorio, ignore_errors=True)

    def get_json(self, url):
        resposta = self.client.get(url)
        return resposta, json.loads(resposta.get_data(as_text=True))

    def post_json(self, corpo):
        resposta = self.client.post('/sequencias', json=corpo)
        return resposta, json.loads(resposta.get_data(as_text=True))

    def test_get_sequencias_lista_o_catalogo_semeado(self):
        resposta, dados = self.get_json('/sequencias')

        self.assertEqual(200, resposta.status_code)
        self.assertTrue(resposta.content_type.startswith('text/html'))
        self.assertEqual([0, 1, 2, 3, 4, 5], [s['id'] for s in dados])
        self.assertEqual(['Bm', 'G', 'D', 'A'], dados[0]['acordes'])

    def test_post_cria_sequencia_e_retorna_total(self):
        resposta, dados = self.post_json({'nome': 'Pop', 'acordes': ['C', 'G', 'Am']})

        self.assertEqual(201, resposta.status_code)
        self.assertTrue(resposta.content_type.startswith('text/html'))
        self.assertEqual(6, dados['id'])
        self.assertEqual('Pop', dados['nome'])
        self.assertEqual(['C', 'G', 'Am'], dados['acordes'])
        self.assertEqual(28, dados['total_musicas'])

        _, catalogo = self.get_json('/sequencias')
        self.assertEqual(7, len(catalogo))

    def test_post_aceita_acordes_como_string(self):
        resposta, dados = self.post_json({'acordes': 'C, G  Am'})

        self.assertEqual(201, resposta.status_code)
        self.assertEqual(['C', 'G', 'Am'], dados['acordes'])
        self.assertEqual(28, dados['total_musicas'])

    def test_post_duplicado_retorna_200_com_registro_existente(self):
        _, primeiro = self.post_json({'nome': 'Pop', 'acordes': ['C', 'G', 'Am']})
        resposta, duplicado = self.post_json({'nome': 'Outro', 'acordes': ['C', 'G', 'Am']})

        self.assertEqual(200, resposta.status_code)
        self.assertEqual(primeiro['id'], duplicado['id'])
        self.assertEqual('Pop', duplicado['nome'])
        self.assertIn('total_musicas', duplicado)

        _, catalogo = self.get_json('/sequencias')
        self.assertEqual(7, len(catalogo))

    def test_post_invalido_retorna_400(self):
        for corpo in ({}, {'acordes': []}, {'acordes': ['A'] * 33}, {'nome': 'x' * 81, 'acordes': ['C']}):
            with self.subTest(corpo=corpo):
                resposta, dados = self.post_json(corpo)
                self.assertEqual(400, resposta.status_code)
                self.assertIn('erro', dados)

    def test_post_com_corpo_nao_json_retorna_400(self):
        resposta = self.client.post('/sequencias', data='nao e json', content_type='application/json')
        self.assertEqual(400, resposta.status_code)

    def test_busca_por_sequencia_id(self):
        resposta, dados = self.get_json('/similares?sequencia_id=0')
        self.assertEqual(200, resposta.status_code)
        self.assertTrue(resposta.content_type.startswith('text/html'))
        self.assertEqual(100, len(dados))

    def test_sequencia_id_desconhecido_ou_invalido_retorna_vazio(self):
        for valor in ('999', 'abc'):
            with self.subTest(valor=valor):
                _, dados = self.get_json('/similares?sequencia_id=' + valor)
                self.assertEqual([], dados)

    def test_busca_por_sequencia_cadastrada(self):
        _, criada = self.post_json({'nome': 'Pop', 'acordes': ['C', 'G', 'Am']})
        _, dados = self.get_json('/similares?sequencia_id=%d' % criada['id'])
        self.assertEqual(criada['total_musicas'], len(dados))

    def test_compatibilidade_com_parametro_sequencia(self):
        casos = {
            '/similares?sequencia=BmGDA': 100,
            '/similares?sequencia=Bm,G,D,A': 100,
            '/similares?sequencia=Bm%20G%20D%20A': 100,
            '/similares?sequencia=CGAmF&pagina=3': 96,
            '/similares?sequencia=bmgda': 0,
        }
        for url, tamanho in casos.items():
            with self.subTest(url=url):
                _, dados = self.get_json(url)
                self.assertEqual(tamanho, len(dados))


if __name__ == '__main__':
    unittest.main()
