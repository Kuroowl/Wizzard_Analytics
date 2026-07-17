import numpy as np
import pandas as pd


def _validar_coluna_numerica(df, coluna):
    """
    Validação comum: a coluna existe e tem valores numéricos válidos.
    Retorna a série já convertida e sem NaN (pra estatística, descartar
    valores inválidos é o comportamento certo — não faz sentido incluir
    'NaN' numa média ou num histograma).
    """
    if coluna not in df.columns:
        raise KeyError(f"Coluna '{coluna}' não encontrada. Disponíveis: {list(df.columns)}")

    serie = pd.to_numeric(df[coluna], errors='coerce').dropna()

    if serie.empty:
        raise ValueError(f"A coluna '{coluna}' não contém nenhum valor numérico válido.")

    return serie


# ---------------------------------------------------------------------------
# Resumo escalar — dict simples, pronto pra exibir em cards/labels na interface
# ---------------------------------------------------------------------------

def estatisticas_descritivas(df, coluna):
    """
    Calcula um resumo estatístico de uma coluna numérica. Retorna um dict
    (não um gráfico) — a interface decide como exibir (cards, tabela, etc).
    """
    serie = _validar_coluna_numerica(df, coluna)

    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)
    media = serie.mean()
    desvio = serie.std()

    return {
        'contagem': int(serie.count()),
        'media': float(media),
        'desvio_padrao': float(desvio),
        'minimo': float(serie.min()),
        'maximo': float(serie.max()),
        'amplitude': float(serie.max() - serie.min()),
        'mediana': float(serie.median()),
        'q1': float(q1),
        'q3': float(q3),
        'iqr': float(q3 - q1),
        'coef_variacao': float(desvio / media) if media != 0 else None,
    }


# ---------------------------------------------------------------------------
# Histograma — "parece" desenho, mas o cálculo (bins + contagens) é dado puro
# ---------------------------------------------------------------------------

def histograma(df, coluna, n_bins=10, intervalo=None):
    """
    Calcula as bordas dos bins e as contagens de um histograma. NÃO desenha
    nada — devolve os números pra interface plotar com a lib que quiser
    (matplotlib, plotly, o que for).

    Parâmetros:
        n_bins (int): número de bins.
        intervalo (tuple, opcional): (min, max) do histograma. Se None,
            usa min/max dos próprios dados.

    Retorna um dict:
        'bordas': limites dos bins (tamanho n_bins + 1)
        'centros': centro de cada bin (tamanho n_bins) — útil pra plotar
            como barras centradas ou linha
        'contagens': quantos pontos caem em cada bin (tamanho n_bins)
    """
    serie = _validar_coluna_numerica(df, coluna)

    if n_bins <= 0:
        raise ValueError("n_bins precisa ser maior que zero.")

    contagens, bordas = np.histogram(serie, bins=n_bins, range=intervalo)
    centros = (bordas[:-1] + bordas[1:]) / 2

    return {
        'bordas': bordas.tolist(),
        'centros': centros.tolist(),
        'contagens': contagens.tolist(),
    }


# ---------------------------------------------------------------------------
# Correlação — DataFrame, porque toda lib de plot/tabela aceita DataFrame
# ---------------------------------------------------------------------------

def matriz_correlacao(df, colunas=None, metodo='pearson'):
    """
    Calcula a matriz de correlação entre colunas numéricas. Retorna um
    DataFrame (não um heatmap) — a interface decide se quer mostrar como
    tabela, heatmap, etc.

    Parâmetros:
        colunas (list, opcional): quais colunas incluir. Se None, usa todas
            as colunas numéricas do DataFrame.
        metodo (str): 'pearson', 'spearman' ou 'kendall'.
    """
    if metodo not in ('pearson', 'spearman', 'kendall'):
        raise ValueError("metodo deve ser 'pearson', 'spearman' ou 'kendall'.")

    if colunas is None:
        colunas = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(colunas) < 2:
            raise ValueError(
                "O DataFrame não tem pelo menos 2 colunas numéricas pra calcular correlação."
            )
    else:
        faltando = [c for c in colunas if c not in df.columns]
        if faltando:
            raise KeyError(f"Coluna(s) não encontrada(s): {faltando}. Disponíveis: {list(df.columns)}")
        if len(colunas) < 2:
            raise ValueError("Informe pelo menos 2 colunas pra calcular correlação.")

    matriz_numerica = df[colunas].apply(pd.to_numeric, errors='coerce')
    return matriz_numerica.corr(method=metodo)


# ---------------------------------------------------------------------------
# Outliers — série/dict/DataFrame conforme o que a interface for usar
# ---------------------------------------------------------------------------

def detectar_outliers(df, coluna, metodo='iqr', fator=None, retorno='mascara'):
    """
    Detecta outliers de uma coluna numérica.

    Parâmetros:
        metodo (str): 'iqr' (padrão) usa Q1 - fator*IQR e Q3 + fator*IQR;
            'zscore' usa |z| > fator.
        fator (float, opcional): limiar de sensibilidade. Se None, usa o
            padrão de cada método (1.5 pra 'iqr', 3.0 pra 'zscore').
        retorno (str): 'mascara' devolve uma Series booleana (True = é
            outlier), do mesmo tamanho e índice do df original — fácil de
            combinar com outros filtros. 'linhas' devolve só as linhas
            identificadas como outlier (DataFrame). 'limites' devolve só o
            dict com os limiares calculados, sem aplicar o filtro.
    """
    if metodo not in ('iqr', 'zscore'):
        raise ValueError("metodo deve ser 'iqr' ou 'zscore'.")
    if retorno not in ('mascara', 'linhas', 'limites'):
        raise ValueError("retorno deve ser 'mascara', 'linhas' ou 'limites'.")

    serie_completa = pd.to_numeric(df[coluna], errors='coerce') if coluna in df.columns else None
    if serie_completa is None:
        raise KeyError(f"Coluna '{coluna}' não encontrada. Disponíveis: {list(df.columns)}")

    serie_valida = _validar_coluna_numerica(df, coluna)

    if metodo == 'iqr':
        fator = 1.5 if fator is None else fator
        q1, q3 = serie_valida.quantile(0.25), serie_valida.quantile(0.75)
        iqr = q3 - q1
        limite_inferior = q1 - fator * iqr
        limite_superior = q3 + fator * iqr
    else:  # zscore
        fator = 3.0 if fator is None else fator
        media, desvio = serie_valida.mean(), serie_valida.std()
        if desvio == 0:
            raise ValueError(
                f"A coluna '{coluna}' tem desvio padrão zero (todos os valores "
                "iguais) — z-score não é calculável."
            )
        limite_inferior = media - fator * desvio
        limite_superior = media + fator * desvio

    if retorno == 'limites':
        return {'limite_inferior': float(limite_inferior), 'limite_superior': float(limite_superior)}

    mascara = (serie_completa < limite_inferior) | (serie_completa > limite_superior)
    mascara = mascara.fillna(False)  # valores não-numéricos não são outlier, são inválidos

    if retorno == 'mascara':
        return mascara

    return df[mascara].reset_index(drop=True)


if __name__ == '__main__':
    np.random.seed(42)
    df_teste = pd.DataFrame({
        'P1': np.random.normal(loc=50, scale=5, size=200),
        'P2': np.random.normal(loc=100, scale=10, size=200),
    })
    # P2 correlacionado com P1 (pra testar matriz_correlacao)
    df_teste['P2'] = df_teste['P1'] * 2 + np.random.normal(0, 1, size=200)
    # injeta 3 outliers propositais em P1
    df_teste.loc[0, 'P1'] = 500
    df_teste.loc[1, 'P1'] = -500
    df_teste.loc[2, 'P1'] = 400

    print("--- estatisticas_descritivas ---")
    print(estatisticas_descritivas(df_teste, 'P1'))

    print("\n--- histograma (5 bins) ---")
    h = histograma(df_teste, 'P2', n_bins=5)
    print(h)
    print("soma das contagens == total de linhas?", sum(h['contagens']) == len(df_teste))

    print("\n--- matriz_correlacao (deve mostrar P1/P2 fortemente correlacionados) ---")
    print(matriz_correlacao(df_teste, ['P1', 'P2']))

    print("\n--- detectar_outliers (iqr, retorno='mascara') ---")
    mascara = detectar_outliers(df_teste, 'P1', metodo='iqr')
    print("Quantos outliers achou:", mascara.sum())
    print("Os 3 outliers injetados foram pegos?", mascara.iloc[[0, 1, 2]].all())

    print("\n--- detectar_outliers (zscore, retorno='linhas') ---")
    print(detectar_outliers(df_teste, 'P1', metodo='zscore', retorno='linhas'))

    print("\n--- detectar_outliers (retorno='limites') ---")
    print(detectar_outliers(df_teste, 'P1', metodo='iqr', retorno='limites'))

    print("\n--- erro esperado: coluna inexistente ---")
    try:
        estatisticas_descritivas(df_teste, 'coluna_que_nao_existe')
    except KeyError as e:
        print(f"KeyError capturado corretamente: {e}")
