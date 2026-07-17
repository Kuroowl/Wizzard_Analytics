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


# ---------------------------------------------------------------------------
# Derivada e integral de uma coluna em relação a outra
# ---------------------------------------------------------------------------

def _detectar_lacunas(x, fator_limiar=5):
    """
    Identifica lacunas anormais no espaçamento de x: pontos onde o passo
    (dx) é muito maior que o típico do conjunto (ex: depois de um
    excluir_dados, que corta um trecho inteiro e deixa x saltar de 0.7 pra
    1.5 direto). Retorna os índices i tais que existe uma lacuna entre x[i]
    e x[i+1].

    fator_limiar: quantas vezes o dx mediano um passo precisa ser pra
    contar como lacuna (não como uma variação normal de amostragem).
    """
    dx = np.diff(x)
    mediana_dx = np.median(dx)
    if mediana_dx <= 0:
        return np.array([], dtype=int)
    return np.where(dx > fator_limiar * mediana_dx)[0]


def _validar_x_y(df, coluna_y, coluna_x, lacunas='avisar', fator_limiar_lacuna=5):
    """
    Validações de derivada/integral: colunas existem, são numéricas, x é
    crescente e sem repetição. Além disso, detecta lacunas anormais em x
    (ex: um trecho excluído dos dados) e trata conforme 'lacunas':
        'avisar'    -> avisa no console e segue calculando normalmente
                       (a lacuna é interpolada como se fosse um único passo)
        'erro'      -> levanta ValueError, obrigando a decisão explícita
        'segmentar' -> não trata aqui; sinaliza os índices de corte para
                       quem chamou (derivada_coluna/integral_coluna) tratar
                       cada trecho contínuo separadamente

    Retorna (x, y, indices_lacuna).
    """
    for c in (coluna_y, coluna_x):
        if c not in df.columns:
            raise KeyError(f"Coluna '{c}' não encontrada. Disponíveis: {list(df.columns)}")

    if len(df) < 2:
        raise ValueError("São necessários pelo menos 2 pontos para calcular derivada/integral.")

    if lacunas not in ('avisar', 'erro', 'segmentar'):
        raise ValueError("lacunas deve ser 'avisar', 'erro' ou 'segmentar'.")

    x = pd.to_numeric(df[coluna_x], errors='coerce')
    y = pd.to_numeric(df[coluna_y], errors='coerce')

    if x.isna().any() or y.isna().any():
        raise ValueError(
            f"'{coluna_x}' ou '{coluna_y}' contém valores não numéricos ou vazios. "
            "Trate esses valores antes de calcular derivada/integral."
        )

    if not x.is_monotonic_increasing:
        raise ValueError(
            f"A coluna '{coluna_x}' precisa estar ordenada de forma crescente para "
            "derivada/integral fazerem sentido. Ordene o DataFrame por essa coluna "
            "antes de aplicar a operação."
        )

    if x.duplicated().any():
        raise ValueError(
            f"A coluna '{coluna_x}' tem valores repetidos, o que geraria divisão "
            "por zero no cálculo (dois pontos no mesmo X). Remova ou agregue as "
            "duplicatas antes de calcular."
        )

    x_np, y_np = x.to_numpy(), y.to_numpy()
    indices_lacuna = _detectar_lacunas(x_np, fator_limiar_lacuna)

    if len(indices_lacuna) > 0:
        detalhes = ", ".join(
            f"entre x={x_np[i]:.4g} e x={x_np[i+1]:.4g}" for i in indices_lacuna
        )
        if lacunas == 'erro':
            raise ValueError(
                f"Detectada(s) lacuna(s) anormal(is) em '{coluna_x}' ({detalhes}). "
                "Isso costuma acontecer depois de um excluir_dados. Escolha "
                "lacunas='avisar' (interpola através do buraco) ou "
                "lacunas='segmentar' (calcula cada trecho contínuo separadamente)."
            )
        elif lacunas == 'avisar':
            print(
                f"Aviso: lacuna(s) detectada(s) em '{coluna_x}' ({detalhes}). "
                "O cálculo vai interpolar através do(s) buraco(s), o que pode "
                "não refletir o que aconteceria de fato nesse trecho excluído."
            )

    return x_np, y_np, indices_lacuna


def _segmentos(tamanho, indices_lacuna):
    """Divide range(tamanho) em blocos contínuos, cortando nos índices de lacuna."""
    cortes = sorted(indices_lacuna)
    inicio = 0
    for corte in cortes:
        yield inicio, corte + 1  # fim exclusivo
        inicio = corte + 1
    yield inicio, tamanho


def derivada_coluna(df, coluna_y, coluna_x, nome_saida=None, lacunas='avisar', fator_limiar_lacuna=5):
    """
    Calcula a derivada numérica de coluna_y em relação a coluna_x
    (d(coluna_y)/d(coluna_x)) por diferenças centrais (np.gradient), que
    lida corretamente com espaçamento não-uniforme em coluna_x — importante
    porque colunas como 'Tempo_decorrido_s' nem sempre têm passo constante.

    Parâmetros:
        nome_saida (str, opcional): nome da coluna de saída. Se None, usa
            'd{coluna_y}_d{coluna_x}'.
        lacunas (str): como tratar saltos anormais em coluna_x (ex: depois
            de um excluir_dados). 'avisar' (padrão) interpola através do
            buraco e avisa; 'erro' recusa calcular; 'segmentar' calcula a
            derivada de cada trecho contínuo separadamente, sem cruzar a
            lacuna (o primeiro ponto de cada trecho fica com derivada
            unilateral, calculada só com o vizinho seguinte).
    """
    x, y, indices_lacuna = _validar_x_y(df, coluna_y, coluna_x, lacunas, fator_limiar_lacuna)

    if df.empty:
        return df.copy()

    if lacunas == 'segmentar' and len(indices_lacuna) > 0:
        derivada = np.empty_like(y, dtype=float)
        for ini, fim in _segmentos(len(x), indices_lacuna):
            if fim - ini == 1:
                derivada[ini] = np.nan  # ponto isolado: derivada indefinida
            else:
                derivada[ini:fim] = np.gradient(y[ini:fim], x[ini:fim])
    else:
        derivada = np.gradient(y, x)

    destino = nome_saida if nome_saida else f'd{coluna_y}_d{coluna_x}'
    df_novo = df.copy()
    df_novo[destino] = derivada
    return df_novo.reset_index(drop=True)


def integral_coluna(df, coluna_y, coluna_x, nome_saida=None, retorno='cumulativa',
                     lacunas='avisar', fator_limiar_lacuna=5):
    """
    Calcula a integral numérica de coluna_y em relação a coluna_x pela regra
    do trapézio.

    Parâmetros:
        retorno='cumulativa' (padrão): adiciona coluna nova com a integral
            ACUMULADA até cada ponto — útil pra plotar junto com os dados.
            Devolve um DataFrame, como as outras funções do módulo.
        retorno='total': devolve só o valor ESCALAR da integral no
            intervalo inteiro (float, não DataFrame).
        nome_saida (str, opcional): nome da coluna de saída (só usado em
            retorno='cumulativa'). Se None, usa 'integral_{coluna_y}_d{coluna_x}'.
        lacunas (str): como tratar saltos anormais em coluna_x (ex: depois
            de um excluir_dados). 'avisar' (padrão) interpola através do
            buraco como se fosse um único passo, e avisa; 'erro' recusa
            calcular; 'segmentar' calcula a área de cada trecho contínuo
            separadamente, SEM somar nenhuma área durante a lacuna — ou
            seja, assume que a grandeza não varia no trecho excluído. Se a
            grandeza de fato continuou variando ali (só não foi registrada),
            'segmentar' vai subestimar a integral; use 'avisar' se preferir
            assumir uma interpolação linear através do buraco.
    """
    if retorno not in ('cumulativa', 'total'):
        raise ValueError("retorno deve ser 'cumulativa' ou 'total'.")

    x, y, indices_lacuna = _validar_x_y(df, coluna_y, coluna_x, lacunas, fator_limiar_lacuna)

    if lacunas == 'segmentar' and len(indices_lacuna) > 0:
        integral_acumulada = np.empty_like(y, dtype=float)
        offset = 0.0
        for ini, fim in _segmentos(len(x), indices_lacuna):
            if fim - ini == 1:
                integral_acumulada[ini] = offset  # ponto isolado: nada a integrar
            else:
                dx_seg = np.diff(x[ini:fim])
                trapezios_seg = dx_seg * (y[ini:fim][:-1] + y[ini:fim][1:]) / 2.0
                integral_acumulada[ini:fim] = offset + np.concatenate(([0.0], np.cumsum(trapezios_seg)))
                offset = integral_acumulada[fim - 1]

        if retorno == 'total':
            return float(integral_acumulada[-1])

        destino = nome_saida if nome_saida else f'integral_{coluna_y}_d{coluna_x}'
        df_novo = df.copy()
        df_novo[destino] = integral_acumulada
        return df_novo.reset_index(drop=True)

    # sem segmentação: regra do trapézio direto, interpolando eventuais lacunas
    dx = np.diff(x)
    trapezios = dx * (y[:-1] + y[1:]) / 2.0

    if retorno == 'total':
        return float(np.sum(trapezios))

    if df.empty:
        return df.copy()

    integral_acumulada = np.concatenate(([0.0], np.cumsum(trapezios)))

    destino = nome_saida if nome_saida else f'integral_{coluna_y}_d{coluna_x}'
    df_novo = df.copy()
    df_novo[destino] = integral_acumulada
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

    # --- derivada e integral: teste com y = x^2, onde já sabemos a resposta ---
    # derivada esperada: dy/dx = 2x | integral esperada: x^3/3
    x_vals = np.linspace(0, 10, 1000)
    df_curva = pd.DataFrame({'x': x_vals, 'y': x_vals ** 2})

    print("\n--- derivada de y=x^2 em relação a x (esperado: ~2x) ---")
    df_deriv = derivada_coluna(df_curva, 'y', 'x')
    print(df_deriv[['x', 'y', 'dy_dx']].iloc[[0, 500, 999]])
    print("comparação com 2x nesses pontos:", 2 * df_curva['x'].iloc[[0, 500, 999]].to_numpy())

    print("\n--- integral cumulativa de y=x^2 em relação a x (esperado: ~x^3/3) ---")
    df_int = integral_coluna(df_curva, 'y', 'x')
    print(df_int[['x', 'y', 'integral_y_dx']].iloc[[0, 500, 999]])
    print("comparação com x^3/3 nesses pontos:", (df_curva['x'].iloc[[0, 500, 999]] ** 3 / 3).to_numpy())

    print("\n--- integral total (escalar) de y=x^2 de 0 a 10 (esperado: 1000/3 ≈ 333.33) ---")
    print(integral_coluna(df_curva, 'y', 'x', retorno='total'))

    print("\n--- x não-crescente: deve dar erro claro ---")
    df_bagunçado = pd.DataFrame({'x': [0, 2, 1, 3], 'y': [0, 4, 1, 9]})
    try:
        derivada_coluna(df_bagunçado, 'y', 'x')
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    print("\n--- x com valores repetidos: deve dar erro claro ---")
    df_duplicado = pd.DataFrame({'x': [0, 1, 1, 2], 'y': [0, 1, 1, 4]})
    try:
        derivada_coluna(df_duplicado, 'y', 'x')
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    # --- cenário do excluir_dados: tempos 0.5,0.6,0.7 seguidos de 1.5,1.6,1.7 ---
    df_lacuna = pd.DataFrame({
        'tempo': [0.5, 0.6, 0.7, 1.5, 1.6, 1.7],
        'valor': [5.0, 6.0, 7.0, 15.0, 16.0, 17.0],
    })

    print("\n--- lacunas='avisar' (padrão): interpola através do buraco, mas avisa ---")
    df_r = derivada_coluna(df_lacuna, 'valor', 'tempo')
    print(df_r)

    print("\n--- lacunas='erro': recusa calcular ---")
    try:
        derivada_coluna(df_lacuna, 'valor', 'tempo', lacunas='erro')
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    print("\n--- lacunas='segmentar': calcula cada trecho separadamente ---")
    df_r = derivada_coluna(df_lacuna, 'valor', 'tempo', lacunas='segmentar')
    print(df_r)
    print("(repare: o primeiro ponto do 2º trecho, índice 3, não usa mais o dx gigante de 0.8)")

    print("\n--- integral cumulativa com lacunas='segmentar' ---")
    df_r = integral_coluna(df_lacuna, 'valor', 'tempo', lacunas='segmentar')
    print(df_r)
    print("(a integral não soma nenhuma área durante o buraco entre 0.7 e 1.5)")
