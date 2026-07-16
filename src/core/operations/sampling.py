import pandas as pd
import numpy as np

def aparar_dados(df, coluna_eixo_x, limite_min, limite_max):
    """
    Mantém apenas o 'recheio' dos dados dentro de um intervalo escolhido pelo usuário.
    É universal: funciona com tempo, pressão, temperatura ou qualquer coluna no eixo X.
    
    Parâmetros:
        df (pd.DataFrame): Tabela de dados original.
        coluna_eixo_x (str): Nome da coluna que representa o eixo horizontal (X).
        limite_min (float): O valor inicial do corte.
        limite_max (float): O valor final do corte.
    """
    if df.empty:
        return df.copy()
        
    # Garante que a coluna do eixo X está no formato numérico para a comparação funcionar
    df_temp = df.copy()
    df_temp[coluna_eixo_x] = pd.to_numeric(df_temp[coluna_eixo_x], errors='coerce')
    
    # Aplica o filtro do intervalo escolhido (o "recheio")
    df_cortado = df_temp[
        (df_temp[coluna_eixo_x] >= limite_min) & 
        (df_temp[coluna_eixo_x] <= limite_max)
    ].copy()
    
    # Reseta os índices para a tabela ficar limpa após a remoção das linhas de fora
    return df_cortado.reset_index(drop=True)

def excluir_dados(df, coluna_eixo_x, limite_min, limite_max):
    """
    Exclui o 'recheio' do intervalo escolhido, cavando um buraco nos dados.
    Conserva apenas o que estiver ANTES de limite_min OU DEPOIS de limite_max.
    """
    if df.empty:
        return df.copy()
        
    df_temp = df.copy()
    df_temp[coluna_eixo_x] = pd.to_numeric(df_temp[coluna_eixo_x], errors='coerce')
    
    # Filtra mantendo apenas o que está FORA do intervalo
    # Usamos o operador '|' (que significa OU) para pegar as duas pontas
    df_cortado = df_temp[
        (df_temp[coluna_eixo_x] < limite_min) | 
        (df_temp[coluna_eixo_x] > limite_max)
    ].copy()
    
    return df_cortado.reset_index(drop=True)

def aplicar_downsampling(df, num_pontos=100):
    """
    Reduz o número de linhas de TODO o DataFrame para uma quantidade fixa de pontos,
    distribuídos uniformemente ao longo do ensaio.
    
    Preserva todas as colunas originais (tempo, pressões, temperatura, etc.) 
    alinhadas na mesma linha física, o que evita bugs de plotagem.
    
    Parâmetros:
        df (pd.DataFrame): O DataFrame completo com todos os dados.
        num_pontos (int): Quantidade exata de pontos desejada no final (ex: 50, 100, 500).
    """
    if df.empty:
        return df.copy()
        
    total_linhas = len(df)
    
    # Se o arquivo já for menor do que a quantidade de pontos desejada, 
    # não precisa reduzir nada, retorna ele inteiro.
    if total_linhas <= num_pontos:
        return df.copy().reset_index(drop=True)
    
    # Calcula índices distribuídos uniformemente do início ao fim do DataFrame
    indices = np.linspace(0, total_linhas - 1, num=num_pontos, dtype=int)
    
    # Seleciona as linhas correspondentes e reseta o índice físico
    df_amostrado = df.iloc[indices].copy()
    
    return df_amostrado.reset_index(drop=True)
