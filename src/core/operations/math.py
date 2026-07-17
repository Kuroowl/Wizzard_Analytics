import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Operações entre uma coluna e uma constante (calibração, ganho, tara, etc.)
# ---------------------------------------------------------------------------

OPERACOES_CONSTANTE = {
    'somar':       lambda serie, k: serie + k,
    'subtrair':    lambda serie, k: serie - k,
    'multiplicar': lambda serie, k: serie * k,
    'dividir':     lambda serie, k: serie / k,
    'elevar':      lambda serie, k: serie ** k,
}


def aplicar_operacao_constante(df, coluna, constante, operacao, nome_saida=None):
    """
    Aplica uma operação matemática entre uma coluna e uma constante:
    soma, subtração, multiplicação, divisão ou potência.

    Substitui multiplicar_por_constante / dividir_por_constante /
    somar_constante / subtrair_constante / elevar_por_constante — mesma
    lógica, um parâmetro 'operacao' em vez de cinco funções quase iguais.

    Parâmetros:
        df (pd.DataFrame): tabela de dados original.
        coluna (str): coluna numérica de entrada.
        constante (float): valor a somar/subtrair/multiplicar/dividir/elevar.
        operacao (str): uma de 'somar', 'subtrair', 'multiplicar', 'dividir', 'elevar'.
        nome_saida (str, opcional): se None, SOBRESCREVE 'coluna' (ex: tara,
            calibração, inversão de sinal). Se informado, cria uma coluna
            nova com esse nome e preserva a original — útil quando a
            interface quiser comparar antes/depois.
    """
    if coluna not in df.columns:
        raise KeyError(f"Coluna '{coluna}' não encontrada. Colunas disponíveis: {list(df.columns)}")

    if operacao not in OPERACOES_CONSTANTE:
        raise ValueError(f"Operação '{operacao}' inválida. Use uma de: {list(OPERACOES_CONSTANTE)}")

    if operacao == 'dividir' and constante == 0:
        raise ValueError("Impossível dividir por zero.")

    if df.empty:
        return df.copy()

    df_novo = df.copy()
    serie = pd.to_numeric(df_novo[coluna], errors='coerce')
    resultado = OPERACOES_CONSTANTE[operacao](serie, constante)

    destino = nome_saida if nome_saida else coluna
    df_novo[destino] = resultado
    return df_novo.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Operações entre colunas (soma, média, produto, máximo, mínimo, razão...)
# ---------------------------------------------------------------------------

def _soma(mat):
    return mat.sum(axis=1, skipna=False)

def _media(mat):
    return mat.mean(axis=1, skipna=False)

def _produto(mat):
    return mat.prod(axis=1, skipna=False)

def _maximo(mat):
    return mat.max(axis=1, skipna=False)

def _minimo(mat):
    return mat.min(axis=1, skipna=False)

def _diferenca(mat):
    # primeira coluna menos a soma das demais (ex: A - B - C)
    return mat.iloc[:, 0] - mat.iloc[:, 1:].sum(axis=1, skipna=False)

def _razao(mat):
    if (mat.iloc[:, 1] == 0).any():
        raise ValueError(
            "A coluna do denominador contém zero em pelo menos uma linha — "
            "a divisão geraria infinito. Trate esses valores antes de dividir."
        )
    return mat.iloc[:, 0] / mat.iloc[:, 1]


OPERACOES_COLUNAS = {
    'soma': _soma,
    'media': _media,
    'produto': _produto,
    'maximo': _maximo,
    'minimo': _minimo,
    'diferenca': _diferenca,  # requer exatamente 2+ colunas
    'razao': _razao,          # requer exatamente 2 colunas
}

# operações que exigem exatamente 2 colunas (não fazem sentido com 3+)
OPERACOES_DUAS_COLUNAS = {'diferenca', 'razao'}


def combinar_colunas(df, colunas, nova_coluna, operacao='soma'):
    """
    Combina duas ou mais colunas numéricas numa nova coluna.

    Cobre soma, média, produto, máximo, mínimo, diferença e razão — todas
    com a mesma função, então "média entre duas colunas" é só
    combinar_colunas(df, ['P1', 'P2'], 'media_p1_p2', operacao='media'),
    sem precisar de uma função nova pra cada combinação.

    Parâmetros:
        df (pd.DataFrame): tabela de dados original.
        colunas (list[str]): lista de 2+ colunas numéricas a combinar.
        nova_coluna (str): nome da coluna de saída.
        operacao (str): uma de 'soma', 'media', 'produto', 'maximo',
            'minimo', 'diferenca', 'razao'.
    """
    if operacao not in OPERACOES_COLUNAS:
        raise ValueError(f"Operação '{operacao}' inválida. Use uma de: {list(OPERACOES_COLUNAS)}")

    if not isinstance(colunas, (list, tuple)) or len(colunas) < 2:
        raise ValueError("Informe uma lista com pelo menos 2 colunas.")

    if operacao in OPERACOES_DUAS_COLUNAS and len(colunas) != 2:
        raise ValueError(f"A operação '{operacao}' aceita exatamente 2 colunas, recebi {len(colunas)}.")

    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise KeyError(f"Coluna(s) não encontrada(s): {faltando}. Disponíveis: {list(df.columns)}")

    if df.empty:
        return df.copy()

    df_novo = df.copy()
    matriz = df_novo[colunas].apply(pd.to_numeric, errors='coerce')

    df_novo[nova_coluna] = OPERACOES_COLUNAS[operacao](matriz)
    return df_novo.reset_index(drop=True)


if __name__ == '__main__':
    df_teste = pd.DataFrame({
        'P1': [1.0, 2.0, 3.0],
        'P2': [4.0, 5.0, 6.0],
        'P3': [0.0, 1.0, 2.0],
    })

    print("--- calibração: multiplicar P1 por 2, sobrescrevendo ---")
    print(aplicar_operacao_constante(df_teste, 'P1', 2, 'multiplicar'))

    print("\n--- ganho: multiplicar P1 por 2, em coluna nova ---")
    print(aplicar_operacao_constante(df_teste, 'P1', 2, 'multiplicar', nome_saida='P1_calibrado'))

    print("\n--- tara: subtrair 1 de P1, em coluna nova ---")
    print(aplicar_operacao_constante(df_teste, 'P1', 1, 'subtrair', nome_saida='P1_tarado'))

    print("\n--- média entre P1 e P2 (sem função nova) ---")
    print(combinar_colunas(df_teste, ['P1', 'P2'], 'media_p1_p2', operacao='media'))

    print("\n--- soma entre P1, P2 e P3 ---")
    print(combinar_colunas(df_teste, ['P1', 'P2', 'P3'], 'soma_total', operacao='soma'))

    print("\n--- razão com zero no denominador: deve dar erro claro ---")
    try:
        combinar_colunas(df_teste, ['P1', 'P3'], 'razao_p1_p3', operacao='razao')
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    print("\n--- divisão por zero (constante): deve dar erro claro ---")
    try:
        aplicar_operacao_constante(df_teste, 'P1', 0, 'dividir')
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")
