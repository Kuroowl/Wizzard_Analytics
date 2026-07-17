import numpy as np
import pandas as pd
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
