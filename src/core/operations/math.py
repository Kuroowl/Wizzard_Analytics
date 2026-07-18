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

def _desvio_padrao(mat):
    return mat.std(axis=1, skipna=False)  # ddof=1 (amostral), padrão do pandas


OPERACOES_COLUNAS = {
    'soma': _soma,
    'media': _media,
    'produto': _produto,
    'maximo': _maximo,
    'minimo': _minimo,
    'diferenca': _diferenca,     # requer exatamente 2+ colunas
    'razao': _razao,             # requer exatamente 2 colunas
    'desvio_padrao': _desvio_padrao,
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
            'minimo', 'diferenca', 'razao', 'desvio_padrao'.
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


def media_e_desvio_colunas(df, colunas, nome_media=None, nome_desvio=None, ddof=1):
    """
    Calcula, linha a linha, a média e o desvio padrão entre 2+ colunas
    numéricas, adicionando as DUAS colunas de uma vez — útil pra medidas
    redundantes (ex: vários sensores de pressão no mesmo ponto), onde você
    quer o valor médio e a dispersão/incerteza entre eles juntos.

    Equivale a chamar combinar_colunas(..., operacao='media') e
    combinar_colunas(..., operacao='desvio_padrao') separadamente, mas
    calcula a conversão numérica das colunas uma única vez em vez de duas.

    Parâmetros:
        df (pd.DataFrame): tabela de dados original.
        colunas (list[str]): lista de 2+ colunas numéricas a combinar.
        nome_media (str, opcional): nome da coluna de média. Se None, usa
            'media_' + nomes das colunas (ex: 'media_P1_P2').
        nome_desvio (str, opcional): nome da coluna de desvio padrão. Se
            None, usa 'desvio_padrao_' + nomes das colunas.
        ddof (int): graus de liberdade do desvio padrão. Padrão ddof=1
            (amostral, mesmo padrão do pandas .std()). Use ddof=0 pro
            desvio padrão populacional.

    Retorna o DataFrame original com as duas colunas novas adicionadas.
    """
    if not isinstance(colunas, (list, tuple)) or len(colunas) < 2:
        raise ValueError("Informe uma lista com pelo menos 2 colunas.")

    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise KeyError(f"Coluna(s) não encontrada(s): {faltando}. Disponíveis: {list(df.columns)}")

    if df.empty:
        return df.copy()

    df_novo = df.copy()
    matriz = df_novo[colunas].apply(pd.to_numeric, errors='coerce')

    sufixo = '_'.join(colunas)
    destino_media = nome_media if nome_media else f'media_{sufixo}'
    destino_desvio = nome_desvio if nome_desvio else f'desvio_padrao_{sufixo}'

    df_novo[destino_media] = matriz.mean(axis=1, skipna=False)
    df_novo[destino_desvio] = matriz.std(axis=1, ddof=ddof, skipna=False)

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


# ===========================================================================
# Ajustes de curva (fits): reta, polinômio genérico, e curvas não-lineares
# ===========================================================================

from scipy.optimize import curve_fit


def _validar_x_y_ajuste(df, coluna_x, coluna_y, n_parametros_minimo=2):
    """
    Validação comum aos ajustes: colunas existem, são numéricas, sem NaN,
    e há pontos suficientes pra estimar os parâmetros pedidos (ex: reta
    precisa de pelo menos 2 pontos, uma cúbica de pelo menos 4).
    """
    for c in (coluna_x, coluna_y):
        if c not in df.columns:
            raise KeyError(f"Coluna '{c}' não encontrada. Disponíveis: {list(df.columns)}")

    x = pd.to_numeric(df[coluna_x], errors='coerce')
    y = pd.to_numeric(df[coluna_y], errors='coerce')

    mascara_valida = x.notna() & y.notna()
    if mascara_valida.sum() < n_parametros_minimo:
        raise ValueError(
            f"São necessários pelo menos {n_parametros_minimo} pontos válidos "
            f"para este ajuste; encontrei {mascara_valida.sum()}."
        )

    return x[mascara_valida].to_numpy(), y[mascara_valida].to_numpy()


def _r2(y_real, y_previsto):
    """R² = 1 - (soma dos resíduos ao quadrado) / (variância total dos dados)."""
    ss_res = np.sum((y_real - y_previsto) ** 2)
    ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# Ajuste polinomial (a reta é o caso particular de grau 1)
# ---------------------------------------------------------------------------

def ajuste_polinomial(df, coluna_x, coluna_y, grau=1):
    """
    Ajusta um polinômio de grau arbitrário (y = c0*x^n + c1*x^(n-1) + ... + cn)
    aos dados por mínimos quadrados.

    Retorna um dict com os coeficientes, o R² do ajuste, e uma função
    'prever' pronta pra gerar a curva ajustada em qualquer x (útil pra
    plotar por cima dos dados: x_curva = linspace(...); y_curva =
    resultado['prever'](x_curva)).
    """
    if grau < 1:
        raise ValueError("grau precisa ser 1 ou maior.")

    x, y = _validar_x_y_ajuste(df, coluna_x, coluna_y, n_parametros_minimo=grau + 1)

    coeficientes = np.polyfit(x, y, grau)
    polinomio = np.poly1d(coeficientes)
    r2 = _r2(y, polinomio(x))

    return {
        'grau': grau,
        'coeficientes': coeficientes.tolist(),  # do maior grau pro menor, como np.polyfit devolve
        'equacao': str(polinomio).strip(),
        'r2': float(r2),
        'prever': polinomio,  # np.poly1d é "chamável": polinomio(x_novo) -> y_novo
    }


def ajuste_linear(df, coluna_x, coluna_y):
    """
    Caso particular de ajuste_polinomial com grau=1 (y = a*x + b). Além do
    que ajuste_polinomial já devolve, nomeia os coeficientes pra ficar mais
    direto de ler na interface, sem precisar interpretar a ordem do array.
    """
    resultado = ajuste_polinomial(df, coluna_x, coluna_y, grau=1)
    resultado['coeficiente_angular'] = resultado['coeficientes'][0]  # 'a' (inclinação)
    resultado['coeficiente_linear'] = resultado['coeficientes'][1]   # 'b' (intercepto)
    return resultado


# ---------------------------------------------------------------------------
# Ajuste de curva genérica — o "motor" fica pronto; a UI decide como o
# usuário informa a curva. Já vem com modelos comuns prontos pra uso.
# ---------------------------------------------------------------------------

MODELOS_PREDEFINIDOS = {
    # nome: (função y = f(x, *params), nomes dos parâmetros, chute_inicial padrão)
    'exponencial': (lambda x, a, b, c: a * np.exp(b * x) + c, ['a', 'b', 'c'], [1.0, 0.01, 0.0]),
    'logaritmica': (lambda x, a, b: a * np.log(x) + b, ['a', 'b'], [1.0, 0.0]),
    'potencia':    (lambda x, a, b: a * np.power(x, b), ['a', 'b'], [1.0, 1.0]),
    'sigmoide':    (lambda x, a, b, c: a / (1 + np.exp(-b * (x - c))), ['a', 'b', 'c'], [1.0, 1.0, 0.0]),
}


def ajuste_curva(df, coluna_x, coluna_y, funcao, chute_inicial=None, nomes_parametros=None):
    """
    Ajusta os parâmetros de uma função y = f(x, *params) aos dados por
    mínimos quadrados (scipy.optimize.curve_fit) — o mesmo princípio do
    ajuste polinomial, mas pra qualquer forma de curva.

    Este é o bloco genérico "em aberto": funciona perfeitamente quando VOCÊ
    (no código) já sabe qual função usar. O que ainda não está resolvido é
    como um usuário da interface vai INFORMAR essa função sem escrever
    Python. Duas rotas possíveis, pra decidir quando for montar a tela:

      1) Modelos pré-definidos (recomendado pra começar): a interface
         mostra um dropdown com curvas conhecidas — veja
         ajuste_curva_modelo() abaixo, que já cobre isso.
      2) Expressão livre digitada pelo usuário (ex: "a*exp(b*x)+c"): mais
         flexível, mas nunca deve ser resolvida com eval() puro em texto de
         usuário (risco de execução de código arbitrário). Dá pra fazer com
         um parser restrito (ex: sympy.sympify com namespace limitado), mas
         isso é uma decisão de produto/segurança pra tomar depois, não
         antecipei aqui.

    Parâmetros:
        funcao (callable): função no formato f(x, p1, p2, ...).
        chute_inicial (list, opcional): estimativa inicial dos parâmetros.
            Se None, o scipy tenta com 1.0 pra cada — funciona pra curvas
            simples, mas pra exponenciais/sigmoides costuma ser necessário
            informar, senão o ajuste não converge.
        nomes_parametros (list, opcional): nomes pra rotular os parâmetros
            no resultado (ex: ['a', 'b', 'c']). Se None, usa 'p0', 'p1', ...
    """
    n_parametros = funcao.__code__.co_argcount - 1  # menos o 'x'
    x, y = _validar_x_y_ajuste(df, coluna_x, coluna_y, n_parametros_minimo=n_parametros + 1)

    try:
        parametros, covariancia = curve_fit(funcao, x, y, p0=chute_inicial, maxfev=10000)
    except RuntimeError as e:
        raise RuntimeError(
            f"O ajuste não convergiu: {e}. Tente informar um chute_inicial "
            "mais próximo dos valores esperados."
        )

    y_previsto = funcao(x, *parametros)
    r2 = _r2(y, y_previsto)
    incertezas = np.sqrt(np.diag(covariancia))

    nomes = nomes_parametros if nomes_parametros else [f'p{i}' for i in range(n_parametros)]

    return {
        'parametros': dict(zip(nomes, parametros.tolist())),
        'incertezas': dict(zip(nomes, incertezas.tolist())),
        'r2': float(r2),
        'prever': lambda x_novo: funcao(np.asarray(x_novo), *parametros),
    }


def ajuste_curva_modelo(df, coluna_x, coluna_y, modelo, chute_inicial=None):
    """
    Atalho pra ajuste_curva usando um dos modelos pré-definidos em
    MODELOS_PREDEFINIDOS ('exponencial', 'logaritmica', 'potencia', 'sigmoide').
    Pronto pra virar um dropdown na interface hoje, sem precisar resolver
    ainda a questão de "curva digitada livremente pelo usuário".
    """
    if modelo not in MODELOS_PREDEFINIDOS:
        raise ValueError(f"Modelo '{modelo}' inválido. Use um de: {list(MODELOS_PREDEFINIDOS)}")

    funcao, nomes, chute_padrao = MODELOS_PREDEFINIDOS[modelo]
    return ajuste_curva(
        df, coluna_x, coluna_y, funcao,
        chute_inicial=chute_inicial if chute_inicial else chute_padrao,
        nomes_parametros=nomes,
    )




if __name__ == '__main__':
    # --- testes das operações de constante/coluna (antigo operacoes.py) ---
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


    print('\n' + '='*70)
    print('--- testes dos ajustes (antigo other.py) ---')
    print('='*70 + '\n')

    np.random.seed(0)

    # --- ajuste_linear: y = 3x + 2 + ruído ---
    x = np.linspace(0, 10, 50)
    y = 3 * x + 2 + np.random.normal(0, 0.5, 50)
    df_linear = pd.DataFrame({'x': x, 'y': y})

    print("--- ajuste_linear (esperado: a≈3, b≈2) ---")
    r = ajuste_linear(df_linear, 'x', 'y')
    print(f"a={r['coeficiente_angular']:.3f}, b={r['coeficiente_linear']:.3f}, r2={r['r2']:.4f}")

    # --- ajuste_polinomial grau 2: y = x^2 - 4x + 3 + ruído ---
    y_quad = x ** 2 - 4 * x + 3 + np.random.normal(0, 1, 50)
    df_quad = pd.DataFrame({'x': x, 'y': y_quad})

    print("\n--- ajuste_polinomial grau 2 (esperado: [1, -4, 3]) ---")
    r = ajuste_polinomial(df_quad, 'x', 'y', grau=2)
    print(f"coeficientes={[round(c, 2) for c in r['coeficientes']]}, r2={r['r2']:.4f}")
    print(f"equação: {r['equacao']}")

    # --- ajuste_curva_modelo exponencial: y = 5*exp(0.3*x) + 1 + ruído ---
    y_exp = 5 * np.exp(0.3 * x) + 1 + np.random.normal(0, 2, 50)
    df_exp = pd.DataFrame({'x': x, 'y': y_exp})

    print("\n--- ajuste_curva_modelo('exponencial') (esperado: a≈5, b≈0.3, c≈1) ---")
    r = ajuste_curva_modelo(df_exp, 'x', 'y', modelo='exponencial')
    print(f"parametros={ {k: round(v, 3) for k, v in r['parametros'].items()} }, r2={r['r2']:.4f}")

    # --- usar 'prever' pra gerar a curva de ajuste (o que a interface faria pra plotar) ---
    x_curva = np.linspace(0, 10, 5)
    print("\n--- usando 'prever' do ajuste exponencial pra gerar pontos da curva ---")
    print(r['prever'](x_curva))

    # --- erro esperado: função exponencial sem chute inicial pode não convergir bem,
    #     mas com chute customizado deve funcionar mesmo assim ---
    print("\n--- ajuste_curva direto (sem usar o atalho de modelo), com chute customizado ---")
    r2_direto = ajuste_curva(
        df_exp, 'x', 'y',
        funcao=lambda x, a, b, c: a * np.exp(b * x) + c,
        chute_inicial=[1, 0.1, 0],
        nomes_parametros=['a', 'b', 'c'],
    )
    print(f"parametros={ {k: round(v, 3) for k, v in r2_direto['parametros'].items()} }")

    print("\n--- erro esperado: poucos pontos pra grau alto ---")
    try:
        ajuste_polinomial(df_linear.iloc[:2], 'x', 'y', grau=5)
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")