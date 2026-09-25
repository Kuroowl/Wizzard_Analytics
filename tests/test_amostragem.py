"""
Testes do core da Nova Amostragem (sem Dash).

    python -m unittest discover -s tests -v      (da raiz do repositório)
"""
import unittest

import numpy as np
import pandas as pd

from src.core.arquivo import Arquivo
from src.core.derivados import ArvoreDerivados, NoDerivado, Serie
from src.core.operations import amostragem as am


def serie_linear(n=1001, inicio=0.0, fim=10.0):
    x = np.linspace(inicio, fim, n)
    return Serie(x, 2 * x + 1)


class TestSerie(unittest.TestCase):

    def test_de_colunas_descarta_nan_e_ordena(self):
        df = pd.DataFrame({'t': [3, 1, None, 2, 4], 'p': [30, 10, 99, None, 40]})
        s = Serie.de_colunas(df, 't', 'p')
        np.testing.assert_array_equal(s.x, [1, 3, 4])
        np.testing.assert_array_equal(s.y, [10, 30, 40])

    def test_tamanhos_diferentes_recusados(self):
        with self.assertRaises(ValueError):
            Serie([1, 2, 3], [1, 2])

    def test_coluna_inexistente(self):
        with self.assertRaises(KeyError):
            Serie.de_colunas(pd.DataFrame({'a': [1]}), 'a', 'b')


class TestDownsampling(unittest.TestCase):

    def test_pontos_existem_e_sao_uniformes(self):
        s = serie_linear()
        r = am.downsampling(s, 11)
        self.assertEqual(len(r.serie), 11)
        np.testing.assert_allclose(r.serie.x, np.linspace(0, 10, 11))
        # Nada interpolado: todo (x, y) do resultado existe na origem.
        for x, y in zip(r.serie.x, r.serie.y):
            i = np.flatnonzero(s.x == x)
            self.assertEqual(len(i), 1)
            self.assertEqual(s.y[i[0]], y)

    def test_inclui_extremos(self):
        r = am.downsampling(serie_linear(), 7)
        self.assertEqual(r.serie.x[0], 0)
        self.assertEqual(r.serie.x[-1], 10)

    def test_aquisicao_irregular_nao_duplica(self):
        # Muitos pontos no começo, um só no fim: alvos caem no mesmo ponto.
        x = np.concatenate([np.linspace(0, 1, 100), [10]])
        r = am.downsampling(Serie(x, x), 10)
        self.assertEqual(len(np.unique(r.serie.x)), len(r.serie))
        self.assertLess(r.info['n_obtido'], 10)
        self.assertEqual(r.info['n_pedido'], 10)

    def test_n_maior_que_serie_devolve_tudo(self):
        s = serie_linear(n=5)
        r = am.downsampling(s, 500)
        np.testing.assert_array_equal(r.serie.x, s.x)

    def test_parametros_invalidos(self):
        for n in (0, -3, 2.5, 'abc', None):
            with self.assertRaises(ValueError, msg=n):
                am.downsampling(serie_linear(), n)


class TestMediaMovel(unittest.TestCase):

    def test_constante_da_media_exata_e_sigma_zero(self):
        x = np.linspace(0, 10, 101)
        r = am.media_movel(Serie(x, np.full_like(x, 5.0)), 11, 0.5)
        np.testing.assert_allclose(r.serie.y, 5.0)
        np.testing.assert_allclose(r.serie.sigma, 0.0)
        np.testing.assert_allclose(r.serie.x, np.linspace(0, 10, 11))

    def test_janela_inclui_limites_e_trunca_nas_bordas(self):
        x = np.arange(0.0, 11.0)       # 0, 1, ..., 10
        y = x.copy()
        r = am.media_movel(Serie(x, y), 3, 1.0)   # centros 0, 5, 10
        # borda esquerda: janela [-1, 1] -> só 0 e 1 existem
        self.assertAlmostEqual(r.serie.y[0], 0.5)
        # meio: [4, 6] -> 4, 5, 6 (limites incluídos)
        self.assertAlmostEqual(r.serie.y[1], 5.0)
        self.assertAlmostEqual(r.serie.sigma[1], np.std([4, 5, 6]))
        # borda direita: [9, 11] -> 9 e 10
        self.assertAlmostEqual(r.serie.y[2], 9.5)
        self.assertEqual(r.info['pontos_por_janela_min'], 2)
        self.assertEqual(r.info['pontos_por_janela_max'], 3)

    def test_janelas_vazias_descartadas(self):
        x = np.array([0.0, 0.1, 0.2, 9.8, 9.9, 10.0])
        r = am.media_movel(Serie(x, x), 11, 0.3)
        self.assertGreater(r.info['janelas_vazias'], 0)
        self.assertEqual(len(r.serie) + r.info['janelas_vazias'], 11)

    def test_delta_x_invalido(self):
        for dx in (0, -1, 'x', None, float('nan')):
            with self.assertRaises(ValueError, msg=dx):
                am.media_movel(serie_linear(), 10, dx)

    def test_delta_x_sugerido_encosta_janelas(self):
        self.assertAlmostEqual(am.delta_x_sugerido(serie_linear(), 11), 0.5)


class TestAjustePolinomial(unittest.TestCase):

    def test_recupera_coeficientes(self):
        x = np.linspace(-3, 3, 200)
        for grau, coefs in ((1, [2, 1]), (2, [0.5, -1, 3]), (3, [1, 0, -2, 4])):
            r = am.ajuste_polinomial(Serie(x, np.polyval(coefs, x)), grau, 50)
            np.testing.assert_allclose(r.info['coeficientes'], coefs, atol=1e-8)
            self.assertAlmostEqual(r.info['r2'], 1.0)
            self.assertEqual(len(r.serie), 50)
            self.assertEqual(r.serie.x[0], -3)
            self.assertEqual(r.serie.x[-1], 3)

    def test_x_grande_nao_perde_precisao(self):
        x = 1.7e9 + np.linspace(0, 100, 500)     # timestamp em segundos
        y = 3e-4 * (x - 1.7e9) ** 2 + 2
        r = am.ajuste_polinomial(Serie(x, y), 2, 10)
        np.testing.assert_allclose(r.serie.y, 3e-4 * (r.serie.x - 1.7e9) ** 2 + 2, rtol=1e-6)

    def test_coeficiente_zero_no_fim_nao_some(self):
        x = np.linspace(-1, 1, 50)
        r = am.ajuste_polinomial(Serie(x, x ** 2), 2, 10)     # y = x² + 0x + 0
        self.assertEqual(len(r.info['coeficientes']), 3)

    def test_equacao(self):
        self.assertEqual(am._equacao([2, -0.5, 1]), 'y = 2·x² − 0.5·x + 1')
        self.assertEqual(am._equacao([-1, 0, 0, 3]), 'y = −1·x³ + 0·x² + 0·x + 3')

    def test_invalidos(self):
        with self.assertRaises(ValueError):
            am.ajuste_polinomial(serie_linear(), 4, 10)
        with self.assertRaises(ValueError):
            am.ajuste_polinomial(serie_linear(), 1, 1)
        with self.assertRaises(ValueError):       # 2 valores de x, grau 2
            am.ajuste_polinomial(Serie([1, 1, 2], [1, 2, 3]), 2, 10)


class TestCatalogo(unittest.TestCase):

    def test_executar_e_parametros_iniciais(self):
        s = serie_linear()
        for chave in am.OPERACOES:
            parametros = am.parametros_iniciais(chave, s)
            r = am.executar_operacao(chave, s, parametros)
            self.assertFalse(r.serie.vazia, chave)

    def test_parametro_faltando(self):
        with self.assertRaises(ValueError):
            am.executar_operacao('media_movel', serie_linear(), {'n_pontos': 10})

    def test_operacao_desconhecida(self):
        with self.assertRaises(ValueError):
            am.executar_operacao('model_fit', serie_linear(), {})

    def test_nome_padrao(self):
        self.assertEqual(am.nome_padrao('downsampling', 'Pressão'), 'Downsampling Pressão')


def _no(arvore, canal='p', pai=None):
    return arvore.adicionar(NoDerivado(
        id=arvore.novo_id(), nome='n', canal_raiz=canal, eixo_x='t', pai=pai,
        operacao='downsampling', parametros={}, serie=Serie([1], [1])))


class TestArvore(unittest.TestCase):

    def test_hierarquia_e_exclusao_em_cascata(self):
        a = ArvoreDerivados()
        n1 = _no(a)
        n2 = _no(a, pai=n1.id)
        n3 = _no(a, pai=n2.id)
        n4 = _no(a)
        _no(a, canal='q')
        self.assertEqual([n.id for n in a.filhos(None, 'p')], [n1.id, n4.id])
        self.assertEqual([n.id for n in a.ancestrais(n3.id)], [n3.id, n2.id, n1.id])
        self.assertEqual(a.canais_com_derivados(), ['p', 'q'])
        self.assertEqual(a.excluir(n1.id), [n1.id, n2.id, n3.id])
        self.assertEqual(len(a), 2)

    def test_filho_com_outro_canal_raiz_recusado(self):
        a = ArvoreDerivados()
        n1 = _no(a)
        with self.assertRaises(ValueError):
            _no(a, canal='q', pai=n1.id)

    def test_pai_inexistente(self):
        with self.assertRaises(KeyError):
            _no(ArvoreDerivados(), pai='d99')


def arquivo_teste():
    t = np.linspace(0, 10, 101)
    df = pd.DataFrame({'t': t, 'p': np.sin(t), 'q': t ** 2})
    return Arquivo.criar_de_leitura('a.csv', df)


class TestArquivoDerivados(unittest.TestCase):

    def test_cadeia_de_operacoes(self):
        arq = arquivo_teste()
        s = arq.serie_de_origem('p', 't')
        r1 = am.executar_operacao('media_movel', s, {'n_pontos': 20, 'delta_x': 0.3})
        n1 = arq.registrar_derivado('media_movel', {'n_pontos': 20, 'delta_x': 0.3}, r1, 'p', 't')
        self.assertEqual(n1.nome, 'Média móvel p')

        s2 = arq.serie_de_origem('p', 't', n1.id)
        self.assertEqual(len(s2), len(r1.serie))
        r2 = am.executar_operacao('ajuste_polinomial', s2, {'grau': 3, 'n_pontos': 50})
        # O filho herda canal raiz e eixo X do pai, mesmo se o chamador mandar outros.
        n2 = arq.registrar_derivado('ajuste_polinomial', {'grau': 3, 'n_pontos': 50}, r2,
                                    'q', 'outro', pai=n1.id)
        self.assertEqual((n2.canal_raiz, n2.eixo_x), ('p', 't'))
        self.assertEqual(n2.nome, 'Polynomial Fit Média móvel p')
        # O df não ganhou coluna nenhuma: derivado não é canal.
        self.assertEqual(list(arq.df_editado.columns), ['t', 'p', 'q'])

    def test_corte_marca_cadeia_desatualizada(self):
        arq = arquivo_teste()
        r = am.downsampling(arq.serie_do_canal('p', 't'), 10)
        n1 = arq.registrar_derivado('downsampling', {'n_pontos': 10}, r, 'p', 't')
        self.assertFalse(arq.derivado_desatualizado(n1.id))
        arq.cortar_dados('t', 8, 2, modo='aparar')       # ordem dos cliques não importa
        self.assertEqual(arq.df_editado['t'].min(), 2)
        self.assertTrue(arq.derivado_desatualizado(n1.id))
        # Filho criado DEPOIS do corte, mas de um pai velho: também velho.
        n2 = arq.registrar_derivado('downsampling', {'n_pontos': 5},
                                    am.downsampling(n1.serie, 5), 'p', 't', pai=n1.id)
        self.assertTrue(arq.derivado_desatualizado(n2.id))
        # Nó novo direto do canal: em dia. O resultado antigo não mudou.
        n3 = arq.registrar_derivado('downsampling', {'n_pontos': 10},
                                    am.downsampling(arq.serie_do_canal('p', 't'), 10), 'p', 't')
        self.assertFalse(arq.derivado_desatualizado(n3.id))
        self.assertEqual(n1.serie.x[0], 0)

    def test_sobrescrever_so_afeta_quem_usa_a_coluna(self):
        arq = arquivo_teste()
        np_ = arq.registrar_derivado('downsampling', {}, am.downsampling(arq.serie_do_canal('p', 't'), 5), 'p', 't')
        nq = arq.registrar_derivado('downsampling', {}, am.downsampling(arq.serie_do_canal('q', 't'), 5), 'q', 't')
        arq.sobrescrever_canal_com_calculo('q', arq.df_editado['q'] * 2, 'q*2')
        self.assertFalse(arq.derivado_desatualizado(np_.id))
        self.assertTrue(arq.derivado_desatualizado(nq.id))

    def test_excluir_derivado(self):
        arq = arquivo_teste()
        r = am.downsampling(arq.serie_do_canal('p', 't'), 5)
        n1 = arq.registrar_derivado('downsampling', {}, r, 'p', 't')
        arq.registrar_derivado('downsampling', {}, r, 'p', 't', pai=n1.id)
        self.assertEqual(len(arq.excluir_derivado(n1.id)), 2)
        self.assertEqual(len(arq.arvore), 0)

    def test_arvores_independentes_por_arquivo(self):
        a, b = arquivo_teste(), arquivo_teste()
        a.registrar_derivado('downsampling', {}, am.downsampling(a.serie_do_canal('p', 't'), 5), 'p', 't')
        self.assertEqual(len(b.arvore), 0)


if __name__ == '__main__':
    unittest.main()
