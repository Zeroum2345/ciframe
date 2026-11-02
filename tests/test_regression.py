import support  # noqa: F401
import unittest

import main
from sequence_store import SEQUENCIAS_ORIGINAIS


CONTAGENS_ESPERADAS = {0: 199, 1: 296, 2: 4, 3: 5, 4: 7, 5: 3}


class RegressaoTest(unittest.TestCase):

    def test_seis_sequencias_mantem_lista_e_ordem(self):
        collection = main.apply_filtro(main.musicas.values(), main.generos)

        for seq_id, chave, acordes in SEQUENCIAS_ORIGINAIS:
            with self.subTest(sequencia=chave):
                esperado = [
                    musica.id_unico_musica for musica in collection
                    if str(seq_id) in musica.seqs_famosas
                ]
                obtido = [
                    similar['id_unico_musica']
                    for similar in main.get_similares_por_sequencia(acordes, main.generos)
                ]

                self.assertEqual(CONTAGENS_ESPERADAS[seq_id], len(esperado))
                self.assertEqual(esperado, obtido)

    def test_parametros_legados_resolvem_para_o_catalogo(self):
        for seq_id, chave, acordes in SEQUENCIAS_ORIGINAIS:
            with self.subTest(sequencia=chave):
                self.assertEqual(acordes, main.acordes_da_sequencia(None, chave))
                self.assertEqual(acordes, main.acordes_da_sequencia(str(seq_id), None))


if __name__ == '__main__':
    unittest.main()
