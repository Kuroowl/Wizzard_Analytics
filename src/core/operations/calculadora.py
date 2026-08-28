"""
Vocabulário fixo de tokens da calculadora do modo 'Nova Análise' (ver
renderizar_calculadora_barra/renderizar_calculadora_botoes em
src/gui/renderizadores.py e a barra de cálculo dentro de
'#area-modo-nova-analise').

Cada token é um par (display, codigo):
  - display: o texto mostrado no BOTÃO e ecoado (como um "chip"
    colorido, não texto solto — ver renderizar_calculadora_barra) na
    barra de expressão quando clicado.
  - codigo: o fragmento de Python de VERDADE, concatenado com os
    outros tokens clicados e avaliado só na hora de 'Criar' (ver
    avaliar_expressao_calculadora logo abaixo) — 'np.' aqui sempre se
    refere a numpy, injetado explicitamente no namespace restrito da
    avaliação, nunca ao módulo importado neste arquivo.

Os tokens de COLUNA (um botão por canal visível do arquivo ativo) não
vivem aqui — são gerados dinamicamente por arquivo em
renderizar_calculadora_barra/_botoes, já que dependem de qual
arquivo/aba está ativa. Só o vocabulário FIXO (operadores, funções)
mora aqui.
"""

import numpy as np
import pandas as pd


NUMEROS = [
    # Grade estilo teclado numérico de calculadora de verdade (7-8-9 /
    # 4-5-6 / 1-2-3 / 0-.) — separado de OPERADORES (logo abaixo) de
    # propósito: os dois eram um grid só antes, misturando números e
    # símbolos sem distinção visual nenhuma. Ver '.calculadora-token-
    # numero' (fundo claro/neutro) em edit_menu.css.
    ('7', '7'), ('8', '8'), ('9', '9'),
    ('4', '4'), ('5', '5'), ('6', '6'),
    ('1', '1'), ('2', '2'), ('3', '3'),
    ('0', '0'), ('.', '.'),
]

OPERADORES = [
    # Símbolos/operadores — cor DIFERENTE de NUMEROS (ver
    # '.calculadora-token-operador', fundo âmbar, em edit_menu.css),
    # igual toda calculadora física separa visualmente a coluna de
    # operadores do teclado numérico.
    ('÷', '/'), ('×', '*'), ('−', '-'), ('+', '+'),
    ('(', '('), (')', ')'),
]

FUNCOES = [
    # Cada função abre parêntese sozinha — o usuário fecha com o ')' de
    # OPERADORES (mesmo espírito de digitar 'sin(' numa calculadora
    # científica de verdade: abre, digita/clica o argumento — um botão
    # de coluna, um número, ou uma sub-expressão inteira com operações
    # internas — e fecha).
    ('sin(', 'np.sin('),
    ('cos(', 'np.cos('),
    ('tan(', 'np.tan('),
    ('√(', 'np.sqrt('),
    ('log₁₀(', 'np.log10('),
    ('ln(', 'np.log('),
    ('exp(', 'np.exp('),
    ('abs(', 'np.abs('),
]

OPERACOES_RAPIDAS = [
    # Mudança de proposta: ANTES estas eram botões de AÇÃO IMEDIATA
    # (clicar computava na hora, sobre as colunas já clicadas na
    # expressão) — agora têm a MESMA forma/comportamento de sin(/cos(
    # acima: abrem parêntese, o usuário clica a coluna (ou uma
    # sub-expressão com operações internas) que quer usar como
    # argumento, e fecha o parêntese — viram FUNÇÕES de verdade dentro
    # da linguagem da expressão (ver Derivada/Integral/Media/Maximo/
    # Minimo, injetadas no namespace de avaliar_expressao_calculadora
    # logo abaixo), não mais um mecanismo à parte com resultado
    # "pendente".
    #
    # Símbolo auxiliar antes do nome (∂, ∫, x̄, ↑, ↓) — pedido
    # explícito, pra reconhecer o botão de relance sem precisar ler o
    # texto inteiro.
    ('∂ Derivada(', 'Derivada('),
    ('∫ Integral(', 'Integral('),
    ('x̄ Média(', 'Media('),
    ('↑ Máximo(', 'Maximo('),
    ('↓ Mínimo(', 'Minimo('),
]


def avaliar_expressao_calculadora(codigo, arquivo, estado):
    """
    Avalia 'codigo' (a concatenação dos 'codigo' de cada token
    clicado, ver 'calc-expressao-store' em layout.py) contra as
    colunas de 'arquivo.df_editado' e devolve uma pd.Series pronta
    pra virar uma coluna nova.

    'estado' (o EstadoApp global) é necessário agora porque
    Derivada()/Integral() (ver namespace_seguro abaixo) precisam saber
    qual é o eixo X do arquivo (resolver_eixo_x) — antes isso vivia só
    em 'aplicar_operacao_rapida', separado deste motor; as duas
    funções se fundiram numa só agora que Derivada/Integral também são
    funções de expressão, não mais um mecanismo à parte.

    FUNÇÕES INJETADAS (além de 'col'/'np', ver namespace_seguro):
      - Media(x)/Maximo(x)/Minimo(x): 'x' pode ser uma coluna
        (col['A']) OU uma sub-expressão inteira (col['A']+col['B']) —
        calcula o escalar (média/máximo/mínimo) e devolve um ARRAY DO
        MESMO TAMANHO do arquivo, com esse escalar repetido em toda
        linha. É de propósito: plotado, vira uma linha HORIZONTAL
        interceptando o valor calculado (ex: uma reta na altura do
        máximo de uma curva), não um número solto.
      - Derivada(x)/Integral(x): idem sobre o eixo X do arquivo
        (resolver_eixo_x) — derivada numérica (np.gradient) ou
        integral cumulativa (trapézio), ambas devolvendo um array do
        mesmo tamanho do arquivo.

    SEGURANÇA: 'codigo' só pode conter fragmentos que ESTE módulo
    definiu (NUMEROS/OPERADORES/FUNCOES/OPERACOES_RAPIDAS) mais
    'col["<nome_interno>"]' pros tokens de coluna (gerados em
    renderizar_calculadora_barra/_botoes com nome_interno passado por
    'repr()', não concatenação de string crua) — nunca texto livre
    digitado pelo usuário. Mesmo assim, o eval roda com
    '__builtins__' vazio (bloqueia 'import', 'open', 'exec' etc.) e só
    os nomes explicitamente listados em 'namespace_seguro', então
    mesmo um bug de token não vira uma porta pra executar código
    arbitrário.

    Levanta ValueError com uma mensagem amigável (pra virar mensagem
    do mago) se a expressão estiver vazia, malformada, ou não
    referenciar coluna nenhuma dando um resultado que não é uma
    Series/array do mesmo tamanho do df.
    """
    from src.core.plotting.plotter import resolver_eixo_x

    codigo = (codigo or '').strip()
    if not codigo:
        raise ValueError('a expressão está vazia.')

    df = arquivo.df_editado
    n_linhas = len(df)
    col = {nome: df[nome] for nome in df.columns}

    def _como_serie(valor):
        """Normaliza o argumento de Media/Maximo/Minimo/Derivada/
        Integral pra uma pd.Series alinhada ao índice do df — aceita
        tanto uma coluna direta (col['X']) quanto uma sub-expressão
        já resolvida pelo eval (col['X']+col['Y'], np.sin(col['X']),
        um escalar puro etc.)."""
        if isinstance(valor, pd.Series):
            return valor
        if np.isscalar(valor):
            return pd.Series([valor] * n_linhas, index=df.index)
        return pd.Series(valor, index=df.index)

    def Media(valor):
        serie = _como_serie(valor)
        return pd.Series(serie.mean(), index=df.index)

    def Maximo(valor):
        serie = _como_serie(valor)
        return pd.Series(serie.max(), index=df.index)

    def Minimo(valor):
        serie = _como_serie(valor)
        return pd.Series(serie.min(), index=df.index)

    def Derivada(valor):
        serie = _como_serie(valor)
        coluna_x = resolver_eixo_x(estado, df)
        x = df[coluna_x].to_numpy(dtype=float)
        y = serie.to_numpy(dtype=float)
        return pd.Series(np.gradient(y, x), index=df.index)

    def Integral(valor):
        # Trapézio cumulativo — mesmo espírito de
        # 'integral_coluna(..., retorno="cumulativa")' em
        # src/core/operations/math.py, só reimplementado aqui direto
        # em numpy porque opera sobre uma Series/sub-expressão
        # qualquer, não um NOME de coluna (a função de math.py só
        # aceita nomes de coluna, não uma expressão arbitrária já
        # calculada).
        serie = _como_serie(valor)
        coluna_x = resolver_eixo_x(estado, df)
        x = df[coluna_x].to_numpy(dtype=float)
        y = serie.to_numpy(dtype=float)
        if len(x) < 2:
            return pd.Series(np.zeros(n_linhas), index=df.index)
        area = np.concatenate(([0.0], np.cumsum(np.diff(x) * (y[:-1] + y[1:]) / 2.0)))
        return pd.Series(area, index=df.index)

    namespace_seguro = {
        'col': col, 'np': np,
        'Media': Media, 'Maximo': Maximo, 'Minimo': Minimo,
        'Derivada': Derivada, 'Integral': Integral,
    }

    try:
        resultado = eval(codigo, {'__builtins__': {}}, namespace_seguro)  # noqa: S307 — namespace restrito, ver docstring
    except ZeroDivisionError:
        raise ValueError('divisão por zero na expressão.')
    except Exception as e:
        raise ValueError(f'expressão inválida ({e}).')

    if np.isscalar(resultado) or isinstance(resultado, (int, float, np.number)):
        # Expressão sem coluna nenhuma (ex: '2+2') — permite, mas
        # espalha o mesmo valor em todas as linhas, pra virar uma
        # coluna de verdade (constante) em vez de recusar.
        resultado = pd.Series([resultado] * n_linhas, index=df.index)
    elif len(resultado) != n_linhas:
        raise ValueError('o resultado não tem o mesmo número de linhas do arquivo.')

    return resultado
