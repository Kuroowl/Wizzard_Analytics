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