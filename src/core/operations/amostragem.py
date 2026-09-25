"""
Operações da Nova Amostragem: recebem uma Serie (x, y) e devolvem um
ResultadoAmostragem (uma Serie nova + informações do resultado).

São funções puras, sem Dash e sem Arquivo: quem decide DE ONDE vem a
série (canal do gráfico ou nó da árvore) e ONDE o resultado vai parar
(preview, árvore, canal) é o chamador.

    resultado = executar_operacao('media_movel', serie, {'n_pontos': 100, 'delta_x': 0.5})
    resultado.serie.x, resultado.serie.y, resultado.serie.sigma, resultado.info

Toda operação espera a série ORDENADA por x (Serie.de_colunas já entrega
assim) e sem NaN.
"""

from dataclasses import dataclass, field

import numpy as np

from src.core.derivados import Serie


@dataclass(frozen=True)
class ResultadoAmostragem:
    serie: Serie
    info: dict = field(default_factory=dict)


def _exigir_pontos(serie: Serie, minimo: int, operacao: str):
    if len(serie) < minimo:
        raise ValueError(
            f'{operacao} precisa de pelo menos {minimo} ponto(s) válido(s); '
            f'a série tem {len(serie)}.')


def _inteiro_positivo(valor, nome: str, minimo: int = 1) -> int:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        numero = float('nan')
    if not np.isfinite(numero) or not numero.is_integer():
        raise ValueError(f'{nome} precisa ser um número inteiro.')
    inteiro = int(numero)
    if inteiro < minimo:
        raise ValueError(f'{nome} precisa ser pelo menos {minimo}.')
    return inteiro


# ============================================================================
# 2.1 Downsampling
# ============================================================================

def downsampling(serie: Serie, n_pontos) -> ResultadoAmostragem:
    """
    Escolhe até 'n_pontos' pontos QUE JÁ EXISTEM na série, espalhados de
    forma aproximadamente uniforme em x: para cada alvo de um linspace
    entre x mínimo e x máximo, pega o ponto de x mais próximo (empate: o
    da esquerda). Nada é interpolado.

    Onde a aquisição é esparsa, dois alvos podem cair no mesmo ponto; o
    repetido é descartado, então o resultado pode ter MENOS que n_pontos
    (info['n_obtido']). Se n_pontos >= tamanho da série, devolve a série
    inteira.
    """
    n_pontos = _inteiro_positivo(n_pontos, 'A quantidade de pontos')
    _exigir_pontos(serie, 1, 'O downsampling')
    x, y = serie.x, serie.y

    if n_pontos >= len(x):
        indices = np.arange(len(x))
    else:
        alvos = np.linspace(x[0], x[-1], n_pontos)
        direita = np.clip(np.searchsorted(x, alvos, side='left'), 0, len(x) - 1)
        esquerda = np.clip(direita - 1, 0, len(x) - 1)
        usa_esquerda = np.abs(alvos - x[esquerda]) <= np.abs(x[direita] - alvos)
        indices = np.unique(np.where(usa_esquerda, esquerda, direita))

    return ResultadoAmostragem(
        Serie(x[indices], y[indices]),
        {'n_pedido': n_pontos, 'n_obtido': int(len(indices)), 'n_origem': int(len(x))},
    )


# ============================================================================
# 2.2 Média móvel
# ============================================================================

def media_movel(serie: Serie, n_pontos, delta_x) -> ResultadoAmostragem:
    """
    'n_pontos' subpontos x_i uniformes entre x mínimo e x máximo. Para cada
    um, a janela x_i - Δx <= x <= x_i + Δx: o resultado é a média dos y
    dentro dela, com o desvio padrão (populacional) desses y em 'sigma'.

    Bordas: a janela é TRUNCADA — perto dos extremos ela usa só os pontos
    que existem (menos pontos na média, sem inventar dados).
    Janelas sem nenhum ponto (buraco nos dados maior que 2Δx) são
    descartadas; quantas foram fica em info['janelas_vazias'].
    """
    n_pontos = _inteiro_positivo(n_pontos, 'A quantidade de pontos')
    try:
        delta_x = float(delta_x)
    except (TypeError, ValueError):
        raise ValueError('Δx precisa ser um número.') from None
    if not np.isfinite(delta_x) or delta_x <= 0:
        raise ValueError('Δx precisa ser maior que zero.')
    _exigir_pontos(serie, 1, 'A média móvel')
    x, y = serie.x, serie.y

    centros = np.linspace(x[0], x[-1], n_pontos)
    inicio = np.searchsorted(x, centros - delta_x, side='left')
    fim = np.searchsorted(x, centros + delta_x, side='right')

    medias, desvios, contagens, centros_validos = [], [], [], []
    for centro, a, b in zip(centros, inicio, fim):
        if b <= a:
            continue
        janela = y[a:b]
        centros_validos.append(centro)
        medias.append(janela.mean())
        desvios.append(janela.std())
        contagens.append(b - a)

    if not medias:
        raise ValueError('Nenhuma janela tem pontos. Aumente o Δx.')

    contagens = np.asarray(contagens)
    return ResultadoAmostragem(
        Serie(centros_validos, medias, sigma=desvios),
        {
            'n_pedido': n_pontos,
            'n_obtido': int(len(medias)),
            'janelas_vazias': int(n_pontos - len(medias)),
            'pontos_por_janela_min': int(contagens.min()),
            'pontos_por_janela_max': int(contagens.max()),
            'pontos_por_janela_media': float(contagens.mean()),
        },
    )


def delta_x_sugerido(serie: Serie, n_pontos) -> float:
    """
    Δx que faz as janelas encostarem uma na outra sem sobrepor: metade do
    espaçamento entre subpontos. Só um valor inicial pro campo do painel.
    """
    n_pontos = max(int(n_pontos), 2)
    if len(serie) < 2 or serie.x[-1] == serie.x[0]:
        return 1.0
    return float((serie.x[-1] - serie.x[0]) / (2 * (n_pontos - 1)))


# ============================================================================
# 2.3 Polynomial fit
# ============================================================================

GRAUS_POLINOMIO = (1, 2, 3)


def _r2(y, y_ajustado) -> float:
    ss_res = float(np.sum((y - y_ajustado) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - ss_res / ss_tot


def _equacao(coeficientes) -> str:
    """'y = 2·x² − 0.5·x + 1' a partir dos coeficientes (maior grau primeiro)."""
    grau = len(coeficientes) - 1
    termos = []
    for potencia, c in zip(range(grau, -1, -1), coeficientes):
        valor = f'{abs(c):.6g}'
        if potencia == 0:
            termo = valor
        elif potencia == 1:
            termo = f'{valor}·x'
        else:
            termo = f'{valor}·x{"²³"[potencia - 2] if potencia <= 3 else "^" + str(potencia)}'
        sinal = '−' if c < 0 else '+'
        termos.append((sinal, termo))
    primeiro_sinal, primeiro = termos[0]
    texto = ('−' if primeiro_sinal == '−' else '') + primeiro
    for sinal, termo in termos[1:]:
        texto += f' {sinal} {termo}'
    return f'y = {texto}'


def ajuste_polinomial(serie: Serie, grau, n_pontos) -> ResultadoAmostragem:
    """
    Ajusta y = c_n·x^n + ... + c_0 (grau 1, 2 ou 3) por mínimos quadrados
    e devolve a curva em 'n_pontos' pontos uniformes entre x mínimo e
    máximo dos dados.

    O ajuste é feito numa escala normalizada de x (numpy Polynomial.fit),
    o que evita perder precisão quando x é grande (ex: tempo em segundos
    desde 1970); os coeficientes devolvidos são os do x ORIGINAL.

    info: 'coeficientes' (maior grau primeiro, como np.polyfit),
          'equacao', 'r2', 'n_origem'.
    """
    grau = _inteiro_positivo(grau, 'O grau')
    if grau not in GRAUS_POLINOMIO:
        raise ValueError(f'O grau precisa ser {", ".join(map(str, GRAUS_POLINOMIO))}.')
    n_pontos = _inteiro_positivo(n_pontos, 'A quantidade de pontos da curva', minimo=2)
    x, y = serie.x, serie.y
    if len(np.unique(x)) < grau + 1:
        raise ValueError(
            f'Um polinômio de grau {grau} precisa de pelo menos {grau + 1} valores '
            f'diferentes de x; a série tem {len(np.unique(x))}.')

    polinomio = np.polynomial.Polynomial.fit(x, y, grau)
    coeficientes = polinomio.convert().coef[::-1]           # maior grau primeiro
    coeficientes = np.pad(coeficientes, (grau + 1 - len(coeficientes), 0))  # convert() corta zeros à direita

    x_curva = np.linspace(x[0], x[-1], n_pontos)
    return ResultadoAmostragem(
        Serie(x_curva, polinomio(x_curva)),
        {
            'grau': grau,
            'coeficientes': [float(c) for c in coeficientes],
            'equacao': _equacao(coeficientes),
            'r2': _r2(y, polinomio(x)),
            'n_origem': int(len(x)),
        },
    )


# ============================================================================
# Catálogo (o que a barra de operações oferece)
# ============================================================================

@dataclass(frozen=True)
class Operacao:
    chave: str
    rotulo: str          # nome na barra e no nome automático do nó
    funcao: object
    parametros_padrao: dict


OPERACOES = {
    op.chave: op for op in (
        Operacao('downsampling', 'Downsampling', downsampling, {'n_pontos': 500}),
        Operacao('media_movel', 'Média móvel', media_movel, {'n_pontos': 100, 'delta_x': None}),
        Operacao('ajuste_polinomial', 'Polynomial Fit', ajuste_polinomial, {'grau': 1, 'n_pontos': 200}),
    )
}


def operacao(chave: str) -> Operacao:
    try:
        return OPERACOES[chave]
    except KeyError:
        raise ValueError(f'Operação desconhecida: {chave!r}.') from None


def parametros_iniciais(chave: str, serie: Serie) -> dict:
    """Parâmetros padrão da operação, com os que dependem dos dados já preenchidos."""
    parametros = dict(operacao(chave).parametros_padrao)
    if chave == 'media_movel' and parametros.get('delta_x') is None:
        parametros['delta_x'] = delta_x_sugerido(serie, parametros['n_pontos'])
    return parametros


def executar_operacao(chave: str, serie: Serie, parametros: dict) -> ResultadoAmostragem:
    """Roda a operação 'chave' sobre 'serie'. Erros de parâmetro/dados: ValueError com texto pro usuário."""
    op = operacao(chave)
    faltando = [p for p in op.parametros_padrao if parametros.get(p) is None]
    if faltando:
        raise ValueError(f'Preencha: {", ".join(faltando)}.')
    argumentos = {p: parametros[p] for p in op.parametros_padrao}
    return op.funcao(serie, **argumentos)


def nome_padrao(chave: str, rotulo_origem: str) -> str:
    """'Downsampling Pressão', 'Média móvel Pressão'..."""
    return f'{operacao(chave).rotulo} {rotulo_origem}'
