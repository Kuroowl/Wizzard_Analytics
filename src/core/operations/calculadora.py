"""
Vocabulário fixo de tokens da calculadora do modo 'Nova Análise' (ver
renderizar_calculadora em src/gui/renderizadores.py e a barra de
cálculo dentro de '#area-modo-nova-analise').

Cada token é um par (display, codigo):
  - display: o texto mostrado no BOTÃO e ecoado na barra de expressão
    quando clicado.
  - codigo: o fragmento de Python de VERDADE, concatenado com os
    outros tokens clicados e avaliado só na hora de 'Criar' (ver
    avaliar_expressao_calculadora logo abaixo) — 'np.' aqui sempre se
    refere a numpy, injetado explicitamente no namespace restrito da
    avaliação, nunca ao módulo importado neste arquivo.

Os tokens de COLUNA (um botão por canal visível do arquivo ativo) não
vivem aqui — são gerados dinamicamente por arquivo em
renderizar_calculadora, já que dependem de qual arquivo/aba está
ativa. Só o vocabulário FIXO (operadores, funções, atalhos) mora
aqui.
"""

import numpy as np


OPERADORES_BASICOS = [
    ('7', '7'), ('8', '8'), ('9', '9'), ('÷', '/'),
    ('4', '4'), ('5', '5'), ('6', '6'), ('×', '*'),
    ('1', '1'), ('2', '2'), ('3', '3'), ('−', '-'),
    ('0', '0'), ('.', '.'), ('(', '('), (')', ')'),
    ('+', '+'),
]

FUNCOES = [
    # Cada função abre parêntese sozinha — o usuário fecha com o ')' de
    # 'Operações básicas' (mesmo espírito de digitar 'sin(' numa
    # calculadora científica de verdade: abre, digita/clica o
    # argumento, fecha).
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
    # Encadeáveis DEPOIS de um número/coluna/fecha-parêntese já
    # digitado — mesmo espírito das teclas 'x²'/'%' de uma calculadora
    # física, que operam sobre o valor já mostrado, sem abrir
    # parêntese novo.
    ('x²', '**2'),
    ('x³', '**3'),
    ('%', '/100'),
    ('π', 'np.pi'),
    ('e', 'np.e'),
]


def avaliar_expressao_calculadora(codigo, arquivo):
    """
    Avalia 'codigo' (a concatenação dos 'codigo' de cada token
    clicado, ver 'calc-expressao-store' em layout.py) contra as
    colunas de 'arquivo.df_editado' e devolve uma pd.Series pronta
    pra virar uma coluna nova.

    SEGURANÇA: 'codigo' só pode conter fragmentos que ESTE módulo
    definiu (OPERADORES_BASICOS/FUNCOES/OPERACOES_RAPIDAS) mais
    'col["<nome_interno>"]' pros tokens de coluna (gerados em
    renderizar_calculadora com nome_interno passado por 'repr()`, não
    concatenação de string crua — ver lá) — nunca texto livre digitado
    pelo usuário. Mesmo assim, o eval roda com '__builtins__' vazio
    (bloqueia 'import', 'open', 'exec' etc.) e só 'col'/'np' no
    namespace, então mesmo um bug de token não vira uma porta pra
    executar código arbitrário.

    Levanta ValueError com uma mensagem amigável (pra virar mensagem
    do mago) se a expressão estiver vazia, malformada, ou não
    referenciar coluna nenhuma dando um resultado que não é uma
    Series/array do mesmo tamanho do df.
    """
    codigo = (codigo or '').strip()
    if not codigo:
        raise ValueError('a expressão está vazia.')

    col = {nome: arquivo.df_editado[nome] for nome in arquivo.df_editado.columns}
    namespace_seguro = {'col': col, 'np': np}

    try:
        resultado = eval(codigo, {'__builtins__': {}}, namespace_seguro)  # noqa: S307 — namespace restrito, ver docstring
    except ZeroDivisionError:
        raise ValueError('divisão por zero na expressão.')
    except Exception as e:
        raise ValueError(f'expressão inválida ({e}).')

    n_linhas = len(arquivo.df_editado)
    if np.isscalar(resultado) or isinstance(resultado, (int, float, np.number)):
        # Expressão sem coluna nenhuma (ex: '2+2') — permite, mas
        # espalha o mesmo valor em todas as linhas, pra virar uma
        # coluna de verdade (constante) em vez de recusar.
        import pandas as pd
        resultado = pd.Series([resultado] * n_linhas, index=arquivo.df_editado.index)
    elif len(resultado) != n_linhas:
        raise ValueError('o resultado não tem o mesmo número de linhas do arquivo.')

    return resultado
