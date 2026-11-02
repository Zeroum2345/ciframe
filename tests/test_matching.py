import support  # noqa: F401
import unittest

import main
from musica import Musica


def criar_musica(cifra):
    return Musica('artista', 'Artista', 'musica', 'Música', 'Rock', 100, [], 'C', cifra)


class CasaSequenciaTest(unittest.TestCase):

    def test_casa_sequencia_exata(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A'])
        self.assertTrue(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_aceita_repeticao_de_acordes_da_sequencia(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A', 'Bm', 'G', 'D'])
        self.assertTrue(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_musica_menor_que_a_sequencia_nao_casa(self):
        musica = criar_musica(['Bm', 'G', 'D'])
        self.assertFalse(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_rejeita_acorde_extra_na_musica(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A', 'E'])
        self.assertFalse(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_rejeita_ordem_trocada(self):
        musica = criar_musica(['Bm', 'D', 'G', 'A'])
        self.assertFalse(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_rejeita_cifra_vazia(self):
        musica = criar_musica([])
        self.assertFalse(main.casa_sequencia(['Bm', 'G', 'D', 'A'], musica))

    def test_rejeita_sequencia_vazia(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A'])
        self.assertFalse(main.casa_sequencia([], musica))

    def test_respeita_repeticao(self):
        self.assertTrue(main.casa_sequencia(['A', 'A', 'B'], criar_musica(['A', 'A', 'B'])))
        self.assertFalse(main.casa_sequencia(['A', 'A', 'B'], criar_musica(['A', 'B'])))
        self.assertFalse(main.casa_sequencia(['A', 'A', 'B'], criar_musica(['A', 'B', 'A', 'B'])))

    def test_comparacao_exata_de_caixa(self):
        self.assertFalse(main.casa_sequencia(['AM7', 'D'], criar_musica(['Am7', 'D'])))
        self.assertFalse(main.casa_sequencia(['Am7', 'D'], criar_musica(['AM7', 'D'])))

    def test_parse_acordes(self):
        self.assertEqual(main.parse_acordes('C, A7  Dm,G7'), ['C', 'A7', 'Dm', 'G7'])
        self.assertEqual(main.parse_acordes('Bm,,G'), ['Bm', 'G'])
        self.assertEqual(main.parse_acordes('   '), [])


if __name__ == '__main__':
    unittest.main()
