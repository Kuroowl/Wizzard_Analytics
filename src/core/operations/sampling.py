import numpy as np
import pandas as pd


def _validar_serie_numerica(df, coluna_eixo_x, limite_min=None, limite_max=None):
    """
    Validações comuns às operações de filtro por eixo X:
      - a coluna existe?
      - limite_min <= limite_max? (quando informados)
      - a coluna tem valores numéricos válidos?
    A conversão para número deve ter sido feita no carregamento dos dados
    (ex: 'Tempo_decorrido_s' em vez de 'Hora' como texto). Aqui só
    verificamos e avisamos claramente se algo estiver errado, em vez de
    devolver silenciosamente uma tabela vazia.
    """
    if coluna_eixo_x not in df.columns:
        raise KeyError(
            f"A coluna '{coluna_eixo_x}' não existe no DataFrame. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    if limite_min is not None and limite_max is not None and limite_min > limite_max:
        raise ValueError(
            f"limite_min ({limite_min}) não pode ser maior que limite_max ({limite_max}). "
            "Confira se os controles da interface não foram invertidos."
        )

    serie = pd.to_numeric(df[coluna_eixo_x], errors='coerce')

    if serie.isna().all():
        raise ValueError(
            f"A coluna '{coluna_eixo_x}' não contém valores numéricos válidos. "
            "Se for uma coluna de data/hora em texto, use a coluna numérica "
            "equivalente (ex: 'Tempo_decorrido_s') gerada no carregamento dos dados."
        )

    n_invalidos = serie.isna().sum()
    if n_invalidos > 0:
        print(
            f"Aviso: {n_invalidos} valor(es) em '{coluna_eixo_x}' não são "
            "numéricos e serão ignorados nesta operação."
        )

    return serie


def aparar_dados(df, coluna_eixo_x, limite_min, limite_max):
    """
    Mantém apenas o 'recheio' dos dados dentro de um intervalo escolhido
    pelo usuário. Funciona com qualquer coluna numérica no eixo X (tempo
    decorrido, pressão, temperatura, etc).

    Parâmetros:
        df (pd.DataFrame): Tabela de dados original.
        coluna_eixo_x (str): Nome da coluna numérica que representa o eixo X.
        limite_min (float): Valor inicial do corte.
        limite_max (float): Valor final do corte.
    """
    if df.empty:
        return df.copy()

    serie = _validar_serie_numerica(df, coluna_eixo_x, limite_min, limite_max)
    mascara = (serie >= limite_min) & (serie <= limite_max)

    # Filtra o DataFrame ORIGINAL (não a versão coagida), preservando os
    # valores originais de todas as colunas, inclusive a do eixo X.
    return df[mascara].reset_index(drop=True)


def excluir_dados(df, coluna_eixo_x, limite_min, limite_max):
    """
    Exclui o 'recheio' do intervalo escolhido, cavando um buraco nos dados.
    Conserva apenas o que estiver ANTES de limite_min OU DEPOIS de limite_max.
    """
    if df.empty:
        return df.copy()

    serie = _validar_serie_numerica(df, coluna_eixo_x, limite_min, limite_max)
    mascara = (serie < limite_min) | (serie > limite_max)

    return df[mascara].reset_index(drop=True)


def amostrar_dados_espacados(df, coluna_eixo_x, n_pontos, modo='valor'):
    """
    Retira uma amostra de n_pontos igualmente espaçados.

    modo='linhas': espaça por POSIÇÃO (uma linha a cada N). Simples e rápido,
        mas se a taxa de aquisição não for constante, o espaçamento no eixo X
        pode ficar irregular.
    modo='valor': espaça por VALOR do eixo X (ex: um ponto a cada 5 segundos,
        pegando a linha mais próxima de cada valor-alvo). Mais correto
        visualmente quando a amostragem original não é uniforme, mas exige
        que coluna_eixo_x seja numérica.

    Parâmetros:
        df (pd.DataFrame): Tabela de dados original.
        coluna_eixo_x (str): Nome da coluna do eixo X (só usada no modo='valor').
        n_pontos (int): Quantidade de pontos desejada na amostra.
        modo (str): 'linhas' ou 'valor'.
    """
    if df.empty or n_pontos <= 0:
        return df.iloc[0:0].copy()

    n_pontos = min(n_pontos, len(df))

    if modo == 'linhas':
        indices = np.unique(np.linspace(0, len(df) - 1, num=n_pontos, dtype=int))
        return df.iloc[indices].reset_index(drop=True)

    elif modo == 'valor':
        serie = _validar_serie_numerica(df, coluna_eixo_x)
        df_valido = df.loc[serie.notna()]
        serie_valida = serie.loc[serie.notna()]

        valores_alvo = np.linspace(serie_valida.min(), serie_valida.max(), n_pontos)

        indices_selecionados = []
        for alvo in valores_alvo:
            idx_mais_proximo = (serie_valida - alvo).abs().idxmin()
            if idx_mais_proximo not in indices_selecionados:
                indices_selecionados.append(idx_mais_proximo)

        return df_valido.loc[indices_selecionados].reset_index(drop=True)

    else:
        raise ValueError("modo deve ser 'linhas' ou 'valor'")


if __name__ == '__main__':
    # Testes rápidos com uma coluna numérica e uma coluna de texto (Hora),
    # pra confirmar que o erro é claro em vez de retornar vazio em silêncio.
    df_teste = pd.DataFrame({
        'Hora': ['08:12:37.3', '08:12:38.3', '08:12:39.3', '08:12:40.3', '08:12:41.3'],
        'Tempo_decorrido_s': [0.0, 1.0, 2.0, 3.0, 4.0],
        'P1': [0.97, 0.98, 0.99, 1.00, 1.01],
    })

    print("--- aparar_dados (coluna numérica correta) ---")
    print(aparar_dados(df_teste, 'Tempo_decorrido_s', 1, 3))

    print("\n--- excluir_dados (coluna numérica correta) ---")
    print(excluir_dados(df_teste, 'Tempo_decorrido_s', 1, 3))

    print("\n--- amostrar_dados_espacados (modo='linhas', 3 pontos) ---")
    print(amostrar_dados_espacados(df_teste, 'Tempo_decorrido_s', 3, modo='linhas'))

    print("\n--- amostrar_dados_espacados (modo='valor', 3 pontos) ---")
    print(amostrar_dados_espacados(df_teste, 'Tempo_decorrido_s', 3, modo='valor'))

    print("\n--- tentando usar 'Hora' (texto) como eixo X: deve dar erro claro ---")
    try:
        aparar_dados(df_teste, 'Hora', 1, 3)
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    print("\n--- limite_min > limite_max: deve dar erro claro ---")
    try:
        aparar_dados(df_teste, 'Tempo_decorrido_s', 3, 1)
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")