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
